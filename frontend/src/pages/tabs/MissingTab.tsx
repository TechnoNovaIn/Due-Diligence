import { useState } from 'react'
import { api } from '../../api'
import { Callout, Card, Empty, Loading, Pill } from '../../components/ui'
import { formatDate, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'
import type { Requirement } from '../../types'

const ORDER = ['statutory', 'conditional', 'discrepancy', 'recommended', 'external_check', 'professional']
const STATUSES = ['pending_collection', 'incomplete', 'pending_verification', 'not_performed',
                  'available_analysed', 'satisfied', 'waived']

export default function MissingTab({ caseId, refreshToken, onChange }: {
  caseId: string; refreshToken: number; onChange: () => void
}) {
  const { t, lang } = useLang()
  const reference = useAsync(() => api.reference(), [])
  const reqs = useAsync(() => api.requirements(caseId), [caseId, refreshToken])
  const statusLabel = (value: string) =>
    (lang === 'kn' && reference.data?.vocabularies?.requirement_status?.[value]?.kn)
    || titleCase(value)
  const [showClosed, setShowClosed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  async function update(r: Requirement, status: string) {
    const note = window.prompt(`${r.name} — ${t('missing.notePrompt')}`) ?? ''
    setBusy(r.id)
    try {
      await api.updateRequirement(r.id, status, note)
      reqs.reload()
      onChange()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  if (reqs.loading && !reqs.data) return <Loading />
  const all = reqs.data ?? []
  const openStatuses = new Set(['pending_collection', 'incomplete', 'pending_verification', 'not_performed'])
  const visible = all.filter((r) => showClosed || openStatuses.has(r.status))
  const grouped = ORDER.map((category) => ({
    category,
    rows: visible.filter((r) => r.category === category),
  })).filter((g) => g.rows.length)

  return (
    <div className="space-y-5">
      <Callout>
        {t('missing.note')}
      </Callout>

      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} />
        {t('missing.showClosed')}
      </label>

      {grouped.length === 0 && <Empty title={t('missing.none')} />}

      {grouped.map((group) => (
        <Card key={group.category} title={t(`missing.group.${group.category}`)}>
          <div className="space-y-4">
            {group.rows.map((r) => (
              <div key={r.id} className="border-b border-line pb-4 last:border-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{r.name}</div>
                    <div className="mt-0.5 flex flex-wrap gap-1.5">
                      <Pill tone={r.priority === 'mandatory' ? 'text-critical font-semibold' : ''}>
                        {r.priority_label || titleCase(r.priority)}
                      </Pill>
                      <Pill>{r.status_label || titleCase(r.status)}</Pill>
                      {!r.jurisdiction_confirmed && <Pill>{t('missing.jurisdictionNotConfirmed')}</Pill>}
                      {r.untranslated && lang === 'kn' && <Pill>{t('common.untranslated')}</Pill>}
                    </div>
                  </div>
                  <select className="input w-[200px] py-1 text-[12px]" value={r.status}
                          disabled={busy === r.id} onChange={(e) => update(r, e.target.value)}>
                    {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                  </select>
                </div>

                <dl className="mt-2 grid gap-x-6 gap-y-1 text-[13px] sm:grid-cols-2">
                  {r.reason && <div><span className="label">{t('missing.whyRequired')}</span><div>{r.reason}</div></div>}
                  {r.resolves_issue && (
                    <div><span className="label">{t('missing.resolves')}</span><div>{r.resolves_issue}</div></div>)}
                  {(r.period_from || r.relates_to) && (
                    <div><span className="label">{t('missing.period')}</span>
                      <div>{r.period_from
                        ? `${formatDate(r.period_from)} to ${formatDate(r.period_to)}`
                        : r.relates_to}</div></div>)}
                  {r.issuing_authority && (
                    <div><span className="label">{t('missing.whereToObtain')}</span><div>{r.issuing_authority}</div></div>)}
                  {r.next_action && (
                    <div><span className="label">{t('missing.nextAction')}</span><div>{r.next_action}</div></div>)}
                  {r.risk_if_absent && (
                    <div><span className="label">{t('missing.riskIfAbsent')}</span>
                      <div>{r.risk_if_absent}</div></div>)}
                  {r.closure_criteria && (
                    <div className="sm:col-span-2"><span className="label">{t('missing.closesWhen')}</span>
                      <div>{r.closure_criteria}</div></div>)}
                  {r.note && (
                    <div className="sm:col-span-2 text-muted"><span className="label">{t('missing.note_')}</span>
                      <div>{r.note}</div></div>)}
                </dl>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}
