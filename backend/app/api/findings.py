"""Findings and requirements endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..enums import FindingStatus, JobType, RequirementStatus, SEVERITY_ORDER, Severity
from ..models import Case, Finding, Requirement
from ..schemas import FindingOut, FindingUpdate, RequirementOut, RequirementUpdate
from ..services import audit as audit_service
from ..services import risk
from ..services.jobs import enqueue
from .deps import Principal, current_principal, get_case, require_write
from .translate import get_lang, localise_finding, localise_requirement

router = APIRouter(tags=["findings"])


@router.get("/cases/{case_id}/findings", response_model=List[FindingOut])
def list_findings(case: Case = Depends(get_case), db: Session = Depends(get_db),
                  principal: Principal = Depends(current_principal),
                  severity: Optional[str] = None, status: Optional[str] = None,
                  category: Optional[str] = None,
                  lang: str = Depends(get_lang)) -> List[FindingOut]:
    stmt = select(Finding).where(Finding.case_id == case.id)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if status:
        stmt = stmt.where(Finding.status == status)
    if category:
        stmt = stmt.where(Finding.category == category)
    findings = db.scalars(stmt).all()
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(Severity(f.severity), 9), f.risk_ref))
    return [localise_finding(FindingOut.model_validate(f), f, lang) for f in findings]


@router.patch("/findings/{finding_id}", response_model=FindingOut)
def update_finding(finding_id: str, payload: FindingUpdate, db: Session = Depends(get_db),
                   principal: Principal = Depends(require_write),
                   lang: str = Depends(get_lang)) -> FindingOut:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    allowed = {s.value for s in FindingStatus}
    if payload.status and payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")

    previous = finding.status
    if payload.status:
        finding.status = payload.status
        finding.resolved_at = datetime.utcnow() if payload.status != FindingStatus.OPEN.value else None
    if payload.resolution_note is not None:
        finding.resolution_note = payload.resolution_note
    if payload.verification_status:
        finding.verification_status = payload.verification_status
    finding.score = risk.score_finding(finding.severity, finding.confidence, finding.confirmed,
                                       finding.status)
    audit_service.record(db, "finding_updated", case_id=finding.case_id, actor=principal.username,
                         message="{} {} -> {}".format(finding.risk_ref, previous, finding.status),
                         payload={"note": payload.resolution_note})
    enqueue(db, JobType.GENERATE_REPORT.value, case_id=finding.case_id,
            dedupe_key="report:{}".format(finding.case_id), delay_seconds=0.5, priority=300)
    db.commit()
    db.refresh(finding)
    return localise_finding(FindingOut.model_validate(finding), finding, lang)


@router.get("/cases/{case_id}/requirements", response_model=List[RequirementOut])
def list_requirements(case: Case = Depends(get_case), db: Session = Depends(get_db),
                      principal: Principal = Depends(current_principal),
                      category: Optional[str] = None, status: Optional[str] = None,
                      lang: str = Depends(get_lang)) -> List[RequirementOut]:
    stmt = select(Requirement).where(Requirement.case_id == case.id)
    if category:
        stmt = stmt.where(Requirement.category == category)
    if status:
        stmt = stmt.where(Requirement.status == status)
    order = {"mandatory": 0, "conditional": 1, "recommended": 2, "professional_advice": 3}
    reqs = db.scalars(stmt).all()
    reqs.sort(key=lambda r: (order.get(r.priority, 9), r.name))
    return [localise_requirement(RequirementOut.model_validate(r), r, lang) for r in reqs]


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def update_requirement(requirement_id: str, payload: RequirementUpdate,
                       db: Session = Depends(get_db),
                       principal: Principal = Depends(require_write),
                       lang: str = Depends(get_lang)) -> RequirementOut:
    req = db.get(Requirement, requirement_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if payload.status not in {s.value for s in RequirementStatus}:
        raise HTTPException(status_code=400, detail="Invalid status")
    previous = req.status
    req.status = payload.status
    req.auto_generated = False  # a human decision is not overwritten by the engine
    if payload.note:
        req.note = "{} (recorded by {})".format(payload.note, principal.username)
    audit_service.record(db, "requirement_updated", case_id=req.case_id, actor=principal.username,
                         message="{}: {} -> {}".format(req.name, previous, req.status),
                         payload={"note": payload.note})
    enqueue(db, JobType.GENERATE_REPORT.value, case_id=req.case_id,
            dedupe_key="report:{}".format(req.case_id), delay_seconds=0.5, priority=300)
    db.commit()
    db.refresh(req)
    return localise_requirement(RequirementOut.model_validate(req), req, lang)
