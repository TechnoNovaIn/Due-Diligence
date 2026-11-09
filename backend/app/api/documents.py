"""Document endpoints: inventory, detail, preview, corrections, reprocessing."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..enums import DocStatus, JobType, Provenance
from ..models import Case, Document, DocumentPage, ExtractedField
from ..schemas import (
    DocumentDetail,
    DocumentOut,
    DocumentTypeOverride,
    FieldCorrection,
    FieldOut,
)
from ..services import audit as audit_service
from ..services import filesafe
from ..services.jobs import enqueue
from ..services.knowledge import doc_label, doc_types
from .deps import Principal, current_principal, get_case, require_write
from .translate import get_lang, localise_document

router = APIRouter(tags=["documents"])


def _out(doc: Document, lang: str = "en") -> DocumentOut:
    return localise_document(DocumentOut.model_validate(doc), doc, lang)


@router.get("/cases/{case_id}/documents", response_model=List[DocumentOut])
def list_documents(case: Case = Depends(get_case), db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal),
                   status: Optional[str] = None, doc_type: Optional[str] = None,
                   include_superseded: bool = False,
                   lang: str = Depends(get_lang)) -> List[DocumentOut]:
    stmt = select(Document).where(Document.case_id == case.id)
    if not include_superseded:
        stmt = stmt.where(Document.is_current.is_(True))
    if status:
        stmt = stmt.where(Document.status == status)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    docs = db.scalars(stmt.order_by(Document.first_seen_at.desc())).all()
    return [_out(d, lang) for d in docs]


def _get_document(document_id: str, db: Session) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, db: Session = Depends(get_db),
                    principal: Principal = Depends(current_principal),
                    lang: str = Depends(get_lang)) -> DocumentDetail:
    doc = _get_document(document_id, db)
    base = _out(doc, lang).model_dump()
    return DocumentDetail(
        **base,
        fields=[FieldOut.model_validate(f) for f in
                sorted(doc.fields, key=lambda f: (f.field_key, -(f.confidence or 0)))],
        pages=[{"page_no": page.page_no, "char_count": page.char_count,
                "ocr_used": page.ocr_used, "confidence": page.confidence} for page in doc.pages],
    )


@router.get("/documents/{document_id}/pages/{page_no}", response_class=PlainTextResponse)
def page_text(document_id: str, page_no: int, db: Session = Depends(get_db),
              principal: Principal = Depends(current_principal)) -> str:
    page = db.scalars(
        select(DocumentPage).where(DocumentPage.document_id == document_id,
                                   DocumentPage.page_no == page_no)
    ).first()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page.text


@router.get("/documents/{document_id}/file")
def document_file(document_id: str, db: Session = Depends(get_db),
                  principal: Principal = Depends(current_principal)) -> FileResponse:
    """Serve the original file for preview.  The path is re-validated on every request."""
    doc = _get_document(document_id, db)
    settings = get_settings()
    try:
        path = filesafe.resolve_within(Path(doc.abs_path), settings.allowed_watch_roots)
    except filesafe.UnsafePathError:
        raise HTTPException(status_code=403, detail="File is outside the permitted roots")
    if not path.exists():
        raise HTTPException(status_code=404, detail="The file is no longer present on disk")
    media_type = doc.mime_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return FileResponse(str(path), media_type=media_type, filename=doc.filename)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentOut)
def reprocess(document_id: str, db: Session = Depends(get_db),
              principal: Principal = Depends(require_write),
              wait: bool = Query(default=False)) -> DocumentOut:
    doc = _get_document(document_id, db)
    doc.status = DocStatus.QUEUED.value
    doc.error = None
    audit_service.record(db, "document_reprocess_requested", case_id=doc.case_id, document_id=doc.id,
                         actor=principal.username, message="Manual reprocessing requested.")
    if wait:
        from ..services.pipeline import process_document

        db.commit()
        process_document(db, doc.id)
        enqueue(db, JobType.REANALYSE_CASE.value, case_id=doc.case_id,
                dedupe_key="reanalyse:{}".format(doc.case_id), delay_seconds=0.1, priority=200)
        db.commit()
        db.refresh(doc)
        return _out(doc)
    enqueue(db, JobType.PROCESS_DOCUMENT.value, case_id=doc.case_id, document_id=doc.id,
            dedupe_key="process:{}".format(doc.id), priority=50)
    db.commit()
    db.refresh(doc)
    return _out(doc)


@router.post("/documents/{document_id}/type", response_model=DocumentOut)
def set_document_type(document_id: str, payload: DocumentTypeOverride,
                      db: Session = Depends(get_db),
                      principal: Principal = Depends(require_write)) -> DocumentOut:
    """A reviewer's classification overrides the automatic one."""
    doc = _get_document(document_id, db)
    if payload.doc_type not in doc_types():
        raise HTTPException(status_code=400, detail="Unknown document type")
    previous = doc.doc_type
    doc.doc_type = payload.doc_type
    doc.classification_confidence = 1.0
    doc.classification_method = "user"
    doc.classification_rationale = "Set manually by {}.{}".format(
        principal.username, " Note: {}".format(payload.note) if payload.note else "")
    if doc.status == DocStatus.NEEDS_MANUAL_REVIEW.value:
        doc.status = DocStatus.ANALYSED.value
    audit_service.record(db, "document_type_overridden", case_id=doc.case_id, document_id=doc.id,
                         actor=principal.username,
                         message="Document type set to {} (was {}).".format(
                             doc_label(payload.doc_type), doc_label(previous)),
                         payload={"from": previous, "to": payload.doc_type, "note": payload.note})
    enqueue(db, JobType.REANALYSE_CASE.value, case_id=doc.case_id,
            dedupe_key="reanalyse:{}".format(doc.case_id), delay_seconds=0.2, priority=200)
    db.commit()
    db.refresh(doc)
    return _out(doc)


@router.patch("/fields/{field_id}", response_model=FieldOut)
def correct_field(field_id: int, payload: FieldCorrection, db: Session = Depends(get_db),
                  principal: Principal = Depends(require_write)) -> FieldOut:
    """Record a reviewer's correction.  Corrected fields survive reprocessing."""
    field = db.get(ExtractedField, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")
    if field.original_value is None:
        field.original_value = field.value_norm or field.value_raw
    field.value_norm = payload.value
    field.value_raw = payload.value
    field.corrected_by_user = True
    field.provenance = Provenance.USER_CORRECTED.value
    field.confidence = 1.0
    field.extractor = "user"
    audit_service.record(db, "field_corrected", case_id=field.case_id, document_id=field.document_id,
                         actor=principal.username,
                         message="{} corrected to '{}'.".format(field.field_key, payload.value),
                         payload={"field_key": field.field_key, "from": field.original_value,
                                  "to": payload.value, "note": payload.note})
    enqueue(db, JobType.REANALYSE_CASE.value, case_id=field.case_id,
            dedupe_key="reanalyse:{}".format(field.case_id), delay_seconds=0.2, priority=200)
    db.commit()
    db.refresh(field)
    return FieldOut.model_validate(field)


@router.post("/cases/{case_id}/documents/upload", response_model=DocumentOut, status_code=201)
async def upload_document(case: Case = Depends(get_case), db: Session = Depends(get_db),
                          principal: Principal = Depends(require_write),
                          file: UploadFile = File(...)) -> DocumentOut:
    """Optional manual upload - the file is written into the watched folder."""
    settings = get_settings()
    name = Path(file.filename or "upload").name
    if Path(name).suffix.lower() not in filesafe.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    target = Path(case.watch_folder) / name
    counter = 1
    while target.exists():
        target = Path(case.watch_folder) / "{}-{}{}".format(
            Path(name).stem, counter, Path(name).suffix)
        counter += 1
    # Streamed to disk a megabyte at a time, so an upload of any size is handled
    # without holding the file in memory. A limit applies only if one is configured.
    limit = settings.max_file_bytes
    size = 0
    try:
        with open(target, "wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if limit is not None and size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the configured limit of {} MB.".format(
                            settings.max_file_mb))
                fh.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    from ..services.pipeline import ingest_path

    doc = ingest_path(db, case, target, actor=principal.username)
    if doc is None:
        raise HTTPException(status_code=409, detail="The file was ignored (duplicate or unsupported)")
    doc.status = DocStatus.QUEUED.value
    enqueue(db, JobType.PROCESS_DOCUMENT.value, case_id=case.id, document_id=doc.id,
            dedupe_key="process:{}".format(doc.id), priority=50)
    db.commit()
    db.refresh(doc)
    return _out(doc)
