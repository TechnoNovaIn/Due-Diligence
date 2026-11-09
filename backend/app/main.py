"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import api_router
from .config import get_settings
from .db import init_db
from .logging_config import configure_logging
from .services.jobs import get_runner
from .services.watcher import get_watch_service

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.logs_dir)
    settings.ensure_dirs()
    init_db()
    log.info("Database ready at %s", settings.database_url.split("://")[-1])

    runner = get_runner()
    runner.start()

    watcher = get_watch_service()
    if settings.watch_enabled:
        watcher.start()
    else:
        log.warning("Folder monitoring is disabled by configuration (WATCH_ENABLED=false).")

    from .services.llm import provider_status

    status = provider_status()
    if status.get("sends_document_text_off_device"):
        log.warning("AI provider '%s' is active: %s", status["provider"], status["data_leaving_device"])
    else:
        log.info("AI processing is local only: %s", status["data_leaving_device"])

    try:
        yield
    finally:
        watcher.stop()
        runner.stop()
        log.info("Background services stopped.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Property Due Diligence System",
        description=(
            "Monitors a local folder of property documents, reads and cross-checks them, tracks what is "
            "missing, and produces an evidence-linked due diligence report. Preliminary assessment only "
            "- not a legal opinion."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")

    static_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(str(static_dir / "index.html"))

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = static_dir / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(static_dir / "index.html"))
    else:
        @app.get("/", include_in_schema=False)
        def root() -> JSONResponse:
            return JSONResponse({
                "name": "Property Due Diligence System",
                "version": __version__,
                "api_docs": "/docs",
                "note": "The dashboard has not been built. Run `npm install && npm run build` in "
                        "frontend/, or start the Vite dev server with `npm run dev`.",
            })

    return app


app = create_app()
