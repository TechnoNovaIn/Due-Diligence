# -*- coding: utf-8 -*-
"""Document size and length are unlimited by default.

Property files routinely contain large scanned deed books. A cap can still be
configured, and when one is hit the system says so rather than failing quietly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import filesafe
from app.services.extraction import extract_document


def _pdf_with_pages(path: Path, pages: int) -> Path:
    """A long document with a realistic amount of text on every page.

    Page density matters: a page with almost no text reads as a scan and is sent
    to OCR, so a sparse fixture would measure OCR throughput rather than the
    document handling this module is about.
    """
    import fitz

    body = ("The Vendor hereby conveys unto the Purchaser the schedule property together with "
            "all rights, easements and appurtenances. Survey No. 123/4B, Hosahalli Village, "
            "Nelamangala Taluk, Bengaluru Rural District, measuring 2 acres 15 guntas. ")
    doc = fitz.open()
    for n in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(50, 50, 545, 790),
                            "Page {} of the schedule. ".format(n + 1) + body * 6, fontsize=9)
    doc.save(str(path))
    doc.close()
    return path


# ------------------------------------------------------------------ size
def _file_of_mb(path: Path, megabytes: float) -> Path:
    """A real PDF padded to a given size, so the size check is genuinely exercised."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "Schedule of property. Survey No. 123/4B.", fontsize=11)
    doc.save(str(path))
    doc.close()
    # PDF readers ignore bytes after %%EOF, so padding keeps the file valid.
    with open(path, "ab") as fh:
        fh.write(b"\n%" + b"0" * int(megabytes * 1024 * 1024))
    return path


def test_a_large_file_is_accepted_by_default(tmp_path):
    big = _file_of_mb(tmp_path / "deed_book.pdf", 80)
    assert big.stat().st_size > 60 * 1024 * 1024, "larger than the limit that used to apply"

    check = filesafe.check_file(big)
    assert check.ok, check.reason
    assert filesafe.check_file(big, max_mb=0).ok, "0 means no limit"


def test_a_configured_cap_is_enforced_and_explains_itself(tmp_path):
    path = _file_of_mb(tmp_path / "deed_book.pdf", 3)

    assert filesafe.check_file(path, max_mb=10).ok

    blocked = filesafe.check_file(path, max_mb=1)
    assert not blocked.ok
    assert "over the configured limit of 1 MB" in blocked.reason
    assert "MAX_FILE_MB" in blocked.reason, "the refusal must say how to lift the cap"
    assert "0 for no limit" in blocked.reason
    assert not blocked.quarantine, "being large is not a reason to quarantine a file"


def test_a_large_file_still_has_to_be_a_real_document(tmp_path):
    """Removing the size limit must not weaken the other checks."""
    fake = tmp_path / "huge.pdf"
    fake.write_bytes(b"MZ\x90\x00" + b"0" * (5 * 1024 * 1024))
    check = filesafe.check_file(fake)
    assert not check.ok
    assert check.quarantine


def test_settings_expose_unlimited_as_none(env, monkeypatch):
    from app import config

    monkeypatch.setenv("MAX_FILE_MB", "0")
    config.reset_settings_cache()
    assert config.get_settings().max_file_bytes is None

    monkeypatch.setenv("MAX_FILE_MB", "25")
    config.reset_settings_cache()
    assert config.get_settings().max_file_bytes == 25 * 1024 * 1024
    config.reset_settings_cache()


# ------------------------------------------------------------------ pages
def test_every_page_is_read_when_no_page_limit_is_set(tmp_path):
    path = _pdf_with_pages(tmp_path / "long.pdf", 405)
    result = extract_document(path, ocr_enabled=False, max_pages=0)

    assert result.ok
    assert result.page_count == 405, "the whole document must be read"
    assert result.pages[-1].page_no == 405
    assert "Page 405" in result.pages[-1].text
    assert not [i for i in result.issues if "only the first" in i]


def test_a_configured_page_limit_truncates_and_says_so(tmp_path):
    path = _pdf_with_pages(tmp_path / "long.pdf", 60)
    result = extract_document(path, ocr_enabled=False, max_pages=10)

    assert result.page_count == 10
    truncation = [i for i in result.issues if "only the first" in i]
    assert truncation, "truncation must be reported, never silent"
    assert "MAX_PAGES_PER_DOCUMENT" in truncation[0]


def test_a_long_document_flows_through_the_pipeline(make_case, pump, tmp_path):
    """A document longer than the old 400-page cap is analysed in full."""
    import time

    from helpers import documents_for, ingest_and_run

    case_id, folder = make_case()
    _pdf_with_pages(Path(folder) / "long_deed_book.pdf", 405)
    started = time.time()
    ingest_and_run(case_id, pump)
    elapsed = time.time() - started
    assert elapsed < 60, "405 pages took {:.1f}s end to end".format(elapsed)

    docs = documents_for(case_id)
    assert len(docs) == 1
    assert docs[0].page_count == 405
    assert docs[0].status in ("analysed", "needs_manual_review")
    assert not any("only the first" in (i.get("detail") or "") for i in (docs[0].issues or []))
