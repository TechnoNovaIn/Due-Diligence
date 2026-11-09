"""Section 11 - questions for the seller, generated from actual gaps.

A question is only produced when the evidence does not already answer it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..enums import FindingStatus, OPEN_REQUIREMENT_STATUSES, RequirementCategory, Severity
from . import normalize as nz
from .context import CaseContext

_DETECTOR_QUESTIONS = {
    "missing_parent_deed": "Can you provide a certified copy of the {subject}, which the current title document refers to?",
    "ownership_chain_break": "How did the property pass from {a} to {b}? Which registered document records that transfer?",
    "chain_coverage": "Can you provide the deeds preceding {date}, so the title can be traced for the full review period?",
    "mortgage_unreleased": "Is there a registered release of mortgage, or a loan closure / no-dues certificate, for the charge recorded against this property?",
    "ec_short_period": "Can you obtain an Encumbrance Certificate covering the full review period, rather than only {from_date} onwards?",
    "ec_gap": "Can you obtain an Encumbrance Certificate covering {from_date} to {to_date}?",
    "ec_stale": "Can you obtain a current Encumbrance Certificate, as the latest one on record ends {to_date}?",
    "area_mismatch": "Why does the extent stated in the title document differ from the extent in the revenue record?",
    "identity_conflict": "Which {label} is correct for this property, and what record reconciles the different values in the documents?",
    "identity_subdivision": "Can you provide the phodi / subdivision record showing how the parent survey number was divided?",
    "record_holder_mismatch": "Why does the revenue or municipal record stand in a different name from the title documents? Has the mutation been applied for?",
    "conversion_missing": "Has a conversion order been obtained permitting non-agricultural use of this land? If so, can you provide it?",
    "conversion_partial": "Which portion of the land is covered by the conversion order, and what is the position for the balance extent?",
    "building_approval_missing": "Can you provide the sanctioned building plan and the building licence for the construction on this property?",
    "oc_missing": "Has an Occupancy Certificate been issued for this building? If not, what is the current position?",
    "litigation_reference": "Are there any pending disputes, claims, notices or court proceedings affecting this property? The documents refer to {tag}.",
    "transfer_restriction": "What is the source of the restriction on transfer referred to in the documents, and has the required permission been obtained?",
    "grant_land": "Was this land originally granted land? If so, can you provide the grant order and confirmation that no PTCL proceedings affect it?",
    "poa_present": "Is the power of attorney registered, does it authorise the sale of this property, and does the principal confirm it remains in force?",
    "seller_not_titleholder": "Under what authority is {seller} proposing to transfer the property, given that the title documents name {holder}?",
    "claimed_owner_mismatch": "Which document records the acquisition of the property by {claimed}?",
    "attachment_reference": "Is the attachment or prohibitory order referred to in the documents still in force?",
    "date_inconsistency": "Can you confirm the correct execution and registration dates for {doc}?",
    "late_registration": "Why was {doc} registered {delay} after it was executed?",
    "duplicate_registration": "Which of the documents sharing registration number {reg} is the operative one?",
    "integrity": "Can you provide a complete and legible copy of {doc}?",
    "document_not_processed": "Can you provide a readable copy of {doc}, preferably as a PDF?",
    "unclassified_document": "What is {doc}, and how does it relate to this property?",
    "approval_expired": "Has the approval that expired on {date} been renewed?",
    "ec_conflicts_mortgage": "The Encumbrance Certificate reports no entries but other documents refer to a charge - can you explain the position, and confirm with the lender?",
    "ec_missing_registered_deed": "Why does the registered deed not appear in the Encumbrance Certificate covering its date? Were the same property identifiers used?",
}


def generate_questions(ctx: CaseContext, findings: Sequence[Any], requirements: Sequence[Any]) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    seen = set()

    for f in findings:
        if f.status != FindingStatus.OPEN.value:
            continue
        template = _DETECTOR_QUESTIONS.get(f.detector)
        if not template:
            continue
        text = _fill(template, f, ctx)
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        questions.append({
            "question": text,
            "reason": f.title,
            "severity": f.severity,
            "risk_ref": f.risk_ref,
            "source": "finding",
        })

    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    for r in requirements:
        if r.status not in open_statuses:
            continue
        if r.category not in (RequirementCategory.STATUTORY.value, RequirementCategory.CONDITIONAL.value):
            continue
        if r.related_finding_id:
            continue
        text = "Can you provide {}?".format(_lower_first(r.name))
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        questions.append({
            "question": text,
            "reason": r.reason or r.name,
            "severity": None,
            "requirement_key": r.key,
            "source": "requirement",
        })

    order = {Severity.CRITICAL.value: 0, Severity.HIGH.value: 1, Severity.MEDIUM.value: 2,
             Severity.LOW.value: 3, Severity.INFORMATIONAL.value: 4, None: 5}
    questions.sort(key=lambda q: order.get(q.get("severity"), 5))
    return questions


def _lower_first(text: str) -> str:
    return text[0].lower() + text[1:] if text else text


def _fill(template: str, finding: Any, ctx: CaseContext) -> str:
    values = {
        "subject": (finding.required_documents or [finding.title])[0],
        "doc": _first_evidence_name(finding) or "the document",
        "label": finding.title.split(":")[0].lower(),
        "tag": finding.title.replace("Reference to ", "").split(" in the")[0],
        "seller": nz.normalize_name(ctx.case.seller_name) or "the seller",
        "holder": _extract_between(finding.description, "vesting in ", "."),
        "claimed": nz.normalize_name(ctx.case.claimed_owner) or "the claimed owner",
        "a": _extract_between(finding.title, "between ", " and "),
        "b": finding.title.split(" and ")[-1] if " and " in finding.title else "the next owner",
        "date": _first_date(finding.description),
        "from_date": _first_date(finding.description),
        "to_date": _last_date(finding.description),
        "reg": _extract_between(finding.description, "Registration number ", " appears"),
        "delay": "some years later",
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        return finding.recommended_action or finding.title


def _first_evidence_name(finding: Any) -> str:
    evidence = getattr(finding, "evidence", None) or []
    for ev in evidence:
        name = getattr(ev, "document_name", None)
        if name:
            return name
    title = getattr(finding, "title", "")
    return title.split(":")[0] if ":" in title else ""


def _extract_between(text: str, start: str, end: str) -> str:
    if not text or start not in text:
        return "the other party"
    rest = text.split(start, 1)[1]
    return rest.split(end, 1)[0].strip() if end in rest else rest.strip()[:60]


def _first_date(text: str) -> str:
    import re

    m = re.search(r"\d{1,2} [A-Z][a-z]{2} \d{4}", text or "")
    return m.group(0) if m else "the relevant date"


def _last_date(text: str) -> str:
    import re

    matches = re.findall(r"\d{1,2} [A-Z][a-z]{2} \d{4}", text or "")
    return matches[-1] if matches else "the current date"
