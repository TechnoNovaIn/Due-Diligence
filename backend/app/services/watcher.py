"""Local folder monitoring.

Two mechanisms run together, because filesystem events alone are not reliable:

* a watchdog observer per case folder gives low-latency notification;
* a periodic reconciliation sweep re-reads every folder, so events dropped by
  the OS, files copied while the service was down, and deletions are all
  picked up anyway.

A file is only ingested once it has stopped changing, so half-copied downloads
are never processed.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from sqlalchemy import select
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..config import get_settings
from ..db import session_scope
from ..enums import DocStatus, JobType
from ..models import Case, Document
from . import audit, filesafe
from .jobs import enqueue
from .pipeline import case_lock, ingest_path, mark_missing_documents

log = logging.getLogger(__name__)


class _CaseEventHandler(FileSystemEventHandler):
    def __init__(self, case_id: str, service: "WatchService") -> None:
        self.case_id = case_id
        self.service = service

    def _note(self, path: str) -> None:
        p = Path(path)
        if p.is_dir() or filesafe.is_ignored(p):
            return
        self.service.note_change(self.case_id, p)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._note(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._note(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._note(event.dest_path)
            self.service.note_deletion(self.case_id)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.service.note_deletion(self.case_id)


class WatchService:
    """Owns the observer, the settle loop and the reconciliation sweep."""

    def __init__(self) -> None:
        self._observer: Optional[Observer] = None
        self._watches: Dict[str, object] = {}
        self._pending: Dict[str, Dict[str, float]] = {}
        self._deletions: Set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._settle_thread: Optional[threading.Thread] = None
        self._reconcile_thread: Optional[threading.Thread] = None
        self.last_reconcile_at: Optional[float] = None
        self.started_at: Optional[float] = None

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self._observer is not None:
            return
        self._stop.clear()
        self._observer = Observer()
        self._observer.start()
        self.started_at = time.time()
        self._settle_thread = threading.Thread(target=self._settle_loop, name="dd-settle", daemon=True)
        self._settle_thread.start()
        self._reconcile_thread = threading.Thread(target=self._reconcile_loop, name="dd-reconcile",
                                                  daemon=True)
        self._reconcile_thread.start()
        self.refresh_watches()
        log.info("Folder watch service started.")

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            self._observer.stop()
            try:
                self._observer.join(timeout=5)
            except RuntimeError:  # pragma: no cover
                pass
            self._observer = None
        self._watches.clear()
        for t in (self._settle_thread, self._reconcile_thread):
            if t is not None:
                t.join(timeout=5)
        self._settle_thread = self._reconcile_thread = None

    @property
    def running(self) -> bool:
        return self._observer is not None and not self._stop.is_set()

    # -- watch registration ------------------------------------------------
    def refresh_watches(self) -> None:
        if self._observer is None:
            return
        with session_scope() as session:
            cases = session.scalars(select(Case).where(Case.watch_enabled.is_(True))).all()
            wanted = {c.id: c.watch_folder for c in cases}
        for case_id, folder in wanted.items():
            if case_id in self._watches:
                continue
            path = Path(folder)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            try:
                watch = self._observer.schedule(_CaseEventHandler(case_id, self), str(path),
                                                recursive=True)
                self._watches[case_id] = watch
                log.info("Watching %s for case %s", path, case_id)
            except OSError as exc:  # pragma: no cover - platform limits
                log.error("Could not watch %s: %s", path, exc)
        for case_id in list(self._watches):
            if case_id not in wanted:
                try:
                    self._observer.unschedule(self._watches[case_id])
                except Exception:  # pragma: no cover
                    pass
                self._watches.pop(case_id, None)

    def note_change(self, case_id: str, path: Path) -> None:
        with self._lock:
            self._pending.setdefault(case_id, {})[str(path)] = time.time()

    def note_deletion(self, case_id: str) -> None:
        with self._lock:
            self._deletions.add(case_id)

    # -- loops -------------------------------------------------------------
    def _settle_loop(self) -> None:
        settings = get_settings()
        while not self._stop.is_set():
            self._stop.wait(1.0)
            if self._stop.is_set():
                break
            now = time.time()
            ready: Dict[str, List[Path]] = {}
            with self._lock:
                for case_id, paths in list(self._pending.items()):
                    for path_str in list(paths):
                        path = Path(path_str)
                        if not path.exists():
                            paths.pop(path_str, None)
                            self._deletions.add(case_id)
                            continue
                        if filesafe.is_settled(path, settings.file_settle_seconds, now):
                            ready.setdefault(case_id, []).append(path)
                            paths.pop(path_str, None)
                    if not paths:
                        self._pending.pop(case_id, None)
                deletions = list(self._deletions)
                self._deletions.clear()

            for case_id, paths in ready.items():
                try:
                    self.ingest_paths(case_id, paths)
                except Exception:  # pragma: no cover - never kill the loop
                    log.exception("Failed to ingest changes for case %s", case_id)
            for case_id in deletions:
                try:
                    self.handle_deletions(case_id)
                except Exception:  # pragma: no cover
                    log.exception("Failed to handle deletions for case %s", case_id)

    def _reconcile_loop(self) -> None:
        settings = get_settings()
        # A sweep at startup catches anything added while the service was down.
        self._stop.wait(1.0)
        while not self._stop.is_set():
            try:
                self.reconcile_all()
            except Exception:  # pragma: no cover
                log.exception("Reconciliation sweep failed")
            self._stop.wait(settings.reconcile_interval_seconds)

    # -- work --------------------------------------------------------------
    def ingest_paths(self, case_id: str, paths: List[Path]) -> int:
        queued = 0
        with case_lock(case_id), session_scope() as session:
            case = session.get(Case, case_id)
            if case is None:
                return 0
            for path in paths:
                doc = ingest_path(session, case, path)
                if doc is None:
                    continue
                doc.status = DocStatus.QUEUED.value
                enqueue(session, JobType.PROCESS_DOCUMENT.value, case_id=case.id, document_id=doc.id,
                        dedupe_key="process:{}".format(doc.id), priority=100)
                queued += 1
            if queued:
                self.refresh_watches()
        return queued

    def handle_deletions(self, case_id: str) -> int:
        from ..config import get_settings as _gs

        with session_scope() as session:
            case = session.get(Case, case_id)
            if case is None:
                return 0
            removed = mark_missing_documents(session, case)
            if removed:
                enqueue(session, JobType.REANALYSE_CASE.value, case_id=case.id,
                        dedupe_key="reanalyse:{}".format(case.id),
                        delay_seconds=_gs().report_debounce_seconds, priority=200)
            return len(removed)

    def scan_case(self, case_id: str) -> Dict[str, int]:
        """Full sweep of one case folder: ingest new/changed files, flag missing ones."""
        with session_scope() as session:
            case = session.get(Case, case_id)
            if case is None:
                return {"queued": 0, "removed": 0}
            folder = Path(case.watch_folder)
            folder.mkdir(parents=True, exist_ok=True)
        files = [p for p in folder.rglob("*") if p.is_file() and not filesafe.is_ignored(p)]
        settings = get_settings()
        now = time.time()
        settled = [p for p in files if filesafe.is_settled(p, settings.file_settle_seconds, now)]
        queued = self.ingest_paths(case_id, settled)
        removed = self.handle_deletions(case_id)
        return {"queued": queued, "removed": removed, "files_seen": len(files)}

    def reconcile_all(self) -> Dict[str, int]:
        with session_scope() as session:
            case_ids = [c.id for c in session.scalars(
                select(Case).where(Case.watch_enabled.is_(True))).all()]
        totals = {"queued": 0, "removed": 0, "cases": len(case_ids)}
        for case_id in case_ids:
            result = self.scan_case(case_id)
            totals["queued"] += result["queued"]
            totals["removed"] += result["removed"]
        self.last_reconcile_at = time.time()
        if totals["queued"] or totals["removed"]:
            log.info("Reconciliation queued %s file(s), flagged %s removal(s).",
                     totals["queued"], totals["removed"])
        self.refresh_watches()
        return totals

    def status(self) -> Dict[str, object]:
        with self._lock:
            pending = sum(len(v) for v in self._pending.values())
        return {
            "running": self.running,
            "watched_cases": len(self._watches),
            "pending_settle": pending,
            "last_reconcile_at": self.last_reconcile_at,
            "started_at": self.started_at,
            "reconcile_interval_seconds": get_settings().reconcile_interval_seconds,
            "file_settle_seconds": get_settings().file_settle_seconds,
        }


_service: Optional[WatchService] = None


def get_watch_service() -> WatchService:
    global _service
    if _service is None:
        _service = WatchService()
    return _service


def reset_watch_service() -> None:
    global _service
    if _service is not None:
        _service.stop()
    _service = None
