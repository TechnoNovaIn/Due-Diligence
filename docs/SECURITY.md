# Security and privacy

Property files contain names, addresses, identity numbers, financial details and family
arrangements. The design assumes all of it is sensitive.

## What leaves the machine

With the default configuration — **nothing**. `LLM_PROVIDER=offline` means classification,
field extraction, cross-verification, the checklist, risk scoring and the report are all
produced by local rules. There is no telemetry and no outbound request.

A remote provider is used only when **both** of these are set:

```
LLM_PROVIDER=anthropic
ALLOW_REMOTE_AI=true
```

A provider configured without `ALLOW_REMOTE_AI=true` is refused and the system stays
offline, with the reason recorded. When remote processing is active:

| What is sent | When |
|---|---|
| Document text, truncated to `LLM_MAX_CHARS_PER_CALL` (default 60,000 characters) | Classification, when the rules are not confident; document summarisation |
| Extracted field values and document filenames, as JSON | The open-ended cross-document pass |

Never sent: the files themselves, case metadata you entered, the database, or anything
from another case.

This is stated in three places: the System page, the footer of every report, and
`GET /api/system/status`. Each report records the provider and model that produced it.

## Storage

OCR is local whichever engine is in use: Tesseract runs as a local binary, and the macOS
Vision backend calls the recognition engine built into the operating system. No page image
is ever uploaded for recognition. Translation is local too: the Kannada text is a static
catalogue in the repository, not a translation service — no document content is sent
anywhere to be translated.

Documents stay where you put them — the system reads them and never moves, modifies or
deletes them. Extracted text, fields, findings and reports live in `DATA_DIR`.

Identity numbers are masked at extraction. An Aadhaar number becomes `XXXX XXXX ####` and a
PAN becomes `XXXXX####X` before it is written to the database, so the full number never
reaches storage, a report or a log. Identity documents are additionally masked across every
extracted value.

For encryption at rest, use the operating system's facility (FileVault, LUKS, an encrypted
volume) and point `DATA_DIR` at it. Application-level encryption is deliberately not
implemented — it would offer little against an attacker who can read the process memory,
and would complicate backup and recovery.

## Access control

Off by default, because the normal configuration is one reviewer on one machine bound to
`127.0.0.1`. Enable it for anything else:

```
AUTH_ENABLED=true
ADMIN_API_KEY=<a long random string>
```

Then every request needs an `X-API-Key` header. Roles:

| Role | May |
|---|---|
| `admin` | Everything, including system configuration endpoints |
| `reviewer` | Create and edit cases, correct fields, set finding and requirement statuses |
| `readonly` | Read cases, documents, findings, requirements and reports |

Additional users are rows in `users` holding a SHA-256 of their key:

```python
import hashlib, secrets
from app.db import session_scope
from app.models import User

key = secrets.token_urlsafe(32)
with session_scope() as s:
    s.add(User(username="asha", role="reviewer",
               api_key_hash=hashlib.sha256(key.encode()).hexdigest()))
print("give this to the user once:", key)
```

Keys are never stored in plaintext and never returned by the API.

## Untrusted input

**Every document is treated as hostile input.**

*Path handling.* A file path is resolved — following symlinks — and must land under a
configured watch root, or it is refused. Symlinks are never processed. The same check runs
again when a file is served for preview, so a file moved after ingestion cannot be read
through the API.

*File validation.* Extension allow-list, size limit, and magic bytes checked against the
extension. A `.pdf` that is not a PDF is quarantined rather than parsed. No file is ever
executed, and no archive is expanded. `MALWARE_SCAN_COMMAND` adds an external scanner
before the file is opened.

*Prompt injection.* Document text is fenced before it reaches any model; the fence cannot
be closed from inside (a literal `</document>` in the text is neutralised); and the system
prompt states that the fenced material is data, that instructions inside it must never be
acted on, and that the model must not conclude title is clear or a document genuine.
Independently of the model, every document is scanned for text addressed to an automated
system; a hit becomes a **high-severity document-integrity finding** quoting the text, on
the view that such text does not belong in a property document and the original needs to
be examined. The sample document set includes one such file so you can see the behaviour.

*Model output.* Structured output is schema-validated. A model-raised observation is
recorded as unconfirmed, capped in confidence, labelled as such in the report, and cannot
resolve or override a deterministic finding.

## Case isolation

Every row carries `case_id`; every query is scoped to it; search endpoints are per-case and
reject a document id from another case. A test asserts that documents, findings and search
results from one case never appear in another.

## Audit trail

`audit_events` is append-only and records case creation and edits, every document
discovery, replacement, removal and processing outcome, classification overrides, field
corrections, finding and requirement status changes, report generation and job failures.
Each row carries the actor, the ruleset version and the model version in force. The Audit
History tab shows it; `GET /api/cases/{id}/audit` exports it.

## Retention and deletion

Deleting a case removes its database records — documents, pages, fields, findings,
requirements, ownership links and reports — and **leaves every file on disk untouched**,
so the deletion is yours to complete. Rendered reports under `DATA_DIR/reports/<case_ref>/`
are also left in place; remove that directory if you want them gone.

`RETENTION_DAYS` is reserved for automatic purging and is disabled (`0`) by default: in a
due diligence context, silently deleting evidence is worse than keeping it.

## Reporting a problem

Keep the stack trace and the audit events for the case; both are in
`DATA_DIR/logs/duediligence.log`. Do not attach property documents to a bug report.
