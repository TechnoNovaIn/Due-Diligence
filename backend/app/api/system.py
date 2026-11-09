"""System status, reference data and the dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .. import RULESET_VERSION, __version__
from ..config import get_settings
from ..db import get_db
from ..enums import (
    OPEN_REQUIREMENT_STATUSES,
    CaseStatus,
    DocStatus,
    FindingStatus,
    PropertyType,
    Severity,
    TransactionType,
)
from ..models import AuditEvent, Case, Document, Finding, Report, Requirement
from ..services.extraction.ocr import ocr_status
from ..services.jobs import get_runner, queue_depth
from ..services.knowledge import available_jurisdictions, doc_types
from ..services.llm import provider_status
from ..services.watcher import get_watch_service
from .. import i18n
from ..services.findings_i18n import catalogue_coverage
from .deps import Principal, current_principal

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "version": __version__}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db),
                  principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    settings = get_settings()
    return {
        "version": __version__,
        "ruleset_version": RULESET_VERSION,
        "principal": {"username": principal.username, "role": principal.role},
        "ai": provider_status(),
        "ocr": ocr_status(),
        "watcher": get_watch_service().status(),
        "jobs": {"running": get_runner().running, "queue": queue_depth(db),
                 "workers": get_runner().worker_count},
        "storage": {
            "data_dir": str(settings.data_dir),
            "cases_root": str(settings.cases_root),
            "reports_dir": str(settings.reports_dir),
            "database": settings.database_url.split("://")[0],
        },
        "limits": {
            "max_file_mb": settings.max_file_mb or None,
            "max_pages_per_document": settings.max_pages_per_document or None,
            "file_settle_seconds": settings.file_settle_seconds,
            "reconcile_interval_seconds": settings.reconcile_interval_seconds,
        },
        "security": {
            "auth_enabled": settings.auth_enabled,
            "remote_ai_allowed": settings.allow_remote_ai,
            "malware_scan_configured": bool(settings.malware_scan_command),
        },
        "languages": dict(i18n.coverage(), **catalogue_coverage()),
    }


@router.get("/system/reference")
def reference_data(principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    """Reference data in every supported language, so the interface can switch
    language without another round trip."""
    return {
        "languages": [{"code": code, "label": i18n.LANGUAGE_NAMES[code]} for code in i18n.LANGUAGES],
        "property_types": [
            {"value": t.value,
             "label": t.value.replace("_", " ").title(),
             "label_kn": i18n.PROPERTY_TYPE.get(t.value, t.value)}
            for t in PropertyType
        ],
        "transaction_types": [
            {"value": t.value,
             "label": t.value.replace("_", " ").title(),
             "label_kn": i18n.TRANSACTION_TYPE.get(t.value, t.value)}
            for t in TransactionType
        ],
        "case_statuses": [s.value for s in CaseStatus],
        "severities": [s.value for s in Severity],
        "document_types": [
            {"key": key, "label": meta["label"], "label_kn": meta.get("label_kn", meta["label"]),
             "group": meta["group"]}
            for key, meta in sorted(doc_types().items(), key=lambda kv: (kv[1]["group"], kv[1]["label"]))
        ],
        "jurisdictions": available_jurisdictions(),
        "vocabularies": i18n.vocabulary_payload(),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db),
              principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    cases = db.scalars(select(Case)).all()
    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}

    finding_rows = db.execute(
        select(Finding.case_id, Finding.severity, func.count())
        .where(Finding.status == FindingStatus.OPEN.value)
        .group_by(Finding.case_id, Finding.severity)
    ).all()
    by_case: Dict[str, Dict[str, int]] = {}
    for case_id, severity, count in finding_rows:
        by_case.setdefault(case_id, {})[severity] = count

    req_rows = db.execute(
        select(Requirement.case_id, func.count())
        .where(Requirement.status.in_(open_statuses))
        .group_by(Requirement.case_id)
    ).all()
    open_reqs = {case_id: count for case_id, count in req_rows}

    doc_rows = db.execute(
        select(Document.case_id, Document.status, func.count())
        .where(Document.is_current.is_(True))
        .group_by(Document.case_id, Document.status)
    ).all()
    docs_by_case: Dict[str, Dict[str, int]] = {}
    for case_id, status_value, count in doc_rows:
        docs_by_case.setdefault(case_id, {})[status_value] = count

    critical_cases = [c for c in cases if by_case.get(c.id, {}).get(Severity.CRITICAL.value)]
    high_cases = [c for c in cases if by_case.get(c.id, {}).get(Severity.HIGH.value)]
    awaiting = [c for c in cases if open_reqs.get(c.id, 0) > 0]
    analysing = [c for c in cases if any(
        docs_by_case.get(c.id, {}).get(s, 0)
        for s in (DocStatus.QUEUED.value, DocStatus.PROCESSING.value, DocStatus.DISCOVERED.value))]
    ready = [c for c in cases if c.assessment_status == "ready_for_independent_professional_review"]

    recent_docs = db.scalars(
        select(Document).where(Document.is_current.is_(True))
        .order_by(desc(Document.first_seen_at)).limit(10)
    ).all()
    recent_reports = db.scalars(
        select(Report).order_by(desc(Report.generated_at)).limit(10)
    ).all()
    case_names = {c.id: {"case_ref": c.case_ref, "property_name": c.property_name} for c in cases}

    pending_actions: List[Dict[str, Any]] = []
    for r in db.scalars(
        select(Requirement).where(Requirement.status.in_(open_statuses),
                                  Requirement.priority == "mandatory")
        .order_by(desc(Requirement.updated_at)).limit(15)
    ).all():
        pending_actions.append({
            "case_id": r.case_id, "case": case_names.get(r.case_id, {}),
            "requirement": r.name, "status": r.status, "next_action": r.next_action,
        })

    return {
        "totals": {
            "cases": len(cases),
            "under_analysis": len(analysing),
            "awaiting_documents": len(awaiting),
            "with_critical_risks": len(critical_cases),
            "with_high_findings": len(high_cases),
            "ready_for_professional_review": len(ready),
            "documents": sum(sum(v.values()) for v in docs_by_case.values()),
            "open_findings": sum(sum(v.values()) for v in by_case.values()),
            "open_requirements": sum(open_reqs.values()),
        },
        "cases": [
            {
                "id": c.id, "case_ref": c.case_ref, "property_name": c.property_name,
                "property_type": c.property_type, "status": c.status,
                "overall_risk": c.overall_risk, "assessment_status": c.assessment_status,
                "risk_score": c.risk_score,
                "open_findings": sum(by_case.get(c.id, {}).values()),
                "critical": by_case.get(c.id, {}).get(Severity.CRITICAL.value, 0),
                "high": by_case.get(c.id, {}).get(Severity.HIGH.value, 0),
                "open_requirements": open_reqs.get(c.id, 0),
                "documents": sum(docs_by_case.get(c.id, {}).values()),
                "last_analysis_at": c.last_analysis_at,
                "assigned_reviewer": c.assigned_reviewer,
            }
            for c in sorted(cases, key=lambda x: x.updated_at, reverse=True)
        ],
        "recent_documents": [
            {"id": d.id, "case_id": d.case_id, "case": case_names.get(d.case_id, {}),
             "filename": d.filename, "status": d.status, "doc_type": d.doc_type,
             "first_seen_at": d.first_seen_at}
            for d in recent_docs
        ],
        "recent_reports": [
            {"id": r.id, "case_id": r.case_id, "case": case_names.get(r.case_id, {}),
             "version": r.version, "generated_at": r.generated_at,
             "assessment_status": r.assessment_status, "overall_risk": r.overall_risk}
            for r in recent_reports
        ],
        "pending_actions": pending_actions,
    }
