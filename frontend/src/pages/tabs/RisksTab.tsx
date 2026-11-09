import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Badge, Card, Callout, Empty, ErrorNote, Loading } from '../../components/ui'
import { percent, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'
import type { Finding } from '../../types'

const STATUSES = ['open', 'resolved', 'accepted', 'not_applicable', 'superseded']

export default function RisksTab({ caseId, refreshToken, onChange }: {
  caseId: string; refreshToken: number; onChange: () => void
}) {
  const { t, lang } = useLang()
  const reference = useAsync(() => api.reference(), [])
  const statusLabel = (value: string) =>
    (lang === 'kn' && reference.data?.vocabularies?.finding_status?.[value]?.kn) || titleCase(value)
  const findings = useAsync(() => api.findings(caseId), [caseId, refreshToken])
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('open')
  const [busy, setBusy] = useState<string | null>(null)

  async function update(f: Finding, next: string) {
    const note = next === 'open' ? '' : window.prompt(`${f.risk_ref}: ${t('risks.statusPrompt')}`) ?? ''
    setBusy(f.id)
    try {
      await api.updateFinding(f.id, { status: next, resolution_note: note })
      findings.reload()
      onChange()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const rows = (findings.data ?? []).filter(
    (f) => (!severity || f.severity === severity) && (!status || f.status === status))

  return (
    <div className="space-y-5">
      <Callout>
        {t('risks.note')}
      </Callout>

      <div className="flex flex-wrap gap-2">
        <select className="input max-w-[200px]" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">{t('risks.anySeverity')}</option>
          {['critical', 'high', 'medium', 'low', 'informational'].map((s) =>
            <option key={s} value={s}>{titleCase(s)}</option>)}
        </select>
        <select className="input max-w-[200px]" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t('risks.anyStatus')}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
        </select>
      </div>

      {findings.loading && !findings.data && <Loading />}
      {findings.error && <ErrorNote error={findings.error} onRetry={findings.reload} />}
      {findings.data && rows.length === 0 && (
        <Empty title={t('risks.noMatch')} hint={t('risks.noMatchHint')} />
      )}

      <div className="space-y-4">
        {rows.map((f) => (
          <Card key={f.id}
                title={<span className="flex flex-wrap items-center gap-2">
                  <Badge severity={f.severity} label={f.severity_label} />
                  <span className="font-mono text-[12px]">{f.risk_ref}</span>
                  <span>{f.title}</span>
                </span>}
                actions={<span className="flex items-center gap-2 text-[12px] text-muted">
                  {f.confirmed ? t('risks.confirmed') : t('risks.suspected')} · {percent(f.confidence)}
                  <select className="input w-[150px] py-1" value={f.status} disabled={busy === f.id}
                          onChange={(e) => update(f, e.target.value)}>
                    {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                  </select>
                </span>}>
            <p className="text-[13px]">
              {f.description}
              {f.description_untranslated && (
                <span className="ml-1.5 align-middle rounded border border-line bg-panel px-1 py-0.5
                                 text-[10px] uppercase tracking-wider text-muted"
                      title={f.description_note ?? ''}>
                  {t('common.untranslated')}
                </span>
              )}
            </p>
            {f.consequence && (
              <p className="mt-2 text-[13px]"><span className="label">{t('col.impact')}</span><br />{f.consequence}</p>
            )}
            {f.recommended_action && (
              <p className="mt-2 text-[13px]"><span className="label">{t('col.action')}</span><br />{f.recommended_action}</p>
            )}
            {f.required_documents?.length ? (
              <div className="mt-2">
                <span className="label">{t('risks.documentsRequired')}</span>
                <ul className="mt-1 list-disc pl-5 text-[13px]">
                  {f.required_documents.map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              </div>
            ) : null}
            {f.evidence.length > 0 && (
              <div className="mt-3">
                <span className="label">{t('col.evidence')}</span>
                <div className="text-[11.5px] text-muted">{t('common.sourceScript')}</div>
                {f.evidence.map((e, i) => (
                  <div key={i} className="mt-1.5 text-[13px]">
                    {e.document_id ? (
                      <Link className="font-medium underline decoration-line underline-offset-2"
                            to={`/documents/${e.document_id}${e.page_no ? `?page=${e.page_no}` : ''}`}>
                        {e.document_name}{e.page_no ? ` — page ${e.page_no}` : ''}
                      </Link>
                    ) : <span className="font-medium">{e.document_name ?? 'No document'}</span>}
                    {e.note && <div className="text-[12px] text-muted">{e.note}</div>}
                    {e.quote && <div className="evidence">“{e.quote}”</div>}
                  </div>
                ))}
              </div>
            )}
            <p className="mt-3 text-[11.5px] text-muted">
              {t('risks.verification')}: {f.verification_status_label || titleCase(f.verification_status)}
              {' · '}{t('overview.score')} {f.score}
              {f.requires_legal_review && <> · <strong>{t('risks.requiresLegalReview')}</strong></>}
              {f.first_report_version && <> · {t('risks.firstReported')} {f.first_report_version}</>}
            </p>
            {f.resolution_note && (
              <p className="mt-1 text-[12px] text-muted">{t('risks.resolution')}: {f.resolution_note}</p>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
