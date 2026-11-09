import { useState } from 'react'
import { api } from '../../api'
import { Badge, Card, Empty, Loading } from '../../components/ui'
import { formatDateTime, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'

export default function ReportsTab({ caseId, refreshToken, onChange }: {
  caseId: string; refreshToken: number; onChange: () => void
}) {
  const { t, lang } = useLang()
  const reports = useAsync(() => api.reports(caseId), [caseId, refreshToken])
  const [selected, setSelected] = useState<number | 'latest'>('latest')
  const [busy, setBusy] = useState(false)

  async function regenerate() {
    setBusy(true)
    try {
      await api.generateReport(caseId)
      reports.reload()
      onChange()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (reports.loading && !reports.data) return <Loading />
  const rows = reports.data ?? []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" onClick={regenerate} disabled={busy}>
          {busy ? t('reports.generating') : t('reports.generate')}
        </button>
        {rows.length > 0 && (
          <>
            <a className="btn" href={api.reportPdfUrl(caseId, selected)} target="_blank" rel="noreferrer">
              {t('case.downloadPdf')}
            </a>
            <a className="btn" href={api.reportHtmlUrl(caseId, selected)} target="_blank" rel="noreferrer">
              {t('reports.openFull')}
            </a>
            <select className="input max-w-[200px]" value={String(selected)}
                    onChange={(e) => setSelected(e.target.value === 'latest' ? 'latest' : Number(e.target.value))}>
              <option value="latest">{t('reports.latestVersion')}</option>
              {rows.map((r) => (
                <option key={r.id} value={r.version}>{t('reports.version')} {r.version}</option>
              ))}
            </select>
          </>
        )}
      </div>

      {rows.length === 0 ? (
        <Empty title={t('reports.none')} hint={t('reports.noneHint')} />
      ) : (
        <>
          <Card title={t('reports.history')}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">{t('col.version')}</th><th className="th">{t('col.generated')}</th>
                    <th className="th">{t('col.assessment')}</th><th className="th">{t('col.risk')}</th>
                    <th className="th">{t('col.documents')}</th>
                    <th className="th">{t('dash.openRequirements')}</th>
                    <th className="th">{t('col.changed')}</th><th className="th">{t('col.export')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="td font-mono">{r.version}</td>
                      <td className="td text-[12.5px]">{formatDateTime(r.generated_at)}</td>
                      <td className="td text-[12.5px]">{titleCase(r.assessment_status)}</td>
                      <td className="td"><Badge severity={r.overall_risk} /></td>
                      <td className="td">{r.documents_analysed}/{r.documents_received}</td>
                      <td className="td">{r.open_requirements}</td>
                      <td className="td text-[12.5px]">
                        <ul className="space-y-0.5">
                          {(r.change_summary ?? []).slice(0, 6).map((c, i) => (
                            <li key={i}><span className="text-muted">{titleCase(c.type)}:</span> {c.detail}</li>
                          ))}
                        </ul>
                      </td>
                      <td className="td">
                        <a className="underline decoration-line underline-offset-2"
                           href={api.reportPdfUrl(caseId, r.version)} target="_blank" rel="noreferrer">PDF</a>
                        {' · '}
                        <a className="underline decoration-line underline-offset-2"
                           href={api.reportHtmlUrl(caseId, r.version)} target="_blank" rel="noreferrer">HTML</a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title={t('reports.preview')}>
            <iframe title={t('reports.preview')} key={lang}
                    className="h-[900px] w-full rounded-md border border-line"
                    src={api.reportHtmlUrl(caseId, selected)} />
          </Card>
        </>
      )}
    </div>
  )
}
