"""API-level tests, including role-based access control."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

CASE_PAYLOAD = {
    "property_name": "Hosahalli agricultural land",
    "property_type": "agricultural_land",
    "transaction_type": "purchase",
    "survey_number": "123/4B",
    "village": "Hosahalli",
    "district": "Bengaluru Rural",
    "state": "Karnataka",
    "jurisdiction_code": "KA",
    "claimed_owner": "Latha Rao",
    "seller_name": "Latha Rao",
}


def _drain(timeout=60):
    from app.services.jobs import get_runner

    assert get_runner().wait_until_idle(timeout=timeout), "background jobs did not finish"


def test_health_and_system_status(api_client):
    assert api_client.get("/api/health").json()["status"] == "ok"
    status = api_client.get("/api/system/status").json()
    assert status["ai"]["provider"] == "offline"
    assert status["ai"]["sends_document_text_off_device"] is False
    assert "ocr" in status and "watcher" in status


def test_reference_data_lists_the_closed_vocabularies(api_client):
    ref = api_client.get("/api/system/reference").json()
    assert any(t["value"] == "agricultural_land" for t in ref["property_types"])
    assert any(d["key"] == "encumbrance_certificate" for d in ref["document_types"])
    assert any(j["code"] == "KA" for j in ref["jurisdictions"])


def test_case_lifecycle_through_the_api(api_client, samples, tmp_path):
    created = api_client.post("/api/cases", json=CASE_PAYLOAD)
    assert created.status_code == 201
    case = created.json()
    assert case["case_ref"].startswith("PDD-")
    assert Path(case["watch_folder"]).is_dir()

    staging = samples("initial")
    for name in ("01_sale_deed_2015.pdf", "02_rtc_pahani_2024.pdf",
                 "04_encumbrance_certificate_2019_2024.pdf"):
        with open(staging / name, "rb") as fh:
            response = api_client.post(
                "/api/cases/{}/documents/upload".format(case["id"]),
                files={"file": (name, fh, "application/pdf")})
        assert response.status_code == 201, response.text
    _drain()

    docs = api_client.get("/api/cases/{}/documents".format(case["id"])).json()
    assert len(docs) == 3
    assert {d["doc_type"] for d in docs} >= {"sale_deed", "rtc_pahani", "encumbrance_certificate"}

    findings = api_client.get("/api/cases/{}/findings".format(case["id"])).json()
    assert findings
    assert all(f["risk_ref"].startswith("R-") for f in findings)

    requirements = api_client.get("/api/cases/{}/requirements".format(case["id"])).json()
    assert any(r["key"] == "encumbrance_certificate_full_period" for r in requirements)

    reports = api_client.get("/api/cases/{}/reports".format(case["id"])).json()
    assert reports

    html = api_client.get("/api/cases/{}/reports/latest/html".format(case["id"]))
    assert html.status_code == 200
    assert "Due Diligence Report" in html.text
    assert "not a legal opinion" in html.text

    pdf = api_client.get("/api/cases/{}/reports/latest/pdf".format(case["id"]))
    assert pdf.status_code == 200
    assert pdf.content[:5] == b"%PDF-"

    detail = api_client.get("/api/cases/{}/reports/latest".format(case["id"])).json()
    assert "section_10_missing_documents" in detail["payload"]

    dashboard = api_client.get("/api/dashboard").json()
    assert dashboard["totals"]["cases"] == 1
    assert dashboard["recent_documents"]


def test_document_detail_fields_and_corrections(api_client, samples):
    case = api_client.post("/api/cases", json=CASE_PAYLOAD).json()
    staging = samples("initial")
    with open(staging / "01_sale_deed_2015.pdf", "rb") as fh:
        api_client.post("/api/cases/{}/documents/upload".format(case["id"]),
                        files={"file": ("sale.pdf", fh, "application/pdf")})
    _drain()

    doc = api_client.get("/api/cases/{}/documents".format(case["id"])).json()[0]
    detail = api_client.get("/api/documents/{}".format(doc["id"])).json()
    assert detail["fields"]
    assert detail["pages"]
    assert all(f["page_no"] for f in detail["fields"] if f["field_key"] == "survey_number")

    page = api_client.get("/api/documents/{}/pages/1".format(doc["id"]))
    assert "SALE" in page.text.upper()

    original = api_client.get("/api/documents/{}/file".format(doc["id"]))
    assert original.status_code == 200
    assert original.content[:5] == b"%PDF-"

    field = next(f for f in detail["fields"] if f["field_key"] == "survey_number")
    corrected = api_client.patch("/api/fields/{}".format(field["id"]),
                                 json={"value": "123/4C", "note": "checked against the original"}).json()
    assert corrected["value_norm"] == "123/4C"
    assert corrected["corrected_by_user"] is True
    assert corrected["provenance"] == "user_corrected"
    assert corrected["original_value"]

    # A correction survives reprocessing.
    api_client.post("/api/documents/{}/reprocess?wait=true".format(doc["id"]))
    after = api_client.get("/api/documents/{}".format(doc["id"])).json()
    survey = [f for f in after["fields"] if f["field_key"] == "survey_number"]
    assert any(f["value_norm"] == "123/4C" and f["corrected_by_user"] for f in survey)


def test_manual_document_type_override(api_client, samples):
    case = api_client.post("/api/cases", json=CASE_PAYLOAD).json()
    staging = samples("initial")
    with open(staging / "06_sellers_note.txt", "rb") as fh:
        api_client.post("/api/cases/{}/documents/upload".format(case["id"]),
                        files={"file": ("note.txt", fh, "text/plain")})
    _drain()
    doc = api_client.get("/api/cases/{}/documents".format(case["id"])).json()[0]
    assert doc["doc_type"] == "unknown"

    updated = api_client.post("/api/documents/{}/type".format(doc["id"]),
                              json={"doc_type": "affidavit", "note": "reviewed by hand"}).json()
    assert updated["doc_type"] == "affidavit"
    assert updated["classification_method"] == "user"
    assert updated["classification_confidence"] == 1.0

    audit = api_client.get("/api/cases/{}/audit".format(case["id"])).json()
    assert any(e["event_type"] == "document_type_overridden" for e in audit)


def test_finding_and_requirement_updates_are_audited(api_client, samples):
    case = api_client.post("/api/cases", json=CASE_PAYLOAD).json()
    staging = samples("initial")
    with open(staging / "05_mortgage_deed_2016.pdf", "rb") as fh:
        api_client.post("/api/cases/{}/documents/upload".format(case["id"]),
                        files={"file": ("mortgage.pdf", fh, "application/pdf")})
    _drain()

    findings = api_client.get("/api/cases/{}/findings".format(case["id"])).json()
    mortgage = next(f for f in findings if f["detector"] == "mortgage_unreleased")
    assert mortgage["severity"] in ("critical", "high")
    assert mortgage["evidence"]

    updated = api_client.patch("/api/findings/{}".format(mortgage["id"]),
                               json={"status": "accepted",
                                     "resolution_note": "Lender confirmed closure by email."}).json()
    assert updated["status"] == "accepted"
    assert updated["score"] < mortgage["score"]

    requirements = api_client.get("/api/cases/{}/requirements".format(case["id"])).json()
    req = requirements[0]
    done = api_client.patch("/api/requirements/{}".format(req["id"]),
                            json={"status": "satisfied", "note": "collected offline"}).json()
    assert done["status"] == "satisfied"

    audit = api_client.get("/api/cases/{}/audit".format(case["id"])).json()
    kinds = {e["event_type"] for e in audit}
    assert {"finding_updated", "requirement_updated", "document_processed", "case_created"} <= kinds


def test_search_within_a_case(api_client, samples):
    case = api_client.post("/api/cases", json=CASE_PAYLOAD).json()
    staging = samples("initial")
    with open(staging / "01_sale_deed_2015.pdf", "rb") as fh:
        api_client.post("/api/cases/{}/documents/upload".format(case["id"]),
                        files={"file": ("sale.pdf", fh, "application/pdf")})
    _drain()
    results = api_client.get("/api/cases/{}/search".format(case["id"]), params={"q": "Nelamangala"}).json()
    assert results["pages"]
    assert results["pages"][0]["excerpt"]


def test_case_isolation_at_the_api(api_client, samples):
    a = api_client.post("/api/cases", json=CASE_PAYLOAD).json()
    b = api_client.post("/api/cases", json={**CASE_PAYLOAD, "property_name": "Second property"}).json()
    staging = samples("all")
    with open(staging / "01_sale_deed_2015.pdf", "rb") as fh:
        api_client.post("/api/cases/{}/documents/upload".format(a["id"]),
                        files={"file": ("sale.pdf", fh, "application/pdf")})
    with open(staging / "09_khata_certificate.pdf", "rb") as fh:
        api_client.post("/api/cases/{}/documents/upload".format(b["id"]),
                        files={"file": ("khata.pdf", fh, "application/pdf")})
    _drain()

    docs_a = api_client.get("/api/cases/{}/documents".format(a["id"])).json()
    docs_b = api_client.get("/api/cases/{}/documents".format(b["id"])).json()
    assert {d["filename"] for d in docs_a}.isdisjoint({d["filename"] for d in docs_b})

    findings_a = api_client.get("/api/cases/{}/findings".format(a["id"])).json()
    findings_b = api_client.get("/api/cases/{}/findings".format(b["id"])).json()
    assert {f["id"] for f in findings_a}.isdisjoint({f["id"] for f in findings_b})

    search = api_client.get("/api/cases/{}/search".format(b["id"]), params={"q": "Ramesh"}).json()
    assert not search["pages"], "case B must not surface case A's text"


def test_unsupported_upload_is_rejected(api_client, tmp_path):
    case = api_client.post("/api/cases", json=CASE_PAYLOAD).json()
    bad = tmp_path / "script.exe"
    bad.write_bytes(b"MZ\x90\x00")
    with open(bad, "rb") as fh:
        response = api_client.post("/api/cases/{}/documents/upload".format(case["id"]),
                                   files={"file": ("script.exe", fh, "application/octet-stream")})
    assert response.status_code == 400


def test_role_based_access_control(env, monkeypatch, samples):
    """With auth enabled, a read-only key cannot change anything."""
    import hashlib

    from fastapi.testclient import TestClient

    from app.config import get_settings, reset_settings_cache
    from app.db import session_scope
    from app.main import create_app
    from app.models import User

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("ADMIN_API_KEY", "admin-secret")
    reset_settings_cache()
    get_settings().ensure_dirs()

    with session_scope() as s:
        s.add(User(username="viewer", role="readonly",
                   api_key_hash=hashlib.sha256(b"viewer-key").hexdigest()))
        s.add(User(username="checker", role="reviewer",
                   api_key_hash=hashlib.sha256(b"reviewer-key").hexdigest()))

    with TestClient(create_app()) as client:
        assert client.get("/api/dashboard").status_code == 401
        assert client.get("/api/dashboard", headers={"X-API-Key": "wrong"}).status_code == 401

        viewer = {"X-API-Key": "viewer-key"}
        assert client.get("/api/dashboard", headers=viewer).status_code == 200
        assert client.post("/api/cases", json=CASE_PAYLOAD, headers=viewer).status_code == 403

        reviewer = {"X-API-Key": "reviewer-key"}
        created = client.post("/api/cases", json=CASE_PAYLOAD, headers=reviewer)
        assert created.status_code == 201

        admin = {"X-API-Key": "admin-secret"}
        assert client.get("/api/system/status", headers=admin).json()["principal"]["role"] == "admin"

    reset_settings_cache()
