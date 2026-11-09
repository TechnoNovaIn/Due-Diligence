"""Shared helpers for the acceptance tests."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import session_scope
from app.enums import DocStatus, JobType
from app.models import Case, Document, Finding, Report, Requirement


def copy_files(src: Path, dest: Path, names: List[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(src / name, dest / name)


def ingest_and_run(case_id: str, pump) -> None:
    """Sweep the case folder, then drain the queue."""
    from app.services.watcher import WatchService

    WatchService().scan_case(case_id)
    pump()


def findings_for(case_id: str, detector: str = None, status: str = None) -> List[Finding]:
    with session_scope() as s:
        stmt = select(Finding).options(selectinload(Finding.evidence)).where(
            Finding.case_id == case_id)
        if detector:
            stmt = stmt.where(Finding.detector == detector)
        if status:
            stmt = stmt.where(Finding.status == status)
        return list(s.scalars(stmt).all())


def requirements_for(case_id: str) -> List[Requirement]:
    with session_scope() as s:
        return list(s.scalars(select(Requirement).where(Requirement.case_id == case_id)).all())


def documents_for(case_id: str) -> List[Document]:
    with session_scope() as s:
        return list(s.scalars(
            select(Document).options(selectinload(Document.fields), selectinload(Document.pages))
            .where(Document.case_id == case_id, Document.is_current.is_(True))).all())


def latest_report(case_id: str) -> Report:
    with session_scope() as s:
        return s.scalars(
            select(Report).where(Report.case_id == case_id).order_by(Report.version.desc())
        ).first()


def reports_for(case_id: str) -> List[Report]:
    with session_scope() as s:
        return list(s.scalars(
            select(Report).where(Report.case_id == case_id).order_by(Report.version)).all())
