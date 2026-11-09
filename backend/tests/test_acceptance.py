"""Acceptance tests - one per scenario in the specification."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import (
    copy_files,
    documents_for,
    findings_for,
    ingest_and_run,
    latest_report,
    reports_for,
    requirements_for,
)

INITIAL = ["01_sale_deed_2015.pdf", "02_rtc_pahani_2024.pdf", "03_property_tax_receipt_2024.pdf",
           "04_encumbrance_certificate_2019_2024.pdf", "05_mortgage_deed_2016.pdf"]


@pytest.fixture()
def loaded_case(make_case, samples, pump):
    """A case with the initial document batch ingested and analysed."""
    case_id, folder = make_case()
    staging = samples("all")
    copy_files(staging, Path(folder), INITIAL)
    ingest_and_run(case_id, pump)
    return case_id, Path(folder), staging


# --------------------------------------------------------------------------
def test_1_initial_document_collection(loaded_case):
    """Documents are detected, classified, extracted and reported on."""
    case_id, folder, _ = loaded_case
    docs = documents_for(case_id)
    assert len(docs) == len(INITIAL)

    by_type = {d.doc_type for d in docs}
    assert "sale_deed" in by_type
    assert "rtc_pahani" in by_type
    assert "encumbrance_certificate" in by_type
    assert "mortgage_deed" in by_type
    assert all(d.page_count >= 1 for d in docs)
    assert all(d.extraction_confidence > 0 for d in docs)

    report = latest_report(case_id)
    assert report is not None and report.version == 1
    assert Path(report.html_path).exists()
    assert Path(report.pdf_path).exists()
    assert Path(report.json_path).exists()
    payload = report.payload
    for section in ("section_1_executive_summary", "section_9_risk_register",
                    "section_10_missing_documents", "section_13_final_assessment"):
        assert section in payload


def test_2_missing_documents_are_identified(loaded_case):
    """An absent supporting document becomes a tracked requirement with a reason."""
    case_id, _folder, _ = loaded_case
    reqs = requirements_for(case_id)
    keys = {r.key for r in reqs}
    assert "parent_deeds_chain" in keys
    assert "litigation_search_external" in keys
    assert "legal_title_opinion" in keys

    parent = next(r for r in reqs if r.key == "parent_deeds_chain")
    assert parent.status in ("pending_collection", "incomplete")
    assert parent.reason and parent.issuing_authority and parent.risk_if_absent
    assert parent.next_action and parent.closure_criteria

    # The sale deed names a partition deed that was not supplied.
    missing = findings_for(case_id, detector="missing_parent_deed", status="open")
    assert missing, "the referenced partition deed should be flagged as missing"
    assert "Partition" in missing[0].title
    assert missing[0].required_documents


def test_3_conflicting_information_is_flagged_with_both_sources(loaded_case):
    """The sale deed says 2a 15g, the RTC says 2a 20g - both must be cited."""
    case_id, _folder, _ = loaded_case
    area = findings_for(case_id, detector="area_mismatch", status="open")
    assert area, "the extent difference between deed and revenue record should be detected"
    finding = area[0]
    cited = {e.document_name for e in finding.evidence}
    assert len(cited) >= 2, "both conflicting documents must be cited"
    assert any("sale_deed" in c for c in cited)
    assert any("rtc" in c for c in cited)
    assert "%" in finding.title


def test_4_newly_added_evidence_updates_the_assessment(loaded_case, pump):
    """Adding the missing parent deed resolves the finding and produces a new version."""
    case_id, folder, staging = loaded_case
    before = findings_for(case_id, detector="missing_parent_deed", status="open")
    assert before
    v1 = latest_report(case_id).version

    copy_files(staging, folder, ["08_partition_deed_1998.pdf"])
    ingest_and_run(case_id, pump)

    after_open = findings_for(case_id, detector="missing_parent_deed", status="open")
    assert not after_open, "the finding should close once the parent deed is supplied"
    resolved = findings_for(case_id, detector="missing_parent_deed", status="resolved")
    assert resolved and resolved[0].resolution_note

    v2 = latest_report(case_id)
    assert v2.version > v1
    kinds = {c["type"] for c in v2.change_summary}
    assert "document_added" in kinds
    assert any(c["type"] == "finding_status" for c in v2.change_summary)


def test_5_ownership_timeline_is_constructed(loaded_case, pump):
    """A chronological chain is built and gaps are identified."""
    case_id, folder, staging = loaded_case
    from app.db import session_scope
    from app.models import OwnershipLink
    from sqlalchemy import select

    with session_scope() as s:
        links = list(s.scalars(select(OwnershipLink).where(OwnershipLink.case_id == case_id)
                               .order_by(OwnershipLink.sequence)).all())
    assert links, "the sale deed alone should produce one documented transfer"
    assert links[0].from_owner and links[0].to_owner
    assert links[0].verification_status == "documented"

    # Coverage is short of the 30-year review period until the 1998 deed arrives.
    assert findings_for(case_id, detector="chain_coverage", status="open")

    copy_files(staging, folder, ["08_partition_deed_1998.pdf"])
    ingest_and_run(case_id, pump)
    with session_scope() as s:
        links2 = list(s.scalars(select(OwnershipLink).where(OwnershipLink.case_id == case_id)
                                .order_by(OwnershipLink.sequence)).all())
    assert len(links2) > len(links)
    assert links2[0].transfer_date < links2[-1].transfer_date


def test_6_encumbrance_review(loaded_case):
    """EC coverage limits and the unreleased mortgage are both reported."""
    case_id, _folder, _ = loaded_case
    short = findings_for(case_id, detector="ec_short_period", status="open")
    assert short, "a five-year EC against a 30-year review period must be flagged"
    assert "30-year" in short[0].title or "year" in short[0].title

    mortgage = findings_for(case_id, detector="mortgage_unreleased", status="open")
    assert mortgage
    assert mortgage[0].severity in ("critical", "high")
    assert any("release" in d.lower() or "closure" in d.lower()
               for d in mortgage[0].required_documents)

    report = latest_report(case_id)
    section = report.payload["section_7_encumbrance"]
    assert section["encumbrance_certificates"]
    assert section["limitations"]


def test_7_unreadable_documents_are_flagged_not_invented(make_case, samples, pump):
    """A scanned page with no extractable text is sent to manual review."""
    case_id, folder = make_case()
    staging = samples("all")
    copy_files(staging, Path(folder), ["07_scanned_page.pdf"])
    ingest_and_run(case_id, pump)

    docs = documents_for(case_id)
    scanned = next(d for d in docs if "scanned" in d.filename)
    assert scanned.status in ("needs_manual_review", "failed")
    assert scanned.error
    assert not scanned.fields, "nothing may be extracted from a document that could not be read"
    assert findings_for(case_id, detector="document_not_processed", status="open")


def test_8_report_versioning_preserves_history(loaded_case, pump):
    case_id, folder, staging = loaded_case
    copy_files(staging, folder, ["08_partition_deed_1998.pdf"])
    ingest_and_run(case_id, pump)

    versions = reports_for(case_id)
    assert len(versions) >= 2
    assert [r.version for r in versions] == sorted(r.version for r in versions)
    assert versions[0].payload != versions[-1].payload
    assert all(Path(r.html_path).exists() for r in versions)
    assert versions[-1].change_summary


def test_9_case_isolation(make_case, samples, pump):
    """Two cases never see each other's documents, findings or requirements."""
    case_a, folder_a = make_case(property_name="Case A land")
    case_b, folder_b = make_case(property_name="Case B flat", property_type="apartment",
                                 survey_number=None)
    staging = samples("all")
    copy_files(staging, Path(folder_a), INITIAL)
    copy_files(staging, Path(folder_b), ["09_khata_certificate.pdf"])
    ingest_and_run(case_a, pump)
    ingest_and_run(case_b, pump)

    docs_a = {d.filename for d in documents_for(case_a)}
    docs_b = {d.filename for d in documents_for(case_b)}
    assert docs_a and docs_b and not (docs_a & docs_b)

    findings_a = {f.id for f in findings_for(case_a)}
    findings_b = {f.id for f in findings_for(case_b)}
    assert not (findings_a & findings_b)

    report_a = latest_report(case_a)
    names_in_a = {d["filename"] for d in report_a.payload["section_3_document_inventory"]}
    assert not (names_in_a & docs_b)


def test_10_evidence_traceability(loaded_case):
    """Every material finding cites a document, and most cite a page."""
    case_id, _folder, _ = loaded_case
    material = [f for f in findings_for(case_id, status="open")
                if f.severity in ("critical", "high", "medium")
                and f.detector not in ("scope_no_external_checks",)]
    assert material
    for finding in material:
        if finding.detector in ("building_approval_missing", "oc_missing", "conversion_missing"):
            continue  # absence findings have no document to cite, by definition
        assert finding.evidence, "{} has no evidence".format(finding.risk_ref)
        assert any(e.document_name for e in finding.evidence)

    report = latest_report(case_id)
    for row in report.payload["section_9_risk_register"]["register"]:
        assert "evidence" in row


def test_11_processing_failures_are_recorded_and_retryable(loaded_case):
    """A corrupt file fails cleanly, keeps the case intact and can be reprocessed."""
    case_id, folder, _ = loaded_case
    broken = folder / "10_broken.pdf"
    broken.write_bytes(b"%PDF-1.4\nthis is not a real pdf body")
    from app.services.watcher import WatchService

    WatchService().scan_case(case_id)
    from app.db import session_scope
    from app.services.pipeline import process_document
    from sqlalchemy import select
    from app.models import Document

    with session_scope() as s:
        doc = s.scalars(select(Document).where(Document.case_id == case_id,
                                               Document.filename == "10_broken.pdf")).first()
        assert doc is not None
        outcome = process_document(s, doc.id)
    assert not outcome["ok"]

    # Previously extracted data is untouched.
    assert len([d for d in documents_for(case_id) if d.status == "analysed"]) >= 4

    with session_scope() as s:
        doc = s.scalars(select(Document).where(Document.case_id == case_id,
                                               Document.filename == "10_broken.pdf")).first()
        assert doc.error
        assert doc.attempts >= 1
        before = doc.attempts
        process_document(s, doc.id)
        s.flush()
        assert doc.attempts == before + 1


def test_12_honest_assessment(loaded_case):
    """The report never claims title, authenticity or absence of litigation."""
    case_id, _folder, _ = loaded_case
    report = latest_report(case_id)

    # Search only the parts of the report that make assertions. Disclaimers and
    # scope statements legitimately contain phrases like "title is clear" in a
    # negated form ("nothing here confirms that title is clear").
    excluded_keys = {"disclaimer", "scope_statement", "scope_and_limitations", "limitations",
                     "note", "jurisdiction_caveat", "how_determined", "method"}

    def claims(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in excluded_keys:
                    continue
                yield from claims(value)
        elif isinstance(node, list):
            for item in node:
                yield from claims(item)
        elif isinstance(node, str):
            yield node.lower()

    text = " ".join(claims(report.payload))
    for forbidden in ("title is clear", "marketable title confirmed", "no litigation exists",
                      "free from encumbrances", "safe to purchase", "document is genuine",
                      "ownership verified", "legally verified", "title has been verified",
                      "title is confirmed", "property is clear"):
        assert forbidden not in text, "report must not assert: {}".format(forbidden)

    final = report.payload["section_13_final_assessment"]
    assert final["status"] != "no_material_issues_identified_in_reviewed_evidence"
    assert final["disclaimer"]
    assert len(final["scope_and_limitations"]) >= 3

    # The scope statement about external checks is always present.
    assert findings_for(case_id, detector="scope_no_external_checks")
    s8 = report.payload["section_8_legal_regulatory"]
    assert s8["checks_outstanding"]
