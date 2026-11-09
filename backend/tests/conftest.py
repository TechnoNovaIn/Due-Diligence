"""Test fixtures: an isolated data directory, database and job runner per test."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Point the whole application at a throwaway directory."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(data_dir / "test.db"))
    monkeypatch.setenv("LLM_PROVIDER", "offline")
    monkeypatch.setenv("ALLOW_REMOTE_AI", "false")
    monkeypatch.setenv("WATCH_ENABLED", "false")
    monkeypatch.setenv("FILE_SETTLE_SECONDS", "0")
    monkeypatch.setenv("REPORT_DEBOUNCE_SECONDS", "0.1")
    monkeypatch.setenv("WORKER_COUNT", "2")
    monkeypatch.setenv("AUTH_ENABLED", "false")

    from app import config, db
    from app.services import knowledge
    from app.services.llm import factory

    config.reset_settings_cache()
    db.reset_engine_cache()
    factory.reset_llm_cache()
    knowledge.jurisdiction.cache_clear()

    settings = config.get_settings()
    settings.ensure_dirs()
    db.init_db()
    yield settings

    from app.services import jobs, watcher

    jobs.reset_runner()
    watcher.reset_watch_service()
    db.reset_engine_cache()
    config.reset_settings_cache()


@pytest.fixture()
def session(env):
    from app.db import session_scope

    with session_scope() as s:
        yield s


@pytest.fixture()
def make_case(env):
    from app.db import session_scope
    from app.services.cases import create_case

    def _make(**overrides):
        payload = {
            "property_name": "Hosahalli agricultural land",
            "property_type": "agricultural_land",
            "transaction_type": "purchase",
            "survey_number": "123/4B",
            "village": "Hosahalli",
            "taluk": "Nelamangala",
            "district": "Bengaluru Rural",
            "state": "Karnataka",
            "jurisdiction_code": "KA",
            "claimed_owner": "Latha Rao",
            "seller_name": "Latha Rao",
            "buyer_name": "Anil Shetty",
            "purpose": "Purchase due diligence",
        }
        payload.update(overrides)
        with session_scope() as s:
            case = create_case(s, payload)
            s.flush()
            return case.id, case.watch_folder

    return _make


@pytest.fixture()
def samples(tmp_path):
    """Generate the synthetic document set into a staging folder."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen", SAMPLES / "generate_samples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    staging = tmp_path / "staging"

    def _generate(stage="initial", folder=None):
        target = Path(folder) if folder else staging
        module.generate(target, stage)
        return target

    return _generate


@pytest.fixture()
def pump(env):
    """Run every queued job to completion, synchronously and deterministically."""
    from datetime import datetime

    from sqlalchemy import select

    from app.db import session_scope
    from app.enums import JobStatus
    from app.models import Job
    from app.services import jobs as jobs_module

    runner = jobs_module.JobRunner(worker_count=1)

    def _pump(max_iterations: int = 200):
        for _ in range(max_iterations):
            with session_scope() as s:
                job = s.scalars(
                    select(Job).where(Job.status == JobStatus.PENDING.value)
                    .order_by(Job.priority, Job.scheduled_at).limit(1)
                ).first()
                if job is None:
                    return
                job_id = job.id
                job.status = JobStatus.RUNNING.value
                job.started_at = datetime.utcnow()
                job.attempts += 1
                job.scheduled_at = datetime.utcnow()
            runner._run(job_id)
            with session_scope() as s:
                job = s.get(Job, job_id)
                if job and job.status == JobStatus.PENDING.value:
                    job.scheduled_at = datetime.utcnow()
        raise AssertionError("Job queue did not drain")

    return _pump


@pytest.fixture()
def api_client(env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    # The lifespan would start the watcher and the worker pool; tests drive both
    # explicitly so that assertions are deterministic.
    with TestClient(app) as client:  # noqa: SIM117
        yield client
