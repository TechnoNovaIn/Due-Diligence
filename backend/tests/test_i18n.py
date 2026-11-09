# -*- coding: utf-8 -*-
"""Bilingual behaviour: English and Kannada, with honest fallback."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import i18n
from app.services.findings_i18n import CATALOGUE, translate_finding
from app.services.knowledge import doc_label, doc_types, jurisdiction
from app.services.report_i18n import DISCLAIMER_KN, font_status, rt
from helpers import ingest_and_run, latest_report

KANNADA = re.compile(r"[ಀ-೿]")


# --------------------------------------------------------------- catalogues
def test_language_negotiation():
    assert i18n.normalise_language("kn") == "kn"
    assert i18n.normalise_language("kn-IN") == "kn"
    assert i18n.normalise_language("en-GB") == "en"
    assert i18n.normalise_language(None) == "en"
    assert i18n.normalise_language("fr") == "en", "an unsupported language falls back to English"


@pytest.mark.parametrize("vocabulary,value", [
    ("severity", "critical"), ("finding_status", "open"), ("requirement_status", "pending_collection"),
    ("priority", "mandatory"), ("doc_status", "analysed"), ("property_type", "agricultural_land"),
    ("assessment_status", "high_risk_findings_identified"), ("field_title", "survey_number"),
])
def test_every_vocabulary_has_kannada(vocabulary, value):
    translated = i18n.term(vocabulary, value, "kn")
    assert KANNADA.search(translated), "{}.{} is not translated".format(vocabulary, value)
    assert i18n.term(vocabulary, value, "en") != translated


def test_an_unknown_value_falls_back_readably():
    assert i18n.term("severity", "not_a_severity", "kn") == "Not a severity"


def test_every_document_type_has_a_kannada_label():
    missing = [key for key, meta in doc_types().items()
               if key != "unknown" and not KANNADA.search(meta.get("label_kn", ""))]
    assert not missing, "document types without a Kannada label: {}".format(missing[:5])


def test_document_labels_differ_by_language():
    assert doc_label("rtc_pahani", "en") != doc_label("rtc_pahani", "kn")
    assert KANNADA.search(doc_label("encumbrance_certificate", "kn"))


def test_every_karnataka_requirement_is_translated():
    reqs = jurisdiction("KA")["requirements"]
    missing = [r["key"] for r in reqs if not KANNADA.search(r.get("name_kn", ""))]
    assert not missing, "requirements without Kannada: {}".format(missing)
    for r in reqs:
        for field in ("reason_kn", "authority_kn", "next_action_kn",
                      "risk_if_absent_kn", "closure_criteria_kn"):
            assert KANNADA.search(r.get(field, "")), "{} missing {}".format(r["key"], field)


def test_finding_catalogue_is_kannada_and_complete_for_its_keys():
    for detector, entry in CATALOGUE.items():
        for field in ("title", "consequence", "recommended_action"):
            assert KANNADA.search(entry[field]), "{}.{} is not Kannada".format(detector, field)


def test_a_finding_without_a_catalogue_entry_falls_back():
    class Unknown:
        detector = "a_detector_that_does_not_exist"

    assert translate_finding(Unknown()) == {}


def test_a_translated_finding_marks_its_description_as_english():
    class Known:
        detector = "mortgage_unreleased"

    kn = translate_finding(Known())["kn"]
    assert KANNADA.search(kn["title"])
    assert kn["description_untranslated"] is True
    assert KANNADA.search(kn["description_note"])


def test_report_headings_and_disclaimer():
    assert rt("s9", "en") == "9. Risk register"
    assert KANNADA.search(rt("s9", "kn"))
    assert KANNADA.search(DISCLAIMER_KN)
    # The Kannada disclaimer must deny the same things as the English one.
    for phrase in ("ಹಕ್ಕು ತನಿಖೆಯಲ್ಲ", "ಕಾನೂನು", "ವಕೀಲರ"):
        assert phrase in DISCLAIMER_KN


# --------------------------------------------------------------- API
def test_api_answers_in_the_requested_language(api_client, samples):
    created = api_client.post("/api/cases", json={
        "property_name": "ಹೊಸಹಳ್ಳಿ ಕೃಷಿ ಭೂಮಿ", "property_type": "agricultural_land",
        "transaction_type": "purchase", "jurisdiction_code": "KA",
    }).json()
    case_id = created["id"]
    staging = samples("kannada")
    for name in sorted(Path(staging).glob("*.pdf")):
        with open(name, "rb") as fh:
            api_client.post("/api/cases/{}/documents/upload".format(case_id),
                            files={"file": (name.name, fh, "application/pdf")})
    from app.services.jobs import get_runner
    assert get_runner().wait_until_idle(timeout=60)

    english = api_client.get("/api/cases/{}".format(case_id)).json()
    kannada = api_client.get("/api/cases/{}?lang=kn".format(case_id)).json()
    assert english["property_type_label"] == "Agricultural land"
    assert KANNADA.search(kannada["property_type_label"])
    assert KANNADA.search(kannada["overall_risk_label"])

    docs_kn = api_client.get("/api/cases/{}/documents?lang=kn".format(case_id)).json()
    assert any(KANNADA.search(d["doc_type_label"] or "") for d in docs_kn)
    assert all(KANNADA.search(d["status_label"] or "") for d in docs_kn)

    findings_kn = api_client.get("/api/cases/{}/findings?lang=kn".format(case_id)).json()
    assert findings_kn
    assert all(KANNADA.search(f["severity_label"]) for f in findings_kn)
    translated = [f for f in findings_kn if not f["untranslated"]]
    assert translated, "at least some findings should carry Kannada text"
    assert all(KANNADA.search(f["title"]) for f in translated)

    reqs_kn = api_client.get("/api/cases/{}/requirements?lang=kn".format(case_id)).json()
    template_reqs = [r for r in reqs_kn if not r["key"].startswith("issue:")]
    assert template_reqs
    assert all(KANNADA.search(r["name"]) for r in template_reqs)
    assert all(KANNADA.search(r["status_label"]) for r in reqs_kn)


def test_accept_language_header_is_honoured(api_client):
    api_client.post("/api/cases", json={"property_name": "X", "property_type": "apartment"})
    response = api_client.get("/api/cases", headers={"Accept-Language": "kn-IN,kn;q=0.9"})
    assert KANNADA.search(response.json()[0]["property_type_label"])


def test_reference_data_carries_both_languages(api_client):
    ref = api_client.get("/api/system/reference").json()
    assert [l["code"] for l in ref["languages"]] == ["en", "kn"]
    assert all(KANNADA.search(t["label_kn"]) for t in ref["property_types"])
    assert KANNADA.search(ref["vocabularies"]["severity"]["critical"]["kn"])


# --------------------------------------------------------------- report
def test_report_renders_in_both_languages(make_case, samples, pump):
    case_id, folder = make_case()
    samples("kannada", folder=folder)
    ingest_and_run(case_id, pump)
    report = latest_report(case_id)

    from app.db import session_scope
    from app.models import Case
    from app.services.render_html import render_html

    with session_scope() as s:
        case = s.get(Case, case_id)
        english = render_html(case, report, report.payload, "en")
        kannada = render_html(case, report, report.payload, "kn")

    assert "9. Risk register" in english
    assert rt("s9", "kn") in kannada
    assert DISCLAIMER_KN in kannada
    assert "Scope and limitations." in english
    # The Kannada report must carry the same refusals as the English one.
    assert KANNADA.search(kannada)
    assert len(KANNADA.findall(kannada)) > 500


@pytest.mark.skipif(not font_status()["kannada_pdf_available"],
                    reason="no Kannada font installed")
def test_kannada_pdf_is_produced_and_shaped(make_case, samples, pump, tmp_path):
    case_id, folder = make_case()
    samples("kannada", folder=folder)
    ingest_and_run(case_id, pump)
    report = latest_report(case_id)

    from app.db import session_scope
    from app.models import Case
    from app.services.render_html import render_html
    from app.services.render_pdf_kn import render_pdf_kannada

    with session_scope() as s:
        case = s.get(Case, case_id)
        html = render_html(case, report, report.payload, "kn")
    out = render_pdf_kannada(html, tmp_path / "report-kn.pdf", footer="test")

    import fitz

    doc = fitz.open(str(out))
    try:
        assert doc.page_count >= 2, "a full report should paginate"
        fonts = {name for page in doc for (_x, _e, _t, name, *_rest) in page.get_fonts()}
        assert any("Noto" in f or "Kannada" in f or "kannada" in f.lower() for f in fonts), \
            "the Kannada font must be embedded, fonts were {}".format(fonts)
        # Shaped conjunct glyphs have no reverse mapping to Unicode, so the text
        # layer is lossy. What matters is that the page carries Kannada ink.
        page = doc.load_page(0)
        pixmap = page.get_pixmap(dpi=72)
        assert pixmap.samples.count(255) < len(pixmap.samples), "page 1 is blank"
        assert len(page.get_text("text").strip()) > 500, "page 1 has no text layer at all"
    finally:
        doc.close()


def test_the_kannada_pdf_text_layer_is_known_to_be_lossy():
    """Documented limitation: conjunct glyphs do not map back to Unicode.

    The Kannada PDF is correct to read and print; copying text out of it, or
    searching it in a PDF reader, is unreliable. The HTML report is the
    machine-readable form.
    """
    from app.services.render_pdf_kn import TEXT_LAYER_CAVEAT

    assert KANNADA.search(TEXT_LAYER_CAVEAT["kn"])
    assert "search" in TEXT_LAYER_CAVEAT["en"].lower()
