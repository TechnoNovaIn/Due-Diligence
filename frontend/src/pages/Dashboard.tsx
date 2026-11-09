import { Link } from 'react-router-dom'
import { api } from '../api'
import { Badge, Card, Empty, ErrorNote, Loading, Stat } from '../components/ui'
import { formatDateTime, titleCase } from '../format'
import { useAsync, usePolling } from '../hooks'
import { useLang } from '../i18n'

export default function Dashboard() {
  const { t } = useLang()
  const { data, error, loading, reload } = useAsync(() => api.dashboard(), [])
  usePolling(reload, 15000)

  if (loading && !data) return <Loading />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!data) return null

  const totals = data.totals
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t('dash.title')}</h1>
        <Link to="/cases/new" className="btn btn-primary">{t('dash.newCase')}</Link>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <Stat value={totals.cases} label={t('dash.totalCases')} />
        <Stat value={totals.under_analysis} label={t('dash.underAnalysis')} />
        <Stat value={totals.awaiting_documents} label={t('dash.awaitingDocuments')} />
        <Stat value={totals.with_critical_risks} label={t('dash.criticalRisks')}
              tone={totals.with_critical_risks ? 'text-critical' : ''} />
        <Stat value={totals.with_high_findings} label={t('dash.highFindings')}
              tone={totals.with_high_findings ? 'text-high' : ''} />
        <Stat value={totals.ready_for_professional_review} label={t('dash.readyForReview')} />
        <Stat value={totals.open_requirements} label={t('dash.openRequirements')} />
      </div>

      <Card title={t('dash.propertyCases')}>
        {data.cases.length === 0 ? (
          <Empty title={t('dash.noCases')} hint={t('dash.noCasesHint')} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">{t('col.case')}</th>
                  <th className="th">{t('col.property')}</th>
                  <th className="th">{t('col.type')}</th>
                  <th className="th">{t('col.docs')}</th>
                  <th className="th">{t('col.openFindings')}</th>
                  <th className="th">{t('col.requirements')}</th>
                  <th className="th">{t('col.risk')}</th>
                  <th className="th">{t('col.assessment')}</th>
                  <th className="th">{t('col.lastAnalysed')}</th>
                </tr>
              </thead>
              <tbody>
                {data.cases.map((c) => (
                  <tr key={c.id} className="hover:bg-panel/60">
                    <td className="td font-mono text-[12px]">
                      <Link className="underline decoration-line underline-offset-2" to={`/cases/${c.id}/overview`}>
                        {c.case_ref}
                      </Link>
                    </td>
                    <td className="td font-medium">{c.property_name}</td>
                    <td className="td">{c.property_type_label || titleCase(c.property_type)}</td>
                    <td className="td">{c.documents}</td>
                    <td className="td">
                      {c.open_findings}
                      {c.critical > 0 && <span className="ml-2 text-critical">{c.critical} critical</span>}
                      {c.high > 0 && <span className="ml-2 text-high">{c.high} high</span>}
                    </td>
                    <td className="td">{c.open_requirements}</td>
                    <td className="td"><Badge severity={c.overall_risk} label={c.overall_risk_label} /></td>
                    <td className="td text-[12.5px]">
                      {c.assessment_status_label || titleCase(c.assessment_status)}
                    </td>
                    <td className="td text-[12.5px] text-muted">{formatDateTime(c.last_analysis_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title={t('dash.recentDocuments')}>
          {data.recent_documents.length === 0 ? <p className="text-[13px] text-muted">{t('dash.nothingYet')}</p> : (
            <ul className="space-y-2.5">
              {data.recent_documents.map((d) => (
                <li key={d.id} className="text-[13px]">
                  <Link className="font-medium underline decoration-line underline-offset-2" to={`/documents/${d.id}`}>
                    {d.filename}
                  </Link>
                  <div className="text-[12px] text-muted">
                    {d.case.case_ref} · {titleCase(d.doc_type)} · {titleCase(d.status)} · {formatDateTime(d.first_seen_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t('dash.recentReports')}>
          {data.recent_reports.length === 0 ? <p className="text-[13px] text-muted">{t('dash.nothingYet')}</p> : (
            <ul className="space-y-2.5">
              {data.recent_reports.map((r) => (
                <li key={r.id} className="text-[13px]">
                  <Link className="font-medium underline decoration-line underline-offset-2"
                        to={`/cases/${r.case_id}/reports`}>
                    {r.case.case_ref} — version {r.version}
                  </Link>
                  <div className="text-[12px] text-muted">
                    {titleCase(r.assessment_status)} · {formatDateTime(r.generated_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t('dash.pendingActions')}>
          {data.pending_actions.length === 0 ? <p className="text-[13px] text-muted">{t('dash.noneOutstanding')}</p> : (
            <ul className="space-y-2.5">
              {data.pending_actions.map((a, i) => (
                <li key={i} className="text-[13px]">
                  <Link className="font-medium underline decoration-line underline-offset-2"
                        to={`/cases/${a.case_id}/missing`}>
                    {a.requirement}
                  </Link>
                  <div className="text-[12px] text-muted">{a.case.case_ref} · {titleCase(a.status)}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
