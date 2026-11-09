"""Case management endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..enums import OPEN_REQUIREMENT_STATUSES, FindingStatus, JobType, Severity
from ..models import AuditEvent, Case, Document, ExtractedField, Finding, OwnershipLink, Report, Requirement
from ..schemas import AuditOut, CaseCreate, CaseOut, CaseSummary, CaseUpdate, OwnershipOut
from ..services import audit as audit_service
from ..services.analysis import analyse_case
from ..services.cases import create_case
from ..services.jobs import enqueue, get_runner, queue_depth
from ..services.report import generate_report
from ..services.watcher import get_watch_service
from .deps import Principal, current_principal, get_case, require_write
from .translate import get_lang, localise_case

router = APIRouter(prefix="/cases", tags=["cases"])


def _summarise(db: Session, case: Case, lang: str = "en") -> CaseSummary:
    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    docs = db.execute(
        select(Document.status, func.count()).where(
            Document.case_id == case.id, Document.is_current.is_(True)
        ).group_by(Document.status)
    ).all()
    doc_counts = {s: c for s, c in docs}
    findings = db.execute(
        select(Finding.severity, func.count()).where(
            Finding.case_id == case.id, Finding.status == FindingStatus.OPEN.value
        ).group_by(Finding.severity)
    ).all()
    f_counts = {s: c for s, c in findings}
    open_reqs = db.scalar(
        select(func.count()).select_from(Requirement).where(
            Requirement.case_id == case.id, Requirement.status.in_(open_statuses))
    ) or 0
    latest = db.scalar(select(func.max(Report.version)).where(Report.case_id == case.id))

    data = CaseOut.model_validate(case).model_dump()
    pending = sum(doc_counts.get(s, 0) for s in ("discovered", "queued", "processing"))
    summary = CaseSummary(
        **data,
        document_count=sum(doc_counts.values()),
        documents_analysed=doc_counts.get("analysed", 0),
        documents_pending=pending,
        open_findings=sum(f_counts.values()),
        critical_findings=f_counts.get(Severity.CRITICAL.value, 0),
        high_findings=f_counts.get(Severity.HIGH.value, 0),
        open_requirements=open_reqs,
        latest_report_version=latest,
    )
    return localise_case(summary, case, lang)


@router.get("", response_model=List[CaseSummary])
def list_cases(
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
    q: Optional[str] = None,
    status: Optional[str] = None,
    risk: Optional[str] = None,
    property_type: Optional[str] = None,
    reviewer: Optional[str] = None,
    lang: str = Depends(get_lang),
) -> List[CaseSummary]:
    stmt = select(Case)
    if q:
        like = "%{}%".format(q)
        stmt = stmt.where(or_(Case.property_name.ilike(like), Case.case_ref.ilike(like),
                              Case.survey_number.ilike(like), Case.claimed_owner.ilike(like),
                              Case.address.ilike(like), Case.village.ilike(like)))
    if status:
        stmt = stmt.where(Case.status == status)
    if risk:
        stmt = stmt.where(Case.overall_risk == risk)
    if property_type:
        stmt = stmt.where(Case.property_type == property_type)
    if reviewer:
        stmt = stmt.where(Case.assigned_reviewer == reviewer)
    cases = db.scalars(stmt.order_by(Case.updated_at.desc())).all()
    return [_summarise(db, c, lang) for c in cases]


@router.post("", response_model=CaseSummary, status_code=201)
def create(payload: CaseCreate, db: Session = Depends(get_db),
           principal: Principal = Depends(require_write)) -> CaseSummary:
    case = create_case(db, payload.model_dump(), actor=principal.username)
    db.commit()
    service = get_watch_service()
    if service.running:
        service.refresh_watches()
        service.scan_case(case.id)
    db.refresh(case)
    return _summarise(db, case)


@router.get("/{case_id}", response_model=CaseSummary)
def get_one(case: Case = Depends(get_case), db: Session = Depends(get_db),
            principal: Principal = Depends(current_principal),
            lang: str = Depends(get_lang)) -> CaseSummary:
    return _summarise(db, case, lang)


@router.patch("/{case_id}", response_model=CaseSummary)
def update(payload: CaseUpdate, case: Case = Depends(get_case), db: Session = Depends(get_db),
           principal: Principal = Depends(require_write)) -> CaseSummary:
    changes = {}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if getattr(case, key, None) != value:
            changes[key] = {"from": getattr(case, key, None), "to": value}
            setattr(case, key, value)
    if changes:
        audit_service.record(db, "case_updated", case_id=case.id, actor=principal.username,
                             message="Case details updated.", payload=changes)
        enqueue(db, JobType.REANALYSE_CASE.value, case_id=case.id,
                dedupe_key="reanalyse:{}".format(case.id), delay_seconds=0.2, priority=200)
    db.commit()
    return _summarise(db, case)


@router.delete("/{case_id}", status_code=204)
def delete(case: Case = Depends(get_case), db: Session = Depends(get_db),
           principal: Principal = Depends(require_write)) -> None:
    """Remove the case and its records.  Files in the watched folder are never touched."""
    audit_service.record(db, "case_deleted", case_id=case.id, actor=principal.username,
                         message="Case {} deleted. Documents on disk were left untouched.".format(
                             case.case_ref))
    db.delete(case)
    db.commit()
    service = get_watch_service()
    if service.running:
        service.refresh_watches()


@router.post("/{case_id}/scan")
def scan(case: Case = Depends(get_case), db: Session = Depends(get_db),
         principal: Principal = Depends(require_write)) -> Dict[str, Any]:
    """Force an immediate sweep of the case folder."""
    result = get_watch_service().scan_case(case.id)
    return {"case_id": case.id, **result}


@router.post("/{case_id}/reanalyse")
def reanalyse(case: Case = Depends(get_case), db: Session = Depends(get_db),
              principal: Principal = Depends(require_write),
              wait: bool = Query(default=True)) -> Dict[str, Any]:
    """Re-run cross-document analysis and produce a new report version."""
    if wait:
        result = analyse_case(db, case)
        report = generate_report(db, case, actor=principal.username)
        db.commit()
        return {"assessment": result["assessment"], "changes": result["changes"],
                "report_version": report.version}
    enqueue(db, JobType.REANALYSE_CASE.value, case_id=case.id,
            dedupe_key="reanalyse:{}".format(case.id), delay_seconds=0.1, priority=200)
    db.commit()
    return {"queued": True}


@router.get("/{case_id}/ownership", response_model=List[OwnershipOut])
def ownership(case: Case = Depends(get_case), db: Session = Depends(get_db),
              principal: Principal = Depends(current_principal)) -> List[OwnershipOut]:
    links = db.scalars(
        select(OwnershipLink).where(OwnershipLink.case_id == case.id)
        .order_by(OwnershipLink.sequence)
    ).all()
    return [OwnershipOut.model_validate(l) for l in links]


@router.get("/{case_id}/audit", response_model=List[AuditOut])
def audit_log(case: Case = Depends(get_case), db: Session = Depends(get_db),
              principal: Principal = Depends(current_principal),
              limit: int = Query(default=200, le=1000),
              event_type: Optional[str] = None) -> List[AuditOut]:
    stmt = select(AuditEvent).where(AuditEvent.case_id == case.id)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    events = db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [AuditOut.model_validate(e) for e in events]


@router.get("/{case_id}/queue")
def case_queue(case: Case = Depends(get_case), db: Session = Depends(get_db),
               principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    return {"case_id": case.id, "queue": queue_depth(db, case.id),
            "runner_running": get_runner().running}


@router.get("/{case_id}/search")
def search_case(q: str, case: Case = Depends(get_case), db: Session = Depends(get_db),
                principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    """Search extracted text and fields within one case."""
    from ..models import DocumentPage

    like = "%{}%".format(q)
    page_hits = db.execute(
        select(DocumentPage.document_id, DocumentPage.page_no, DocumentPage.text)
        .join(Document, Document.id == DocumentPage.document_id)
        .where(Document.case_id == case.id, DocumentPage.text.ilike(like))
        .limit(50)
    ).all()
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.case_id == case.id)).all()}

    def excerpt(text: str) -> str:
        idx = text.lower().find(q.lower())
        start = max(0, idx - 120)
        return text[start:idx + 200].replace("\n", " ")

    field_hits = db.scalars(
        select(ExtractedField).where(
            ExtractedField.case_id == case.id,
            or_(ExtractedField.value_norm.ilike(like), ExtractedField.value_raw.ilike(like)),
        ).limit(50)
    ).all()
    return {
        "pages": [
            {"document_id": doc_id, "filename": docs[doc_id].filename if doc_id in docs else "",
             "page_no": page_no, "excerpt": excerpt(text)}
            for doc_id, page_no, text in page_hits
        ],
        "fields": [
            {"document_id": f.document_id,
             "filename": docs[f.document_id].filename if f.document_id in docs else "",
             "field_key": f.field_key, "value": f.value_norm or f.value_raw,
             "page_no": f.page_no, "evidence": f.evidence_text}
            for f in field_hits
        ],
    }
