# -*- coding: utf-8 -*-
"""Invisible characters embedded by document producers.

Kaveri and Bhoomi PDFs carry stray control characters *inside* words - a real
encumbrance certificate reads ``ನ\\x1fಮೂನೆ 15`` where it should read ``ನಮೂನೆ 15``.
Replacing them with a space splits the word and every phrase match fails, which
silently defeated classification of the most common document type in Karnataka.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.classify import classify_by_rules
from app.services.extraction import extract_document
from app.services.extraction.base import sanitise_text
from app.services.fields import extract_fields
from app.services.extraction.base import PageText


@pytest.mark.parametrize("raw,expected", [
    ("ನ\x1fಮೂನೆ 15", "ನಮೂನೆ 15"),              # control character inside a word
    ("ಸಸಂ\rಖ್ಯೆ", "ಸಸಂಖ್ಯೆ"),                    # carriage return inside a word
    ("Survey​ No. 123", "Survey No. 123"),  # zero-width space
    ("ಕೆಎ‌-‍ಬಿಎನ್ಜಿ", "ಕೆಎ-ಬಿಎನ್ಜಿ"),   # zero-width joiners
    ("﻿Encumbrance", "Encumbrance"),        # byte-order mark
    ("soft­hyphen", "softhyphen"),
])
def test_invisible_characters_are_deleted_not_spaced(raw, expected):
    assert sanitise_text(raw) == expected


def test_real_text_is_left_alone():
    text = "DEED OF SALE\nSurvey No. 123/4B\tHosahalli\n\nMeasuring 2 acres."
    assert sanitise_text(text) == text


def test_line_endings_are_normalised():
    assert sanitise_text("line one\r\nline two\rline three") == "line one\nline two\nline three"


def _pdf_with(text: str, path: Path) -> Path:
    """Write a PDF with a real text layer, as Kaveri and Bhoomi do.

    Kannada needs an embedded font: the built-in fonts have no glyphs for it and
    PyMuPDF would silently write question marks, so the test would check nothing.
    """
    import fitz

    from samples.generate_samples import find_kannada_font

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    box = fitz.Rect(40, 40, 555, 780)
    if _has_kannada(text):
        font = find_kannada_font()
        if not font:
            pytest.skip("no Kannada font installed to build the fixture with")
        page.insert_font(fontname="kn", fontfile=font)
        page.insert_textbox(box, text, fontname="kn", fontsize=10)
    else:
        page.insert_textbox(box, text, fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


def _has_kannada(text: str) -> bool:
    return any("\u0c80" <= ch <= "\u0cff" for ch in text)


def test_a_certificate_with_embedded_control_characters_still_classifies(tmp_path):
    """The exact failure seen on a real Kaveri encumbrance certificate."""
    body = ("Only For Information\n"
            "Karnataka Government\n"
            "Application Number : TMPEC-260601398326\n"
            "ನ\x1fಮೂನೆ 15 (148ne niya)\n"
            "Sub-Registrar office. Period from 01/04/2019 to 30/06/2024.\n"
            "Entries relating to the said property are as follows.")
    path = _pdf_with(body, tmp_path / "ec.pdf")

    result = extract_document(path, ocr_enabled=False)
    assert "ನಮೂನೆ 15" in result.text, "the control character must be gone by extraction"

    classification = classify_by_rules(result.text, path.name)
    assert classification.doc_type == "encumbrance_certificate", classification.rationale


def test_fields_are_found_despite_embedded_control_characters():
    text = "ಸರ್ವೇ ಸ\x1fಂಖ್ಯೆ: ೧೨೩/೪ಬಿ\nಗ್ರಾ​ಮ: ಹೊಸಹಳ್ಳಿ"
    hits = {h.key: h.value_norm for h in extract_fields([PageText(1, sanitise_text(text))],
                                                        "rtc_pahani")}
    assert hits["survey_number"] == "123/4ಬಿ"
    assert hits["village"] == "ಹೊಸಹಳ್ಳಿ"


# ------------------------------------------------------------ layout plans
def test_an_approved_layout_plan_is_recognised(tmp_path):
    body = ("HAMSA LAYOUT\nLAYOUT PLAN\nTUDA TUMKUR\nTOWN PLANNER   MEMBER\n"
            "DRG NO 2361.41\nAREA IN SQ. M\nC.A. & Play Ground\nKHARAB\n"
            "PROPOSED 9M WIDE ROAD\nRESIDENTIAL")
    path = _pdf_with(body, tmp_path / "layout.pdf")

    result = classify_by_rules(extract_document(path, ocr_enabled=False).text, path.name)
    assert result.doc_type == "approved_layout_plan"
    assert result.confidence > 0.55


def test_a_deed_reciting_an_approved_layout_is_not_mistaken_for_the_plan():
    """A sale deed says the site lies in an approved layout; it is still a deed."""
    text = ("THIS DEED OF ABSOLUTE SALE is made between the VENDOR and the PURCHASER. "
            "The schedule site was formed in the approved layout and a release order was "
            "issued. Sale consideration of Rs. 12,15,000/-. SCHEDULE OF PROPERTY: Site No. 42.")
    result = classify_by_rules(text, "sale_deed.pdf")
    assert result.doc_type == "sale_deed", result.rationale


def test_the_layout_plan_satisfies_the_layout_requirement():
    from app.services.knowledge import jurisdiction

    entry = [r for r in jurisdiction("KA")["requirements"] if r["key"] == "layout_approval"][0]
    assert "approved_layout_plan" in entry["satisfied_by"]
    assert entry.get("name_kn"), "the requirement keeps its Kannada text"
