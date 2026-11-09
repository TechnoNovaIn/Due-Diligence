"""API request / response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
class CaseCreate(BaseModel):
    property_name: str = Field(min_length=1, max_length=255)
    property_type: str
    transaction_type: str = "purchase"
    address: Optional[str] = None
    survey_number: Optional[str] = None
    subdivision_number: Optional[str] = None
    khata_number: Optional[str] = None
    plot_number: Optional[str] = None
    flat_number: Optional[str] = None
    village: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    jurisdiction_code: Optional[str] = None
    property_classification: Optional[str] = None
    land_area_value: Optional[float] = None
    land_area_unit: Optional[str] = None
    dimensions: Optional[str] = None
    claimed_owner: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    purpose: Optional[str] = None
    assigned_reviewer: Optional[str] = None
    watch_folder: Optional[str] = None
    watch_enabled: bool = True


class CaseUpdate(BaseModel):
    property_name: Optional[str] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    address: Optional[str] = None
    survey_number: Optional[str] = None
    subdivision_number: Optional[str] = None
    khata_number: Optional[str] = None
    plot_number: Optional[str] = None
    flat_number: Optional[str] = None
    village: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    jurisdiction_code: Optional[str] = None
    property_classification: Optional[str] = None
    land_area_value: Optional[float] = None
    land_area_unit: Optional[str] = None
    dimensions: Optional[str] = None
    claimed_owner: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    purpose: Optional[str] = None
    assigned_reviewer: Optional[str] = None
    status: Optional[str] = None
    watch_enabled: Optional[bool] = None


class CaseOut(ORMModel):
    id: str
    case_ref: str
    property_name: str
    address: Optional[str] = None
    survey_number: Optional[str] = None
    subdivision_number: Optional[str] = None
    khata_number: Optional[str] = None
    plot_number: Optional[str] = None
    flat_number: Optional[str] = None
    village: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    jurisdiction_code: str
    property_type: str
    property_classification: Optional[str] = None
    land_area_value: Optional[float] = None
    land_area_unit: Optional[str] = None
    dimensions: Optional[str] = None
    claimed_owner: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    transaction_type: str
    purpose: Optional[str] = None
    assigned_reviewer: Optional[str] = None
    watch_folder: str
    watch_enabled: bool
    status: str
    overall_risk: str
    risk_score: float
    assessment_status: Optional[str] = None
    document_collection_status: str
    last_analysis_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # --- localised labels ---
    status_label: Optional[str] = None
    overall_risk_label: Optional[str] = None
    property_type_label: Optional[str] = None
    transaction_type_label: Optional[str] = None
    assessment_status_label: Optional[str] = None


class LocalisedMixin(BaseModel):
    """Labels resolved for the requested language, alongside the raw enum values."""
    untranslated: bool = False


class CaseSummary(CaseOut):
    document_count: int = 0
    documents_analysed: int = 0
    documents_pending: int = 0
    open_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    open_requirements: int = 0
    latest_report_version: Optional[int] = None


# ---------------------------------------------------------------------------
class FieldOut(ORMModel):
    id: int
    field_key: str
    value_raw: Optional[str] = None
    value_norm: Optional[str] = None
    value_number: Optional[float] = None
    unit: Optional[str] = None
    page_no: Optional[int] = None
    evidence_text: Optional[str] = None
    confidence: float
    provenance: str
    extractor: str
    corrected_by_user: bool
    original_value: Optional[str] = None
    document_id: str


class DocumentOut(ORMModel):
    id: str
    case_id: str
    filename: str
    relative_path: str
    sha256: Optional[str] = None
    size_bytes: int
    extension: Optional[str] = None
    mime_type: Optional[str] = None
    doc_type: Optional[str] = None
    doc_type_label: Optional[str] = None
    classification_confidence: float
    classification_method: Optional[str] = None
    classification_rationale: Optional[str] = None
    status: str
    page_count: int
    pages_analysed: int
    extraction_method: Optional[str] = None
    extraction_confidence: float
    ocr_used: bool
    document_date: Optional[str] = None
    summary: Optional[str] = None
    issues: Optional[List[Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    version: int
    is_current: bool
    first_seen_at: datetime
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
    status_label: Optional[str] = None


class DocumentDetail(DocumentOut):
    fields: List[FieldOut] = []
    pages: List[Dict[str, Any]] = []


class FieldCorrection(BaseModel):
    value: str
    note: Optional[str] = None


class DocumentTypeOverride(BaseModel):
    doc_type: str
    note: Optional[str] = None


# ---------------------------------------------------------------------------
class EvidenceOut(ORMModel):
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page_no: Optional[int] = None
    quote: Optional[str] = None
    note: Optional[str] = None


class FindingOut(ORMModel):
    id: str
    risk_ref: str
    category: str
    severity: str
    title: str
    description: str
    consequence: Optional[str] = None
    recommended_action: Optional[str] = None
    required_documents: Optional[List[Any]] = None
    confidence: float
    score: float
    confirmed: bool
    requires_legal_review: bool
    verification_status: str
    status: str
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    first_report_version: Optional[int] = None
    detector: Optional[str] = None
    evidence: List[EvidenceOut] = []
    created_at: datetime
    # --- localised labels ---
    severity_label: Optional[str] = None
    category_label: Optional[str] = None
    status_label: Optional[str] = None
    verification_status_label: Optional[str] = None
    #: True when no Kannada rendering exists for this finding at all.
    untranslated: bool = False
    #: True when the title and action are translated but the description is not.
    description_untranslated: bool = False
    description_note: Optional[str] = None


class FindingUpdate(BaseModel):
    status: Optional[str] = None
    resolution_note: Optional[str] = None
    verification_status: Optional[str] = None


class RequirementOut(ORMModel):
    id: str
    key: str
    name: str
    category: str
    priority: str
    status: str
    reason: Optional[str] = None
    resolves_issue: Optional[str] = None
    related_finding_id: Optional[str] = None
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    relates_to: Optional[str] = None
    issuing_authority: Optional[str] = None
    next_action: Optional[str] = None
    risk_if_absent: Optional[str] = None
    closure_criteria: Optional[str] = None
    expected_doc_types: Optional[List[Any]] = None
    satisfied_by_document_id: Optional[str] = None
    jurisdiction_confirmed: bool
    note: Optional[str] = None
    updated_at: datetime
    # --- localised labels ---
    category_label: Optional[str] = None
    priority_label: Optional[str] = None
    status_label: Optional[str] = None
    untranslated: bool = False


class RequirementUpdate(BaseModel):
    status: str
    note: Optional[str] = None


class OwnershipOut(ORMModel):
    sequence: int
    from_owner: Optional[str] = None
    to_owner: Optional[str] = None
    transfer_type: Optional[str] = None
    transfer_date: Optional[str] = None
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    registration_ref: Optional[str] = None
    verification_status: str
    gap_before: bool
    notes: Optional[str] = None


class ReportOut(ORMModel):
    id: str
    case_id: str
    version: int
    generated_at: datetime
    assessment_status: str
    overall_risk: str
    risk_score: float
    documents_received: int
    documents_analysed: int
    open_requirements: int
    risk_counts: Optional[Dict[str, Any]] = None
    change_summary: Optional[List[Any]] = None
    html_path: Optional[str] = None
    pdf_path: Optional[str] = None
    json_path: Optional[str] = None
    model_info: Optional[Dict[str, Any]] = None


class ReportDetail(ReportOut):
    payload: Dict[str, Any]


class AuditOut(ORMModel):
    id: int
    case_id: Optional[str] = None
    document_id: Optional[str] = None
    event_type: str
    actor: str
    message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    report_version: Optional[int] = None
    model_version: Optional[str] = None
    ruleset_version: Optional[str] = None
    created_at: datetime
