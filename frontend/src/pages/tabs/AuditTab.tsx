import { useState } from 'react'
import { api } from '../../api'
import { Card, Empty, Loading } from '../../components/ui'
import { formatDateTime, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'

export default function AuditTab({ caseId, refreshToken }: { caseId: string; refreshToken: number }) {
  const { t } = useLang()
  const events = useAsync(() => api.audit(caseId), [caseId, refreshToken])
  const [filter, setFilter] = useState('')

  if (events.loading && !events.data) return <Loading />
  const rows = (events.data ?? []).filter(
    (e) => !filter || e.event_type.includes(filter) || (e.message ?? '').toLowerCase().includes(filter.toLowerCase()))

  return (
    <div className="space-y-4">
      <input className="input max-w-sm" placeholder={t('audit.filter')}
             value={filter} onChange={(e) => setFilter(e.target.value)} />
      {rows.length === 0 ? <Empty title={t('audit.none')} /> : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr><th className="th">{t('col.when')}</th><th className="th">{t('col.event')}</th>
                    <th className="th">{t('col.actor')}</th>
                    <th className="th">{t('col.detail')}</th><th className="th">{t('col.versions')}</th></tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id}>
                    <td className="td whitespace-nowrap text-[12.5px] text-muted">{formatDateTime(e.created_at)}</td>
                    <td className="td font-medium">{titleCase(e.event_type)}</td>
                    <td className="td text-[12.5px]">{e.actor}</td>
                    <td className="td text-[12.5px]">{e.message}</td>
                    <td className="td text-[11.5px] text-muted">
                      {e.report_version && <>report v{e.report_version}<br /></>}
                      {e.model_version && <>model {e.model_version}<br /></>}
                      {e.ruleset_version}
                    </td>
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
