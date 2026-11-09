import { api } from '../../api'
import { Callout, Card, Empty, Loading } from '../../components/ui'
import { formatDate, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'

export default function OwnershipTab({ caseId, refreshToken }: { caseId: string; refreshToken: number }) {
  const { t } = useLang()
  const links = useAsync(() => api.ownership(caseId), [caseId, refreshToken])

  if (links.loading && !links.data) return <Loading />
  const steps = links.data ?? []

  return (
    <div className="space-y-5">
      <Callout>
        {t('ownership.note')}
      </Callout>
      <p className="text-[12.5px] text-muted">{t('common.sourceScript')}</p>

      {steps.length === 0 ? (
        <Empty title={t('ownership.none')} hint={t('ownership.noneHint')} />
      ) : (
        <Card title={t('ownership.chain')}>
          <ol className="space-y-0">
            {steps.map((s) => (
              <li key={s.sequence} className="relative border-l-2 border-line pb-6 pl-5 last:pb-0">
                <span className={`absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-white
                  ${s.gap_before ? 'bg-critical' : 'bg-ink'}`} />
                {s.gap_before && (
                  <div className="mb-2 rounded-md border border-critical/30 bg-critical/5 px-3 py-1.5 text-[12.5px]">
                    <strong className="text-critical">{t('ownership.gapBefore')}</strong> {s.notes}
                  </div>
                )}
                <div className="text-[14px] font-medium">
                  {s.from_owner || '—'} <span className="text-muted">→</span> {s.to_owner || '—'}
                </div>
                <div className="mt-0.5 text-[12.5px] text-muted">
                  {s.transfer_type} · {formatDate(s.transfer_date)} ·{' '}
                  {s.document_name ?? t('ownership.noDocument')} · {s.registration_ref || '—'} ·{' '}
                  {titleCase(s.verification_status)}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}
