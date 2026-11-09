"""Case-level analysis orchestration.

Runs the cross-document engine, reconciles the results against what is already
stored, and never deletes history: a finding that no longer reproduces is
marked resolved with an explanation, and a requirement that stops applying is
marked waived rather than removed.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..enums import (
    CaseStatus,
    DocStatus,
    FindingStatus,
    RequirementStatus,
    Severity,
)
from ..models import Case, Finding, FindingEvidence, OwnershipLink, Requirement
from . import audit, risk
from .context import AnalysisResult, CaseContext, ProposedFinding, ProposedRequirement, build_context
from .crossverify import verify
from .findings_i18n import translate_finding
from .llm import get_llm
from .requirements_engine import build_requirements

log = logging.getLogger(__name__)


def analyse_case(session: Session, case: Case, use_llm: bool = True) -> Dict[str, Any]:
    """Re-derive every finding and requirement for a case from the current evidence."""
    ctx = build_context(session, case)
    result = verify(ctx)
    if use_llm:
        _add_model_observations(ctx, result)
    result.requirements = build_requirements(ctx, result)

    changes: Dict[str, Any] = {"new_findings": [], "resolved_findings": [], "reopened_findings": [],
                               "new_requirements": [], "closed_requirements": [], "reopened_requirements": []}

    finding_by_fingerprint = _sync_findings(session, case, result.findings, changes)
    _sync_requirements(session, case, result.requirements, finding_by_fingerprint, changes)
    _sync_ownership(session, case, result)

    session.flush()
    findings = session.scalars(select(Finding).where(Finding.case_id == case.id)).all()
    requirements = session.scalars(select(Requirement).where(Requirement.case_id == case.id)).all()

    documents = [d for d in ctx.docs if d.status != DocStatus.REMOVED.value]
    pending = len(ctx.pending_docs)
    analysed = len(ctx.analysed_docs)

    assessment = risk.assess(findings, requirements, pending, len(documents), analysed)

    case.overall_risk = assessment["overall_risk"]
    case.risk_score = assessment["risk_score"]
    case.assessment_status = assessment["assessment_status"]
    case.last_analysis_at = datetime.utcnow()
    case.document_collection_status = _collection_status(requirements)
    if case.status in (CaseStatus.CREATED.value, CaseStatus.AWAITING_DOCUMENTS.value,
                       CaseStatus.ANALYSING.value):
        case.status = CaseStatus.ANALYSING.value if pending else CaseStatus.REVIEW_READY.value

    audit.record(session, "case_analysed", case_id=case.id,
                 message="Analysis completed: {} finding(s), {} requirement(s).".format(
                     len(findings), len(requirements)),
                 payload={"assessment": assessment, "changes": changes},
                 model_version=get_llm().model)

    return {
        "assessment": assessment,
        "changes": changes,
        "conditions": sorted(result.conditions),
        "comparisons": result.comparisons,
        "notes": result.notes,
        "context": ctx,
        "findings": findings,
        "requirements": requirements,
    }


# ---------------------------------------------------------------------------
def _add_model_observations(ctx: CaseContext, result: AnalysisResult) -> None:
    """Ask a configured model for substantive issues the field comparison missed."""
    llm = get_llm()
    if not llm.available:
        return
    payload = {
        "property_type": ctx.case.property_type,
        "transaction_type": ctx.case.transaction_type,
        "documents": [
            {
                "file": d.filename,
                "type": d.label,
                "date": d.document_date,
                "fields": {k: [v.display for v in vs][:4] for k, vs in d.fields.items()},
            }
            for d in ctx.analysed_docs
        ],
        "deterministic_findings": [f.title for f in result.findings],
    }
    try:
        observations = llm.cross_document_observations(json.dumps(payload, default=str))
    except Exception as exc:  # pragma: no cover - provider failure must not break analysis
        log.warning("Model cross-document pass failed: %s", exc)
        return

    docs_by_name = {d.filename: d for d in ctx.analysed_docs}
    for obs in observations[:12]:
        severity = obs.get("severity", Severity.MEDIUM.value)
        if severity not in {s.value for s in Severity}:
            severity = Severity.MEDIUM.value
        from .context import Evidence

        evidence = []
        for name in (obs.get("documents") or [])[:4]:
            doc = docs_by_name.get(name)
            if doc:
                evidence.append(Evidence.from_doc(doc, "Cited by the model."))
        result.findings.append(ProposedFinding(
            fingerprint=ProposedFinding.make_fingerprint("model_observation", obs.get("title", "")),
            category="legal" if "litig" in (obs.get("title", "") + obs.get("detail", "")).lower() else "process",
            severity=severity,
            title=obs.get("title", "")[:280],
            description="{} (Raised by the language model from the extracted evidence; it has not been "
                        "independently confirmed.)".format(obs.get("detail", "")),
            consequence="",
            recommended_action="Review the cited documents and confirm whether the observation holds.",
            confidence=min(0.6, float(obs.get("confidence") or 0.5)),
            confirmed=False,
            requires_legal_review=severity in (Severity.CRITICAL.value, Severity.HIGH.value),
            evidence=evidence,
            detector="model_observation",
        ))


# ---------------------------------------------------------------------------
def _next_risk_ref(session: Session, case_id: str) -> str:
    count = len(session.scalars(select(Finding.id).where(Finding.case_id == case_id)).all())
    return "R-{:03d}".format(count + 1)


def _sync_findings(session: Session, case: Case, proposed: Sequence[ProposedFinding],
                   changes: Dict[str, Any]) -> Dict[str, Finding]:
    existing = {f.fingerprint: f for f in session.scalars(
        select(Finding).where(Finding.case_id == case.id)).all()}
    proposed_by_fp = {p.fingerprint: p for p in proposed}
    out: Dict[str, Finding] = {}

    for fp, prop in proposed_by_fp.items():
        found = existing.get(fp)
        if found is None:
            found = Finding(
                case_id=case.id,
                risk_ref=_next_risk_ref(session, case.id),
                fingerprint=fp,
                category=prop.category,
                severity=prop.severity,
                title=prop.title,
                description=prop.description,
                consequence=prop.consequence,
                recommended_action=prop.recommended_action,
                required_documents=list(prop.required_documents),
                confidence=prop.confidence,
                confirmed=prop.confirmed,
                requires_legal_review=prop.requires_legal_review,
                verification_status=prop.verification_status,
                detector=prop.detector,
                status=FindingStatus.OPEN.value,
                translations=translate_finding(prop),
            )
            found.score = risk.score_finding(prop.severity, prop.confidence, prop.confirmed,
                                             FindingStatus.OPEN.value)
            session.add(found)
            session.flush()
            changes["new_findings"].append({"risk_ref": found.risk_ref, "title": found.title,
                                            "severity": found.severity})
            audit.record(session, "finding_raised", case_id=case.id,
                         message="{} {}".format(found.risk_ref, found.title),
                         payload={"severity": found.severity, "detector": found.detector})
        else:
            if found.status in (FindingStatus.RESOLVED.value, FindingStatus.SUPERSEDED.value,
                                FindingStatus.NOT_APPLICABLE.value):
                found.status = FindingStatus.OPEN.value
                found.resolution_note = None
                found.resolved_at = None
                changes["reopened_findings"].append({"risk_ref": found.risk_ref, "title": found.title})
                audit.record(session, "finding_reopened", case_id=case.id,
                             message="{} re-detected in the current evidence.".format(found.risk_ref))
            found.severity = prop.severity
            found.description = prop.description
            found.consequence = prop.consequence
            found.recommended_action = prop.recommended_action
            found.required_documents = list(prop.required_documents)
            found.confidence = prop.confidence
            found.confirmed = prop.confirmed
            found.verification_status = prop.verification_status
            found.translations = translate_finding(prop)
            found.score = risk.score_finding(prop.severity, prop.confidence, prop.confirmed, found.status)
        found.last_seen_at = datetime.utcnow()

        # Evidence is rebuilt each run so citations follow the current documents.
        for ev in list(found.evidence):
            session.delete(ev)
        session.flush()
        for ev in prop.evidence:
            if not ev or (not ev.document_id and not ev.note and not ev.quote):
                continue
            session.add(FindingEvidence(
                finding_id=found.id, document_id=ev.document_id, document_name=ev.document_name,
                page_no=ev.page_no, quote=(ev.quote or "")[:1500] or None, note=ev.note,
            ))
        out[fp] = found

    for fp, found in existing.items():
        if fp in proposed_by_fp or found.status != FindingStatus.OPEN.value:
            continue
        found.status = FindingStatus.RESOLVED.value
        found.resolved_at = datetime.utcnow()
        found.resolution_note = (
            "This finding no longer reproduces against the current evidence - the documents that "
            "supported it have changed, been replaced, or the gap it described has been filled."
        )
        found.score = 0.0
        changes["resolved_findings"].append({"risk_ref": found.risk_ref, "title": found.title})
        audit.record(session, "finding_resolved", case_id=case.id,
                     message="{} resolved: no longer present in the evidence.".format(found.risk_ref))
    return out


def _sync_requirements(session: Session, case: Case, proposed: Sequence[ProposedRequirement],
                       findings_by_fp: Dict[str, Finding], changes: Dict[str, Any]) -> None:
    existing = {r.key: r for r in session.scalars(
        select(Requirement).where(Requirement.case_id == case.id)).all()}
    proposed_by_key = {p.key: p for p in proposed}

    for key, prop in proposed_by_key.items():
        related_id = None
        if prop.related_finding_fingerprint:
            rel = findings_by_fp.get(prop.related_finding_fingerprint)
            related_id = rel.id if rel else None

        req = existing.get(key)
        if req is None:
            req = Requirement(case_id=case.id, key=key)
            session.add(req)
            changes["new_requirements"].append({"key": key, "name": prop.name, "status": prop.status})
            audit.record(session, "requirement_raised", case_id=case.id, message=prop.name,
                         payload={"category": prop.category, "priority": prop.priority})
        else:
            # A user decision (waived / satisfied by hand) is respected.
            if req.status in (RequirementStatus.WAIVED.value, RequirementStatus.SATISFIED.value) \
                    and not req.auto_generated:
                continue
            if req.status in (RequirementStatus.SATISFIED.value, RequirementStatus.AVAILABLE_ANALYSED.value) \
                    and prop.status in (RequirementStatus.PENDING_COLLECTION.value,
                                        RequirementStatus.INCOMPLETE.value):
                changes["reopened_requirements"].append({"key": key, "name": prop.name})
                audit.record(session, "requirement_reopened", case_id=case.id, message=prop.name)
            elif req.status in (RequirementStatus.PENDING_COLLECTION.value,
                                RequirementStatus.INCOMPLETE.value,
                                RequirementStatus.PENDING_VERIFICATION.value) \
                    and prop.status == RequirementStatus.AVAILABLE_ANALYSED.value:
                changes["closed_requirements"].append({"key": key, "name": prop.name})
                audit.record(session, "requirement_met", case_id=case.id, message=prop.name)

        req.name = prop.name
        req.category = prop.category
        req.priority = prop.priority
        req.status = prop.status
        req.reason = prop.reason
        req.resolves_issue = prop.resolves_issue
        req.related_finding_id = related_id
        req.period_from = prop.period_from
        req.period_to = prop.period_to
        req.relates_to = prop.relates_to
        req.issuing_authority = prop.issuing_authority
        req.next_action = prop.next_action
        req.risk_if_absent = prop.risk_if_absent
        req.closure_criteria = prop.closure_criteria
        req.expected_doc_types = list(prop.expected_doc_types)
        req.satisfied_by_document_id = prop.satisfied_by_document_id
        req.jurisdiction_confirmed = prop.jurisdiction_confirmed
        req.note = prop.note
        req.translations = dict(prop.translations or {})

    for key, req in existing.items():
        if key in proposed_by_key:
            continue
        if req.status in (RequirementStatus.WAIVED.value,):
            continue
        req.status = RequirementStatus.WAIVED.value
        req.note = ("No longer applicable: the condition that raised this requirement is not present in "
                    "the current evidence. Retained for the record.")
        changes["closed_requirements"].append({"key": key, "name": req.name, "reason": "no longer applicable"})
        audit.record(session, "requirement_withdrawn", case_id=case.id, message=req.name)


def _sync_ownership(session: Session, case: Case, result: AnalysisResult) -> None:
    for link in session.scalars(select(OwnershipLink).where(OwnershipLink.case_id == case.id)).all():
        session.delete(link)
    session.flush()
    for step in result.ownership:
        session.add(OwnershipLink(
            case_id=case.id, sequence=step.sequence, from_owner=step.from_owner,
            to_owner=step.to_owner, transfer_type=step.transfer_type,
            transfer_date=step.transfer_date, document_id=step.document_id,
            document_name=step.document_name, registration_ref=step.registration_ref,
            verification_status=step.verification_status, gap_before=step.gap_before,
            notes=step.notes,
        ))


def _collection_status(requirements: Sequence[Requirement]) -> str:
    from ..enums import OPEN_REQUIREMENT_STATUSES, Priority

    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    open_reqs = [r for r in requirements if r.status in open_statuses]
    if not requirements:
        return "not_started"
    mandatory_open = [r for r in open_reqs if r.priority == Priority.MANDATORY.value]
    if mandatory_open:
        return "mandatory_documents_outstanding"
    if open_reqs:
        return "supporting_documents_outstanding"
    return "complete_for_tracked_requirements"
