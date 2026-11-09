import { useCallback, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Badge, ErrorNote, Loading } from '../components/ui'
import { formatDateTime, titleCase } from '../format'
import { useAsync, usePolling } from '../hooks'
import { useLang } from '../i18n'
import ActionsTab from './tabs/ActionsTab'
import AuditTab from './tabs/AuditTab'
import DocumentsTab from './tabs/DocumentsTab'
import DocumentAnalysisTab from './tabs/DocumentAnalysisTab'
import MissingTab from './tabs/MissingTab'
import OverviewTab from './tabs/OverviewTab'
import OwnershipTab from './tabs/OwnershipTab'
import ReportsTab from './tabs/ReportsTab'
import RisksTab from './tabs/RisksTab'
import VerificationTab from './tabs/VerificationTab'

const TABS = ['overview', 'documents', 'analysis', 'ownership', 'verification',
              'risks', 'missing', 'actions', 'reports', 'audit'] as const

export default function CaseWorkspace() {
  const { caseId = '', tab = 'overview' } = useParams()
  const { t } = useLang()
  const navigate = useNavigate()
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const caseState = useAsync(() => api.getCase(caseId), [caseId])
  const queue = useAsync(() => api.caseQueue(caseId), [caseId])
  const [refreshToken, setRefreshToken] = useState(0)

  const refreshAll = useCallback(() => {
    caseState.reload()
    queue.reload()
    setRefreshToken((n) => n + 1)
  }, [caseState, queue])

  const pending = Object.entries(queue.data?.queue ?? {})
    .filter(([status]) => status === 'pending' || status === 'running')
    .reduce((sum, [, count]) => sum + count, 0)
  usePolling(refreshAll, 6000, pending > 0 || (caseState.data?.documents_pending ?? 0) > 0)

  async function run(id: string, label: string, fn: () => Promise<unknown>) {
    setBusy(id)
    setNotice(null)
    try {
      await fn()
      setNotice(`${label} ✓`)
      refreshAll()
    } catch (err) {
      setNotice(`${label}: ${(err as Error).message}`)
    } finally {
      setBusy(null)
    }
  }

  if (caseState.loading && !caseState.data) return <Loading />
  if (caseState.error) return <ErrorNote error={caseState.error} onRetry={caseState.reload} />
  const c = caseState.data
  if (!c) return null

  const content = () => {
    switch (tab) {
      case 'documents': return <DocumentsTab caseId={caseId} refreshToken={refreshToken} onChange={refreshAll} />
      case 'analysis': return <DocumentAnalysisTab caseId={caseId} refreshToken={refreshToken} />
      case 'ownership': return <OwnershipTab caseId={caseId} refreshToken={refreshToken} />
      case 'verification': return <VerificationTab caseId={caseId} refreshToken={refreshToken} />
      case 'risks': return <RisksTab caseId={caseId} refreshToken={refreshToken} onChange={refreshAll} />
      case 'missing': return <MissingTab caseId={caseId} refreshToken={refreshToken} onChange={refreshAll} />
      case 'actions': return <ActionsTab caseId={caseId} refreshToken={refreshToken} />
      case 'reports': return <ReportsTab caseId={caseId} refreshToken={refreshToken} onChange={refreshAll} />
      case 'audit': return <AuditTab caseId={caseId} refreshToken={refreshToken} />
      default: return <OverviewTab caseItem={c} refreshToken={refreshToken} onChange={refreshAll} />
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{c.property_name}</h1>
            <Badge severity={c.overall_risk} label={c.overall_risk_label} />
          </div>
          <p className="mt-1 text-[13px] text-muted">
            <span className="font-mono">{c.case_ref}</span> ·{' '}
            {c.property_type_label || titleCase(c.property_type)} ·{' '}
            {c.transaction_type_label || titleCase(c.transaction_type)} ·{' '}
            {c.assessment_status
              ? c.assessment_status_label || titleCase(c.assessment_status)
              : t('case.notYetAssessed')} ·{' '}
            {t('case.lastAnalysed')} {formatDateTime(c.last_analysis_at)}
          </p>
          <p className="mt-1 font-mono text-[11.5px] text-muted">{c.watch_folder}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" disabled={busy !== null}
                  onClick={() => run('scan', t('case.scanFolder'), () => api.scanCase(caseId))}>
            {busy === 'scan' ? t('case.scanning') : t('case.scanFolder')}
          </button>
          <button className="btn" disabled={busy !== null}
                  onClick={() => run('reanalyse', t('case.reanalyse'), () => api.reanalyse(caseId))}>
            {busy === 'reanalyse' ? t('case.analysing') : t('case.reanalyse')}
          </button>
          <a className="btn" href={api.reportPdfUrl(caseId, 'latest')} target="_blank" rel="noreferrer">
            {t('case.downloadPdf')}
          </a>
          <button className="btn" onClick={() => {
            if (confirm(t('case.deleteConfirm'))) {
              api.deleteCase(caseId).then(() => navigate('/cases'))
            }
          }}>{t('common.delete')}</button>
        </div>
      </div>

      {pending > 0 && (
        <div className="rounded-md border border-info/30 bg-info/5 px-4 py-2 text-[13px]">
          {pending} {t('case.jobsRunning')}
        </div>
      )}
      {notice && <div className="rounded-md border border-line bg-panel px-4 py-2 text-[13px]">{notice}</div>}

      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((key) => (
          <Link key={key} to={`/cases/${caseId}/${key}`}
                className={`tab ${tab === key ? 'tab-active' : ''}`}>
            {t(`tab.${key}`)}
          </Link>
        ))}
      </div>

      {content()}
    </div>
  )
}
