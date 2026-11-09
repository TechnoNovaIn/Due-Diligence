import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Badge, Card, Empty, ErrorNote, Loading } from '../components/ui'
import { formatDateTime, titleCase } from '../format'
import { useAsync } from '../hooks'
import { useLang } from '../i18n'

export default function Cases() {
  const { t, pick } = useLang()
  const [q, setQ] = useState('')
  const [risk, setRisk] = useState('')
  const [propertyType, setPropertyType] = useState('')
  const reference = useAsync(() => api.reference(), [])
  const cases = useAsync(() => api.listCases({ q, risk, property_type: propertyType }),
    [q, risk, propertyType])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t('nav.cases')}</h1>
        <Link to="/cases/new" className="btn btn-primary">{t('dash.newCase')}</Link>
      </div>

      <div className="flex flex-wrap gap-2">
        <input className="input max-w-xs" placeholder={t('cases.search')}
               value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input max-w-[180px]" value={risk} onChange={(e) => setRisk(e.target.value)}>
          <option value="">{t('cases.anyRisk')}</option>
          {(reference.data?.severities ?? []).map((s) => (
            <option key={s} value={s}>
              {pick(titleCase(s), reference.data?.vocabularies?.severity?.[s]?.kn)}
            </option>
          ))}
        </select>
        <select className="input max-w-[220px]" value={propertyType}
                onChange={(e) => setPropertyType(e.target.value)}>
          <option value="">{t('cases.anyType')}</option>
          {(reference.data?.property_types ?? []).map((item) => (
            <option key={item.value} value={item.value}>{pick(item.label, item.label_kn)}</option>
          ))}
        </select>
      </div>

      {cases.loading && !cases.data && <Loading />}
      {cases.error && <ErrorNote error={cases.error} onRetry={cases.reload} />}
      {cases.data && cases.data.length === 0 && (
        <Empty title={t('cases.noMatch')} hint={t('cases.noMatchHint')} />
      )}
      {cases.data && cases.data.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">{t('col.case')}</th><th className="th">{t('col.property')}</th>
                  <th className="th">{t('col.location')}</th>
                  <th className="th">{t('col.documents')}</th><th className="th">{t('col.findings')}</th>
                  <th className="th">{t('col.requirements')}</th><th className="th">{t('col.risk')}</th>
                  <th className="th">{t('col.reviewer')}</th><th className="th">{t('col.updated')}</th>
                </tr>
              </thead>
              <tbody>
                {cases.data.map((c) => (
                  <tr key={c.id} className="hover:bg-panel/60">
                    <td className="td font-mono text-[12px]">
                      <Link className="underline decoration-line underline-offset-2"
                            to={`/cases/${c.id}/overview`}>{c.case_ref}</Link>
                    </td>
                    <td className="td">
                      <div className="font-medium">{c.property_name}</div>
                      <div className="text-[12px] text-muted">
                        {c.property_type_label || titleCase(c.property_type)}
                      </div>
                    </td>
                    <td className="td text-[12.5px]">
                      {[c.survey_number && `Sy. ${c.survey_number}`, c.village, c.district]
                        .filter(Boolean).join(' · ') || '—'}
                    </td>
                    <td className="td">{c.documents_analysed}/{c.document_count}
                      {c.documents_pending > 0 && <span className="ml-1 text-info">(+{c.documents_pending})</span>}
                    </td>
                    <td className="td">{c.open_findings}</td>
                    <td className="td">{c.open_requirements}</td>
                    <td className="td"><Badge severity={c.overall_risk} label={c.overall_risk_label} /></td>
                    <td className="td text-[12.5px]">{c.assigned_reviewer || '—'}</td>
                    <td className="td text-[12.5px] text-muted">{formatDateTime(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
