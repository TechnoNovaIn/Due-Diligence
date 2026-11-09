"""Audit trail helper."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .. import RULESET_VERSION
from ..models import AuditEvent


def record(session: Session, event_type: str, *, case_id: Optional[str] = None,
           document_id: Optional[str] = None, actor: str = "system", message: str = "",
           payload: Optional[Dict[str, Any]] = None, report_version: Optional[int] = None,
           model_version: Optional[str] = None) -> AuditEvent:
    event = AuditEvent(
        case_id=case_id, document_id=document_id, event_type=event_type, actor=actor,
        message=message, payload=payload or {}, report_version=report_version,
        model_version=model_version, ruleset_version=RULESET_VERSION,
    )
    session.add(event)
    return event
