import { api } from '../../api'
import { Badge, Callout, Card, Field, Loading, Stat } from '../../components/ui'
import { formatDateTime, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'
import type { CaseSummary } from '../../types'

export default function OverviewTab({ caseItem, refreshToken }: {
  caseItem: CaseSummary; refreshToken: number; onChange: () => void
}) {
  const { t, lang, pick } = useLang()
  const report = useAsync(() => api.report(caseItem.id, 'latest').catch(() => null),
    [caseItem.id, refreshToken])
  const payload = report.data?.payload
  const summary = payload?.section_1_executive_summary
  const final = payload?.section_13_final_assessment

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <Stat value={caseItem.document_count} label={t('col.documents')} />
        <Stat value={caseItem.documents_analysed} label={t('overview.analysed')} />
        <Stat value={caseItem.documents_pending} label={t('overview.pending')} />
        <Stat value={caseItem.open_findings} label={t('col.openFindings')} />
        <Stat value={caseItem.critical_findings} label={t('overview.critical')}
              tone={caseItem.critical_findings ? 'text-critical' : ''} />
        <Stat value={caseItem.open_requirements} label={t('dash.openRequirements')} />
      </div>

      {final && (
        <Callout tone="warn">
          <div className="text-[16px] font-semibold">
            {pick(final.label, final.label_kn) }
          </div>
          <div className="mt-1">
            {t('overview.overallRisk')}{' '}
            <Badge severity={final.overall_risk} label={caseItem.overall_risk_label} /> ·{' '}
            {t('overview.score')} {final.risk_score} ({final.risk_score_normalised}/100)
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {((lang === 'kn' && final.reasons_kn?.length ? final.reasons_kn : final.reasons) ?? [])
              .map((r: string, i: number) => <li key={i}>{r}</li>)}
          </ul>
          <p className="mt-2 text-[12px] text-muted">
            {pick(final.how_determined, final.how_determined_kn)}
          </p>
        </Callout>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t('overview.caseDetails')}>
          <Field label={t('field.caseReference')} value={<span className="font-mono">{caseItem.case_ref}</span>} />
          <Field label={t('field.address')} value={caseItem.address} />
          <Field label={t('field.surveyNumber')} value={caseItem.survey_number} />
          <Field label={t('field.location')} value={[caseItem.village, caseItem.taluk, caseItem.district, caseItem.state]
            .filter(Boolean).join(', ') || '—'} />
          <Field label={t('field.claimedOwner')} value={caseItem.claimed_owner} />
          <Field label={t('field.seller')} value={caseItem.seller_name} />
          <Field label={t('field.buyer')} value={caseItem.buyer_name} />
          <Field label={t('field.reviewer')} value={caseItem.assigned_reviewer} />
          <Field label={t('field.jurisdiction')} value={caseItem.jurisdiction_code} />
          <Field label={t('field.documentCollection')} value={titleCase(caseItem.document_collection_status)} />
          <Field label={t('field.watchFolder')}
                 value={<code className="text-[11.5px]">{caseItem.watch_folder}</code>} />
          <Field label={t('field.created')} value={formatDateTime(caseItem.created_at)} />
        </Card>

        <Card title={t('overview.latestAssessment')}>
          {report.loading && <Loading />}
          {!report.loading && !summary && (
            <p className="text-[13px] text-muted">{t('overview.noReport')}</p>
          )}
          {summary && (
            <>
              <p className="text-[13px]">{summary.purpose}</p>
              <h4 className="label mt-4">{t('overview.majorFindings')}</h4>
              {summary.major_findings?.length ? (
                <ul className="mt-2 space-y-2">
                  {summary.major_findings.map((f: any) => (
                    <li key={f.risk_ref} className="text-[13px]">
                      <Badge severity={f.severity} />{' '}
                      <span className="font-mono text-[11.5px]">{f.risk_ref}</span>{' '}
                      {pick(f.title, f.translations?.kn?.title)}
                    </li>
                  ))}
                </ul>
              ) : <p className="mt-1 text-[13px] text-muted">{t('common.none')}</p>}

              <h4 className="label mt-4">{t('overview.nextSteps')}</h4>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-[13px]">
                {((lang === 'kn' && summary.recommended_next_steps_kn?.length
                   ? summary.recommended_next_steps_kn
                   : summary.recommended_next_steps) ?? [])
                  .map((step: string, i: number) => <li key={i}>{step}</li>)}
              </ol>
              <p className="mt-4 text-[12px] text-muted">
                {lang === 'kn' && final?.scope_and_limitations_kn?.[0]
                  ? final.scope_and_limitations_kn[0]
                  : summary.scope_statement}
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
