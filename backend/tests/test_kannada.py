# -*- coding: utf-8 -*-
"""Kannada document analysis.

Karnataka's own records - Bhoomi RTC/Pahani, Kaveri encumbrance certificates,
panchayat khata and most registered deeds - are issued in Kannada, usually as
digital PDFs with a real text layer. The pipeline must read them as well as it
reads English ones, and must cross-check across the two scripts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import normalize as nz
from app.services.classify import classify_by_rules
from app.services.extraction import extract_document
from app.services.extraction.base import PageText
from app.services.fields import extract_fields
from helpers import documents_for, findings_for, ingest_and_run, latest_report

RTC = """ಹಕ್ಕು, ಬಾಧ್ಯತೆ ಮತ್ತು ಬೆಳೆಗಳ ದಾಖಲೆ (ಪಹಣಿ)
ಗ್ರಾಮ: ಹೊಸಹಳ್ಳಿ        ಹೋಬಳಿ: ಕಸಬಾ        ತಾಲ್ಲೂಕು: ನೆಲಮಂಗಲ
ಜಿಲ್ಲೆ: ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ
ಸರ್ವೇ ಸಂಖ್ಯೆ: ೧೨೩/೪ಬಿ        ಹಿಸ್ಸಾ: ೪ಬಿ
ಖಾತೆದಾರರ ಹೆಸರು: ಶ್ರೀಮತಿ ಲತಾ ರಾವ್ ಕೋಂ ಮೋಹನ್ ರಾವ್
ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ: ೨ ಎಕರೆ ೨೦ ಗುಂಟೆ
ಖರಾಬು: ೫ ಗುಂಟೆ
ದಿನಾಂಕ: ೧೮/೦೬/೨೦೨೪"""

SALE_DEED = """ಕ್ರಯ ಪತ್ರ
ಈ ಸಂಪೂರ್ಣ ಕ್ರಯ ಪತ್ರವನ್ನು ದಿನಾಂಕ ೧೨ ಮಾರ್ಚ್ ೨೦೧೫ ರಂದು ಬರೆದುಕೊಡಲಾಗಿದೆ.
ಮಾರಾಟಗಾರ: ಶ್ರೀ ರಮೇಶ್ ಕುಮಾರ್ ಬಿನ್ ದಿವಂಗತ ಕೃಷ್ಣಪ್ಪ
ಖರೀದಿದಾರ: ಶ್ರೀಮತಿ ಲತಾ ರಾವ್ ಕೋಂ ಶ್ರೀ ಮೋಹನ್ ರಾವ್
ಕ್ರಯದ ಮೊತ್ತ: ರೂ. ೪೫,೦೦,೦೦೦/-
ಸರ್ವೇ ಸಂಖ್ಯೆ ೧೨೩/೪ಬಿ, ಹೊಸಹಳ್ಳಿ ಗ್ರಾಮ, ನೆಲಮಂಗಲ ತಾಲ್ಲೂಕು
ವಿಸ್ತೀರ್ಣ: ೨ ಎಕರೆ ೧೫ ಗುಂಟೆ
ನೋಂದಣಿ ದಿನಾಂಕ: ೧೫/೦೩/೨೦೧೫"""


# --------------------------------------------------------------- normalisation
@pytest.mark.parametrize("text,expected", [
    ("೧೨೩/೪ಬಿ", "123/4ಬಿ"),
    ("ಸರ್ವೇ ಸಂಖ್ಯೆ: ೧೨೩/೪ಬಿ", "123/4ಬಿ"),
    ("Sy. No. 123/4 B", "123/4B"),
])
def test_survey_numbers_normalise_in_both_scripts(text, expected):
    assert nz.normalize_survey_number(text) == expected


@pytest.mark.parametrize("text,sqm", [
    ("೨ ಎಕರೆ ೧೫ ಗುಂಟೆ", 9611.284),
    ("೨ ಎಕರೆ ೨೦ ಗುಂಟೆ", 10117.141),
    ("೫ ಗುಂಟೆ", 505.857),
    ("೧,೨೦೦ ಚದರ ಅಡಿ", 111.484),
])
def test_kannada_areas_convert_to_the_same_unit_as_english(text, sqm):
    parsed = nz.parse_area(text)
    assert parsed is not None
    assert parsed[2] == pytest.approx(sqm, rel=1e-4)


def test_an_acre_is_an_acre_in_either_script():
    assert nz.parse_area("೨ ಎಕರೆ ೧೫ ಗುಂಟೆ")[2] == pytest.approx(nz.parse_area("2 acres 15 guntas")[2])


@pytest.mark.parametrize("text,expected", [
    ("೧೮/೦೬/೨೦೨೪", "2024-06-18"),
    ("೧೨ ಮಾರ್ಚ್ ೨೦೧೫", "2015-03-12"),
    ("೦೪ ಆಗಸ್ಟ್ ೧೯೯೮", "1998-08-04"),
])
def test_kannada_dates(text, expected):
    assert nz.iso_date(text) == expected


def test_kannada_money():
    assert nz.parse_money("ರೂ. ೪೫,೦೦,೦೦೦/-") == 4500000
    assert nz.parse_money("೪೫ ಲಕ್ಷ") == 4500000
    assert nz.parse_money("೧.೫ ಕೋಟಿ") == 15000000


def test_kannada_names_drop_honorifics_and_relation_clauses():
    assert nz.normalize_name("ಶ್ರೀಮತಿ ಲತಾ ರಾವ್ ಕೋಂ ಮೋಹನ್ ರಾವ್") == "ಲತಾ ರಾವ್"
    assert nz.normalize_name("ಶ್ರೀ ರಮೇಶ್ ಕುಮಾರ್ ಬಿನ್ ದಿವಂಗತ ಕೃಷ್ಣಪ್ಪ") == "ರಮೇಶ್ ಕುಮಾರ್"
    assert nz.names_match("ಶ್ರೀಮತಿ ಲತಾ ರಾವ್", "ಲತಾ ರಾವ್ ಕೋಂ ಮೋಹನ್ ರಾವ್")


def test_script_detection():
    assert nz.script_of(RTC) == "kn"
    assert nz.script_of("Village: Hosahalli, Survey No 123/4B") == "en"
    assert nz.script_of("Survey No 123 ಗ್ರಾಮ ಹೊಸಹಳ್ಳಿ Village Taluk") == "mixed"


# --------------------------------------------------------------- classification
@pytest.mark.parametrize("text,expected", [
    (RTC, "rtc_pahani"),
    (SALE_DEED, "sale_deed"),
    ("ಋಣಭಾರ ಪ್ರಮಾಣ ಪತ್ರ ನಮೂನೆ ೧೫ ಉಪ ನೋಂದಣಾಧಿಕಾರಿಗಳ ಕಚೇರಿ ಅವಧಿ ನಮೂದುಗಳು", "encumbrance_certificate"),
    ("ಸರಳ ಅಡಮಾನ ಪತ್ರ ಅಡಮಾನದಾರ ಅಡಮಾನ ಸ್ವೀಕರಿಸಿದವರು ಬ್ಯಾಂಕ್ ಋಣ", "mortgage_deed"),
    ("ಭೂ ಪರಿವರ್ತನೆ ಆದೇಶ ಜಿಲ್ಲಾಧಿಕಾರಿ ಕೃಷಿಯೇತರ ಪರಿವರ್ತನೆ ಶುಲ್ಕ", "land_conversion_order"),
    ("ಪಾಲು ಪತ್ರ ವಿಭಾಗ ಪತ್ರ ಅವಿಭಕ್ತ ಕುಟುಂಬ ಪಾಲುದಾರರು", "partition_deed"),
    ("ಖಾತಾ ಪ್ರಮಾಣ ಪತ್ರ ಗ್ರಾಮ ಪಂಚಾಯತ್ ಖಾತಾ ಸಂಖ್ಯೆ ಹೆಸರಿನಲ್ಲಿದೆ", "khata_certificate"),
    ("ಮುಖ್ತ್ಯಾರ್ ಪತ್ರ ಮುಖ್ತ್ಯಾರ್ದಾರ ನೇಮಕ", "power_of_attorney"),
])
def test_kannada_documents_are_classified(text, expected):
    result = classify_by_rules(text, "")
    assert result.doc_type == expected, result.rationale
    assert result.confidence >= 0.55


# --------------------------------------------------------------- extraction
def test_kannada_rtc_fields():
    hits = {h.key: h.value_norm for h in extract_fields([PageText(1, RTC)], "rtc_pahani")}
    assert hits["survey_number"] == "123/4ಬಿ"
    assert hits["subdivision_number"] == "4ಬಿ"
    assert hits["village"] == "ಹೊಸಹಳ್ಳಿ"
    assert hits["taluk"] == "ನೆಲಮಂಗಲ"
    assert hits["district"] == "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ"
    assert hits["hobli"] == "ಕಸಬಾ"
    assert hits["owner_name"] == "ಲತಾ ರಾವ್"
    assert "2.5 acre" in hits["property_area"]
    assert hits["document_date"] == "2024-06-18"


def test_kannada_deed_parties_and_consideration():
    hits = {h.key: h.value_norm for h in extract_fields([PageText(1, SALE_DEED)], "sale_deed")}
    assert hits["party_seller"] == "ರಮೇಶ್ ಕುಮಾರ್"
    assert hits["party_buyer"] == "ಲತಾ ರಾವ್"
    assert "45,00,000" in hits["consideration_amount"]
    assert hits["registration_date"] == "2015-03-12" or hits["registration_date"] == "2015-03-15"


def test_a_place_label_does_not_match_inside_a_longer_word():
    """ಗ್ರಾಮ (village) is a prefix of ಗ್ರಾಮಾಂತರ (rural) and ಗ್ರಾಮೀಣ."""
    text = "ಜಿಲ್ಲೆ: ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ\nಕರ್ನಾಟಕ ಗ್ರಾಮೀಣ ಬ್ಯಾಂಕ್"
    hits = extract_fields([PageText(1, text)], "rtc_pahani")
    villages = {h.value_norm for h in hits if h.key == "village"}
    assert villages == set()
    districts = {h.value_norm for h in hits if h.key == "district"}
    assert districts == {"ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ"}


@pytest.mark.parametrize("text,expected", [
    # Kannada records lay their labels out in columns on one line, so a value
    # must stop at the next label rather than swallowing it.
    ("ಜಿಲ್ಲೆ: ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ        ವರ್ಷ: ೨೦೨೪-೨೫", ("district", "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ")),
    ("ಗ್ರಾಮ: ಹೊಸಹಳ್ಳಿ        ಹೋಬಳಿ: ಕಸಬಾ", ("village", "ಹೊಸಹಳ್ಳಿ")),
    ("ತಾಲ್ಲೂಕು: ನೆಲಮಂಗಲ   ಸರ್ವೇ ಸಂಖ್ಯೆ: ೧೨೩/೪ಬಿ", ("taluk", "ನೆಲಮಂಗಲ")),
    ("ಗ್ರಾಮ: ಹೊಸಹಳ್ಳಿ   ವಿಸ್ತೀರ್ಣ: ೨ ಎಕರೆ", ("village", "ಹೊಸಹಳ್ಳಿ")),
])
def test_a_place_value_stops_at_the_next_column_label(text, expected):
    key, value = expected
    hits = {h.key: h.value_norm for h in extract_fields([PageText(1, text)], "rtc_pahani")}
    assert hits[key] == value


def test_kannada_digits_are_not_mistaken_for_a_place_name():
    """Kannada digits sit inside the Kannada block and must not match a name class."""
    hits = extract_fields([PageText(1, "ದಿನಾಂಕ: ೧೮/೦೬/೨೦೨೪    ಗ್ರಾಮ ಲೆಕ್ಕಿಗರು")], "rtc_pahani")
    assert not [h for h in hits if h.key == "village"]


def test_a_kannada_covenant_denying_encumbrance_is_not_read_as_one():
    text = "ಈ ಸ್ವತ್ತು ಯಾವುದೇ ಋಣಭಾರ, ಅಡಮಾನ, ವ್ಯಾಜ್ಯದಿಂದ ಮುಕ್ತವಾಗಿದೆ."
    hits = extract_fields([PageText(1, text)], "sale_deed")
    assert not [h for h in hits if h.key == "mortgage_status"]
    assert [h for h in hits if h.key == "covenant_denial"]


def test_an_actual_kannada_mortgage_is_detected():
    text = "ಸ್ವತ್ತಿನ ಮೇಲೆ ಅಡಮಾನ ಸೃಷ್ಟಿಸಲಾಗಿದೆ. ಸಾಲದ ಮೊತ್ತ ರೂ. ೧೮,೦೦,೦೦೦/-"
    hits = extract_fields([PageText(1, text)], "mortgage_deed")
    assert any(h.key == "mortgage_status" and h.value_norm == "mortgage_indicated" for h in hits)


def test_kannada_ec_period_is_read():
    text = "ಅವಧಿ: ೦೧/೦೪/೨೦೧೯ ರಿಂದ ೩೦/೦೬/೨೦೨೪ ವರೆಗೆ"
    hits = {h.key: h.value_norm for h in extract_fields([PageText(1, text)], "encumbrance_certificate")}
    assert hits["ec_period_from"] == "2019-04-01"
    assert hits["ec_period_to"] == "2024-06-30"


def test_every_kannada_hit_keeps_its_page_and_evidence():
    for hit in extract_fields([PageText(4, RTC)], "rtc_pahani"):
        assert hit.page_no == 4
        assert hit.evidence


# --------------------------------------------------------------- end to end
def test_a_kannada_document_set_is_analysed_end_to_end(make_case, samples, pump):
    case_id, folder = make_case()
    samples("kannada", folder=folder)
    ingest_and_run(case_id, pump)

    docs = documents_for(case_id)
    assert len(docs) == 5
    types = {d.doc_type for d in docs}
    assert {"rtc_pahani", "sale_deed", "encumbrance_certificate",
            "mutation_extract", "property_tax_receipt"} <= types
    assert all(d.status == "analysed" for d in docs), [d.status for d in docs]

    report = latest_report(case_id)
    assert report is not None
    assert Path(report.pdf_path).exists()


def test_cross_verification_works_across_kannada_documents(make_case, samples, pump):
    """The Kannada deed says 2a 15g, the Kannada RTC says 2a 20g."""
    case_id, folder = make_case()
    samples("kannada", folder=folder)
    ingest_and_run(case_id, pump)

    area = findings_for(case_id, detector="area_mismatch", status="open")
    assert area, "the extent difference between the Kannada deed and RTC should be detected"
    cited = {e.document_name for e in area[0].evidence}
    assert len(cited) >= 2

    assert findings_for(case_id, detector="ec_short_period", status="open")
    assert findings_for(case_id, detector="mortgage_unreleased", status="open")


def test_a_mixed_script_case_is_reconciled(make_case, samples, pump):
    """An English deed and a Kannada RTC describe one property; both must be read."""
    from helpers import copy_files

    case_id, folder = make_case()
    staging = samples("all")
    copy_files(staging, Path(folder), ["01_sale_deed_2015.pdf"])
    copy_files(staging, Path(folder), ["11_pahani_rtc_kannada.pdf"])
    ingest_and_run(case_id, pump)

    docs = {d.doc_type: d for d in documents_for(case_id)}
    assert "sale_deed" in docs and "rtc_pahani" in docs

    # Both documents describe survey number 123/4B - written "123/4ಬಿ" in Kannada.
    surveys = set()
    for doc in docs.values():
        surveys |= {f.value_norm for f in doc.fields if f.field_key == "survey_number"}
    assert "123/4B" in surveys and "123/4ಬಿ" in surveys

    # The extents differ (2a 15g against 2a 20g), and that must be reported.
    assert findings_for(case_id, detector="area_mismatch", status="open")


# ------------------------------------- comparing names written in two scripts
def test_the_same_village_in_two_scripts_is_not_called_a_conflict():
    """A Kannada deed says ಅರಕೆರೆ and an English one says Arakere.

    Establishing they are the same place needs transliteration, which this
    system does not do - but it has no basis for calling them different either.
    """
    from app.services.crossverify import _conflicting_within_script

    assert _conflicting_within_script({"arakere": 1, "ಅರಕೆರೆ": 1}) == {}


def test_two_different_names_in_one_script_remain_a_conflict():
    from app.services.crossverify import _conflicting_within_script

    assert sorted(_conflicting_within_script({"ಅರಕೆರೆ": 1, "ತುಮಕೂರು": 1})) == [
        "ಅರಕೆರೆ", "ತುಮಕೂರು"]
    assert sorted(_conflicting_within_script({"arakere": 1, "hosahalli": 1})) == [
        "arakere", "hosahalli"]


def test_the_translation_is_left_out_of_a_real_discrepancy():
    """Two Kannada readings disagree; the English spelling is not party to it."""
    from app.services.crossverify import _conflicting_within_script

    assert sorted(_conflicting_within_script(
        {"arakere": 1, "ಅರಕೆರೆ": 1, "ಆರ್ರೆ": 1})) == ["ಅರಕೆರೆ", "ಆರ್ರೆ"]


def test_script_detection_handles_values_without_letters():
    from app.services.crossverify import _script_of

    assert _script_of("96/1,2") == "other"
    assert _script_of("Arakere") == "latin"
    assert _script_of("ಅರಕೆರೆ") == "kannada"


# --------------------------------------- gram panchayat is not the village field
def _villages(text):
    from app.services.extraction.base import PageText
    return [h.value_norm for h in extract_fields([PageText(1, text)], "sale_deed")
            if h.key == "village"]


def test_a_gram_panchayat_is_not_read_as_the_village():
    """Revenue tables put several labelled fields on one line.

    ``ಗ್ರಾಮ ಪಂಚಾಯತಿ`` is a council, so reading its ``ಗ್ರಾಮ`` as the village label
    took the block name that preceded it as the village.
    """
    line = "ಬ್ಲಾಕ್ :ತುಮಕೂರು ಗ್ರಾಮ ಪಂಚಾಯತಿ ಅರಕೆರೆ ಗ್ರಾಮ ಅರಕೆರೆ"
    assert _villages(line) == ["ಅರಕೆರೆ"]


def test_panchayat_in_running_prose_yields_no_village():
    assert _villages("ಸದರಿ ಸ್ವತ್ತಿಗೆ ಗ್ರಾಮ ಪಂಚಾಯಿತಿಯ ಕಂದಾಯ ಕಟ್ಟಿಕೊಂಡು") == []


def test_an_ocr_variant_of_panchayat_is_also_excluded():
    """Tesseract reads ಪಂಚಾಯತಿ as ಪಣಂತಾಯತಿ on a poor scan."""
    line = "ಜಿಲ್ಲೆ :ತುಮಕೂರು ಬ್ಲಾಕ್ :ತುಮಕೂರು ಗ್ರಾಮ ಪಣಂತಾಯತಿ :ಅರಕೆರೆ ಗ್ರಾಮ :ಆರ್ರೆ"
    assert "ತುಮಕೂರು" not in _villages(line)


def test_the_ordinary_village_labels_still_work():
    assert _villages("ಗ್ರಾಮ: ಹೊಸಹಳ್ಳಿ") == ["ಹೊಸಹಳ್ಳಿ"]
    assert _villages("ಹೊಸಹಳ್ಳಿ ಗ್ರಾಮ") == ["ಹೊಸಹಳ್ಳಿ"]


# ------------------------------------------------- false conflicts in the report
def _one(text, key, doc_type="sale_deed"):
    from app.services.extraction.base import PageText
    return [h.value_norm for h in extract_fields([PageText(1, text)], doc_type) if h.key == key]


def test_a_column_label_does_not_become_part_of_the_district():
    """ತುಮಕೂರು ಬ್ಲಾಕ್ was reported as a district conflicting with ತುಮಕೂರು."""
    line = "ಜಿಲ್ಲೆ :ತುಮಕೂರು ಬ್ಲಾಕ್ :ತುಮಕೂರು ಗ್ರಾಮ ಪಂಚಾಯತಿ ಅರಕೆರೆ"
    assert _one(line, "district") == ["ತುಮಕೂರು"]


def test_a_two_word_district_is_still_kept_whole():
    assert _one("ಜಿಲ್ಲೆ: ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ", "district") == ["ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ"]


def test_a_preposition_is_not_part_of_a_place_name():
    """"OF ARAKERE" was reported as conflicting with "Arakere"."""
    assert _one("SITE NO 96/1,96/2 OF ARAKERE VILLAGE", "village") == ["ARAKERE"]


def test_only_a_recognised_land_class_is_reported():
    assert _one("SOIL CLASSIFICATION ANALYSIS", "land_classification", "rtc_pahani") == []
    assert _one("Classification : Agricultural dry land", "land_classification",
                "rtc_pahani") == ["Agricultural dry land"]
    assert _one("ಜಮೀನಿನ ವರ್ಗ: ಖುಷ್ಕಿ", "land_classification", "rtc_pahani") == ["ಖುಷ್ಕಿ"]


def test_a_conflict_is_reported_only_between_values_in_one_script():
    from app.services.crossverify import _conflicting_within_script

    assert _conflicting_within_script({"arakere": 1, "ಅರಕೆರೆ": 1}) == {}
    assert sorted(_conflicting_within_script(
        {"arakere": 1, "ಅರಕೆರೆ": 1, "ಆರ್ರೆ": 1})) == ["ಅರಕೆರೆ", "ಆರ್ರೆ"]
    assert sorted(_conflicting_within_script({"arakere": 1, "hosahalli": 1})) == [
        "arakere", "hosahalli"]


def test_an_extent_that_is_not_an_area_is_dropped():
    """The label pattern ran on into the sentence after it and filled the
    extent row with prose, which then disagreed with the real extent."""
    prose = "ವಿಸ್ತೀರ್ಣ: ದಲ್ಲಿ ಅನುಮೋದಿತ ನಕ್ಷೆಯಲ್ಲಿ ತೋರಿಸಿರುವಂತೆ ಅನಿಯಮಿತ ಅಳತೆಯ 21 ನಿವೇಶನಗಳಿರುತ್ತವೆ"
    assert _one(prose, "property_area", "approved_layout_plan") == []


def test_a_real_extent_is_still_read():
    assert _one("ವಿಸ್ತೀರ್ಣ: ೨ ಎಕರೆ ೨೦ ಗುಂಟೆ", "property_area", "rtc_pahani") == [
        "2.5 acre (10117.1 sq m)"]


def test_a_boundary_in_two_scripts_is_not_a_discrepancy():
    """"SITE NO 90" and "ಸೈಟ್ ನಂ90" score near zero against each other."""
    from app.services.crossverify import _script_of

    assert _script_of("SITE NO 90") != _script_of("ಸೈಟ್ ನಂ90")


def test_an_incomplete_rendering_of_the_same_value_is_not_a_conflict():
    """"North" is "Kasaba North" recorded less fully, not a different hobli."""
    from app.services.crossverify import _conflicting_within_script

    assert _conflicting_within_script({"Kasaba North": 1, "North": 1}) == {}


def test_two_genuinely_different_names_still_conflict():
    """Erring towards flagging: a missed discrepancy is the costlier error."""
    from app.services.crossverify import _conflicting_within_script

    assert sorted(_conflicting_within_script({"ಅರಕೆರೆ": 1, "ತುಮಕೂರು": 1})) == [
        "ಅರಕೆರೆ", "ತುಮಕೂರು"]
