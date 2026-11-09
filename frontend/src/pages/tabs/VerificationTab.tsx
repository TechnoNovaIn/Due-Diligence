import { api } from '../../api'
import { Card, Empty, Loading } from '../../components/ui'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'

export default function VerificationTab({ caseId, refreshToken }: { caseId: string; refreshToken: number }) {
  const { t } = useLang()
  const report = useAsync(() => api.report(caseId, 'latest').catch(() => null),
    [caseId, refreshToken])
  const section = report.data?.payload?.section_6_cross_verification
  const consolidated = report.data?.payload?.section_2_property_details?.from_documents ?? []

  if (report.loading) return <Loading />
  if (!section) return <Empty title={t('verify.none')} />

  return (
    <div className="space-y-5">
      <p className="text-[12.5px] text-muted">{t('common.sourceScript')}</p>
      <Card title={t('verify.comparison')}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr><th className="th">{t('col.field')}</th><th className="th">{t('col.consistent')}</th>
                  <th className="th">{t('col.valuesAndSources')}</th></tr>
            </thead>
            <tbody>
              {section.comparisons.map((c: any, i: number) => (
                <tr key={i} className={c.consistent ? '' : 'bg-medium/5'}>
                  <td className="td font-medium">{c.label}</td>
                  <td className="td">
                    {c.consistent
                      ? <span className="text-low">{t('verify.consistent')}</span>
                      : <span className="font-semibold text-medium">{t('verify.differs')}</span>}
                  </td>
                  <td className="td">
                    {c.values.length === 0 && <span className="text-muted">{t('verify.notStated')}</span>}
                    {c.values.map((v: any, k: number) => (
                      <div key={k} className="mb-1">
                        <strong>{v.value}</strong>{' '}
                        <span className="text-[12px] text-muted">
                          — {v.documents.join(', ')}{v.pages?.length ? ` (p. ${v.pages.join(', ')})` : ''}
                        </span>
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={t('verify.consolidated')}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr><th className="th">{t('col.field')}</th><th className="th">{t('col.value')}</th>
                  <th className="th">{t('col.status')}</th><th className="th">{t('col.source')}</th></tr>
            </thead>
            <tbody>
              {consolidated.map((r: any, i: number) => (
                <tr key={i}>
                  <td className="td">{r.label}</td>
                  <td className="td font-medium">{r.value ?? '—'}</td>
                  <td className="td">
                    <span className={
                      r.status === 'conflicting' ? 'text-high font-semibold'
                        : r.status === 'corroborated' ? 'text-low'
                        : r.status === 'missing' ? 'text-muted' : ''
                    }>{r.status}</span>
                  </td>
                  <td className="td text-[12px] text-muted">
                    {r.sources?.length ? r.sources.join('; ') : r.note}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
