# Deployment

## Local install

```bash
./scripts/setup.sh
./scripts/run.sh            # HOST and PORT are honoured
```

`setup.sh` creates `backend/.venv`, installs dependencies, copies `.env.example` to `.env`,
applies migrations and builds the dashboard. It warns if Tesseract is missing.

Development with hot reload on both sides:

```bash
./scripts/dev.sh            # API on :8000 with reload, Vite on :5173 proxying /api
```

## Configuration

Every setting is an environment variable, read from `.env` in the project root. See
`.env.example` for the full annotated list. The ones that matter most:

| Variable | Default | Notes |
|---|---|---|
| `DATA_DIR` | `./data` | Database, case folders, reports and logs all live here. |
| `CASES_ROOT` | `DATA_DIR/cases` | Where new case folders are created. |
| `ALLOWED_WATCH_ROOTS` | `CASES_ROOT` | Comma-separated. A case folder outside these is refused, and so is any file path that resolves outside them. |
| `DATABASE_URL` | SQLite in `DATA_DIR` | `postgresql+psycopg://user:pass@host/db` for a server. |
| `FILE_SETTLE_SECONDS` | `2` | Raise it on a slow network share. |
| `RECONCILE_INTERVAL_SECONDS` | `120` | Full sweep of every case folder. |
| `WORKER_COUNT` | `2` | Concurrent document processing. |
| `REPORT_DEBOUNCE_SECONDS` | `3` | Quiet period before a report is regenerated. |
| `MAX_FILE_MB` | `0` | **No limit.** Set a positive number of MB to cap uploads. |
| `MAX_PAGES_PER_DOCUMENT` | `0` | **No limit** — the whole document is read however long it is. Set a positive number to stop after that many pages; truncation is then reported on the document, never silent. |
| `OCR_ENABLED`, `OCR_LANGUAGE`, `OCR_DPI` | `true`, `eng`, `300` | Add languages with `eng+kan`. Language codes are Tesseract's and are mapped to each engine's equivalents automatically. **Kannada OCR needs Tesseract or EasyOCR** — macOS Vision does not support it. |
| `TESSERACT_CMD` | unset | Path to the Tesseract binary when it is not on `PATH`. Needed on a Mac without Homebrew, where Tesseract is installed into a self-contained prefix. |
| `LLM_PROVIDER` | `offline` | `anthropic` to enable model assistance. |
| `ALLOW_REMOTE_AI` | `false` | **Must also be true** before any document text leaves the machine. |
| `AUTH_ENABLED`, `ADMIN_API_KEY` | `false` | Enable for anything beyond single-user local use. |
| `MALWARE_SCAN_COMMAND` | unset | e.g. `clamscan --no-summary`; the file path is appended. |

## OCR engines

Scanned documents need an OCR engine. Two are supported, both entirely local, and the
first one present is used:

| Engine | Install | Notes |
|---|---|---|
| Tesseract | `brew install tesseract` (macOS), `apt-get install tesseract-ocr` (Debian) | Cross-platform. Extra languages are separate packages, e.g. `tesseract-ocr-kan`. |
| macOS Vision | `pip install ocrmac` into `backend/.venv` | macOS only, and already a dependency there. No system install, no model download; Indic scripts are supported by the OS. |

`setup.sh` installs `ocrmac` on macOS automatically, so OCR works out of the box there.
Install Tesseract as well if you want the same engine across platforms — it takes
precedence when present.

### Large documents

There is no size or page limit by default. Files are streamed to disk and hashed a
megabyte at a time, and pages are read one at a time, so memory does not scale with the
file: a 250 MB document validates and hashes in under a second with peak memory around
50 MB, and a 2,000-page deed book is read, classified, cross-checked and reported in
about 8 seconds.

What does cost time is OCR, and only when it is actually needed. The decision is made
once per document rather than per page: a document whose pages carry a normal text layer
is never rasterised, while a scan — including one carrying a digital registry stamp on
each page — still goes to OCR in full. Pages that are empty are OCR'd whatever the rest
of the document looks like, so a scanned annexure bound into a digital deed is not missed.

### Kannada

Digital Kannada PDFs (Bhoomi RTC, Kaveri EC) are read without OCR. Scanned Kannada paper
needs Tesseract with the Kannada pack:

```bash
brew install tesseract tesseract-lang                   # macOS
sudo apt-get install tesseract-ocr tesseract-ocr-kan    # Debian/Ubuntu
```

Then set `OCR_LANGUAGE=eng+kan`. A Kannada PDF report also needs a Kannada font — macOS
ships one; on Linux install `fonts-noto-kannada`. See [LANGUAGES.md](LANGUAGES.md).

Check which engine is live on the **System** page, or:

```bash
curl -s localhost:8000/api/system/status | python3 -m json.tool | grep -A6 '"ocr"'
```

## PostgreSQL

```bash
createdb duediligence
export DATABASE_URL="postgresql+psycopg://dd:secret@localhost:5432/duediligence"
cd backend && .venv/bin/python -m pip install "psycopg[binary]"
.venv/bin/python -m alembic upgrade head
```

Nothing else changes. SQLite is fine for a single reviewer; move to PostgreSQL when several
people use the same instance or when you want concurrent writes under load.

## Running as a service

**macOS (launchd)** — `~/Library/LaunchAgents/com.local.duediligence.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.local.duediligence</string>
  <key>ProgramArguments</key>
  <array><string>/full/path/to/scripts/run.sh</string></array>
  <key>WorkingDirectory</key><string>/full/path/to/Due Diligence System</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>/tmp/duediligence.err</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.local.duediligence.plist
```

**Linux (systemd)** — `/etc/systemd/system/duediligence.service`:

```ini
[Unit]
Description=Property Due Diligence System
After=network.target

[Service]
Type=simple
User=duediligence
WorkingDirectory=/opt/duediligence
ExecStart=/opt/duediligence/scripts/run.sh
Restart=on-failure
Environment=HOST=127.0.0.1 PORT=8000

[Install]
WantedBy=multi-user.target
```

Keep it bound to `127.0.0.1`. If it must be reachable over a network, put a TLS-terminating
reverse proxy in front of it, enable `AUTH_ENABLED`, and read [SECURITY.md](SECURITY.md)
first.

### Watch limits

Each case folder is one recursive watch. On Linux, many cases can exhaust inotify watches:

```bash
echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p
```

The reconciliation sweep means the system still works correctly if a watch cannot be
registered — it just notices changes on the sweep interval instead of immediately.

## Backups

Back up three things:

1. `DATA_DIR/duediligence.db` (or the PostgreSQL database) — cases, findings, requirements,
   reports, audit trail.
2. `DATA_DIR/reports/` — the rendered HTML/PDF/JSON for every version.
3. The case folders — the source documents, if they live under `DATA_DIR`.

```bash
sqlite3 "$DATA_DIR/duediligence.db" ".backup '/backups/dd-$(date +%F).db'"
```

Extracted text and fields can always be rebuilt from the source documents by reprocessing;
the database holds the findings, decisions and history that cannot.

## Upgrading

```bash
git pull
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend && .venv/bin/python -m alembic upgrade head
cd ../frontend && npm install && npm run build
```

If the ruleset changed, re-analyse affected cases (**Re-analyse** in the case header, or
`POST /api/cases/{id}/reanalyse`). A new report version will record what the new rules
found; earlier versions keep the old ruleset version stamped on them.
