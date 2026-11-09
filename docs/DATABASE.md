# Database

SQLite by default (`DATA_DIR/duediligence.db`, WAL mode, foreign keys on). Set
`DATABASE_URL=postgresql+psycopg://user:pass@host/db` for PostgreSQL — the models and
migrations are portable.

```bash
cd backend
.venv/bin/python -m alembic upgrade head                      # apply
.venv/bin/python -m alembic revision --autogenerate -m "..."  # after a model change
.venv/bin/python -m alembic downgrade -1                      # roll back one
```

## Tables

### `cases`
One property under investigation. Holds the declared property details (name, address,
survey/subdivision/khata/plot/flat numbers, village/taluk/district/state, type,
classification, extent), the parties (claimed owner, seller, buyer), the transaction type,
the reviewer, the watched folder, and the rolled-up state: `status`, `overall_risk`,
`risk_score`, `assessment_status`, `document_collection_status`, `last_analysis_at`.
`case_ref` is the human reference (`PDD-2026-0001`).

### `documents`
One row per file **per version**. Unique on `(case_id, relative_path, version)`, which is
what stops two concurrent ingests creating duplicate rows. Carries the hash, size, mtime,
MIME type, the classification (type, confidence, method, rationale), the extraction result
(method, page count, pages analysed, confidence, OCR flag), `document_date`, the summary,
the integrity `issues`, the processing `status` and `error`, and `supersedes_id` for a
replaced file.

### `document_pages`
Page-level text with its character count, OCR flag and confidence. This is what makes
"page 3 of the sale deed says…" possible, and what the viewer and search read.

### `extracted_fields`
One atomic fact: `field_key`, raw value, normalised value, numeric value and unit, the
page, the supporting sentence, confidence, `provenance` and which extractor produced it.
`corrected_by_user` marks a reviewer's correction — those survive reprocessing while
machine-extracted fields are replaced.

### `findings` and `finding_evidence`
The risk register. A finding has a stable `fingerprint` (unique per case) so the same issue
is recognised across runs rather than duplicated, a `risk_ref` (`R-001`) for citation,
category, severity, description, consequence, recommended action, the documents it needs,
confidence, whether it is confirmed, whether it needs legal review, its score, and its
lifecycle status with a resolution note. Evidence rows cite document, page and quote.

### `requirements`
The dynamic checklist. Unique on `(case_id, key)`. Category (statutory / conditional /
discrepancy / recommended / external_check / professional), priority, status, the reason,
the issue it resolves, the relevant period, the issuing authority, the next action, the
risk of proceeding without it, and the criteria that close it. `auto_generated` is cleared
when a person sets the status, so the engine stops overwriting their decision.

### `ownership_links`
The reconstructed chain: sequence, from/to owner, transfer type, date, source document,
registration reference, verification status, and whether a gap precedes the step.
Rebuilt on every analysis.

### `reports`
One row per version, with the full JSON payload, the change summary against the previous
version, the paths to the rendered HTML/PDF/JSON, and the AI provider details that applied
at the time.

### `jobs`
The durable queue: type, payload, status, attempts against `max_attempts`, last error,
`dedupe_key` for coalescing, and `scheduled_at` for backoff. Jobs left `running` by an
unclean shutdown are re-queued at start-up.

### `audit_events`
Append-only trail: event type, actor, message, JSON payload, and the report, model and
ruleset versions in force. Used by the Audit History tab.

### `users`
Username, role (`admin` / `reviewer` / `readonly`) and a SHA-256 of the API key. Only
consulted when `AUTH_ENABLED=true`.

## Relationships

```
cases ─┬─< documents ─┬─< document_pages
       │              └─< extracted_fields
       ├─< findings ──< finding_evidence
       ├─< requirements
       ├─< ownership_links
       └─< reports

jobs, audit_events reference a case by id without a cascade, so the history of a deleted
case is not silently destroyed by a foreign key.
```

Deleting a case cascades to its documents, fields, findings, requirements, ownership links
and reports. **Files on disk are never touched.**
