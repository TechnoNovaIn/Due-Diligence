"""Document processing pipeline (file event -> analysed document).

Steps, in order: detect, validate, extract, classify, extract fields, analyse
individually, then hand the case to the cross-document engine.  Every step
records its outcome; a failure preserves whatever was already extracted and
leaves the job retryable.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..enums import CaseStatus, DocStatus, JobType, Provenance
from ..models import Case, Document, DocumentPage, ExtractedField
from . import audit, filesafe
from . import normalize as nz
from .classify import classify
from .extraction import extract_document
from .fields import detect_integrity_issues, extract_fields
from .knowledge import SENSITIVE_TYPES, doc_label
from .llm import get_llm
from .llm.prompts import scan_for_injection

log = logging.getLogger(__name__)

#: Ingestion of one case is serialised in-process; the unique constraint on
#: (case_id, relative_path, version) is the guard against anything else.
_case_locks = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def case_lock(case_id: str) -> threading.Lock:
    with _locks_guard:
        return _case_locks[case_id]


def _insert_document(session: Session, doc: Document) -> Optional[Document]:
    """Insert a document row, tolerating a concurrent insert of the same file."""
    try:
        with session.begin_nested():
            session.add(doc)
            session.flush()
    except IntegrityError:
        log.debug("Concurrent ingest detected for %s; keeping the existing row.", doc.relative_path)
        return None
    return doc


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def ingest_path(session: Session, case: Case, path: Path, actor: str = "watcher") -> Optional[Document]:
    """Register (or update) a file found in the case folder.  Returns the row to process."""
    settings = get_settings()
    try:
        resolved = filesafe.resolve_within(path, settings.allowed_watch_roots)
    except filesafe.UnsafePathError as exc:
        log.warning("Rejected path outside the permitted roots: %s", exc)
        audit.record(session, "file_rejected", case_id=case.id, actor=actor, message=str(exc))
        return None

    if filesafe.is_ignored(resolved):
        return None
    if not resolved.exists():
        return None

    rel = filesafe.safe_relpath(resolved, Path(case.watch_folder))
    stat = resolved.stat()

    existing = session.scalars(
        select(Document).where(
            Document.case_id == case.id,
            Document.relative_path == rel,
            Document.is_current.is_(True),
        )
    ).first()

    try:
        digest = filesafe.sha256_file(resolved)
    except OSError as exc:
        log.warning("Could not hash %s: %s", resolved, exc)
        return None

    # Same content already processed under this case - nothing to do.
    duplicate = session.scalars(
        select(Document).where(
            Document.case_id == case.id,
            Document.sha256 == digest,
            Document.is_current.is_(True),
            Document.status.in_([DocStatus.ANALYSED.value, DocStatus.NEEDS_MANUAL_REVIEW.value]),
        )
    ).first()
    if duplicate and (existing is None or duplicate.id == getattr(existing, "id", None)):
        if existing and existing.id == duplicate.id:
            return None
        if duplicate.relative_path != rel:
            audit.record(session, "duplicate_file_ignored", case_id=case.id, document_id=duplicate.id,
                         actor=actor,
                         message="{} has the same content as {} and was not processed again.".format(
                             rel, duplicate.relative_path))
            return None

    if existing is None:
        doc = _insert_document(session, Document(
            case_id=case.id, filename=resolved.name, relative_path=rel, abs_path=str(resolved),
            sha256=digest, size_bytes=stat.st_size, mtime=stat.st_mtime,
            extension=resolved.suffix.lower(), status=DocStatus.DISCOVERED.value,
        ))
        if doc is None:
            return None
        audit.record(session, "document_discovered", case_id=case.id, document_id=doc.id, actor=actor,
                     message="New file detected: {}".format(rel),
                     payload={"sha256": digest, "size": stat.st_size})
        if case.status == CaseStatus.CREATED.value:
            case.status = CaseStatus.ANALYSING.value
        return doc

    if existing.sha256 == digest and existing.status == DocStatus.ANALYSED.value:
        return None

    if existing.sha256 != digest:
        # The file was replaced: keep the old record as a superseded version.
        existing.is_current = False
        existing.status = DocStatus.SUPERSEDED.value
        session.flush()
        doc = _insert_document(session, Document(
            case_id=case.id, filename=resolved.name, relative_path=rel, abs_path=str(resolved),
            sha256=digest, size_bytes=stat.st_size, mtime=stat.st_mtime,
            extension=resolved.suffix.lower(), status=DocStatus.DISCOVERED.value,
            version=existing.version + 1, supersedes_id=existing.id,
        ))
        if doc is None:
            return None
        audit.record(session, "document_replaced", case_id=case.id, document_id=doc.id, actor=actor,
                     message="{} was replaced; version {} created.".format(rel, doc.version),
                     payload={"previous_sha256": existing.sha256, "sha256": digest})
        return doc

    existing.abs_path = str(resolved)
    existing.size_bytes = stat.st_size
    existing.mtime = stat.st_mtime
    return existing


def mark_missing_documents(session: Session, case: Case, actor: str = "watcher") -> List[Document]:
    """Flag documents whose file has disappeared from the folder."""
    removed = []
    for doc in session.scalars(
        select(Document).where(Document.case_id == case.id, Document.is_current.is_(True))
    ).all():
        if doc.status == DocStatus.REMOVED.value:
            continue
        if not Path(doc.abs_path).exists():
            doc.status = DocStatus.REMOVED.value
            doc.is_current = False
            removed.append(doc)
            audit.record(session, "document_removed", case_id=case.id, document_id=doc.id, actor=actor,
                         message="{} is no longer present in the case folder.".format(doc.relative_path))
    return removed


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
def process_document(session: Session, document_id: str, use_llm: bool = True) -> Dict[str, Any]:
    settings = get_settings()
    doc = session.get(Document, document_id)
    if doc is None:
        return {"ok": False, "error": "document not found"}

    case = session.get(Case, doc.case_id)
    doc.status = DocStatus.PROCESSING.value
    doc.attempts += 1
    doc.error = None
    session.flush()

    path = Path(doc.abs_path)
    # -- step 1/2: validation -------------------------------------------
    if not path.exists():
        return _fail(session, doc, "The file is no longer present at {}.".format(doc.relative_path),
                     status=DocStatus.REMOVED.value)

    check = filesafe.check_file(path, max_mb=settings.max_file_mb,
                                scan_command=settings.malware_scan_command)
    if not check.ok:
        status = DocStatus.QUARANTINED.value if check.quarantine else DocStatus.FAILED.value
        return _fail(session, doc, check.reason or "File validation failed.", status=status)
    doc.mime_type = check.mime

    # -- step 3: extraction ---------------------------------------------
    extraction = extract_document(
        path,
        ocr_enabled=settings.ocr_enabled,
        ocr_language=settings.ocr_language,
        ocr_dpi=settings.ocr_dpi,
        ocr_min_chars=settings.ocr_min_chars_per_page,
        max_pages=settings.max_pages_per_document,
    )
    doc.extraction_method = extraction.method
    doc.ocr_used = extraction.ocr_used
    doc.page_count = extraction.page_count
    doc.char_count = extraction.char_count
    doc.extraction_confidence = extraction.confidence

    _replace_pages(session, doc, extraction)

    if not extraction.ok:
        doc.issues = [{"type": "unreadable", "detail": extraction.error or "Text could not be extracted.",
                       "severity": "high"}] + [
            {"type": "extraction_note", "detail": i, "severity": "low"} for i in extraction.issues]
        return _fail(session, doc,
                     extraction.error or "No text could be extracted from this document.",
                     status=DocStatus.NEEDS_MANUAL_REVIEW.value)

    doc.pages_analysed = len([p for p in extraction.pages if p.char_count >= 40])

    # -- untrusted content check -----------------------------------------
    injection_hits = scan_for_injection(extraction.text)

    # -- step 4: classification ------------------------------------------
    llm = get_llm() if use_llm else None
    result = classify(extraction.text, doc.filename, llm=llm)
    doc.doc_type = result.doc_type
    doc.classification_confidence = result.confidence
    doc.classification_method = result.method
    doc.classification_rationale = result.rationale

    # -- step 5: structured extraction ------------------------------------
    hits = extract_fields(extraction.pages, result.doc_type)
    _replace_fields(session, doc, hits)
    doc.document_date = _document_date(hits, result.doc_type)

    # -- step 6: individual analysis ---------------------------------------
    issues = detect_integrity_issues(extraction.pages, extraction.issues)
    for snippet in injection_hits:
        issues.append({
            "type": "prompt_injection",
            "detail": "The document contains text that reads as an instruction to an automated system: "
                      "“{}”".format(snippet[:200]),
            "severity": "high",
        })
    doc.issues = issues

    analysis: Dict[str, Any] = {"analysed_by": "deterministic rules"}
    if llm is not None and llm.available:
        known = "; ".join(
            "{}={}".format(h.key, h.value_norm or h.value_raw) for h in hits[:40]
        )
        try:
            summary = llm.summarise_document(doc_label(result.doc_type), extraction.text, known)
        except Exception as exc:  # pragma: no cover - provider failure
            log.warning("Model summary failed for %s: %s", doc.filename, exc)
            summary = None
        if summary:
            analysis.update(summary)
            analysis["analysed_by"] = "{} ({})".format(llm.name, llm.model)
            doc.summary = summary.get("purpose")
    if not doc.summary:
        doc.summary = _rule_summary(doc, hits)
    doc.analysis = analysis

    doc.status = (DocStatus.NEEDS_MANUAL_REVIEW.value
                  if result.needs_manual_review or result.doc_type == "unknown"
                  else DocStatus.ANALYSED.value)
    doc.processed_at = datetime.utcnow()
    doc.verification_status = "documented"

    audit.record(
        session, "document_processed", case_id=doc.case_id, document_id=doc.id,
        message="{} classified as {} ({:.0%}); {} field(s) extracted from {} page(s).".format(
            doc.filename, doc_label(doc.doc_type), doc.classification_confidence, len(hits),
            doc.page_count),
        payload={
            "doc_type": doc.doc_type,
            "classification_method": doc.classification_method,
            "extraction_method": doc.extraction_method,
            "ocr_used": doc.ocr_used,
            "fields": len(hits),
            "issues": [i.get("type") for i in issues],
            "status": doc.status,
        },
        model_version=(llm.model if llm and llm.available else "offline"),
    )
    return {"ok": True, "document_id": doc.id, "status": doc.status, "fields": len(hits),
            "doc_type": doc.doc_type}


def _fail(session: Session, doc: Document, message: str, status: str) -> Dict[str, Any]:
    doc.status = status
    doc.error = message
    doc.processed_at = datetime.utcnow()
    audit.record(session, "document_processing_failed", case_id=doc.case_id, document_id=doc.id,
                 message="{}: {}".format(doc.filename, message), payload={"status": status})
    log.warning("Document %s (%s) -> %s: %s", doc.filename, doc.id, status, message)
    return {"ok": False, "document_id": doc.id, "status": status, "error": message}


def _replace_pages(session: Session, doc: Document, extraction) -> None:
    for page in list(doc.pages):
        session.delete(page)
    session.flush()
    for page in extraction.pages:
        session.add(DocumentPage(
            document_id=doc.id, page_no=page.page_no, text=page.text,
            char_count=page.char_count, ocr_used=page.ocr_used, confidence=page.confidence,
        ))


def _replace_fields(session: Session, doc: Document, hits) -> None:
    """Replace machine-extracted fields, preserving user corrections."""
    corrected = {}
    for existing in list(doc.fields):
        if existing.corrected_by_user:
            corrected[existing.field_key] = existing
            continue
        session.delete(existing)
    session.flush()

    sensitive = doc.doc_type in SENSITIVE_TYPES
    for hit in hits:
        if hit.key in corrected:
            continue
        value_raw = hit.value_raw
        value_norm = hit.value_norm
        if sensitive:
            value_raw = nz.mask_sensitive(value_raw)
            value_norm = nz.mask_sensitive(value_norm or "")
        session.add(ExtractedField(
            case_id=doc.case_id, document_id=doc.id, field_key=hit.key,
            value_raw=value_raw, value_norm=value_norm, value_number=hit.value_number,
            unit=hit.unit, page_no=hit.page_no, evidence_text=(hit.evidence or "")[:1500],
            confidence=hit.confidence, provenance=hit.provenance or Provenance.EXPLICIT.value,
            extractor=hit.extractor,
        ))


ISSUED_RECORD_TYPES = {
    "encumbrance_certificate", "rtc_pahani", "khata_certificate", "khata_extract",
    "mutation_extract", "property_tax_receipt", "land_revenue_receipt", "tax_payment_receipt",
    "legal_heir_certificate", "succession_certificate", "occupancy_certificate",
    "completion_certificate", "commencement_certificate", "rera_registration", "survey_record",
    "village_map", "tippani", "phodi_record", "dues_statement", "loan_closure_certificate",
}


def _document_date(hits, doc_type: str = "") -> Optional[str]:
    order = (("issue_date", "ec_period_to", "document_date", "registration_date")
             if doc_type in ISSUED_RECORD_TYPES
             else ("execution_date", "registration_date", "document_date", "issue_date"))
    for key in order:
        for hit in hits:
            if hit.key == key:
                iso = nz.iso_date(hit.value_norm or hit.value_raw)
                if iso:
                    return iso
    return None


def _rule_summary(doc: Document, hits) -> str:
    by_key: Dict[str, str] = {}
    for hit in hits:
        by_key.setdefault(hit.key, hit.value_norm or hit.value_raw)
    bits = ["Classified as {}".format(doc_label(doc.doc_type))]
    if by_key.get("party_seller") or by_key.get("party_buyer"):
        bits.append("between {} and {}".format(by_key.get("party_seller", "an unnamed party"),
                                               by_key.get("party_buyer", "an unnamed party")))
    if doc.doc_type in ISSUED_RECORD_TYPES:
        if by_key.get("issue_date"):
            bits.append("issued {}".format(nz.format_date(by_key["issue_date"])))
        elif by_key.get("ec_period_to"):
            bits.append("certifying the period up to {}".format(nz.format_date(by_key["ec_period_to"])))
    elif by_key.get("execution_date"):
        bits.append("executed {}".format(nz.format_date(by_key["execution_date"])))
    if by_key.get("survey_number"):
        bits.append("covering Sy. No. {}".format(by_key["survey_number"]))
    if by_key.get("property_area"):
        bits.append("measuring {}".format(by_key["property_area"]))
    if by_key.get("consideration_amount"):
        bits.append("for a stated consideration of {}".format(by_key["consideration_amount"]))
    return ", ".join(bits) + "."
