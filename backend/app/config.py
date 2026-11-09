"""Application configuration.

All settings are environment-driven (see ``.env.example``).  Nothing here
reaches out to the network; the AI provider is only contacted when
``LLM_PROVIDER`` is set to a remote provider *and* a key is configured.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Comma-separated list settings are read as plain strings: a dotenv source
    # would otherwise try to JSON-decode a list-typed field and fail.
    _watch_roots: List[Path] = PrivateAttr(default_factory=list)
    _cors: List[str] = PrivateAttr(default_factory=list)

    # --- Core paths -----------------------------------------------------
    app_name: str = "Property Due Diligence System"
    data_dir: Path = Field(default=PROJECT_DIR / "data")
    #: Root under which per-case watch folders are created by default.
    cases_root: Optional[Path] = None
    #: Every watched folder must live under one of these roots (path-traversal guard).
    #: Comma-separated; read through the ``allowed_watch_roots`` property.
    allowed_watch_roots_env: str = Field(default="", alias="ALLOWED_WATCH_ROOTS")

    # --- Database -------------------------------------------------------
    # SQLite by default so the system runs with zero infrastructure.
    # Point this at postgresql+psycopg://user:pass@host/db for a server deployment.
    database_url: str = ""

    # --- Folder monitoring ---------------------------------------------
    watch_enabled: bool = True
    #: Seconds a file must stay unchanged before it is considered fully written.
    file_settle_seconds: float = 2.0
    #: Full reconciliation sweep interval, catches events the OS dropped.
    reconcile_interval_seconds: int = 120
    worker_count: int = 2
    job_max_attempts: int = 3
    job_retry_backoff_seconds: int = 20
    #: 0 means no limit, which is the default: property files routinely include
    #: large scanned deed books. Set a positive number to cap uploads.
    max_file_mb: int = 0
    #: Debounce window before a report is regenerated after the queue drains.
    report_debounce_seconds: float = 3.0

    # --- Extraction -----------------------------------------------------
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    #: Path to the Tesseract binary when it is not on PATH. Needed on a Mac
    #: without Homebrew, where Tesseract is most easily installed into a
    #: self-contained prefix rather than system-wide.
    tesseract_cmd: Optional[str] = None
    ocr_dpi: int = 300
    #: Below this many characters per page a PDF page is treated as scanned.
    ocr_min_chars_per_page: int = 120
    #: 0 means no limit. A large document is usually large because it has many
    #: pages, so capping pages would quietly truncate exactly those files.
    max_pages_per_document: int = 0

    # --- AI provider ----------------------------------------------------
    # "offline" uses the deterministic rule engine only - no data leaves the machine.
    llm_provider: str = "offline"
    llm_model: str = "claude-sonnet-5-5"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 3
    #: Hard ceiling on characters of document text sent to a remote provider.
    llm_max_chars_per_call: int = 60000
    #: Refuse to call a remote provider unless the operator opted in explicitly.
    allow_remote_ai: bool = False

    # --- Security -------------------------------------------------------
    auth_enabled: bool = False
    admin_api_key: Optional[str] = None
    cors_origins_env: str = Field(default="http://localhost:5173,http://127.0.0.1:5173",
                                  alias="CORS_ORIGINS")
    #: Optional external command for malware scanning, e.g. "clamscan --no-summary".
    malware_scan_command: Optional[str] = None
    retention_days: int = 0  # 0 disables automatic purging

    # --- Reporting ------------------------------------------------------
    report_author: str = "Property Due Diligence System"
    jurisdiction_default: str = "KA"

    @staticmethod
    def _resolve(path) -> Path:
        """Expand ~ and resolve a relative path against the project root, not the cwd."""
        p = Path(os.path.expanduser(str(path)))
        if not p.is_absolute():
            p = PROJECT_DIR / p
        return p.resolve()

    def model_post_init(self, __context) -> None:  # noqa: D105
        self.data_dir = self._resolve(self.data_dir)
        if self.cases_root is None:
            self.cases_root = self.data_dir / "cases"
        self.cases_root = self._resolve(self.cases_root)
        roots = [
            self._resolve(part.strip())
            for part in self.allowed_watch_roots_env.split(",")
            if part.strip()
        ]
        if self.cases_root not in roots:
            roots.append(self.cases_root)
        self._watch_roots = roots
        self._cors = [p.strip() for p in self.cors_origins_env.split(",") if p.strip()]
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'duediligence.db'}"

    # --- Derived values ---------------------------------------------------
    @property
    def allowed_watch_roots(self) -> List[Path]:
        return self._watch_roots

    @property
    def cors_origins(self) -> List[str]:
        return self._cors

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.cases_root, self.reports_dir, self.artifacts_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def max_file_bytes(self) -> Optional[int]:
        """``None`` when uploads are unlimited."""
        return self.max_file_mb * 1024 * 1024 if self.max_file_mb and self.max_file_mb > 0 else None

    @property
    def remote_ai_active(self) -> bool:
        return self.llm_provider not in ("offline", "", None) and self.allow_remote_ai


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reset_settings_cache() -> None:
    """Used by the test-suite to pick up a patched environment."""
    global _settings
    _settings = None
