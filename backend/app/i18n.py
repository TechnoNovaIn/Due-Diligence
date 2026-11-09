# -*- coding: utf-8 -*-
"""Translation catalogue.

The system answers in English or Kannada. Everything the interface and the
report put in front of a reader is translated here, keyed by the stable
identifier the rest of the code already uses - an enum value, a requirement key
or a detector name - so nothing has to be matched on English prose.

Coverage is reported honestly by :func:`coverage`: anything without a Kannada
entry falls back to English and is marked as untranslated rather than being
silently mixed in.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

LANGUAGES = ("en", "kn")
DEFAULT_LANGUAGE = "en"

LANGUAGE_NAMES = {"en": "English", "kn": "ಕನ್ನಡ"}


def normalise_language(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_LANGUAGE
    code = value.strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------
SEVERITY = {
    "critical": "ಅತಿ ಗಂಭೀರ",
    "high": "ಗಂಭೀರ",
    "medium": "ಮಧ್ಯಮ",
    "low": "ಕಡಿಮೆ",
    "informational": "ಮಾಹಿತಿ",
}

FINDING_STATUS = {
    "open": "ಇತ್ಯರ್ಥವಾಗಿಲ್ಲ",
    "resolved": "ಇತ್ಯರ್ಥವಾಗಿದೆ",
    "superseded": "ಬದಲಾಯಿಸಲಾಗಿದೆ",
    "not_applicable": "ಅನ್ವಯಿಸುವುದಿಲ್ಲ",
    "accepted": "ಒಪ್ಪಿಕೊಳ್ಳಲಾಗಿದೆ",
}

FINDING_CATEGORY = {
    "ownership": "ಮಾಲೀಕತ್ವ",
    "property_identity": "ಸ್ವತ್ತಿನ ಗುರುತು",
    "encumbrance": "ಋಣಭಾರ",
    "land_use": "ಭೂ ಬಳಕೆ",
    "legal": "ಕಾನೂನು",
    "document_integrity": "ದಾಖಲೆಯ ಸಮಗ್ರತೆ",
    "financial": "ಆರ್ಥಿಕ",
    "process": "ಪ್ರಕ್ರಿಯೆ",
}

REQUIREMENT_CATEGORY = {
    "statutory": "ಕಾನೂನಿನ ಪ್ರಕಾರ ಅಗತ್ಯ",
    "conditional": "ಷರತ್ತುಬದ್ಧ ಅಗತ್ಯ",
    "discrepancy": "ವ್ಯತ್ಯಾಸ ಪರಿಹಾರಕ್ಕೆ ಅಗತ್ಯ",
    "recommended": "ಶಿಫಾರಸು ಮಾಡಲಾಗಿದೆ",
    "external_check": "ಹೊರಗಿನ ಪರಿಶೀಲನೆ",
    "professional": "ವೃತ್ತಿಪರ ಪರಿಶೀಲನೆ",
}

REQUIREMENT_STATUS = {
    "available_analysed": "ಲಭ್ಯವಿದೆ - ವಿಶ್ಲೇಷಿಸಲಾಗಿದೆ",
    "pending_collection": "ಸಂಗ್ರಹಿಸಬೇಕಿದೆ",
    "incomplete": "ಅಪೂರ್ಣ",
    "pending_verification": "ಪರಿಶೀಲನೆ ಬಾಕಿ",
    "not_performed": "ನಡೆಸಲಾಗಿಲ್ಲ",
    "satisfied": "ಪೂರೈಸಲಾಗಿದೆ",
    "waived": "ಕೈಬಿಡಲಾಗಿದೆ",
}

PRIORITY = {
    "mandatory": "ಕಡ್ಡಾಯ",
    "conditional": "ಷರತ್ತುಬದ್ಧ",
    "recommended": "ಶಿಫಾರಸು",
    "professional_advice": "ವೃತ್ತಿಪರ ಸಲಹೆ",
}

DOC_STATUS = {
    "discovered": "ಪತ್ತೆಯಾಗಿದೆ",
    "queued": "ಸರತಿಯಲ್ಲಿದೆ",
    "processing": "ಪ್ರಕ್ರಿಯೆಯಲ್ಲಿದೆ",
    "extracted": "ಪಠ್ಯ ಹೊರತೆಗೆಯಲಾಗಿದೆ",
    "analysed": "ವಿಶ್ಲೇಷಿಸಲಾಗಿದೆ",
    "needs_manual_review": "ಕೈಯಾರೆ ಪರಿಶೀಲನೆ ಅಗತ್ಯ",
    "failed": "ವಿಫಲವಾಗಿದೆ",
    "quarantined": "ಪ್ರತ್ಯೇಕಿಸಲಾಗಿದೆ",
    "removed": "ತೆಗೆದುಹಾಕಲಾಗಿದೆ",
    "superseded": "ಬದಲಾಯಿಸಲಾಗಿದೆ",
}

CASE_STATUS = {
    "created": "ಸೃಷ್ಟಿಸಲಾಗಿದೆ",
    "awaiting_documents": "ದಾಖಲೆಗಳಿಗಾಗಿ ಕಾಯಲಾಗುತ್ತಿದೆ",
    "analysing": "ವಿಶ್ಲೇಷಣೆಯಲ್ಲಿದೆ",
    "review_ready": "ಪರಿಶೀಲನೆಗೆ ಸಿದ್ಧ",
    "on_hold": "ತಡೆಹಿಡಿಯಲಾಗಿದೆ",
    "closed": "ಮುಕ್ತಾಯಗೊಂಡಿದೆ",
}

ASSESSMENT_STATUS = {
    "assessment_incomplete": "ಮೌಲ್ಯಮಾಪನ ಅಪೂರ್ಣ",
    "high_risk_findings_identified": "ಗಂಭೀರ ಅಪಾಯದ ಅಂಶಗಳು ಕಂಡುಬಂದಿವೆ",
    "further_verification_required": "ಹೆಚ್ಚಿನ ಪರಿಶೀಲನೆ ಅಗತ್ಯ",
    "no_material_issues_identified_in_reviewed_evidence":
        "ಪರಿಶೀಲಿಸಿದ ದಾಖಲೆಗಳಲ್ಲಿ ಮಹತ್ವದ ಸಮಸ್ಯೆ ಕಂಡುಬಂದಿಲ್ಲ",
    "ready_for_independent_professional_review": "ಸ್ವತಂತ್ರ ವೃತ್ತಿಪರ ಪರಿಶೀಲನೆಗೆ ಸಿದ್ಧ",
}

VERIFICATION_STATUS = {
    "documented": "ದಾಖಲೆಯಲ್ಲಿ ನಮೂದಾಗಿದೆ",
    "corroborated": "ಹಲವು ದಾಖಲೆಗಳಿಂದ ದೃಢಪಟ್ಟಿದೆ",
    "conflicting": "ಪರಸ್ಪರ ವಿರುದ್ಧವಾಗಿದೆ",
    "unverified": "ಪರಿಶೀಲಿಸಲಾಗಿಲ್ಲ",
    "not_performed": "ನಡೆಸಲಾಗಿಲ್ಲ",
    "user_confirmed": "ಬಳಕೆದಾರರಿಂದ ದೃಢಪಟ್ಟಿದೆ",
}

PROPERTY_TYPE = {
    "agricultural_land": "ಕೃಷಿ ಭೂಮಿ",
    "residential_plot": "ವಸತಿ ನಿವೇಶನ",
    "independent_house": "ಸ್ವತಂತ್ರ ಮನೆ",
    "apartment": "ಅಪಾರ್ಟ್‌ಮೆಂಟ್",
    "commercial": "ವಾಣಿಜ್ಯ ಸ್ವತ್ತು",
    "industrial": "ಕೈಗಾರಿಕಾ ಸ್ವತ್ತು",
    "undeveloped_land": "ಅಭಿವೃದ್ಧಿಯಾಗದ ಭೂಮಿ",
    "under_construction": "ನಿರ್ಮಾಣ ಹಂತದಲ್ಲಿದೆ",
}

TRANSACTION_TYPE = {
    "purchase": "ಖರೀದಿ",
    "sale": "ಮಾರಾಟ",
    "mortgage": "ಅಡಮಾನ",
    "gift": "ದಾನ",
    "inheritance": "ಉತ್ತರಾಧಿಕಾರ",
    "lease": "ಗುತ್ತಿಗೆ",
    "partition": "ವಿಭಾಗ",
    "review_only": "ಪರಿಶೀಲನೆ ಮಾತ್ರ",
}

PROVENANCE = {
    "explicit": "ದಾಖಲೆಯಲ್ಲಿ ಸ್ಪಷ್ಟವಾಗಿದೆ",
    "inferred": "ಹಲವು ದಾಖಲೆಗಳಿಂದ ಊಹಿಸಲಾಗಿದೆ",
    "external": "ಹೊರಗಿನ ಮೂಲದಿಂದ",
    "unverified": "ಪರಿಶೀಲಿಸಲಾಗಿಲ್ಲ",
    "missing": "ಲಭ್ಯವಿಲ್ಲ",
    "user_corrected": "ಬಳಕೆದಾರರಿಂದ ತಿದ್ದುಪಡಿ",
}

#: Field titles used by the report and the document viewer.
FIELD_TITLES = {
    "party_seller": "ಮಾರಾಟಗಾರ / ವರ್ಗಾಯಿಸಿದವರು",
    "party_buyer": "ಖರೀದಿದಾರ / ವರ್ಗಾವಣೆ ಪಡೆದವರು",
    "party_executant": "ಬರೆದುಕೊಟ್ಟವರು",
    "owner_name": "ದಾಖಲೆಯಲ್ಲಿನ ಮಾಲೀಕರು",
    "previous_owner": "ಹಿಂದಿನ ಮಾಲೀಕರು",
    "party_mortgagor": "ಅಡಮಾನದಾರ",
    "party_mortgagee": "ಅಡಮಾನ ಸ್ವೀಕರಿಸಿದವರು / ಸಾಲದಾತ",
    "registration_number": "ನೋಂದಣಿ ಸಂಖ್ಯೆ",
    "registration_date": "ನೋಂದಣಿ ದಿನಾಂಕ",
    "registration_office": "ನೋಂದಣಿ ಕಚೇರಿ",
    "book_volume": "ಪುಸ್ತಕ / ಸಂಪುಟ / ಪುಟ",
    "document_number": "ದಸ್ತಾವೇಜು ಸಂಖ್ಯೆ",
    "execution_date": "ಬರೆದುಕೊಟ್ಟ ದಿನಾಂಕ",
    "document_date": "ದಾಖಲೆಯ ದಿನಾಂಕ",
    "issue_date": "ನೀಡಿದ ದಿನಾಂಕ",
    "survey_number": "ಸರ್ವೇ ಸಂಖ್ಯೆ",
    "subdivision_number": "ಹಿಸ್ಸಾ ಸಂಖ್ಯೆ",
    "khata_number": "ಖಾತಾ ಸಂಖ್ಯೆ",
    "plot_number": "ನಿವೇಶನ ಸಂಖ್ಯೆ",
    "flat_number": "ಫ್ಲಾಟ್ ಸಂಖ್ಯೆ",
    "assessment_number": "ನಿರ್ಧಾರಣ ಸಂಖ್ಯೆ",
    "village": "ಗ್ರಾಮ",
    "hobli": "ಹೋಬಳಿ",
    "taluk": "ತಾಲ್ಲೂಕು",
    "district": "ಜಿಲ್ಲೆ",
    "state": "ರಾಜ್ಯ",
    "property_area": "ವಿಸ್ತೀರ್ಣ",
    "built_up_area": "ಕಟ್ಟಡ ವಿಸ್ತೀರ್ಣ",
    "uds_extent": "ಅವಿಭಜಿತ ಪಾಲು (ಯುಡಿಎಸ್)",
    "kharab_area": "ಖರಾಬು ವಿಸ್ತೀರ್ಣ",
    "boundary_north": "ಚಕ್ಕುಬಂದಿ - ಉತ್ತರ",
    "boundary_south": "ಚಕ್ಕುಬಂದಿ - ದಕ್ಷಿಣ",
    "boundary_east": "ಚಕ್ಕುಬಂದಿ - ಪೂರ್ವ",
    "boundary_west": "ಚಕ್ಕುಬಂದಿ - ಪಶ್ಚಿಮ",
    "consideration_amount": "ಕ್ರಯದ ಮೊತ್ತ",
    "stamp_duty": "ಮುದ್ರಾಂಕ ಶುಲ್ಕ",
    "registration_fee": "ನೋಂದಣಿ ಶುಲ್ಕ",
    "parent_deed_reference": "ಮೂಲ / ಉಲ್ಲೇಖಿತ ದಾಖಲೆ",
    "parent_registration_number": "ಮೂಲ ದಾಖಲೆಯ ನೋಂದಣಿ ಸಂಖ್ಯೆ",
    "mortgage_lender": "ಸಾಲ ನೀಡಿದ ಸಂಸ್ಥೆ",
    "loan_amount": "ಸಾಲದ ಮೊತ್ತ",
    "loan_account": "ಸಾಲದ ಖಾತೆ",
    "mortgage_status": "ಅಡಮಾನ ಸ್ಥಿತಿ",
    "ec_period_from": "ಋಣಭಾರ ಪ್ರಮಾಣ ಪತ್ರ - ಅವಧಿ ಪ್ರಾರಂಭ",
    "ec_period_to": "ಋಣಭಾರ ಪ್ರಮಾಣ ಪತ್ರ - ಅವಧಿ ಅಂತ್ಯ",
    "ec_entries": "ಋಣಭಾರ ನಮೂದುಗಳು",
    "ec_nil": "ಯಾವುದೇ ನಮೂದು ಇಲ್ಲ ಎಂದು ಘೋಷಿಸಲಾಗಿದೆ",
    "land_classification": "ಜಮೀನಿನ ವರ್ಗ",
    "conversion_order_number": "ಭೂ ಪರಿವರ್ತನೆ ಆದೇಶ ಸಂಖ್ಯೆ",
    "mutation_number": "ವರ್ಗಾವಣೆ (ಎಂ.ಆರ್.) ಸಂಖ್ಯೆ",
    "tax_year": "ತೆರಿಗೆ ಅವಧಿ",
    "tax_amount": "ತೆರಿಗೆ ಮೊತ್ತ",
    "tax_receipt_number": "ರಸೀದಿ ಸಂಖ್ಯೆ",
    "court_case_number": "ನ್ಯಾಯಾಲಯ ಪ್ರಕರಣ ಸಂಖ್ಯೆ",
    "litigation_mention": "ವ್ಯಾಜ್ಯದ ಉಲ್ಲೇಖ",
    "restriction_mention": "ನಿರ್ಬಂಧದ ಉಲ್ಲೇಖ",
    "covenant_denial": "ಋಣಭಾರ / ವ್ಯಾಜ್ಯ ಇಲ್ಲವೆಂಬ ಘೋಷಣೆ",
    "adjoining_reference": "ಪಕ್ಕದ ಸ್ವತ್ತಿನ ಉಲ್ಲೇಖ",
    "approval_number": "ಮಂಜೂರಾತಿ / ಆದೇಶ ಸಂಖ್ಯೆ",
    "approval_authority": "ಮಂಜೂರು ಮಾಡಿದ ಪ್ರಾಧಿಕಾರ",
    "validity_date": "ಮಾನ್ಯತೆ ಅವಧಿ",
    "rera_number": "ರೇರಾ ನೋಂದಣಿ ಸಂಖ್ಯೆ",
    "identity_number": "ಗುರುತಿನ ಸಂಖ್ಯೆ (ಮರೆಮಾಚಲಾಗಿದೆ)",
    "signature_present": "ಸಹಿ / ಮುದ್ರೆ ಇರುವಿಕೆ",
}

#: Labels for the case details the user typed in, shown in the report.
CASE_FIELDS = {
    "property_name": "ಸ್ವತ್ತಿನ ಹೆಸರು",
    "address": "ವಿಳಾಸ",
    "survey_number": "ಸರ್ವೇ ಸಂಖ್ಯೆ",
    "subdivision_number": "ಹಿಸ್ಸಾ ಸಂಖ್ಯೆ",
    "khata_number": "ಖಾತಾ ಸಂಖ್ಯೆ",
    "village": "ಗ್ರಾಮ",
    "taluk": "ತಾಲ್ಲೂಕು",
    "district": "ಜಿಲ್ಲೆ",
    "state": "ರಾಜ್ಯ",
    "property_type": "ಸ್ವತ್ತಿನ ಪ್ರಕಾರ",
    "classification": "ವರ್ಗೀಕರಣ",
    "property_area": "ವಿಸ್ತೀರ್ಣ",
    "claimed_owner": "ಹೇಳಲಾದ ಮಾಲೀಕರು",
    "seller": "ಮಾರಾಟಗಾರರು",
    "buyer": "ಖರೀದಿದಾರರು",
    "transaction_type": "ವ್ಯವಹಾರದ ಪ್ರಕಾರ",
    "assigned_reviewer": "ನಿಯೋಜಿತ ಪರಿಶೀಲಕರು",
}

CASE_FIELDS_EN = {
    "property_name": "Property name", "address": "Address", "survey_number": "Survey number",
    "subdivision_number": "Subdivision", "khata_number": "Khata number", "village": "Village",
    "taluk": "Taluk", "district": "District", "state": "State", "property_type": "Property type",
    "classification": "Classification", "property_area": "Extent", "claimed_owner": "Claimed owner",
    "seller": "Seller", "buyer": "Buyer", "transaction_type": "Transaction type",
    "assigned_reviewer": "Assigned reviewer",
}

#: One catalogue per vocabulary, so a caller can translate any enum value.
VOCABULARIES: Dict[str, Dict[str, str]] = {
    "severity": SEVERITY,
    "finding_status": FINDING_STATUS,
    "finding_category": FINDING_CATEGORY,
    "requirement_category": REQUIREMENT_CATEGORY,
    "requirement_status": REQUIREMENT_STATUS,
    "priority": PRIORITY,
    "doc_status": DOC_STATUS,
    "case_status": CASE_STATUS,
    "assessment_status": ASSESSMENT_STATUS,
    "verification_status": VERIFICATION_STATUS,
    "property_type": PROPERTY_TYPE,
    "transaction_type": TRANSACTION_TYPE,
    "provenance": PROVENANCE,
    "field_title": FIELD_TITLES,
    "case_field": CASE_FIELDS,
}


def term(vocabulary: str, value: Optional[str], lang: str = DEFAULT_LANGUAGE,
         default: Optional[str] = None) -> str:
    """Translate one controlled value, falling back to a readable English form."""
    if value is None:
        return default or "—"
    if normalise_language(lang) == "kn":
        translated = VOCABULARIES.get(vocabulary, {}).get(value)
        if translated:
            return translated
    if vocabulary == "case_field":
        return CASE_FIELDS_EN.get(value, str(value).replace("_", " ").capitalize())
    if default is not None:
        return default
    return str(value).replace("_", " ").strip().capitalize()


def vocabulary_payload() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Every vocabulary in both languages, for the interface to use offline."""
    out: Dict[str, Dict[str, Dict[str, str]]] = {}
    for name, catalogue in VOCABULARIES.items():
        out[name] = {
            key: {"en": key.replace("_", " ").strip().capitalize(), "kn": value}
            for key, value in catalogue.items()
        }
    return out


def coverage() -> Dict[str, Any]:
    """How much of the Kannada catalogue is populated, reported honestly."""
    from .services.knowledge import doc_types, jurisdiction

    types = doc_types()
    typed = sum(1 for meta in types.values() if meta.get("label_kn") != meta.get("label"))
    jur = jurisdiction("KA")
    reqs = jur.get("requirements", [])
    translated_reqs = sum(1 for r in reqs if r.get("name_kn"))
    return {
        "languages": list(LANGUAGES),
        "vocabularies": {name: len(cat) for name, cat in VOCABULARIES.items()},
        "document_type_labels": {"total": len(types), "translated": typed},
        "requirement_templates": {"total": len(reqs), "translated": translated_reqs},
        "note": (
            "Findings describe specific evidence and are generated in English. Where a "
            "Kannada rendering is not available the English text is shown and marked, "
            "rather than being left out."
        ),
    }
