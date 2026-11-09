/** Typed client for the backend API. */
import type {
  AuditEvent, CaseSummary, Dashboard, DocumentDetail, DocumentRow, Finding,
  OwnershipStep, ReferenceData, ReportDetail, ReportRow, Requirement, SystemStatus,
} from './types'

const BASE = '/api'

function apiKey(): string | null {
  try {
    return localStorage.getItem('dd_api_key')
  } catch {
    return null
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function currentLang(): string {
  try {
    const stored = localStorage.getItem('dd_lang')
    return stored === 'kn' ? 'kn' : 'en'
  } catch {
    return 'en'
  }
}

/** Append the language the backend should answer in, preserving any existing query. */
function withLang(path: string): string {
  const lang = currentLang()
  if (lang === 'en') return path
  return path + (path.includes('?') ? '&' : '?') + 'lang=' + lang
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  headers.set('Accept-Language', currentLang())
  const key = apiKey()
  if (key) headers.set('X-API-Key', key)

  const response = await fetch(BASE + withLang(path), { ...init, headers })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep statusText */
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  const type = response.headers.get('content-type') || ''
  if (type.includes('application/json')) return response.json() as Promise<T>
  return response.text() as unknown as Promise<T>
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),
  systemStatus: () => request<SystemStatus>('/system/status'),
  reference: () => request<ReferenceData>('/system/reference'),
  dashboard: () => request<Dashboard>('/dashboard'),

  listCases: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
    return request<CaseSummary[]>(`/cases${qs ? `?${qs}` : ''}`)
  },
  getCase: (id: string) => request<CaseSummary>(`/cases/${id}`),
  createCase: (body: Record<string, unknown>) =>
    request<CaseSummary>('/cases', { method: 'POST', body: JSON.stringify(body) }),
  updateCase: (id: string, body: Record<string, unknown>) =>
    request<CaseSummary>(`/cases/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteCase: (id: string) => request<void>(`/cases/${id}`, { method: 'DELETE' }),
  scanCase: (id: string) =>
    request<{ queued: number; removed: number; files_seen: number }>(`/cases/${id}/scan`, { method: 'POST' }),
  reanalyse: (id: string) =>
    request<{ report_version: number }>(`/cases/${id}/reanalyse?wait=true`, { method: 'POST' }),
  caseQueue: (id: string) =>
    request<{ queue: Record<string, number>; runner_running: boolean }>(`/cases/${id}/queue`),
  searchCase: (id: string, q: string) =>
    request<{ pages: any[]; fields: any[] }>(`/cases/${id}/search?q=${encodeURIComponent(q)}`),

  documents: (caseId: string) => request<DocumentRow[]>(`/cases/${caseId}/documents`),
  document: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  pageText: (id: string, page: number) => request<string>(`/documents/${id}/pages/${page}`),
  fileUrl: (id: string) => `${BASE}/documents/${id}/file`,
  reprocess: (id: string) => request<DocumentRow>(`/documents/${id}/reprocess?wait=true`, { method: 'POST' }),
  setDocumentType: (id: string, doc_type: string, note?: string) =>
    request<DocumentRow>(`/documents/${id}/type`, { method: 'POST', body: JSON.stringify({ doc_type, note }) }),
  correctField: (id: number, value: string, note?: string) =>
    request<any>(`/fields/${id}`, { method: 'PATCH', body: JSON.stringify({ value, note }) }),
  upload: (caseId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<DocumentRow>(`/cases/${caseId}/documents/upload`, { method: 'POST', body: form })
  },

  findings: (caseId: string) => request<Finding[]>(`/cases/${caseId}/findings`),
  updateFinding: (id: string, body: Record<string, unknown>) =>
    request<Finding>(`/findings/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  requirements: (caseId: string) => request<Requirement[]>(`/cases/${caseId}/requirements`),
  updateRequirement: (id: string, status: string, note?: string) =>
    request<Requirement>(`/requirements/${id}`, { method: 'PATCH', body: JSON.stringify({ status, note }) }),
  ownership: (caseId: string) => request<OwnershipStep[]>(`/cases/${caseId}/ownership`),

  reports: (caseId: string) => request<ReportRow[]>(`/cases/${caseId}/reports`),
  report: (caseId: string, version: number | 'latest') =>
    request<ReportDetail>(`/cases/${caseId}/reports/${version}`),
  generateReport: (caseId: string) =>
    request<ReportRow>(`/cases/${caseId}/reports`, { method: 'POST' }),
  reportHtmlUrl: (caseId: string, version: number | 'latest') =>
    withLang(`${BASE}/cases/${caseId}/reports/${version}/html`),
  reportPdfUrl: (caseId: string, version: number | 'latest') =>
    withLang(`${BASE}/cases/${caseId}/reports/${version}/pdf`),

  audit: (caseId: string) => request<AuditEvent[]>(`/cases/${caseId}/audit`),
}

export function setApiKey(key: string) {
  try {
    if (key) localStorage.setItem('dd_api_key', key)
    else localStorage.removeItem('dd_api_key')
  } catch {
    /* storage unavailable - the key simply is not remembered */
  }
}
