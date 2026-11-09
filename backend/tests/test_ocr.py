"""OCR behaviour: a scanned document is read when an engine is present, and
honestly reported as unread when one is not.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.classify import classify_by_rules
from app.services.extraction import extract_document
from app.services.extraction.ocr import active_engine, ocr_status
from app.services.fields import extract_fields

SCANNED_BODY = """DEED OF ABSOLUTE SALE

THIS DEED OF ABSOLUTE SALE is made on this 12th day of March 2015

BETWEEN Sri Ramesh Kumar S/o Late Krishnappa, hereinafter called the VENDOR

AND Smt Latha Rao W/o Sri Mohan Rao, hereinafter called the PURCHASER

The sale consideration of Rs. 45,00,000/- has been paid in full.

SCHEDULE OF PROPERTY
Survey No. 123/4B, Hosahalli Village, Nelamangala Taluk,
Bengaluru Rural District, measuring 2 acres 15 guntas.

Registered as document no. KA-BNG-4521/2015 on 15/03/2015."""


def _scanned_pdf(path: Path, body: str = SCANNED_BODY) -> Path:
    """Render text, rasterise it, and drop the text layer entirely."""
    import fitz

    src = fitz.open()
    page = src.new_page(width=595, height=842)
    page.insert_text((55, 70), body, fontsize=11.5, fontname="times-roman")
    pix = page.get_pixmap(dpi=200)
    src.close()

    scanned = fitz.open()
    out = scanned.new_page(width=595, height=842)
    out.insert_image(fitz.Rect(0, 0, 595, 842), pixmap=pix)
    scanned.save(str(path))
    scanned.close()
    return path


def test_the_fixture_really_has_no_text_layer(tmp_path):
    import fitz

    path = _scanned_pdf(tmp_path / "scanned.pdf")
    doc = fitz.open(str(path))
    try:
        assert doc.load_page(0).get_text("text").strip() == ""
    finally:
        doc.close()


def test_ocr_status_reports_the_engine_honestly():
    status = ocr_status()
    assert status["available"] is (active_engine() is not None)
    assert status["note"]
    if not status["available"]:
        assert "manual review" in status["note"]
        assert "install" in status["note"].lower()


@pytest.mark.skipif(active_engine() is None, reason="no OCR engine installed")
def test_a_scanned_deed_is_read_classified_and_extracted(tmp_path):
    path = _scanned_pdf(tmp_path / "scanned_sale_deed.pdf")
    result = extract_document(path)

    assert result.ok, result.error
    assert result.ocr_used
    assert result.method.endswith("ocr")
    assert result.char_count > 200

    classification = classify_by_rules(result.text, path.name)
    assert classification.doc_type == "sale_deed"

    hits = {h.key: h.value_norm for h in extract_fields(result.pages, classification.doc_type)}
    assert hits.get("survey_number") == "123/4B"
    assert hits.get("party_seller") == "Ramesh Kumar"
    assert hits.get("party_buyer") == "Latha Rao"
    assert hits.get("execution_date") == "2015-03-12"
    assert "45,00,000" in (hits.get("consideration_amount") or "")


@pytest.mark.skipif(active_engine() is None, reason="no OCR engine installed")
def test_ocr_preserves_page_references(tmp_path):
    path = _scanned_pdf(tmp_path / "scanned.pdf")
    result = extract_document(path)
    assert result.page_count == 1
    assert result.pages[0].page_no == 1
    assert result.pages[0].ocr_used
    for hit in extract_fields(result.pages, "sale_deed"):
        assert hit.page_no == 1
        assert hit.evidence


@pytest.mark.skipif(active_engine() is None, reason="no OCR engine installed")
def test_a_blank_scan_yields_nothing_rather_than_invention(tmp_path):
    """OCR on an empty page must not produce content."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    pix = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 600, 850))
    pix.clear_with(235)
    page.insert_image(fitz.Rect(0, 0, 595, 842), pixmap=pix)
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    doc.close()

    result = extract_document(path)
    assert not result.ok
    assert result.error
    assert not extract_fields(result.pages, "unknown")


@pytest.mark.skipif(active_engine() is None, reason="no OCR engine installed")
def test_a_scanned_document_flows_through_the_case_pipeline(make_case, samples, pump, tmp_path):
    """End to end: a scanned file in the folder becomes an analysed document."""
    from helpers import ingest_and_run

    case_id, folder = make_case()
    _scanned_pdf(Path(folder) / "scanned_sale_deed.pdf")
    ingest_and_run(case_id, pump)

    from helpers import documents_for

    docs = documents_for(case_id)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.status == "analysed"
    assert doc.ocr_used is True
    assert doc.doc_type == "sale_deed"
    assert doc.pages_analysed == 1
    assert any(f.field_key == "survey_number" and f.value_norm == "123/4B" for f in doc.fields)


# --------------------------------------------------------------- when to OCR
def _digital_pdf(path: Path, pages: int, chars_per_page: int = 900) -> Path:
    """A normal digital PDF: every page carries a full text layer."""
    import fitz

    body = ("The Vendor hereby conveys the schedule property to the Purchaser. "
            "Survey No. 123/4B, Hosahalli Village, Nelamangala Taluk. ")
    doc = fitz.open()
    for n in range(pages):
        page = doc.new_page(width=595, height=842)
        text = ("Page {} of the deed. ".format(n + 1) + body * 10)[:chars_per_page]
        page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=9)
    doc.save(str(path))
    doc.close()
    return path


def _stamped_scan_pdf(path: Path, pages: int) -> Path:
    """A scan carrying a small digital stamp on each page, as registries add."""
    import fitz

    source = fitz.open()
    page = source.new_page(width=595, height=842)
    page.insert_text((60, 90), "DEED OF ABSOLUTE SALE — Survey No. 123/4B, Hosahalli Village.",
                     fontsize=12)
    pix = page.get_pixmap(dpi=150)
    source.close()

    doc = fitz.open()
    for n in range(pages):
        out = doc.new_page(width=595, height=842)
        out.insert_image(fitz.Rect(0, 60, 595, 760), pixmap=pix)
        # The only native text is the registry stamp.
        out.insert_text((50, 800), "SRO NELAMANGALA  {}/{}".format(n + 1, pages), fontsize=7)
    doc.save(str(path))
    doc.close()
    return path


def test_a_digital_document_is_not_sent_to_ocr(tmp_path):
    """Rasterising pages that already have text wastes minutes on a long file."""
    import time

    path = _digital_pdf(tmp_path / "digital.pdf", 120)
    started = time.time()
    result = extract_document(path)
    elapsed = time.time() - started

    assert result.ok
    assert result.page_count == 120
    assert not result.ocr_used, "a document with a full text layer must not be OCR'd"
    assert result.method == "pdf_text"
    assert elapsed < 20, "reading 120 digital pages took {:.1f}s".format(elapsed)


def test_a_thin_page_inside_a_digital_document_is_left_alone(tmp_path):
    import fitz

    path = _digital_pdf(tmp_path / "mixed.pdf", 6)
    doc = fitz.open(str(path))
    sparse = doc.new_page(width=595, height=842)
    sparse.insert_text((60, 80), "SCHEDULE B", fontsize=12)   # a real but thin page
    doc.saveIncr()
    doc.close()

    result = extract_document(path)
    assert result.ok
    assert not result.ocr_used
    assert "SCHEDULE B" in result.pages[-1].text


@pytest.mark.skipif(active_engine() is None, reason="no OCR engine installed")
def test_an_image_page_inside_a_digital_document_is_still_ocrd(tmp_path):
    """A scanned annexure bound into a digital deed must not be skipped."""
    import fitz

    path = _digital_pdf(tmp_path / "with_annexure.pdf", 4)
    scanned = _scanned_pdf(tmp_path / "annexure.pdf")

    doc = fitz.open(str(path))
    doc.insert_pdf(fitz.open(str(scanned)))
    merged = tmp_path / "merged.pdf"
    doc.save(str(merged))
    doc.close()

    result = extract_document(merged)
    assert result.ok
    assert result.ocr_used, "the image-only annexure should have been OCR'd"
    assert "123/4B" in result.pages[-1].text.replace(" ", "")


@pytest.mark.skipif(active_engine() is None, reason="no OCR engine installed")
def test_a_scan_with_a_registry_stamp_is_still_treated_as_a_scan(tmp_path):
    """The stamp gives each page a little native text; the content is still an image."""
    path = _stamped_scan_pdf(tmp_path / "stamped.pdf", 3)
    result = extract_document(path)

    assert result.ok
    assert result.ocr_used, "a stamped scan must not be mistaken for a digital document"
    assert "DEED" in result.text.upper()
