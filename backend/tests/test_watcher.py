"""Live folder-monitoring tests - the real observer and the real worker pool."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from helpers import documents_for, latest_report, reports_for


@pytest.fixture()
def live(env, monkeypatch):
    """A running watch service and job runner, torn down after the test."""
    from app.config import get_settings, reset_settings_cache
    from app.services import jobs, watcher

    monkeypatch.setenv("WATCH_ENABLED", "true")
    monkeypatch.setenv("FILE_SETTLE_SECONDS", "0.3")
    monkeypatch.setenv("REPORT_DEBOUNCE_SECONDS", "0.5")
    monkeypatch.setenv("RECONCILE_INTERVAL_SECONDS", "2")
    reset_settings_cache()
    get_settings().ensure_dirs()

    runner = jobs.get_runner()
    runner.start()
    service = watcher.get_watch_service()
    service.start()
    yield service, runner
    service.stop()
    runner.stop()
    jobs.reset_runner()
    watcher.reset_watch_service()


def _wait_for(predicate, timeout=45.0, interval=0.3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_a_file_dropped_into_the_folder_is_picked_up_automatically(live, make_case, samples):
    service, runner = live
    case_id, folder = make_case()
    service.refresh_watches()
    staging = samples("initial")

    shutil.copy2(staging / "01_sale_deed_2015.pdf", Path(folder) / "01_sale_deed_2015.pdf")

    assert _wait_for(lambda: any(d.status == "analysed" for d in documents_for(case_id))), \
        "the watcher should detect, read and classify the file without any manual step"
    assert _wait_for(lambda: latest_report(case_id) is not None), \
        "a report should be generated once processing settles"

    docs = documents_for(case_id)
    doc = docs[0]
    assert doc.doc_type == "sale_deed"
    report = latest_report(case_id)
    assert report.documents_received == 1


def test_a_later_file_produces_a_new_report_version(live, make_case, samples):
    service, runner = live
    case_id, folder = make_case()
    service.refresh_watches()
    staging = samples("all")

    shutil.copy2(staging / "01_sale_deed_2015.pdf", Path(folder) / "01_sale_deed_2015.pdf")
    assert _wait_for(lambda: latest_report(case_id) is not None)
    first = latest_report(case_id).version

    shutil.copy2(staging / "08_partition_deed_1998.pdf", Path(folder) / "08_partition_deed_1998.pdf")
    assert _wait_for(lambda: latest_report(case_id).version > first, timeout=45), \
        "adding evidence should produce a new report version"
    assert len(reports_for(case_id)) >= 2


def test_a_replaced_file_is_reprocessed_and_versioned(live, make_case, samples):
    service, runner = live
    case_id, folder = make_case()
    service.refresh_watches()
    staging = samples("all")
    target = Path(folder) / "document.pdf"

    shutil.copy2(staging / "01_sale_deed_2015.pdf", target)
    assert _wait_for(lambda: any(d.doc_type == "sale_deed" for d in documents_for(case_id)))

    shutil.copy2(staging / "08_partition_deed_1998.pdf", target)
    assert _wait_for(lambda: any(d.doc_type == "partition_deed" for d in documents_for(case_id)),
                     timeout=45), "a replaced file must be re-read"

    from app.db import session_scope
    from app.models import Document
    from sqlalchemy import select

    with session_scope() as s:
        versions = s.scalars(select(Document).where(Document.case_id == case_id)).all()
    assert len(versions) == 2, "the previous version must be retained, not overwritten"
    assert {v.status for v in versions} >= {"superseded"}


def test_a_removed_file_is_flagged_without_erasing_history(live, make_case, samples):
    service, runner = live
    case_id, folder = make_case()
    service.refresh_watches()
    staging = samples("initial")
    target = Path(folder) / "01_sale_deed_2015.pdf"
    shutil.copy2(staging / "01_sale_deed_2015.pdf", target)
    assert _wait_for(lambda: any(d.status == "analysed" for d in documents_for(case_id)))

    target.unlink()
    service.handle_deletions(case_id)

    from app.db import session_scope
    from app.models import Document
    from sqlalchemy import select

    with session_scope() as s:
        docs = s.scalars(select(Document).where(Document.case_id == case_id)).all()
    assert docs, "the record of the document must survive the file being deleted"
    assert docs[0].status == "removed"


def test_duplicate_content_is_not_processed_twice(live, make_case, samples):
    service, runner = live
    case_id, folder = make_case()
    service.refresh_watches()
    staging = samples("initial")
    shutil.copy2(staging / "01_sale_deed_2015.pdf", Path(folder) / "deed.pdf")
    assert _wait_for(lambda: any(d.status == "analysed" for d in documents_for(case_id)))

    shutil.copy2(staging / "01_sale_deed_2015.pdf", Path(folder) / "deed_copy.pdf")
    time.sleep(3)
    service.scan_case(case_id)
    time.sleep(2)
    assert len(documents_for(case_id)) == 1, "identical content must not be ingested twice"


def test_reconciliation_catches_files_added_while_events_were_missed(live, make_case, samples):
    service, runner = live
    case_id, folder = make_case()
    staging = samples("initial")

    # Write the file before the watch is registered, as if the service were down.
    shutil.copy2(staging / "02_rtc_pahani_2024.pdf", Path(folder) / "02_rtc_pahani_2024.pdf")

    def swept_and_analysed():
        # Drive the sweep directly rather than waiting on its timer, so the test
        # asserts what reconciliation does and not how often it runs.
        service.reconcile_all()
        return any(d.status == "analysed" for d in documents_for(case_id))

    assert _wait_for(swept_and_analysed, timeout=60, interval=1.0), \
        "the reconciliation sweep should pick up files the observer never saw"
