"""Durable job queue and worker pool.

Jobs live in the database, so a crash loses nothing: unfinished work is picked
up again on the next start.  Report generation is coalesced - while documents
are still being processed the re-analysis job pushes itself forward rather than
producing a report from a half-ingested folder.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import session_scope
from ..enums import DocStatus, JobStatus, JobType
from ..models import Case, Document, Job
from . import audit

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
def enqueue(session: Session, job_type: str, *, case_id: Optional[str] = None,
            document_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
            dedupe_key: Optional[str] = None, delay_seconds: float = 0.0,
            priority: int = 100) -> Job:
    """Add a job.  A pending job with the same dedupe key is pushed forward instead."""
    settings = get_settings()
    scheduled = datetime.utcnow() + timedelta(seconds=delay_seconds)

    if dedupe_key:
        existing = session.scalars(
            select(Job).where(Job.dedupe_key == dedupe_key, Job.status == JobStatus.PENDING.value)
        ).first()
        if existing is not None:
            if scheduled > existing.scheduled_at:
                existing.scheduled_at = scheduled
            return existing

    job = Job(
        case_id=case_id, document_id=document_id, job_type=job_type, payload=payload or {},
        dedupe_key=dedupe_key, scheduled_at=scheduled, priority=priority,
        max_attempts=settings.job_max_attempts,
    )
    session.add(job)
    session.flush()
    return job


def queue_depth(session: Session, case_id: Optional[str] = None) -> Dict[str, int]:
    stmt = select(Job)
    if case_id:
        stmt = stmt.where(Job.case_id == case_id)
    jobs = session.scalars(stmt).all()
    out: Dict[str, int] = {}
    for job in jobs:
        out[job.status] = out.get(job.status, 0) + 1
    return out


# ---------------------------------------------------------------------------
class JobRunner:
    """A small pool of worker threads draining the job table."""

    def __init__(self, worker_count: Optional[int] = None, poll_interval: float = 0.5) -> None:
        settings = get_settings()
        self.worker_count = worker_count or settings.worker_count
        self.poll_interval = poll_interval
        self._threads: List[threading.Thread] = []
        self._stop = threading.Event()
        self._idle = threading.Event()
        self._active = 0
        self._lock = threading.Lock()
        self.handlers: Dict[str, Callable[[Session, Job], Dict[str, Any]]] = {
            JobType.PROCESS_DOCUMENT.value: _handle_process_document,
            JobType.REANALYSE_CASE.value: _handle_reanalyse_case,
            JobType.GENERATE_REPORT.value: _handle_generate_report,
        }

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self._threads:
            return
        self._stop.clear()
        self._requeue_stale()
        for i in range(self.worker_count):
            t = threading.Thread(target=self._loop, name="ddjob-{}".format(i), daemon=True)
            t.start()
            self._threads.append(t)
        log.info("Job runner started with %s worker(s).", self.worker_count)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=timeout)
        self._threads = []

    @property
    def running(self) -> bool:
        return bool(self._threads) and not self._stop.is_set()

    def wait_until_idle(self, timeout: float = 120.0) -> bool:
        """Block until no pending/running job remains.  Used by tests and the API."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with session_scope() as session:
                pending = session.scalars(
                    select(Job).where(Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]))
                ).all()
                due = [j for j in pending if j.status == JobStatus.RUNNING.value
                       or j.scheduled_at <= datetime.utcnow() + timedelta(seconds=30)]
            with self._lock:
                active = self._active
            if not due and active == 0:
                return True
            time.sleep(0.2)
        return False

    # -- internals -------------------------------------------------------
    def _requeue_stale(self) -> None:
        with session_scope() as session:
            stale = session.scalars(select(Job).where(Job.status == JobStatus.RUNNING.value)).all()
            for job in stale:
                job.status = JobStatus.PENDING.value
                job.last_error = "Re-queued after an unclean shutdown."
                log.info("Re-queued job %s (%s) left running by a previous process.", job.id, job.job_type)

    def _claim(self) -> Optional[str]:
        """Atomically claim one due job."""
        with session_scope() as session:
            candidate = session.scalars(
                select(Job)
                .where(Job.status == JobStatus.PENDING.value, Job.scheduled_at <= datetime.utcnow())
                .order_by(Job.priority, Job.scheduled_at)
                .limit(1)
            ).first()
            if candidate is None:
                return None
            result = session.execute(
                update(Job)
                .where(Job.id == candidate.id, Job.status == JobStatus.PENDING.value)
                .values(status=JobStatus.RUNNING.value, started_at=datetime.utcnow(),
                        attempts=Job.attempts + 1)
            )
            if result.rowcount != 1:
                return None
            return candidate.id

    def _loop(self) -> None:
        while not self._stop.is_set():
            job_id = None
            try:
                job_id = self._claim()
            except Exception:  # pragma: no cover - database contention
                log.exception("Failed to claim a job")
            if job_id is None:
                self._stop.wait(self.poll_interval)
                continue
            with self._lock:
                self._active += 1
            try:
                self._run(job_id)
            finally:
                with self._lock:
                    self._active -= 1

    def _run(self, job_id: str) -> None:
        settings = get_settings()
        try:
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is None:
                    return
                handler = self.handlers.get(job.job_type)
                if handler is None:
                    job.status = JobStatus.FAILED.value
                    job.last_error = "No handler for job type '{}'".format(job.job_type)
                    job.finished_at = datetime.utcnow()
                    return
                outcome = handler(session, job) or {}
                if outcome.get("requeue"):
                    job.status = JobStatus.PENDING.value
                    job.scheduled_at = datetime.utcnow() + timedelta(
                        seconds=float(outcome.get("delay", settings.report_debounce_seconds)))
                    job.attempts = max(0, job.attempts - 1)  # a deferral is not an attempt
                    return
                job.status = JobStatus.DONE.value
                job.finished_at = datetime.utcnow()
                job.last_error = None
        except Exception as exc:  # noqa: BLE001 - a job must never kill the worker
            log.exception("Job %s failed", job_id)
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is None:
                    return
                job.last_error = "{}: {}".format(type(exc).__name__, str(exc)[:500])
                if job.attempts >= job.max_attempts:
                    job.status = JobStatus.FAILED.value
                    job.finished_at = datetime.utcnow()
                    audit.record(session, "job_failed", case_id=job.case_id, document_id=job.document_id,
                                 message="{} failed after {} attempts: {}".format(
                                     job.job_type, job.attempts, job.last_error))
                else:
                    backoff = get_settings().job_retry_backoff_seconds * (2 ** (job.attempts - 1))
                    job.status = JobStatus.PENDING.value
                    job.scheduled_at = datetime.utcnow() + timedelta(seconds=backoff)
                    log.info("Job %s will be retried in %ss (attempt %s/%s).",
                             job.id, backoff, job.attempts, job.max_attempts)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _handle_process_document(session: Session, job: Job) -> Dict[str, Any]:
    from .pipeline import process_document

    settings = get_settings()
    outcome = process_document(session, job.document_id)
    enqueue(session, JobType.REANALYSE_CASE.value, case_id=job.case_id,
            dedupe_key="reanalyse:{}".format(job.case_id),
            delay_seconds=settings.report_debounce_seconds, priority=200)
    return {"outcome": outcome}


def _handle_reanalyse_case(session: Session, job: Job) -> Dict[str, Any]:
    from .analysis import analyse_case

    settings = get_settings()
    # Never analyse while documents are still in flight.
    in_flight = session.scalars(
        select(Document).where(
            Document.case_id == job.case_id,
            Document.is_current.is_(True),
            Document.status.in_([DocStatus.DISCOVERED.value, DocStatus.QUEUED.value,
                                 DocStatus.PROCESSING.value]),
        )
    ).all()
    queued_jobs = session.scalars(
        select(Job).where(
            Job.case_id == job.case_id,
            Job.job_type == JobType.PROCESS_DOCUMENT.value,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
        )
    ).all()
    if in_flight or queued_jobs:
        return {"requeue": True, "delay": settings.report_debounce_seconds}

    case = session.get(Case, job.case_id)
    if case is None:
        return {}
    result = analyse_case(session, case)
    enqueue(session, JobType.GENERATE_REPORT.value, case_id=case.id,
            dedupe_key="report:{}".format(case.id), delay_seconds=0.2, priority=300)
    return {"assessment": result["assessment"]["assessment_status"]}


def _handle_generate_report(session: Session, job: Job) -> Dict[str, Any]:
    from .report import generate_report

    case = session.get(Case, job.case_id)
    if case is None:
        return {}
    report = generate_report(session, case)
    return {"report_version": report.version}


# ---------------------------------------------------------------------------
_runner: Optional[JobRunner] = None


def get_runner() -> JobRunner:
    global _runner
    if _runner is None:
        _runner = JobRunner()
    return _runner


def reset_runner() -> None:
    global _runner
    if _runner is not None:
        _runner.stop(timeout=2.0)
    _runner = None
