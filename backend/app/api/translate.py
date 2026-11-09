# -*- coding: utf-8 -*-
"""Language selection and response localisation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Header, Query

from ..i18n import normalise_language, term
from ..services.knowledge import doc_label


def get_lang(
    lang: Optional[str] = Query(default=None, description="Response language: 'en' or 'kn'"),
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
) -> str:
    """An explicit ?lang= wins; otherwise the browser's preference is honoured."""
    return normalise_language(lang or (accept_language or "").split(",")[0])


def _kn(row: Any) -> Dict[str, Any]:
    return ((row.translations or {}).get("kn") or {}) if getattr(row, "translations", None) else {}


def localise_finding(model: Any, row: Any, lang: str) -> Any:
    """Apply the Kannada rendering, keeping the English description where there is none."""
    model.severity_label = term("severity", row.severity, lang)
    model.category_label = term("finding_category", row.category, lang)
    model.status_label = term("finding_status", row.status, lang)
    model.verification_status_label = term("verification_status", row.verification_status, lang)
    if lang != "kn":
        return model
    kn = _kn(row)
    if not kn:
        model.untranslated = True
        return model
    model.title = kn.get("title") or model.title
    model.consequence = kn.get("consequence") or model.consequence
    model.recommended_action = kn.get("recommended_action") or model.recommended_action
    model.description_untranslated = bool(kn.get("description_untranslated"))
    model.description_note = kn.get("description_note")
    return model


def localise_requirement(model: Any, row: Any, lang: str) -> Any:
    model.category_label = term("requirement_category", row.category, lang)
    model.priority_label = term("priority", row.priority, lang)
    model.status_label = term("requirement_status", row.status, lang)
    if lang != "kn":
        return model
    kn = _kn(row)
    if not kn:
        model.untranslated = True
        return model
    for field in ("name", "reason", "next_action", "risk_if_absent", "closure_criteria",
                  "issuing_authority", "resolves_issue"):
        value = kn.get(field)
        if value:
            setattr(model, field, value)
    return model


def localise_document(model: Any, row: Any, lang: str) -> Any:
    model.doc_type_label = doc_label(row.doc_type, lang)
    model.status_label = term("doc_status", row.status, lang)
    return model


def localise_case(model: Any, row: Any, lang: str) -> Any:
    model.status_label = term("case_status", row.status, lang)
    model.overall_risk_label = term("severity", row.overall_risk, lang)
    model.property_type_label = term("property_type", row.property_type, lang)
    model.transaction_type_label = term("transaction_type", row.transaction_type, lang)
    model.assessment_status_label = (
        term("assessment_status", row.assessment_status, lang) if row.assessment_status else None)
    return model
