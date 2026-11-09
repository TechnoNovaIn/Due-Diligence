"""Dynamic missing-document checklist.

Requirements come from three places:

1. the jurisdiction template, filtered by property type, transaction type and
   the conditions the evidence actually established;
2. issues found during analysis - a finding that names a document it needs
   creates a requirement that closes only when that document arrives and the
   finding is resolved;
3. external checks and professional reviews, which are never satisfied by a
   document in the folder and stay open until a person records that they were
   done.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from ..enums import (
    OPEN_REQUIREMENT_STATUSES,
    Priority,
    RequirementCategory,
    RequirementStatus,
    Severity,
)
from . import normalize as nz
from .context import AnalysisResult, CaseContext, ProposedFinding, ProposedRequirement
from .knowledge import doc_label

#: Findings whose presence means the related template requirement is not closed
#: even though a document of the right type exists.
_INCOMPLETE_MARKERS = {
    "encumbrance_certificate_full_period": {"ec_short_period", "ec_gap", "ec_stale", "ec_period_unclear"},
    "parent_deeds_chain": {"missing_parent_deed", "chain_coverage", "ownership_chain_break"},
    "current_title_document": {"claimed_owner_mismatch", "seller_not_titleholder"},
    "mutation_records": {"record_holder_mismatch"},
    "land_conversion_order": {"conversion_partial"},
    "khata_certificate_extract": {"record_holder_mismatch"},
}


def build_requirements(ctx: CaseContext, analysis: AnalysisResult) -> List[ProposedRequirement]:
    reqs: List[ProposedRequirement] = []
    reqs.extend(_from_template(ctx, analysis))
    reqs.extend(_from_findings(ctx, analysis))
    # Deduplicate on key, keeping the first (template requirements win).
    seen: Set[str] = set()
    unique: List[ProposedRequirement] = []
    for r in reqs:
        if r.key in seen:
            continue
        seen.add(r.key)
        unique.append(r)
    return unique


# ---------------------------------------------------------------------------
def _applies(entry: Dict[str, Any], ctx: CaseContext, conditions: Set[str]) -> bool:
    types = entry.get("property_types") or ["all"]
    if "all" not in types and ctx.case.property_type not in types:
        return False
    transactions = entry.get("transaction_types")
    if transactions and ctx.case.transaction_type not in transactions:
        return False
    required_conditions = entry.get("conditions")
    if required_conditions and not any(c in conditions for c in required_conditions):
        return False
    return True


def _format(text: Optional[str], ctx: CaseContext) -> str:
    if not text:
        return ""
    return text.format(
        title_lookback_years=ctx.title_lookback_years,
        ec_lookback_years=ctx.ec_lookback_years,
    )


def _detectors_present(analysis: AnalysisResult) -> Set[str]:
    return {f.detector for f in analysis.findings}


def _titles_by_detector(analysis: AnalysisResult) -> Dict[str, str]:
    """Detector name -> the title of the finding it produced, for display."""
    out: Dict[str, str] = {}
    for finding in analysis.findings:
        out.setdefault(finding.detector, finding.title)
    return out


def _from_template(ctx: CaseContext, analysis: AnalysisResult) -> List[ProposedRequirement]:
    out: List[ProposedRequirement] = []
    detectors = _detectors_present(analysis)
    titles = _titles_by_detector(analysis)
    present_types = ctx.doc_types_present
    jur_confirmed = bool(ctx.jurisdiction.get("jurisdiction_confirmed", False))

    for entry in ctx.jurisdiction.get("requirements", []):
        if not _applies(entry, ctx, analysis.conditions):
            continue
        key = entry["key"]
        satisfied_by = set(entry.get("satisfied_by") or [])
        external_only = bool(entry.get("external_only"))

        matching_docs = [d for d in ctx.analysed_docs if d.doc_type in satisfied_by]
        blocking = _INCOMPLETE_MARKERS.get(key, set()) & detectors

        if external_only:
            status = RequirementStatus.NOT_PERFORMED.value
            note = "This check cannot be satisfied by a document in the folder; it requires an external enquiry."
        elif not matching_docs:
            status = RequirementStatus.PENDING_COLLECTION.value
            note = None
        elif blocking:
            status = RequirementStatus.INCOMPLETE.value
            note = "A document of this type is on record but open findings keep the requirement unmet."
        else:
            status = RequirementStatus.AVAILABLE_ANALYSED.value
            note = "Satisfied by: {}".format(", ".join(d.filename for d in matching_docs[:4]))

        category = entry.get("category", RequirementCategory.RECOMMENDED.value)
        priority = entry.get("priority", Priority.RECOMMENDED.value)

        # Kannada text lives in matching *_kn keys on the same template entry.
        kn = {
            field: _format(entry.get(field + "_kn"), ctx)
            for field in ("name", "reason", "authority", "next_action",
                          "risk_if_absent", "closure_criteria")
            if entry.get(field + "_kn")
        }
        if "authority" in kn:
            kn["issuing_authority"] = kn.pop("authority")
        if blocking:
            from .findings_i18n import CATALOGUE

            kn_titles = [(CATALOGUE.get(d) or {}).get("title") or titles.get(d, d)
                         for d in sorted(blocking)]
            kn["resolves_issue"] = "; ".join(kn_titles)

        out.append(ProposedRequirement(
            key=key,
            name=_format(entry.get("name", key), ctx),
            category=category,
            priority=priority,
            status=status,
            reason=_format(entry.get("reason"), ctx),
            # Name the open findings, not the internal detector keys.
            resolves_issue="; ".join(titles.get(d, d.replace("_", " ")) for d in sorted(blocking)),
            period_from=_period_from(ctx, entry),
            period_to=_period_to(ctx, entry),
            relates_to=_relates_to(ctx),
            issuing_authority=_format(entry.get("authority"), ctx),
            next_action=_format(entry.get("next_action"), ctx),
            risk_if_absent=_format(entry.get("risk_if_absent"), ctx),
            closure_criteria=_format(entry.get("closure_criteria"), ctx),
            expected_doc_types=sorted(satisfied_by),
            satisfied_by_document_id=matching_docs[0].id if matching_docs and status in (
                RequirementStatus.AVAILABLE_ANALYSED.value,) else None,
            jurisdiction_confirmed=jur_confirmed,
            note=note,
            translations={"kn": kn} if kn else {},
        ))
    return out


def _period_from(ctx: CaseContext, entry: Dict[str, Any]) -> Optional[str]:
    if entry.get("requires_ec_coverage"):
        return "{}-01-01".format(nz.today().year - ctx.ec_lookback_years)
    if entry.get("requires_chain_coverage"):
        return "{}-01-01".format(nz.today().year - ctx.title_lookback_years)
    return None


def _period_to(ctx: CaseContext, entry: Dict[str, Any]) -> Optional[str]:
    if entry.get("requires_ec_coverage") or entry.get("requires_chain_coverage"):
        return nz.today().isoformat()
    return None


def _relates_to(ctx: CaseContext) -> str:
    bits = [b for b in (
        ctx.case.property_name,
        "Sy. No. {}".format(ctx.case.survey_number) if ctx.case.survey_number else None,
        ctx.case.village,
    ) if b]
    return ", ".join(bits)


# ---------------------------------------------------------------------------
def _from_findings(ctx: CaseContext, analysis: AnalysisResult) -> List[ProposedRequirement]:
    """Every finding that names a document it needs becomes a tracked requirement."""
    out: List[ProposedRequirement] = []
    for finding in analysis.findings:
        if not finding.required_documents:
            continue
        for doc_description in finding.required_documents:
            key = "issue:{}:{}".format(
                finding.detector,
                hashlib.sha1(doc_description.lower().encode("utf-8")).hexdigest()[:10],
            )
            satisfied, satisfying_doc = _already_supplied(ctx, doc_description)
            status = (RequirementStatus.PENDING_VERIFICATION.value if satisfied
                      else RequirementStatus.PENDING_COLLECTION.value)
            if _is_external(doc_description):
                status = RequirementStatus.NOT_PERFORMED.value
                category = RequirementCategory.EXTERNAL_CHECK.value
            else:
                category = RequirementCategory.DISCREPANCY.value

            priority = {
                Severity.CRITICAL.value: Priority.MANDATORY.value,
                Severity.HIGH.value: Priority.MANDATORY.value,
                Severity.MEDIUM.value: Priority.CONDITIONAL.value,
            }.get(finding.severity, Priority.RECOMMENDED.value)

            out.append(ProposedRequirement(
                key=key,
                name=doc_description,
                category=category,
                priority=priority,
                status=status,
                reason="Required to resolve: {}".format(finding.title),
                resolves_issue=finding.title,
                related_finding_fingerprint=finding.fingerprint,
                relates_to=_relates_to(ctx),
                issuing_authority=_authority_for_description(ctx, doc_description),
                next_action=finding.recommended_action or "Obtain this document and add it to the case folder.",
                risk_if_absent=finding.consequence,
                closure_criteria=("The document is supplied, analysed, and the finding \"{}\" is "
                                  "resolved.".format(finding.title)),
                expected_doc_types=[],
                satisfied_by_document_id=satisfying_doc,
                jurisdiction_confirmed=bool(ctx.jurisdiction.get("jurisdiction_confirmed", False)),
                note=("A document that may match is already on record; confirm it resolves the issue."
                      if satisfied else None),
            ))
    return out


def _is_external(description: str) -> bool:
    lowered = description.lower()
    return any(token in lowered for token in (
        "search", "confirmation from", "status report", "inspection", "surveyor",
        "verification", "opinion", "certified copy of the registration entry",
        "no-objection", "no objection",
    ))


_AUTHORITY_HINTS = [
    (r"encumbrance", "encumbrance_certificate"),
    (r"\brtc\b|pahani|revenue record", "rtc_pahani"),
    (r"mutation", "mutation"),
    (r"survey|tippani|sketch|phodi", "survey_records"),
    (r"conversion", "conversion_order"),
    (r"khata|katha", "khata"),
    (r"tax", "property_tax"),
    (r"plan|licence|license|permit|commencement", "building_approval"),
    (r"occupancy|completion", "occupancy_certificate"),
    (r"rera", "rera"),
    (r"court|litigation|case status|suit|decree", "litigation_search"),
    (r"acquisition", "acquisition"),
    (r"loan|mortgage|bank|no-dues|no dues|release", "bank_release"),
    (r"opinion|advocate", "legal_opinion"),
]


def _authority_for_description(ctx: CaseContext, description: str) -> str:
    lowered = description.lower()
    for pattern, key in _AUTHORITY_HINTS:
        if re.search(pattern, lowered):
            return ctx.authority(key)
    return "The seller, or the authority that issued the original record"


def _already_supplied(ctx: CaseContext, description: str) -> (bool, Optional[str]):
    """Weak match of a requirement description against documents already on record."""
    lowered = description.lower()
    for doc in ctx.analysed_docs:
        label = doc.label.lower()
        if label and label.split(" (")[0] in lowered:
            return True, doc.id
        if nz.name_similarity(doc.label, description) > 85:
            return True, doc.id
    return False, None


# ---------------------------------------------------------------------------
def requirement_summary(requirements: Sequence[Any]) -> Dict[str, Any]:
    """Counts used by the dashboard and the executive summary."""
    open_count = 0
    by_category: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    for r in requirements:
        status = getattr(r, "status", None)
        if status in OPEN_REQUIREMENT_STATUSES or status in {s.value for s in OPEN_REQUIREMENT_STATUSES}:
            open_count += 1
            by_category[r.category] = by_category.get(r.category, 0) + 1
            by_priority[r.priority] = by_priority.get(r.priority, 0) + 1
    return {"open": open_count, "by_category": by_category, "by_priority": by_priority,
            "total": len(requirements)}
