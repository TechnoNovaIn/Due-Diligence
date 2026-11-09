export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'informational'

export interface CaseSummary {
  id: string
  case_ref: string
  property_name: string
  address?: string | null
  survey_number?: string | null
  subdivision_number?: string | null
  khata_number?: string | null
  plot_number?: string | null
  flat_number?: string | null
  village?: string | null
  taluk?: string | null
  district?: string | null
  state?: string | null
  jurisdiction_code: string
  property_type: string
  property_classification?: string | null
  land_area_value?: number | null
  land_area_unit?: string | null
  dimensions?: string | null
  claimed_owner?: string | null
  seller_name?: string | null
  buyer_name?: string | null
  transaction_type: string
  purpose?: string | null
  assigned_reviewer?: string | null
  watch_folder: string
  watch_enabled: boolean
  status: string
  overall_risk: Severity
  risk_score: number
  assessment_status?: string | null
  document_collection_status: string
  last_analysis_at?: string | null
  created_at: string
  updated_at: string
  document_count: number
  documents_analysed: number
  documents_pending: number
  open_findings: number
  critical_findings: number
  high_findings: number
  open_requirements: number
  latest_report_version?: number | null
  // Labels resolved by the backend for the requested language.
  status_label?: string | null
  overall_risk_label?: string | null
  property_type_label?: string | null
  transaction_type_label?: string | null
  assessment_status_label?: string | null
}

export interface DocumentRow {
  id: string
  case_id: string
  filename: string
  relative_path: string
  size_bytes: number
  extension?: string | null
  doc_type?: string | null
  doc_type_label?: string | null
  classification_confidence: number
  classification_method?: string | null
  classification_rationale?: string | null
  status: string
  page_count: number
  pages_analysed: number
  extraction_method?: string | null
  extraction_confidence: number
  ocr_used: boolean
  document_date?: string | null
  summary?: string | null
  issues?: { type: string; detail: string; severity: string }[] | null
  analysis?: Record<string, unknown> | null
  version: number
  is_current: boolean
  first_seen_at: string
  processed_at?: string | null
  error?: string | null
  status_label?: string | null
}

export interface ExtractedFieldRow {
  id: number
  field_key: string
  value_raw?: string | null
  value_norm?: string | null
  value_number?: number | null
  unit?: string | null
  page_no?: number | null
  evidence_text?: string | null
  confidence: number
  provenance: string
  extractor: string
  corrected_by_user: boolean
  original_value?: string | null
  document_id: string
}

export interface DocumentDetail extends DocumentRow {
  fields: ExtractedFieldRow[]
  pages: { page_no: number; char_count: number; ocr_used: boolean; confidence: number }[]
}

export interface Evidence {
  document_id?: string | null
  document_name?: string | null
  page_no?: number | null
  quote?: string | null
  note?: string | null
}

export interface Finding {
  id: string
  risk_ref: string
  category: string
  severity: Severity
  title: string
  description: string
  consequence?: string | null
  recommended_action?: string | null
  required_documents?: string[] | null
  confidence: number
  score: number
  confirmed: boolean
  requires_legal_review: boolean
  verification_status: string
  status: string
  resolution_note?: string | null
  first_report_version?: number | null
  detector?: string | null
  evidence: Evidence[]
  created_at: string
  severity_label?: string | null
  category_label?: string | null
  status_label?: string | null
  verification_status_label?: string | null
  untranslated?: boolean
  description_untranslated?: boolean
  description_note?: string | null
}

export interface Requirement {
  id: string
  key: string
  name: string
  category: string
  priority: string
  status: string
  reason?: string | null
  resolves_issue?: string | null
  related_finding_id?: string | null
  period_from?: string | null
  period_to?: string | null
  relates_to?: string | null
  issuing_authority?: string | null
  next_action?: string | null
  risk_if_absent?: string | null
  closure_criteria?: string | null
  satisfied_by_document_id?: string | null
  jurisdiction_confirmed: boolean
  note?: string | null
  updated_at: string
  category_label?: string | null
  priority_label?: string | null
  status_label?: string | null
  untranslated?: boolean
}

export interface OwnershipStep {
  sequence: number
  from_owner?: string | null
  to_owner?: string | null
  transfer_type?: string | null
  transfer_date?: string | null
  document_id?: string | null
  document_name?: string | null
  registration_ref?: string | null
  verification_status: string
  gap_before: boolean
  notes?: string | null
}

export interface ReportRow {
  id: string
  case_id: string
  version: number
  generated_at: string
  assessment_status: string
  overall_risk: Severity
  risk_score: number
  documents_received: number
  documents_analysed: number
  open_requirements: number
  risk_counts?: Record<string, number> | null
  change_summary?: { type: string; detail: string }[] | null
  model_info?: Record<string, unknown> | null
}

export interface ReportDetail extends ReportRow {
  payload: any
}

export interface AuditEvent {
  id: number
  case_id?: string | null
  document_id?: string | null
  event_type: string
  actor: string
  message?: string | null
  payload?: Record<string, unknown> | null
  report_version?: number | null
  model_version?: string | null
  ruleset_version?: string | null
  created_at: string
}

export interface Dashboard {
  totals: Record<string, number>
  cases: {
    id: string; case_ref: string; property_name: string; property_type: string
    status: string; overall_risk: Severity; assessment_status?: string | null
    risk_score: number; open_findings: number; critical: number; high: number
    open_requirements: number; documents: number; last_analysis_at?: string | null
    assigned_reviewer?: string | null
    property_type_label?: string | null; overall_risk_label?: string | null
    assessment_status_label?: string | null
  }[]
  recent_documents: { id: string; case_id: string; case: { case_ref?: string; property_name?: string }
    filename: string; status: string; doc_type?: string | null; first_seen_at: string }[]
  recent_reports: { id: string; case_id: string; case: { case_ref?: string; property_name?: string }
    version: number; generated_at: string; assessment_status: string; overall_risk: Severity }[]
  pending_actions: { case_id: string; case: { case_ref?: string; property_name?: string }
    requirement: string; status: string; next_action?: string | null }[]
}

export interface SystemStatus {
  version: string
  ruleset_version: string
  principal: { username: string; role: string }
  ai: Record<string, any>
  ocr: {
    engine: string; available: boolean; note: string
    languages?: { configured: string[]; readable: string[]; unreadable: string[] }
  }
  watcher: Record<string, any>
  jobs: { running: boolean; queue: Record<string, number>; workers: number }
  storage: Record<string, string>
  limits: Record<string, number | null>
  security: Record<string, boolean>
  languages?: {
    document_type_labels?: { total: number; translated: number }
    requirement_templates?: { total: number; translated: number }
    detectors_translated?: number
    note?: string
  }
}

export interface ReferenceData {
  languages: { code: string; label: string }[]
  property_types: { value: string; label: string; label_kn?: string }[]
  transaction_types: { value: string; label: string; label_kn?: string }[]
  case_statuses: string[]
  severities: string[]
  document_types: { key: string; label: string; label_kn?: string; group: string }[]
  jurisdictions: { code: string; name: string }[]
  vocabularies?: Record<string, Record<string, { en: string; kn: string }>>
}
