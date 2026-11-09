# -*- coding: utf-8 -*-
"""Honesty about which scripts the OCR engine can actually read.

macOS Vision reads no Kannada. Handed ``kn-IN`` it quietly falls back to English
and renders Kannada glyphs as Latin noise, so a Karnataka deployment would be
told it had read documents that were never read. The engine's real language list
is asked at runtime and the gap is reported.
"""
from __future__ import annotations

import pytest

from app.services.extraction import ocr as ocr_module
from app.services.extraction.extractor import _collapse_per_page_issues, _summarise_pages


def _clear():
    ocr_module._missing_for.cache_clear()
    ocr_module.engine_for.cache_clear()


@pytest.fixture
def vision(monkeypatch):
    """Only macOS Vision installed, with its real language list."""
    monkeypatch.setattr(ocr_module, "installed_engines", lambda: ["macos_vision"])
    monkeypatch.setattr(ocr_module, "_vision_supported",
                        lambda: frozenset({"en-US", "hi-IN", "mr-IN", "fr-FR"}))
    _clear()
    yield
    _clear()


@pytest.fixture
def vision_and_easyocr(monkeypatch):
    """Both installed - the arrangement on a Mac without Homebrew."""
    monkeypatch.setattr(ocr_module, "installed_engines",
                        lambda: ["macos_vision", "easyocr"])
    monkeypatch.setattr(ocr_module, "_vision_supported",
                        lambda: frozenset({"en-US", "hi-IN", "mr-IN", "fr-FR"}))
    _clear()
    yield
    _clear()


def test_kannada_is_reported_as_unreadable_by_vision(vision):
    assert ocr_module.unreadable_languages("eng+kan") == ("kan",)


def test_a_language_vision_does_support_is_not_flagged(vision):
    assert ocr_module.unreadable_languages("eng+hin") == ()


def test_an_unsupported_code_is_not_passed_to_vision(vision):
    """Passing it would trigger the silent English fallback."""
    assert ocr_module._vision_languages("eng+kan") == ["en-US"]
    assert "kn-IN" not in ocr_module._vision_languages("kan")


def test_the_warning_names_the_script_and_the_remedy(vision):
    warning = ocr_module._language_warning("eng+kan")
    assert "Kannada" in warning
    assert "manual review" in warning
    assert "tesseract" in warning.lower()


def test_no_warning_when_every_language_is_readable(vision):
    assert ocr_module._language_warning("eng") is None


def test_status_separates_readable_from_unreadable(vision):
    status = ocr_module.ocr_status("eng+kan")
    assert status["languages"] == {
        "configured": ["eng", "kan"], "readable": ["eng"], "unreadable": ["kan"]
    }
    assert "cannot read Kannada" in status["note"]


def test_status_does_not_promise_kannada_when_it_cannot_deliver(vision):
    """The note used to advise `eng+kan` whatever the engine could do."""
    note = ocr_module.ocr_status("eng+kan")["note"]
    assert "for example `eng+kan`" not in note


def test_missing_engine_still_reports_cleanly(monkeypatch):
    monkeypatch.setattr(ocr_module, "installed_engines", lambda: [])
    _clear()
    status = ocr_module.ocr_status("eng+kan")
    assert status["available"] is False
    assert status["languages"]["configured"] == ["eng", "kan"]
    _clear()


# ------------------------------------------- one issue per document, not per page
def test_a_problem_on_every_page_is_reported_once():
    collapsed = _collapse_per_page_issues(["Page {}: cannot read Kannada".format(i)
                                           for i in range(1, 406)])
    assert collapsed == ["Pages 1-405: cannot read Kannada"]


def test_distinct_problems_are_kept_apart():
    assert _collapse_per_page_issues(["Page 1: A", "Page 2: A", "Page 9: B"]) == [
        "Pages 1-2: A", "Page 9: B"]


def test_an_issue_without_a_page_is_left_alone():
    assert _collapse_per_page_issues(["OCR disabled in configuration."]) == [
        "OCR disabled in configuration."]


def test_scattered_pages_are_summarised_not_listed():
    assert _summarise_pages([1, 3, 5, 7, 9, 11, 13]) == "1, 3, 5, 7, 9 and 2 more"


# ------------------------------- choosing between engines that differ in script
def test_easyocr_is_chosen_only_when_the_script_needs_it(vision_and_easyocr):
    """Vision is faster, so it keeps English; Kannada forces the slower engine."""
    assert ocr_module.engine_candidates("eng") == ["macos_vision"]
    assert ocr_module.engine_candidates("eng+kan") == ["macos_vision", "easyocr"]


def test_kannada_becomes_readable_once_easyocr_is_installed(vision_and_easyocr):
    assert ocr_module.unreadable_languages("eng+kan") == ()
    assert ocr_module.ocr_status("eng+kan")["engine"] == "EasyOCR"


def test_a_kannada_page_is_recognised_by_what_was_read(vision_and_easyocr):
    kannada = "\u0c85\u0ca8\u0cc1\u0cae\u0ccb\u0ca6\u0ca8\u0cc6 \u0c86\u0ca6\u0cc7\u0cb6"
    assert ocr_module.script_share(kannada, "eng+kan", "macos_vision") > 0.9


def test_an_english_page_is_not_mistaken_for_kannada(vision_and_easyocr):
    english = "APPROVED LAYOUT PLAN TUDA TUMKUR DRG NO 2361.41 RESIDENTIAL"
    assert ocr_module.script_share(english, "eng+kan", "macos_vision") == 0.0


def test_a_stray_kannada_character_does_not_switch_the_engine(vision_and_easyocr):
    """Recognisers invent a few characters; a quarter of the page is the test."""
    mostly_english = "APPROVED LAYOUT PLAN TUDA TUMKUR RESIDENTIAL \u0c85\u0ca8\u0cc1"
    assert ocr_module.script_share(mostly_english, "eng+kan", "macos_vision") < 0.25


def test_nothing_to_choose_when_one_engine_reads_everything(vision_and_easyocr):
    """No probe, so no page is read at all before the real read."""
    engine, note, reads = ocr_module.choose_engine([b"ignored"], "eng")
    assert engine == "macos_vision"
    assert note is None
    assert reads == {}


def test_the_probe_hands_back_what_it_read(monkeypatch, vision_and_easyocr):
    """A sampled page is not read twice when the probe picked that engine."""
    kannada = "\u0c85\u0ca8\u0cc1\u0cae\u0ccb\u0ca6\u0ca8\u0cc6"
    monkeypatch.setattr(ocr_module, "ocr_image_bytes",
                        lambda data, language, engine=None: (kannada, 0.9, None))
    engine, note, reads = ocr_module.choose_engine([b"a", b"b"], "eng+kan")
    assert engine == "easyocr"
    assert "Kannada" in note
    assert reads == {0: (kannada, 0.9), 1: (kannada, 0.9)}


def test_returned_samples_belong_to_the_engine_that_was_chosen(monkeypatch, vision_and_easyocr):
    """Mixing them would put EasyOCR text into a Vision-read document."""
    monkeypatch.setattr(ocr_module, "ocr_image_bytes",
                        lambda data, language, engine=None: ("read by " + engine, 0.9, None))
    engine, note, reads = ocr_module.choose_engine([b"a"], "eng+kan")
    assert engine == "macos_vision"
    assert reads == {0: ("read by macos_vision", 0.9)}


def test_a_blank_result_falls_back_to_another_engine(monkeypatch, vision_and_easyocr):
    """Tesseract reads nothing from a phone photo that Vision handles."""
    def read(data, language, engine=None):
        return ("", 0.0, None) if engine == "macos_vision" else ("PLENTY OF TEXT HERE", 0.8, None)

    monkeypatch.setattr(ocr_module, "ocr_image_bytes", read)
    engine, note, reads = ocr_module.choose_engine([b"a"], "eng")
    assert engine == "easyocr"
    assert "returned no text" in note
    assert reads == {0: ("PLENTY OF TEXT HERE", 0.8)}


def test_the_preferred_engine_is_kept_silently_when_it_works(monkeypatch, vision_and_easyocr):
    monkeypatch.setattr(ocr_module, "ocr_image_bytes",
                        lambda data, language, engine=None: ("PLENTY OF TEXT HERE", 0.8, None))
    engine, note, _ = ocr_module.choose_engine([b"a"], "eng")
    assert engine == "macos_vision"
    assert note is None
