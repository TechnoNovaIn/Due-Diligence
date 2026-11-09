"""Due diligence report assembly, versioning and rendering."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import RULESET_VERSION, __version__
from ..config import get_settings
from ..enums import (
    ASSESSMENT_LABELS,
    OPEN_REQUIREMENT_STATUSES,
    SEVERITY_ORDER,
    AssessmentStatus,
    DocStatus,
    FindingStatus,
    Priority,
    RequirementCategory,
    Severity,
)
from ..models import Case, Document, Finding, OwnershipLink, Report, Requirement
from . import audit, risk
from . import normalize as nz
from .context import CaseContext, build_context
from .extraction.ocr import ocr_status
from .fields import FIELD_TITLES
from .knowledge import doc_label
from .llm import provider_status
from .questions import generate_questions

log = logging.getLogger(__name__)

DISCLAIMER = (
    "This report is an evidence-based preliminary assessment produced by an automated system from the "
    "documents supplied in the case folder. It is not a title search, not an official verification, and "
    "not a legal opinion. No statement in it should be read as confirming that title is clear or "
    "marketable, that a document is genuine, that the property is free from encumbrances or litigation, "
    "or that the property is suitable for purchase. Material conclusions require an independent title "
    "investigation and the written opinion of a qualified property lawyer."
)


def generate_report(session: Session, case: Case, actor: str = "system") -> Report:
    """Build, persist and render the next report version for a case."""
    settings = get_settings()
    ctx = build_context(session, case)

    findings = session.scalars(select(Finding).where(Finding.case_id == case.id)).all()
    requirements = session.scalars(select(Requirement).where(Requirement.case_id == case.id)).all()
    ownership = session.scalars(
        select(OwnershipLink).where(OwnershipLink.case_id == case.id).order_by(OwnershipLink.sequence)
    ).all()

    documents = [d for d in ctx.docs if d.status != DocStatus.REMOVED.value]
    pending = len(ctx.pending_docs)
    analysed = len(ctx.analysed_docs)
    assessment = risk.assess(findings, requirements, pending, len(documents), analysed)

    previous = session.scalars(
        select(Report).where(Report.case_id == case.id).order_by(Report.version.desc())
    ).first()
    version = (previous.version + 1) if previous else 1

    payload = _build_payload(ctx, case, documents, findings, requirements, ownership,
                             assessment, version)
    change_summary = _diff(previous.payload if previous else None, payload)
    payload["change_summary"] = change_summary

    report = Report(
        case_id=case.id,
        version=version,
        assessment_status=assessment["assessment_status"],
        overall_risk=assessment["overall_risk"],
        risk_score=assessment["risk_score"],
        documents_received=len(documents),
        documents_analysed=analysed,
        open_requirements=assessment["open_requirements"],
        risk_counts=assessment["open_counts"],
        payload=payload,
        change_summary=change_summary,
        model_info=provider_status(),
    )
    session.add(report)
    session.flush()

    for finding in findings:
        if finding.first_report_version is None:
            finding.first_report_version = version

    paths = _render(case, report, payload, settings)
    report.html_path, report.pdf_path, report.json_path = paths

    audit.record(session, "report_generated", case_id=case.id, actor=actor,
                 message="Report version {} generated ({}).".format(version, assessment["assessment_label"]),
                 payload={"version": version, "changes": change_summary},
                 report_version=version, model_version=provider_status().get("model"))
    return report


# ---------------------------------------------------------------------------
def _build_payload(ctx: CaseContext, case: Case, documents, findings, requirements,
                   ownership, assessment: Dict[str, Any], version: int) -> Dict[str, Any]:
    open_findings = [f for f in findings if f.status == FindingStatus.OPEN.value]
    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    open_reqs = [r for r in requirements if r.status in open_statuses]

    return {
        "meta": {
            "version": version,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "system_version": __version__,
            "ruleset_version": RULESET_VERSION,
            "ai": provider_status(),
            "ocr": ocr_status(),
            "jurisdiction": {
                "code": ctx.jurisdiction.get("code"),
                "name": ctx.jurisdiction.get("name"),
                "confirmed_by_professional": bool(ctx.jurisdiction.get("jurisdiction_confirmed")),
                "title_lookback_years": ctx.title_lookback_years,
                "ec_lookback_years": ctx.ec_lookback_years,
            },
            "disclaimer": DISCLAIMER,
        },
        "section_1_executive_summary": _s1(ctx, case, documents, open_findings, open_reqs, assessment),
        "section_2_property_details": _s2(ctx, case),
        "section_3_document_inventory": _s3(ctx, documents),
        "section_4_document_analysis": _s4(ctx),
        "section_5_ownership_history": _s5(ctx, ownership),
        "section_6_cross_verification": _s6(ctx),
        "section_7_encumbrance": _s7(ctx, findings),
        "section_8_legal_regulatory": _s8(ctx, findings, requirements),
        "section_9_risk_register": _s9(findings),
        "section_10_missing_documents": _s10(requirements),
        "section_11_questions": generate_questions(ctx, findings, requirements),
        "section_12_action_plan": risk.priority_actions(findings, requirements),
        "section_13_final_assessment": _s13(assessment, ctx, open_reqs),
    }


def _unique(values) -> List[str]:
    """Preserve order, drop repeats - several requirements often share one action."""
    seen, out = set(), []
    for value in values:
        key = (value or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _s1(ctx, case, documents, open_findings, open_reqs, assessment) -> Dict[str, Any]:
    major = sorted(open_findings, key=lambda f: (SEVERITY_ORDER.get(Severity(f.severity), 9), -f.score))[:6]
    return {
        "property": {
            "name": case.property_name,
            "reference": case.case_ref,
            "address": case.address,
            "survey_number": case.survey_number,
            "village": case.village,
            "taluk": case.taluk,
            "district": case.district,
            "state": case.state,
            "property_type": case.property_type,
            "transaction_type": case.transaction_type,
        },
        "purpose": case.purpose or "Pre-transaction document review and due diligence support.",
        "documents_received": len(documents),
        "documents_analysed": len([d for d in documents if d.analysed]),
        "documents_pending": len(ctx.pending_docs),
        "documents_failed": len(ctx.failed_docs),
        "open_requirements": len(open_reqs),
        "open_findings_by_severity": assessment["open_counts"],
        "overall_risk": assessment["overall_risk"],
        "assessment_status": assessment["assessment_status"],
        "assessment_label": assessment["assessment_label"],
        "status_explanation": assessment["explanation"],
        "status_explanation_kn": assessment.get("explanation_kn", []),
        "major_findings": [
            {"risk_ref": f.risk_ref, "severity": f.severity, "title": f.title,
             "action": f.recommended_action, "translations": dict(f.translations or {})}
            for f in major
        ],
        "recommended_next_steps": _unique(
            r.next_action or "Obtain: {}".format(r.name)
            for r in sorted(open_reqs, key=lambda r: 0 if r.priority == Priority.MANDATORY.value else 1)
        )[:6],
        "recommended_next_steps_kn": _unique(
            ((r.translations or {}).get("kn") or {}).get("next_action")
            or r.next_action or r.name
            for r in sorted(open_reqs, key=lambda r: 0 if r.priority == Priority.MANDATORY.value else 1)
        )[:6],
        "scope_statement": assessment["scope_statement"],
    }


def _consolidated(ctx: CaseContext, key: str) -> Dict[str, Any]:
    values = ctx.values(key)
    if not values:
        return {"label": FIELD_TITLES.get(key, key), "value": None, "status": "missing",
                "sources": [], "note": "Not stated in any supplied document."}
    # Imported here, not at module scope: crossverify imports this module.
    from .crossverify import _conflicting_within_script

    # Case-folded, so "ARAKERE" and "Arakere" are one value rather than a
    # disagreement between two documents that in fact say the same thing.
    groups: Dict[str, List[Any]] = {}
    display: Dict[str, str] = {}
    for v in values:
        shown = (v.norm or v.raw or "").strip()
        if not shown:
            continue
        key_folded = shown.casefold()
        groups.setdefault(key_folded, []).append(v)
        display.setdefault(key_folded, shown)
    groups = {display[k]: vs for k, vs in groups.items()}
    if not groups:
        return {"label": FIELD_TITLES.get(key, key), "value": None, "status": "missing",
                "sources": [], "note": "Not stated in any supplied document."}
    if len(groups) > 1 and not _conflicting_within_script(groups):
        # The renderings are in different scripts, so the system cannot say they
        # disagree - it does not transliterate - and must not imply that they do.
        vs = [v for group in groups.values() for v in group]
        return {
            "label": FIELD_TITLES.get(key, key),
            "value": " / ".join(sorted(groups.keys())[:4]),
            "status": "documented",
            "sources": sorted({"{} (p.{})".format(v.document_name, v.page_no or "-") for v in vs}),
            "note": ("Given in more than one script. Whether these name the same thing has not "
                     "been established; no transliteration was performed."),
        }
    if len(groups) == 1:
        value, vs = next(iter(groups.items()))
        multi = len({v.document_id for v in vs}) > 1
        return {
            "label": FIELD_TITLES.get(key, key),
            "value": value,
            "status": "corroborated" if multi else "documented",
            "sources": sorted({"{} (p.{})".format(v.document_name, v.page_no or "-") for v in vs}),
            "note": ("Stated consistently in {} documents.".format(len({v.document_id for v in vs}))
                     if multi else "Stated in one document only; not corroborated."),
        }
    return {
        "label": FIELD_TITLES.get(key, key),
        "value": " / ".join(sorted(groups.keys())[:4]),
        "status": "conflicting",
        "sources": sorted({"{} (p.{})".format(v.document_name, v.page_no or "-")
                           for vs in groups.values() for v in vs}),
        "note": "Documents disagree; see the cross-verification section.",
    }


_CONSOLIDATED_KEYS = [
    "survey_number", "subdivision_number", "khata_number", "plot_number", "flat_number",
    "village", "hobli", "taluk", "district", "property_area", "built_up_area", "uds_extent",
    "land_classification", "boundary_north", "boundary_south", "boundary_east", "boundary_west",
    "consideration_amount", "registration_number", "registration_date",
]


def _s2(ctx: CaseContext, case: Case) -> Dict[str, Any]:
    # Keyed by field name so the report can label them in either language.
    declared = {
        "property_name": case.property_name,
        "address": case.address,
        "survey_number": case.survey_number,
        "subdivision_number": case.subdivision_number,
        "khata_number": case.khata_number,
        "village": case.village, "taluk": case.taluk, "district": case.district, "state": case.state,
        "property_type": case.property_type, "classification": case.property_classification,
        "property_area": (nz.format_area(case.land_area_value, case.land_area_unit)
                          if case.land_area_value else None),
        "claimed_owner": case.claimed_owner, "seller": case.seller_name, "buyer": case.buyer_name,
        "transaction_type": case.transaction_type, "assigned_reviewer": case.assigned_reviewer,
    }
    return {
        "declared_by_user": {k: v for k, v in declared.items()},
        "from_documents": [_consolidated(ctx, key) for key in _CONSOLIDATED_KEYS],
        "note": ("Values marked 'documented' appear in a single document and have not been corroborated. "
                 "Values marked 'missing' were not found in any supplied document - that is not evidence "
                 "that the underlying fact does not exist."),
    }


def _s3(ctx: CaseContext, documents) -> List[Dict[str, Any]]:
    rows = []
    for d in documents:
        rows.append({
            "filename": d.filename,
            "path": d.relative_path,
            "document_type": d.label,
            "document_type_key": d.doc_type,
            "classification_confidence": round(d.classification_confidence, 2),
            "document_date": nz.format_date(d.document_date) if d.document_date else "—",
            "status": d.status,
            "pages": d.page_count,
            "pages_analysed": d.pages_analysed,
            "extraction_confidence": round(d.extraction_confidence, 2),
            "ocr_used": d.ocr_used,
            "key_information": _key_info(d),
            "issues": [i.get("detail") for i in d.issues],
            "verification_status": ("Contents read and compared against the other documents"
                                    if d.analysed else "Not analysed"),
        })
    return rows


def _key_info(doc) -> List[Dict[str, str]]:
    keys = ["party_seller", "party_buyer", "owner_name", "survey_number", "khata_number",
            "property_area", "registration_number", "registration_date", "execution_date",
            "consideration_amount", "ec_period_from", "ec_period_to"]
    out = []
    for key in keys:
        v = doc.first(key)
        if v:
            out.append({"label": FIELD_TITLES.get(key, key), "value": v.display,
                        "page": v.page_no, "evidence": v.evidence})
    return out


def _s4(ctx: CaseContext) -> List[Dict[str, Any]]:
    out = []
    for d in ctx.docs:
        analysis = d.analysis or {}
        out.append({
            "filename": d.filename,
            "document_type": d.label,
            "status": d.status,
            "purpose": analysis.get("purpose") or _default_purpose(d),
            "parties": analysis.get("parties") or _parties(d),
            "important_dates": _dates(d),
            "property_identifiers": _identifiers(d),
            "legal_or_financial_effect": analysis.get("legal_effect") or _default_effect(d),
            "referenced_documents": analysis.get("referenced_documents")
            or [v.display for v in d.all("parent_deed_reference")][:5],
            "internal_inconsistencies": analysis.get("internal_inconsistencies") or [],
            "items_requiring_verification": analysis.get("items_requiring_verification")
            or _verification_items(d),
            "issues": [i.get("detail") for i in d.issues],
            "summary": d.summary,
            "analysed_by": analysis.get("analysed_by", "deterministic rules"),
        })
    return out


def _default_purpose(doc) -> str:
    if doc.doc_type == "unknown":
        return "Not determined - the document type could not be established with confidence."
    return "A {} relating to the subject property.".format(doc.label.lower())


def _parties(doc) -> List[Dict[str, str]]:
    roles = [("party_seller", "Seller / transferor"), ("party_buyer", "Purchaser / transferee"),
             ("owner_name", "Owner of record"), ("party_mortgagor", "Mortgagor"),
             ("party_mortgagee", "Mortgagee / lender")]
    out = []
    for key, role in roles:
        for v in doc.all(key)[:3]:
            out.append({"name": v.display, "role": role, "page": v.page_no})
    return out


def _dates(doc) -> List[Dict[str, str]]:
    out = []
    for key in ("execution_date", "registration_date", "ec_period_from", "ec_period_to", "validity_date"):
        v = doc.first(key)
        if v:
            out.append({"label": FIELD_TITLES.get(key, key), "value": nz.format_date(v.display),
                        "page": v.page_no})
    return out


def _identifiers(doc) -> List[Dict[str, str]]:
    out = []
    for key in ("survey_number", "subdivision_number", "khata_number", "plot_number", "flat_number",
                "village", "taluk", "district", "property_area"):
        v = doc.first(key)
        if v:
            out.append({"label": FIELD_TITLES.get(key, key), "value": v.display, "page": v.page_no})
    return out


def _default_effect(doc) -> str:
    from .knowledge import TITLE_TRANSFER_TYPES

    if doc.doc_type in TITLE_TRANSFER_TYPES:
        return ("On its own terms this document purports to transfer an interest in the property. "
                "Whether it was validly executed and registered has not been verified against the "
                "official record.")
    if doc.doc_type == "encumbrance_certificate":
        return ("Certifies what was registered against the property identifiers used, for the period "
                "stated. It does not cover unregistered interests, and an equitable mortgage created by "
                "deposit of title deeds may not appear.")
    if doc.doc_type in ("rtc_pahani", "khata_certificate", "khata_extract", "mutation_extract"):
        return ("A revenue or municipal record. It evidences possession and the assessee of record for "
                "tax purposes; it is not conclusive proof of title.")
    if doc.doc_type in ("property_tax_receipt", "land_revenue_receipt", "tax_payment_receipt"):
        return ("Evidences payment for the period stated. Payment of tax is not evidence of ownership.")
    return "The document's effect has not been independently assessed."


def _verification_items(doc) -> List[str]:
    items = []
    if doc.ocr_used:
        items.append("Values were read by OCR and should be checked against the original.")
    if doc.classification_confidence < 0.7:
        items.append("The document type was not established with high confidence.")
    if doc.all("registration_number"):
        items.append("The registration entry has not been verified against the Sub-Registrar's record.")
    if doc.all("identity_number"):
        items.append("Identity details are present; they are stored masked and have not been verified.")
    return items


def _s5(ctx: CaseContext, ownership) -> Dict[str, Any]:
    steps = [{
        "sequence": o.sequence,
        "from_owner": o.from_owner or "—",
        "to_owner": o.to_owner or "—",
        "transfer_type": o.transfer_type,
        "date": nz.format_date(o.transfer_date) if o.transfer_date else "—",
        "document": o.document_name,
        "registration_ref": o.registration_ref or "—",
        "verification_status": o.verification_status,
        "gap_before": o.gap_before,
        "notes": o.notes,
    } for o in ownership]
    return {
        "timeline": steps,
        "note": ("Each step is *documented* - it reflects what a supplied document states. No step has "
                 "been independently verified against the Sub-Registrar's record, and matching names "
                 "across documents is not proof that the same person is involved."),
        "gaps": [s for s in steps if s["gap_before"]],
        "covered": bool(steps),
    }


def _s6(ctx: CaseContext) -> Dict[str, Any]:
    from .crossverify import verify

    comparisons = verify(ctx).comparisons
    return {
        "comparisons": comparisons,
        "consistent_fields": [c["label"] for c in comparisons if c.get("consistent")],
        "conflicting_fields": [c["label"] for c in comparisons if not c.get("consistent")],
    }


def _s7(ctx: CaseContext, findings) -> Dict[str, Any]:
    ec_docs = ctx.by_type("encumbrance_certificate")
    periods = []
    for d in ec_docs:
        f, t = d.first("ec_period_from"), d.first("ec_period_to")
        periods.append({
            "document": d.filename,
            "from": nz.format_date(f.display) if f else "not stated",
            "to": nz.format_date(t.display) if t else "not stated",
            "declares_nil": d.has_tag("ec_nil", "true"),
            "entries_detected": (d.first("ec_entries").display if d.first("ec_entries") else "—"),
        })
    from ..enums import FindingCategory

    related = [f for f in findings if f.category == FindingCategory.ENCUMBRANCE.value
               and f.status == FindingStatus.OPEN.value]
    return {
        "encumbrance_certificates": periods,
        "mortgage_indications": [
            {"document": v.document_name, "page": v.page_no, "evidence": v.evidence,
             "signal": v.display}
            for v in ctx.values("mortgage_status")
        ],
        "findings": [{"risk_ref": f.risk_ref, "severity": f.severity, "title": f.title,
                      "description": f.description} for f in related],
        "limitations": [
            "An Encumbrance Certificate reflects only what was registered against the identifiers used "
            "to obtain it, for the period it certifies.",
            "An equitable mortgage created by deposit of title deeds is frequently not registered and "
            "may therefore not appear.",
            "Unregistered agreements, family arrangements, tenancies and oral claims do not appear.",
            "No certificate has been verified against the Sub-Registrar's own record.",
        ],
    }


def _s8(ctx: CaseContext, findings, requirements) -> Dict[str, Any]:
    from ..enums import FindingCategory

    legal = [f for f in findings if f.category in (FindingCategory.LEGAL.value,
                                                   FindingCategory.LAND_USE.value)]
    approvals = []
    for key, label in (("approval_number", "Approval / sanction"), ("rera_number", "RERA registration"),
                       ("conversion_order_number", "Conversion order"), ("validity_date", "Validity")):
        for v in ctx.values(key)[:4]:
            approvals.append({"label": label, "value": v.display, "document": v.document_name,
                              "page": v.page_no})
    external = [r for r in requirements if r.category in (RequirementCategory.EXTERNAL_CHECK.value,
                                                          RequirementCategory.PROFESSIONAL.value)]
    return {
        "approvals_on_record": approvals,
        "litigation_references": [
            {"document": v.document_name, "page": v.page_no, "signal": v.display, "evidence": v.evidence}
            for v in ctx.values("litigation_mention")
        ],
        "restriction_references": [
            {"document": v.document_name, "page": v.page_no, "signal": v.display, "evidence": v.evidence}
            for v in ctx.values("restriction_mention")
        ],
        "findings": [{"risk_ref": f.risk_ref, "severity": f.severity, "title": f.title,
                      "status": f.status} for f in legal],
        "checks_completed": [
            "Every supplied document was read and compared against the others.",
            "References to litigation, acquisition, restrictions and charges inside the supplied "
            "documents were identified and listed.",
        ],
        "checks_on_supplied_documents_only": [
            "Document classification and field extraction.",
            "Ownership chain reconstruction.",
            "Encumbrance coverage assessment.",
        ],
        "checks_outstanding": [{"name": r.name, "authority": r.issuing_authority, "status": r.status}
                               for r in external],
    }


def _s9(findings) -> Dict[str, Any]:
    rows = []
    for f in sorted(findings, key=lambda x: (SEVERITY_ORDER.get(Severity(x.severity), 9), x.risk_ref)):
        rows.append({
            "risk_ref": f.risk_ref,
            "category": f.category,
            "description": f.title,
            "detail": f.description,
            "severity": f.severity,
            "evidence": [
                {"document": e.document_name, "page": e.page_no, "quote": e.quote, "note": e.note}
                for e in f.evidence
            ],
            "impact": f.consequence,
            "recommended_action": f.recommended_action,
            "required_documents": f.required_documents or [],
            "status": f.status,
            "translations": dict(f.translations or {}),
            "confidence": round(f.confidence, 2),
            "confirmed": f.confirmed,
            "verification_status": f.verification_status,
            "requires_legal_review": f.requires_legal_review,
            "score": f.score,
            "resolution_note": f.resolution_note,
        })
    critical_high = [r for r in rows if r["severity"] in (Severity.CRITICAL.value, Severity.HIGH.value)
                     and r["status"] == FindingStatus.OPEN.value]
    return {"register": rows, "critical_and_high": critical_high}


_CATEGORY_TITLES = {
    RequirementCategory.STATUTORY.value: "1. Documents potentially required by applicable law",
    RequirementCategory.CONDITIONAL.value: "2. Documents conditionally required for this property",
    RequirementCategory.DISCREPANCY.value: "3. Documents needed to resolve identified discrepancies",
    RequirementCategory.RECOMMENDED.value: "4. Documents recommended for stronger due diligence",
    RequirementCategory.EXTERNAL_CHECK.value: "5. External verification checks not yet performed",
    RequirementCategory.PROFESSIONAL.value: "6. Professional assessments still pending",
}


def _s10(requirements) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {title: [] for title in _CATEGORY_TITLES.values()}
    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    satisfied = []
    for r in requirements:
        row = {
            "key": r.key,
            "name": r.name,
            "priority": r.priority,
            "status": r.status,
            "reason": r.reason,
            "related_finding": r.resolves_issue,
            "period": ("{} to {}".format(nz.format_date(r.period_from), nz.format_date(r.period_to))
                       if r.period_from else None),
            "relates_to": r.relates_to,
            "issuing_authority": r.issuing_authority,
            "next_action": r.next_action,
            "risk_if_absent": r.risk_if_absent,
            "closure_criteria": r.closure_criteria,
            "jurisdiction_confirmed": r.jurisdiction_confirmed,
            "note": r.note,
            "translations": dict(r.translations or {}),
        }
        if r.status in open_statuses:
            groups.setdefault(_CATEGORY_TITLES.get(r.category, r.category), []).append(row)
        else:
            satisfied.append(row)
    return {
        "groups": {k: v for k, v in groups.items() if v},
        "satisfied_or_closed": satisfied,
        "note": ("A requirement listed here is something still to be obtained or done. The absence of a "
                 "document is not itself proof of a defect - it means the point has not been verified."),
        "jurisdiction_caveat": ("Requirement sets are templates for the selected jurisdiction and have "
                                "not been confirmed by local counsel. Statutory applicability must be "
                                "confirmed for this property and this transaction."),
    }


from ..i18n import ASSESSMENT_STATUS as _ASSESSMENT_KN


def _s13(assessment: Dict[str, Any], ctx: CaseContext, open_reqs) -> Dict[str, Any]:
    return {
        "status": assessment["assessment_status"],
        "label": assessment["assessment_label"],
        "overall_risk": assessment["overall_risk"],
        "risk_score": assessment["risk_score"],
        "risk_score_normalised": assessment["risk_score_normalised"],
        "how_determined": assessment["method"],
        "how_determined_kn": assessment.get("method_kn", ""),
        "label_kn": _ASSESSMENT_KN.get(assessment["assessment_status"], ""),
        "reasons": assessment["explanation"],
        "reasons_kn": assessment.get("explanation_kn", []),
        "scope_and_limitations_kn": [
            assessment.get("scope_statement_kn", ""),
            "ಈ ಆವೃತ್ತಿಯ ಸಮಯದಲ್ಲಿ ಪ್ರಕರಣದ ಫೋಲ್ಡರ್‌ನಲ್ಲಿದ್ದ ದಾಖಲೆಗಳನ್ನು ಮಾತ್ರ ಪರಿಗಣಿಸಲಾಗಿದೆ.",
            "ಸ್ಕ್ಯಾನ್ ಪ್ರತಿಗಳನ್ನು ಸಲ್ಲಿಸಿದಂತೆಯೇ ಓದಲಾಗಿದೆ; ಯಾವುದೇ ಪ್ರತಿಯನ್ನು ಮೂಲದೊಂದಿಗೆ ಅಥವಾ "
            "ಅಧಿಕೃತ ನೋಂದಣಿಯೊಂದಿಗೆ ಹೋಲಿಸಲಾಗಿಲ್ಲ.",
            "ದಾಖಲೆ ಹೊಂದಿರುವುದು ಮಾಲೀಕತ್ವಕ್ಕೆ ಪುರಾವೆಯಲ್ಲ, ಮತ್ತು ಕಂದಾಯ ದಾಖಲೆಯು ಹಕ್ಕಿಗೆ "
            "ನಿರ್ಣಾಯಕ ಸಾಕ್ಷ್ಯವಲ್ಲ.",
            "ಈ ಆವೃತ್ತಿಯಲ್ಲಿ {} ಅಗತ್ಯ(ಗಳು) ಬಾಕಿ ಇವೆ.".format(len(open_reqs)),
        ],
        "scope_and_limitations": [
            assessment["scope_statement"],
            "Only the documents present in the case folder at the time of this version were considered.",
            "Scanned copies were read as supplied; no copy was compared with an original or with the "
            "official register.",
            "Possession of a document is not evidence of ownership, and a revenue record is not "
            "conclusive evidence of title.",
            "{} requirement(s) remain outstanding at this version.".format(len(open_reqs)),
        ],
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
def _diff(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> List[Dict[str, str]]:
    """Explain what materially changed between two report versions."""
    if not previous:
        return [{"type": "created", "detail": "First assessment for this case."}]

    changes: List[Dict[str, str]] = []
    prev_reg = {r["risk_ref"]: r for r in previous.get("section_9_risk_register", {}).get("register", [])}
    curr_reg = {r["risk_ref"]: r for r in current.get("section_9_risk_register", {}).get("register", [])}

    for ref, row in curr_reg.items():
        old = prev_reg.get(ref)
        if old is None:
            changes.append({"type": "finding_added",
                            "detail": "{} ({}): {}".format(ref, row["severity"], row["description"])})
        elif old["status"] != row["status"]:
            changes.append({"type": "finding_status",
                            "detail": "{}: {} -> {} ({})".format(ref, old["status"], row["status"],
                                                                 row["description"])})
        elif old["severity"] != row["severity"]:
            changes.append({"type": "finding_severity",
                            "detail": "{}: severity {} -> {}".format(ref, old["severity"], row["severity"])})
    for ref, row in prev_reg.items():
        if ref not in curr_reg:
            changes.append({"type": "finding_removed", "detail": "{}: {}".format(ref, row["description"])})

    prev_docs = {d["filename"] for d in previous.get("section_3_document_inventory", [])}
    curr_docs = {d["filename"] for d in current.get("section_3_document_inventory", [])}
    for name in sorted(curr_docs - prev_docs):
        changes.append({"type": "document_added", "detail": name})
    for name in sorted(prev_docs - curr_docs):
        changes.append({"type": "document_removed", "detail": name})

    prev_status = previous.get("section_13_final_assessment", {}).get("label")
    curr_status = current.get("section_13_final_assessment", {}).get("label")
    if prev_status != curr_status:
        changes.append({"type": "assessment_status",
                        "detail": "Overall assessment: {} -> {}".format(prev_status, curr_status)})

    def _open_keys(payload):
        groups = payload.get("section_10_missing_documents", {}).get("groups", {})
        return {row["key"]: row["name"] for rows in groups.values() for row in rows}

    prev_reqs, curr_reqs = _open_keys(previous), _open_keys(current)
    for key, name in curr_reqs.items():
        if key not in prev_reqs:
            changes.append({"type": "requirement_added", "detail": name})
    for key, name in prev_reqs.items():
        if key not in curr_reqs:
            changes.append({"type": "requirement_closed", "detail": name})

    if not changes:
        changes.append({"type": "no_material_change",
                        "detail": "No material change from the previous version."})
    return changes


# ---------------------------------------------------------------------------
def _render(case: Case, report: Report, payload: Dict[str, Any], settings) -> (str, str, str):
    out_dir = Path(settings.reports_dir) / case.case_ref
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "due-diligence-report-v{:03d}".format(report.version)

    json_path = out_dir / "{}.json".format(stem)
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    from .render_html import render_html

    html_path = out_dir / "{}.html".format(stem)
    html_path.write_text(render_html(case, report, payload, "en"), encoding="utf-8")

    pdf_path = out_dir / "{}.pdf".format(stem)
    try:
        from .render_pdf import render_pdf

        render_pdf(case, report, payload, pdf_path)
    except Exception as exc:  # pragma: no cover - PDF must never lose the data
        log.exception("PDF rendering failed for case %s version %s", case.case_ref, report.version)
        pdf_path = None
        report.payload.setdefault("meta", {})["pdf_error"] = str(exc)[:300]

    return (str(html_path), str(pdf_path) if pdf_path else None, str(json_path))
