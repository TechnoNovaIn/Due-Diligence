"""In-memory view of one case, assembled from the database for analysis."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..enums import DocStatus
from ..models import Case, Document, ExtractedField
from . import normalize as nz
from .knowledge import doc_label, doc_type_meta, jurisdiction


@dataclass
class FieldValue:
    key: str
    raw: str
    norm: Optional[str]
    number: Optional[float]
    unit: Optional[str]
    page_no: Optional[int]
    evidence: Optional[str]
    confidence: float
    provenance: str
    document_id: str
    document_name: str
    document_type: str

    @property
    def display(self) -> str:
        return self.norm or self.raw


@dataclass
class DocFacts:
    id: str
    filename: str
    relative_path: str
    doc_type: str
    label: str
    status: str
    document_date: Optional[str]
    page_count: int
    pages_analysed: int
    extraction_confidence: float
    classification_confidence: float
    ocr_used: bool
    summary: Optional[str]
    issues: List[Dict[str, Any]] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    fields: Dict[str, List[FieldValue]] = field(default_factory=lambda: defaultdict(list))

    def first(self, key: str) -> Optional[FieldValue]:
        values = self.fields.get(key) or []
        return max(values, key=lambda v: v.confidence) if values else None

    def value(self, key: str) -> Optional[str]:
        v = self.first(key)
        return v.display if v else None

    def all(self, key: str) -> List[FieldValue]:
        return list(self.fields.get(key) or [])

    def has_tag(self, key: str, tag: str) -> bool:
        return any((v.norm or v.raw) == tag for v in self.all(key))

    @property
    def analysed(self) -> bool:
        return self.status == DocStatus.ANALYSED.value

    #: Document types whose own date is the date they were issued, not the date of
    #: any transaction recited inside them.
    ISSUED_RECORD_TYPES = {
        "encumbrance_certificate", "rtc_pahani", "khata_certificate", "khata_extract",
        "mutation_extract", "property_tax_receipt", "land_revenue_receipt", "tax_payment_receipt",
        "legal_heir_certificate", "succession_certificate", "occupancy_certificate",
        "completion_certificate", "commencement_certificate", "rera_registration",
        "survey_record", "village_map", "tippani", "phodi_record", "dues_statement",
        "loan_closure_certificate",
    }

    @property
    def best_date(self) -> Optional[date]:
        if self.doc_type in self.ISSUED_RECORD_TYPES:
            order = ("issue_date", "ec_period_to", "document_date", "registration_date")
        else:
            order = ("execution_date", "registration_date", "document_date", "issue_date")
        for key in order:
            v = self.first(key)
            if v:
                d = nz.parse_date(v.norm or v.raw)
                if d:
                    return d
        return nz.parse_date(self.document_date) if self.document_date else None


@dataclass
class CaseContext:
    case: Case
    docs: List[DocFacts] = field(default_factory=list)
    jurisdiction: Dict[str, Any] = field(default_factory=dict)
    failed_docs: List[DocFacts] = field(default_factory=list)
    pending_docs: List[DocFacts] = field(default_factory=list)

    # -- lookups ---------------------------------------------------------
    @property
    def analysed_docs(self) -> List[DocFacts]:
        return [d for d in self.docs if d.analysed]

    def by_type(self, *types: str) -> List[DocFacts]:
        wanted = set(types)
        return [d for d in self.analysed_docs if d.doc_type in wanted]

    def has_type(self, *types: str) -> bool:
        return bool(self.by_type(*types))

    def values(self, key: str) -> List[FieldValue]:
        out: List[FieldValue] = []
        for d in self.analysed_docs:
            out.extend(d.all(key))
        return out

    def tagged(self, key: str, tag: str) -> List[FieldValue]:
        return [v for v in self.values(key) if (v.norm or v.raw) == tag]

    @property
    def doc_types_present(self) -> Set[str]:
        return {d.doc_type for d in self.analysed_docs}

    @property
    def title_lookback_years(self) -> int:
        return int(self.jurisdiction.get("title_lookback_years", 30))

    @property
    def ec_lookback_years(self) -> int:
        return int(self.jurisdiction.get("ec_lookback_years", 30))

    def authority(self, key: str, default: str = "The relevant issuing authority") -> str:
        return self.jurisdiction.get("authorities", {}).get(key, default)


def build_context(session: Session, case: Case) -> CaseContext:
    """Load every current document of a case together with its evidence-bound fields."""
    documents = session.scalars(
        select(Document).where(Document.case_id == case.id, Document.is_current.is_(True))
    ).all()
    fields = session.scalars(
        select(ExtractedField).where(
            ExtractedField.case_id == case.id, ExtractedField.superseded.is_(False)
        )
    ).all()

    by_doc: Dict[str, List[ExtractedField]] = defaultdict(list)
    for f in fields:
        by_doc[f.document_id].append(f)

    ctx = CaseContext(case=case, jurisdiction=jurisdiction(case.jurisdiction_code))
    for doc in documents:
        facts = DocFacts(
            id=doc.id,
            filename=doc.filename,
            relative_path=doc.relative_path,
            doc_type=doc.doc_type or "unknown",
            label=doc_label(doc.doc_type),
            status=doc.status,
            document_date=doc.document_date,
            page_count=doc.page_count,
            pages_analysed=doc.pages_analysed,
            extraction_confidence=doc.extraction_confidence or 0.0,
            classification_confidence=doc.classification_confidence or 0.0,
            ocr_used=bool(doc.ocr_used),
            summary=doc.summary,
            issues=list(doc.issues or []),
            analysis=dict(doc.analysis or {}),
            fields=defaultdict(list),
        )
        for f in by_doc.get(doc.id, []):
            facts.fields[f.field_key].append(
                FieldValue(
                    key=f.field_key, raw=f.value_raw or "", norm=f.value_norm,
                    number=f.value_number, unit=f.unit, page_no=f.page_no,
                    evidence=f.evidence_text, confidence=f.confidence,
                    provenance=f.provenance, document_id=doc.id,
                    document_name=doc.filename, document_type=facts.doc_type,
                )
            )
        if doc.status in (DocStatus.FAILED.value, DocStatus.QUARANTINED.value,
                          DocStatus.NEEDS_MANUAL_REVIEW.value):
            ctx.failed_docs.append(facts)
        elif doc.status not in (DocStatus.ANALYSED.value, DocStatus.REMOVED.value,
                                DocStatus.SUPERSEDED.value):
            ctx.pending_docs.append(facts)
        ctx.docs.append(facts)
    return ctx


# ---------------------------------------------------------------------------
@dataclass
class Evidence:
    document_id: Optional[str]
    document_name: Optional[str]
    page_no: Optional[int] = None
    quote: Optional[str] = None
    note: Optional[str] = None

    @classmethod
    def from_value(cls, value: FieldValue, note: Optional[str] = None) -> "Evidence":
        return cls(
            document_id=value.document_id, document_name=value.document_name,
            page_no=value.page_no, quote=value.evidence, note=note,
        )

    @classmethod
    def from_doc(cls, doc: DocFacts, note: Optional[str] = None, page_no: Optional[int] = None) -> "Evidence":
        return cls(document_id=doc.id, document_name=doc.filename, page_no=page_no, quote=None, note=note)


@dataclass
class ProposedFinding:
    fingerprint: str
    category: str
    severity: str
    title: str
    description: str
    consequence: str = ""
    recommended_action: str = ""
    required_documents: List[str] = field(default_factory=list)
    confidence: float = 0.6
    confirmed: bool = False
    requires_legal_review: bool = False
    verification_status: str = "unverified"
    evidence: List[Evidence] = field(default_factory=list)
    detector: str = ""
    #: Values the Kannada template re-uses, so a translation does not have to
    #: parse the English prose back apart.
    params: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make_fingerprint(detector: str, *parts: Any) -> str:
        raw = "|".join(str(p or "") for p in parts)
        return "{}:{}".format(detector, hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16])


@dataclass
class ProposedRequirement:
    key: str
    name: str
    category: str
    priority: str
    status: str
    reason: str = ""
    resolves_issue: str = ""
    related_finding_fingerprint: Optional[str] = None
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    relates_to: Optional[str] = None
    issuing_authority: str = ""
    next_action: str = ""
    risk_if_absent: str = ""
    closure_criteria: str = ""
    expected_doc_types: List[str] = field(default_factory=list)
    satisfied_by_document_id: Optional[str] = None
    jurisdiction_confirmed: bool = False
    note: Optional[str] = None
    translations: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OwnershipStep:
    sequence: int
    from_owner: Optional[str]
    to_owner: Optional[str]
    transfer_type: Optional[str]
    transfer_date: Optional[str]
    document_id: Optional[str]
    document_name: Optional[str]
    registration_ref: Optional[str]
    verification_status: str
    gap_before: bool = False
    notes: Optional[str] = None


@dataclass
class AnalysisResult:
    findings: List[ProposedFinding] = field(default_factory=list)
    requirements: List[ProposedRequirement] = field(default_factory=list)
    ownership: List[OwnershipStep] = field(default_factory=list)
    conditions: Set[str] = field(default_factory=set)
    comparisons: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
