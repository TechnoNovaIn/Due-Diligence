import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Card, Empty, Loading, Pill } from '../../components/ui'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'
import { titleCase } from '../../format'

export default function DocumentAnalysisTab({ caseId, refreshToken }: {
  caseId: string; refreshToken: number
}) {
  const { t } = useLang()
  const report = useAsync(() => api.report(caseId, 'latest').catch(() => null),
    [caseId, refreshToken])
  const docs = report.data?.payload?.section_4_document_analysis ?? []

  if (report.loading) return <Loading />
  if (!docs.length) return <Empty title={t('verify.none')} />

  return (
    <div className="space-y-4">
      <p className="text-[12.5px] text-muted">{t('common.sourceScript')}</p>
      {docs.map((d: any, i: number) => (
        <Card key={i} title={<span>{d.filename}</span>}
              actions={<span className="flex gap-1.5"><Pill>{d.document_type}</Pill>
                <Pill>{titleCase(d.status)}</Pill></span>}>
          <p className="text-[13px]">{d.purpose}</p>
          {d.summary && <p className="mt-2 text-[13px]">{d.summary}</p>}

          {d.parties?.length > 0 && (
            <p className="mt-3 text-[13px]"><span className="label">Parties</span><br />
              {d.parties.map((p: any) => `${p.name} (${p.role})`).join('; ')}</p>
          )}
          {d.important_dates?.length > 0 && (
            <p className="mt-3 text-[13px]"><span className="label">Dates</span><br />
              {d.important_dates.map((x: any) => `${x.label}: ${x.value}`).join('; ')}</p>
          )}
          {d.property_identifiers?.length > 0 && (
            <p className="mt-3 text-[13px]"><span className="label">Property identifiers</span><br />
              {d.property_identifiers.map((x: any) => `${x.label}: ${x.value} (p.${x.page})`).join('; ')}</p>
          )}
          <p className="mt-3 text-[13px]"><span className="label">Legal / financial effect</span><br />
            {d.legal_or_financial_effect}</p>

          {d.referenced_documents?.length > 0 && (
            <div className="mt-3">
              <span className="label">References other documents</span>
              <ul className="mt-1 list-disc pl-5 text-[13px]">
                {d.referenced_documents.map((r: string, k: number) => <li key={k}>{r}</li>)}
              </ul>
            </div>
          )}
          {d.internal_inconsistencies?.length > 0 && (
            <div className="mt-3">
              <span className="label">Internal inconsistencies</span>
              <ul className="mt-1 list-disc pl-5 text-[13px]">
                {d.internal_inconsistencies.map((r: string, k: number) => <li key={k}>{r}</li>)}
              </ul>
            </div>
          )}
          {d.items_requiring_verification?.length > 0 && (
            <div className="mt-3">
              <span className="label">Requires verification</span>
              <ul className="mt-1 list-disc pl-5 text-[13px]">
                {d.items_requiring_verification.map((r: string, k: number) => <li key={k}>{r}</li>)}
              </ul>
            </div>
          )}
          {d.issues?.length > 0 && (
            <div className="mt-3">
              <span className="label">Issues</span>
              <ul className="mt-1 list-disc pl-5 text-[13px] text-high">
                {d.issues.map((r: string, k: number) => <li key={k}>{r}</li>)}
              </ul>
            </div>
          )}
          <p className="mt-3 text-[11.5px] text-muted">Analysed by: {d.analysed_by}</p>
        </Card>
      ))}
      <p className="text-[12px] text-muted">
        Open a document from the <Link className="underline" to={`/cases/${caseId}/documents`}>Documents</Link>{' '}
        tab to see every extracted field with its page reference and supporting text.
      </p>
    </div>
  )
}
