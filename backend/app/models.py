"""SQLAlchemy ORM models.

Design notes
------------
* Every case owns its documents, fields, findings, requirements and reports via
  a mandatory ``case_id`` foreign key.  Case isolation is enforced at query
  level by :func:`app.services.repo.case_scoped`.
* Extracted facts are never flattened into free text: each one keeps its source
  document, page and supporting quote so that any statement in the report can be
  traced back to evidence.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import (
    CaseStatus,
    DocStatus,
    FindingStatus,
    JobStatus,
    Priority,
    Provenance,
    RequirementStatus,
    Role,
    Severity,
    VerificationStatus,
)


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    type_annotation_map = {Dict[str, Any]: JSON, List[Any]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    property_name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    survey_number: Mapped[Optional[str]] = mapped_column(String(80))
    subdivision_number: Mapped[Optional[str]] = mapped_column(String(80))
    khata_number: Mapped[Optional[str]] = mapped_column(String(80))
    plot_number: Mapped[Optional[str]] = mapped_column(String(80))
    flat_number: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(120))
    taluk: Mapped[Optional[str]] = mapped_column(String(120))
    district: Mapped[Optional[str]] = mapped_column(String(120))
    state: Mapped[Optional[str]] = mapped_column(String(120))
    jurisdiction_code: Mapped[str] = mapped_column(String(10), default="KA")

    property_type: Mapped[str] = mapped_column(String(40), nullable=False)
    property_classification: Mapped[Optional[str]] = mapped_column(String(80))
    land_area_value: Mapped[Optional[float]] = mapped_column(Float)
    land_area_unit: Mapped[Optional[str]] = mapped_column(String(30))
    dimensions: Mapped[Optional[str]] = mapped_column(String(255))

    claimed_owner: Mapped[Optional[str]] = mapped_column(String(255))
    seller_name: Mapped[Optional[str]] = mapped_column(String(255))
    buyer_name: Mapped[Optional[str]] = mapped_column(String(255))
    transaction_type: Mapped[str] = mapped_column(String(40), default="purchase")
    purpose: Mapped[Optional[str]] = mapped_column(Text)
    assigned_reviewer: Mapped[Optional[str]] = mapped_column(String(120))

    watch_folder: Mapped[str] = mapped_column(Text, nullable=False)
    watch_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(32), default=CaseStatus.CREATED.value)
    overall_risk: Mapped[str] = mapped_column(String(20), default=Severity.INFORMATIONAL.value)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    assessment_status: Mapped[Optional[str]] = mapped_column(String(64))
    document_collection_status: Mapped[str] = mapped_column(String(40), default="not_started")
    last_analysis_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    documents: Mapped[List["Document"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    findings: Mapped[List["Finding"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    requirements: Mapped[List["Requirement"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    ownership_links: Mapped[List["OwnershipLink"]] = relationship(back_populates="case", cascade="all, delete-orphan")

    @property
    def case_dir_name(self) -> str:
        return self.case_ref


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_case_status", "case_id", "status"),
        Index("ix_documents_case_hash", "case_id", "sha256"),
        # Two concurrent ingests of the same file must not create two rows.
        UniqueConstraint("case_id", "relative_path", "version", name="uq_document_version"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    abs_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[Optional[str]] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mtime: Mapped[Optional[float]] = mapped_column(Float)
    extension: Mapped[Optional[str]] = mapped_column(String(16))
    mime_type: Mapped[Optional[str]] = mapped_column(String(80))

    doc_type: Mapped[Optional[str]] = mapped_column(String(80))
    doc_subtype: Mapped[Optional[str]] = mapped_column(String(80))
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classification_method: Mapped[Optional[str]] = mapped_column(String(40))
    classification_rationale: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(32), default=DocStatus.DISCOVERED.value)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    pages_analysed: Mapped[int] = mapped_column(Integer, default=0)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(40))
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    document_date: Mapped[Optional[str]] = mapped_column(String(20))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    issues: Mapped[Optional[List[Any]]] = mapped_column(JSON, default=list)

    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(32))
    verification_status: Mapped[str] = mapped_column(String(32), default=VerificationStatus.UNVERIFIED.value)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    case: Mapped[Case] = relationship(back_populates="documents")
    pages: Mapped[List["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_no"
    )
    fields: Mapped[List["ExtractedField"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no", name="uq_page_per_document"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    document: Mapped[Document] = relationship(back_populates="pages")


class ExtractedField(Base, TimestampMixin):
    """One atomic, evidence-bound fact extracted from one document."""

    __tablename__ = "extracted_fields"
    __table_args__ = (Index("ix_fields_case_key", "case_id", "field_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    value_raw: Mapped[Optional[str]] = mapped_column(Text)
    value_norm: Mapped[Optional[str]] = mapped_column(Text)
    value_number: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(30))

    page_no: Mapped[Optional[int]] = mapped_column(Integer)
    evidence_text: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    provenance: Mapped[str] = mapped_column(String(24), default=Provenance.EXPLICIT.value)
    extractor: Mapped[str] = mapped_column(String(24), default="rules")

    corrected_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    original_value: Mapped[Optional[str]] = mapped_column(Text)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[Document] = relationship(back_populates="fields")


# ---------------------------------------------------------------------------
# Findings / risk register
# ---------------------------------------------------------------------------
class Finding(Base, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("case_id", "fingerprint", name="uq_finding_per_case"),
        Index("ix_findings_case_severity", "case_id", "severity"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    risk_ref: Mapped[str] = mapped_column(String(20), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(120), nullable=False)

    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    consequence: Mapped[Optional[str]] = mapped_column(Text)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    required_documents: Mapped[Optional[List[Any]]] = mapped_column(JSON, default=list)

    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_legal_review: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(32), default=VerificationStatus.UNVERIFIED.value)

    status: Mapped[str] = mapped_column(String(24), default=FindingStatus.OPEN.value)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    first_report_version: Mapped[Optional[int]] = mapped_column(Integer)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    detector: Mapped[Optional[str]] = mapped_column(String(60))
    #: {"kn": {"title": ..., "description": ...}} - absent keys fall back to English.
    translations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    case: Mapped[Case] = relationship(back_populates="findings")
    evidence: Mapped[List["FindingEvidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    document_name: Mapped[Optional[str]] = mapped_column(String(512))
    page_no: Mapped[Optional[int]] = mapped_column(Integer)
    quote: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)

    finding: Mapped[Finding] = relationship(back_populates="evidence")


# ---------------------------------------------------------------------------
# Requirements (dynamic missing-document checklist)
# ---------------------------------------------------------------------------
class Requirement(Base, TimestampMixin):
    __tablename__ = "requirements"
    __table_args__ = (UniqueConstraint("case_id", "key", name="uq_requirement_per_case"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(160), nullable=False)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default=Priority.RECOMMENDED.value)
    status: Mapped[str] = mapped_column(String(32), default=RequirementStatus.PENDING_COLLECTION.value)

    reason: Mapped[Optional[str]] = mapped_column(Text)
    resolves_issue: Mapped[Optional[str]] = mapped_column(Text)
    related_finding_id: Mapped[Optional[str]] = mapped_column(String(32))
    period_from: Mapped[Optional[str]] = mapped_column(String(20))
    period_to: Mapped[Optional[str]] = mapped_column(String(20))
    relates_to: Mapped[Optional[str]] = mapped_column(Text)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(300))
    next_action: Mapped[Optional[str]] = mapped_column(Text)
    risk_if_absent: Mapped[Optional[str]] = mapped_column(Text)
    closure_criteria: Mapped[Optional[str]] = mapped_column(Text)
    expected_doc_types: Mapped[Optional[List[Any]]] = mapped_column(JSON, default=list)

    satisfied_by_document_id: Mapped[Optional[str]] = mapped_column(String(32))
    jurisdiction_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[Optional[str]] = mapped_column(Text)
    #: {"kn": {"name": ..., "reason": ...}} - absent keys fall back to English.
    translations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    case: Mapped[Case] = relationship(back_populates="requirements")


# ---------------------------------------------------------------------------
# Ownership timeline
# ---------------------------------------------------------------------------
class OwnershipLink(Base, TimestampMixin):
    __tablename__ = "ownership_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    from_owner: Mapped[Optional[str]] = mapped_column(String(300))
    to_owner: Mapped[Optional[str]] = mapped_column(String(300))
    transfer_type: Mapped[Optional[str]] = mapped_column(String(80))
    transfer_date: Mapped[Optional[str]] = mapped_column(String(20))
    document_id: Mapped[Optional[str]] = mapped_column(String(32))
    document_name: Mapped[Optional[str]] = mapped_column(String(512))
    registration_ref: Mapped[Optional[str]] = mapped_column(String(160))
    verification_status: Mapped[str] = mapped_column(String(32), default=VerificationStatus.DOCUMENTED.value)
    gap_before: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    case: Mapped[Case] = relationship(back_populates="ownership_links")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_report_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    assessment_status: Mapped[str] = mapped_column(String(64))
    overall_risk: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    documents_received: Mapped[int] = mapped_column(Integer, default=0)
    documents_analysed: Mapped[int] = mapped_column(Integer, default=0)
    open_requirements: Mapped[int] = mapped_column(Integer, default=0)
    risk_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    change_summary: Mapped[Optional[List[Any]]] = mapped_column(JSON, default=list)
    html_path: Mapped[Optional[str]] = mapped_column(Text)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text)
    json_path: Mapped[Optional[str]] = mapped_column(Text)
    model_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    case: Mapped[Case] = relationship(back_populates="reports")


# ---------------------------------------------------------------------------
# Jobs / audit / users
# ---------------------------------------------------------------------------
class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_sched", "status", "scheduled_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[Optional[str]] = mapped_column(String(32))
    document_id: Mapped[Optional[str]] = mapped_column(String(32))
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(200))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_case_time", "case_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(32))
    document_id: Mapped[Optional[str]] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), default="system")
    message: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    report_version: Mapped[Optional[int]] = mapped_column(Integer)
    model_version: Mapped[Optional[str]] = mapped_column(String(80))
    ruleset_version: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=Role.REVIEWER.value)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
