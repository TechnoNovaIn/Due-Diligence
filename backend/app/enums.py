"""Controlled vocabularies shared by the database, the API and the report."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class PropertyType(StrEnum):
    AGRICULTURAL_LAND = "agricultural_land"
    RESIDENTIAL_PLOT = "residential_plot"
    INDEPENDENT_HOUSE = "independent_house"
    APARTMENT = "apartment"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    UNDEVELOPED_LAND = "undeveloped_land"
    UNDER_CONSTRUCTION = "under_construction"


class TransactionType(StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"
    MORTGAGE = "mortgage"
    GIFT = "gift"
    INHERITANCE = "inheritance"
    LEASE = "lease"
    PARTITION = "partition"
    REVIEW_ONLY = "review_only"


class CaseStatus(StrEnum):
    CREATED = "created"
    AWAITING_DOCUMENTS = "awaiting_documents"
    ANALYSING = "analysing"
    REVIEW_READY = "review_ready"
    ON_HOLD = "on_hold"
    CLOSED = "closed"


class DocStatus(StrEnum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    ANALYSED = "analysed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    REMOVED = "removed"
    SUPERSEDED = "superseded"


TERMINAL_DOC_STATUSES = {
    DocStatus.ANALYSED,
    DocStatus.NEEDS_MANUAL_REVIEW,
    DocStatus.FAILED,
    DocStatus.QUARANTINED,
    DocStatus.REMOVED,
    DocStatus.SUPERSEDED,
}


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFORMATIONAL: 4,
}

SEVERITY_WEIGHT = {
    Severity.CRITICAL: 100.0,
    Severity.HIGH: 60.0,
    Severity.MEDIUM: 30.0,
    Severity.LOW: 10.0,
    Severity.INFORMATIONAL: 2.0,
}


class FindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    NOT_APPLICABLE = "not_applicable"
    ACCEPTED = "accepted"


class FindingCategory(StrEnum):
    OWNERSHIP = "ownership"
    PROPERTY_IDENTITY = "property_identity"
    ENCUMBRANCE = "encumbrance"
    LAND_USE = "land_use"
    LEGAL = "legal"
    DOCUMENT_INTEGRITY = "document_integrity"
    FINANCIAL = "financial"
    PROCESS = "process"


class RequirementCategory(StrEnum):
    STATUTORY = "statutory"           # potentially required by applicable law
    CONDITIONAL = "conditional"       # conditionally required for this property
    DISCREPANCY = "discrepancy"       # needed to resolve an identified discrepancy
    RECOMMENDED = "recommended"       # stronger due diligence
    EXTERNAL_CHECK = "external_check"  # external verification not yet performed
    PROFESSIONAL = "professional"     # professional assessment still pending


class RequirementStatus(StrEnum):
    AVAILABLE_ANALYSED = "available_analysed"
    PENDING_COLLECTION = "pending_collection"
    INCOMPLETE = "incomplete"
    PENDING_VERIFICATION = "pending_verification"
    NOT_PERFORMED = "not_performed"
    SATISFIED = "satisfied"
    WAIVED = "waived"


OPEN_REQUIREMENT_STATUSES = {
    RequirementStatus.PENDING_COLLECTION,
    RequirementStatus.INCOMPLETE,
    RequirementStatus.PENDING_VERIFICATION,
    RequirementStatus.NOT_PERFORMED,
}


class Priority(StrEnum):
    MANDATORY = "mandatory"
    CONDITIONAL = "conditional"
    RECOMMENDED = "recommended"
    PROFESSIONAL_ADVICE = "professional_advice"


class Provenance(StrEnum):
    """How a stored fact came to be known - never collapse these."""
    EXPLICIT = "explicit"        # stated verbatim in a document
    INFERRED = "inferred"        # derived by combining documents
    EXTERNAL = "external"        # obtained from an external source
    UNVERIFIED = "unverified"    # asserted but not corroborated
    MISSING = "missing"          # known to be absent / unreadable
    USER_CORRECTED = "user_corrected"


class VerificationStatus(StrEnum):
    DOCUMENTED = "documented"              # a document says so
    CORROBORATED = "corroborated"          # two or more independent documents agree
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"
    NOT_PERFORMED = "not_performed"
    USER_CONFIRMED = "user_confirmed"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    PROCESS_DOCUMENT = "process_document"
    REANALYSE_CASE = "reanalyse_case"
    GENERATE_REPORT = "generate_report"


class Role(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    READONLY = "readonly"


class AssessmentStatus(StrEnum):
    INCOMPLETE = "assessment_incomplete"
    HIGH_RISK = "high_risk_findings_identified"
    FURTHER_VERIFICATION = "further_verification_required"
    NO_MATERIAL_ISSUES = "no_material_issues_identified_in_reviewed_evidence"
    READY_FOR_REVIEW = "ready_for_independent_professional_review"


ASSESSMENT_LABELS = {
    AssessmentStatus.INCOMPLETE: "Assessment Incomplete",
    AssessmentStatus.HIGH_RISK: "High-Risk Findings Identified",
    AssessmentStatus.FURTHER_VERIFICATION: "Further Verification Required",
    AssessmentStatus.NO_MATERIAL_ISSUES: "No Material Issues Identified in Reviewed Evidence",
    AssessmentStatus.READY_FOR_REVIEW: "Ready for Independent Professional Review",
}
