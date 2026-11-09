# Property Due Diligence and Document Intelligence System

Watches a local folder of property documents, reads them, cross-checks them against each
other, tracks what is still missing, and produces an evidence-linked due diligence report
that updates itself whenever the folder changes.

Built for Indian property transactions, with Karnataka rules supplied and other
jurisdictions configurable. **Reads Kannada documents and runs in English or
Kannada**, which matters because Karnataka's own records — Bhoomi RTC/Pahani,
Kaveri encumbrance certificates, panchayat khata — are issued in Kannada.

> **What this is not.** It is not a title search, not an official verification and not a
> legal opinion. It organises and cross-checks the evidence you give it and says plainly
> what has *not* been established. Material conclusions need an independent title
> investigation and a qualified property lawyer.

---

## What it does

1. You create a case. The system creates a folder for it.
2. You drop documents into that folder — any mix of PDF, DOCX, DOC, RTF, TXT, JPG, PNG, TIFF.
3. A background watcher notices new, replaced and deleted files, waits for each one to
   finish copying, and reads it.
4. Each document is classified against a 58-type taxonomy (sale deed, RTC/Pahani, EC,
   mutation extract, conversion order, khata, mortgage deed, OC, RERA registration, …) and
   its fields are extracted with the page and the supporting sentence attached. **English
   and Kannada are both read**, including Kannada digits (೧೨೩), dates (೧೨ ಮಾರ್ಚ್ ೨೦೧೫),
   extents (೨ ಎಕರೆ ೧೫ ಗುಂಟೆ) and names (ಶ್ರೀಮತಿ ಲತಾ ರಾವ್ ಕೋಂ ಮೋಹನ್ ರಾವ್) — a Kannada
   RTC and an English sale deed in the same case are cross-checked against each other.
5. The cross-document engine reconstructs the ownership chain, compares every property
   identifier, assesses encumbrance coverage, checks land-use approvals, collects
   litigation references and flags document-integrity concerns.
6. A dynamic checklist works out what is still required — by law, by property type, by what
   the analysis found — and explains why, where to get it, and the risk of going without.
7. A 13-section report is generated as HTML and PDF, versioned, with a change log between
   versions.
8. Adding a missing document later re-runs the whole assessment: findings close, new ones
   open, and a new report version explains what changed.

Everything runs locally. With `LLM_PROVIDER=offline` (the default), no document content
leaves the machine and the system is still fully functional — classification, extraction,
cross-verification, the checklist, risk scoring and the report are all deterministic rules.

## Quick start

```bash
./scripts/setup.sh     # Python env, dependencies, database, dashboard build
./scripts/run.sh       # API + folder watcher + workers on http://127.0.0.1:8000
```

Then open <http://127.0.0.1:8000>, create a case, and copy documents into the folder it
shows you. The API documentation is at `/docs`.

To see it work on synthetic documents without supplying your own:

```bash
./scripts/demo.sh
```

### Requirements

| | |
|---|---|
| Python | 3.9 or newer |
| Node.js | 18 or newer (only to build the dashboard) |
| Database | SQLite by default — nothing to install. PostgreSQL via `DATABASE_URL` |
| Document size | **No limit.** Files stream to disk and pages are read one at a time, so memory does not scale with the file |
| OCR | Two options, both fully local: **macOS Vision** (built into macOS, enabled with `pip install ocrmac` — no system install) or **Tesseract** (`brew install tesseract` / `apt-get install tesseract-ocr`). With neither, scanned documents are **flagged for manual review rather than guessed at** |
| Kannada | Digital Kannada PDFs (Bhoomi, Kaveri) need nothing extra. **Scanned** Kannada paper needs Tesseract with the Kannada pack — macOS Vision does not support Kannada. See [docs/LANGUAGES.md](docs/LANGUAGES.md) |

## Layout

```
backend/            FastAPI application, analysis engines, worker pool, folder watcher
  app/services/     extraction · classification · fields · cross-verification ·
                    requirements · risk · reporting · jobs · watcher · LLM providers
  app/rules/        document taxonomy and jurisdiction rule sets (YAML — edit these)
  migrations/       Alembic migrations
  samples/          synthetic property documents for testing
  tests/            70 tests, including one per acceptance scenario
frontend/           React + TypeScript + Tailwind dashboard
docs/               architecture, database, user manual, deployment, security, limitations
scripts/            setup · run · dev · demo
```

## Documentation

| Document | What is in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, the processing pipeline, design decisions |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema, every table and why it exists, migrations |
| [docs/USER_MANUAL.md](docs/USER_MANUAL.md) | Day-to-day use of the dashboard |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Configuration, PostgreSQL, service setup, backups |
| [docs/SECURITY.md](docs/SECURITY.md) | What leaves the machine, access control, untrusted input, retention |
| [docs/LANGUAGES.md](docs/LANGUAGES.md) | Kannada document analysis, the bilingual interface, what is translated and what is not |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | What the system can and cannot establish — read before relying on a report |

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

134 tests. `tests/test_acceptance.py` holds one per scenario in the specification — initial
collection, missing documents, conflicting information, newly added evidence, ownership
history, encumbrance review, unreadable documents, report versioning, case isolation,
evidence traceability, processing failures and honest assessment. `tests/test_watcher.py`
exercises the real filesystem observer and worker pool; `tests/test_kannada.py` covers
Kannada analysis end to end; `tests/test_i18n.py` covers the bilingual interface, API and
report; `tests/test_ocr.py` covers scanned documents.
