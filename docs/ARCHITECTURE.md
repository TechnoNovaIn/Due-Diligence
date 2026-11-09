# Architecture

## Shape of the system

```
                       ┌──────────────────────────────────────────────┐
   case folder ──────► │  WatchService (watchdog observer + sweep)     │
   (user drops files)  │  · debounces until a file stops changing      │
                       │  · periodic reconciliation catches lost events│
                       └───────────────────┬──────────────────────────┘
                                           │ ingest_path()
                                           ▼
                       ┌──────────────────────────────────────────────┐
                       │  Job queue (database table + worker threads)  │
                       │  process_document → reanalyse_case → report   │
                       └───────────────────┬──────────────────────────┘
                                           ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  Document pipeline                                                          │
  │  validate → extract text (+OCR) → classify → extract fields → integrity     │
  └───────────────────┬────────────────────────────────────────────────────────┘
                      ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  Case analysis (runs over ALL documents of the case, never one in isolation)│
  │  cross-verification → requirements engine → risk scoring                    │
  └───────────────────┬────────────────────────────────────────────────────────┘
                      ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  Report builder → payload (13 sections) → HTML + PDF + JSON, versioned      │
  └───────────────────┬────────────────────────────────────────────────────────┘
                      ▼
            FastAPI  ──────►  React dashboard
```

## Components

| Module | Responsibility |
|---|---|
| `services/watcher.py` | One watchdog observer per case folder, a settle loop that waits for copies to finish, and a reconciliation sweep that re-reads every folder on a timer so dropped OS events and offline changes are still picked up. |
| `services/pipeline.py` | Registers a file as a `Document` row (new, replaced → new version, or unchanged → skipped), then runs validation, extraction, classification, field extraction and integrity checks. |
| `services/filesafe.py` | Path containment against the configured roots, magic-byte checks, size limits, symlink refusal, optional external malware scan, ignore rules. |
| `services/extraction/` | PyMuPDF for PDFs with per-page OCR fallback, python-docx for DOCX, salvage readers for RTF/DOC. OCR has two interchangeable backends, tried in order: Tesseract when the binary is present, otherwise the recognition engine built into macOS (via `ocrmac`). Both are local. Page-level text with confidence is preserved for citation. |
| `services/classify.py` | Weighted phrase scoring against the YAML taxonomy; the model is consulted only when the rules waver, and disagreement lowers confidence instead of silently overriding. |
| `services/fields.py` | ~70 labelled and narrative patterns. Every hit carries page, supporting sentence and confidence. Handles boundary context, negated covenants, parent-deed recitals and masking of identity numbers. |
| `services/normalize.py` | Dates (day-first), areas (acre/guntha/cent/sq ft/… → square metres), Indian money grouping, survey-number normalisation, fuzzy name matching — in English **and Kannada**, including Kannada digits, month names, unit names and honorifics. Never delegated to a model. |
| `i18n.py`, `services/findings_i18n.py`, `services/report_i18n.py` | Translation catalogues keyed by the stable identifier the rest of the code already uses — an enum value, a requirement key, a detector name — so nothing is matched on English prose. Coverage is reported honestly; an untranslated string falls back to English and is marked. |
| `services/render_pdf_kn.py` | Kannada PDF via MuPDF's HTML engine, because ReportLab performs no complex-script shaping. |
| `services/crossverify.py` | Seven detector families: ownership, property identity, encumbrance, land use, legal, document integrity, process. Produces findings with evidence and the condition flags that drive the checklist. |
| `services/requirements_engine.py` | Jurisdiction template filtered by property type, transaction type and discovered conditions, plus issue-driven requirements generated from findings. |
| `services/risk.py` | Explainable scoring and the overall classification. |
| `services/analysis.py` | Reconciles each run against stored state: new findings open, absent ones are marked resolved with an explanation, requirements that stop applying are waived rather than deleted. |
| `services/report.py` | Builds the 13-section payload, diffs it against the previous version, and renders HTML, PDF and JSON. |
| `services/jobs.py` | Database-backed queue with worker threads, retries with exponential backoff, deduplication and coalescing. |
| `api/` | FastAPI routers with API-key authentication and role checks. |

## The pipeline, step by step

1. **Detect** — observer event or sweep; the file must be unchanged for `FILE_SETTLE_SECONDS`.
2. **Identify** — SHA-256. Identical content already analysed in the case is skipped; a
   changed hash at the same path creates a new version and supersedes the old row.
3. **Validate** — extension allow-list, size limit, magic bytes against the extension,
   symlink refusal, optional virus scan. A mismatch is quarantined, not read.
4. **Extract** — native text first; a page with fewer than `OCR_MIN_CHARS_PER_PAGE`
   characters is rasterised and sent to whichever OCR engine is available. If none is, the
   page is recorded as unread. Nothing is inferred about pages that could not be read.
5. **Classify** — rule scoring; below 0.55 confidence the type is recorded as `unknown`
   and the document is sent to manual review.
6. **Extract fields** — evidence-bound hits, normalised deterministically.
7. **Analyse the document** — integrity observations (missing pages, absent annexures,
   unreadable pages, low OCR confidence, text addressed to an automated system).
8. **Analyse the case** — only once no document is still in flight. All detectors run over
   the whole case.
9. **Evaluate requirements** — template plus issue-driven, with statuses.
10. **Score risk** — per finding, then the overall classification.
11. **Report** — new version, diffed against the last, rendered to HTML/PDF/JSON.
12. **Audit** — every step writes an event with the ruleset and model version.

## Design decisions

**Deterministic core, optional model.** Dates, areas, money, identifiers and every
comparison are computed by rules, so two runs over the same documents give the same
answer and every finding can be explained. A language model, when configured, adds
narrative summaries, assists classification when the rules are uncertain, and takes one
open-ended pass over the extracted evidence. Its output is labelled as unconfirmed and
cannot change a deterministic finding.

**Evidence or nothing.** `ExtractedField` stores the document, page, supporting sentence,
confidence and provenance (`explicit` / `inferred` / `external` / `unverified` / `missing` /
`user_corrected`). A finding without evidence is a finding about an absence, and says so.

**Absence is not a defect.** Missing documents become requirements with a reason, a source
and a stated risk — never a conclusion that something is wrong.

**History is never erased.** Findings are resolved or superseded with an explanation;
requirements are waived with a note; replaced documents keep their earlier version; every
report version is retained with a change log.

**Case isolation.** Every row carries `case_id` and every query is scoped to it; the search
endpoints are per-case. A test asserts that one case cannot surface another's text.

**Documents are untrusted input.** Content is fenced before it reaches any model, the fence
cannot be closed from inside, and text that reads as an instruction is reported as a
document-integrity finding rather than acted on.

## Technology

Python 3.9+ · FastAPI · SQLAlchemy 2 · Alembic · watchdog · PyMuPDF · python-docx ·
Tesseract or macOS Vision for OCR (either, both optional) · ReportLab · Jinja2 ·
Anthropic SDK (optional) ·
React 18 · TypeScript · Tailwind · Vite.

SQLite is the default so the system runs with no infrastructure; `DATABASE_URL` switches
to PostgreSQL without code changes.
