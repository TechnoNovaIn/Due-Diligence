import { api } from '../../api'
import { Badge, Card, Empty, Loading } from '../../components/ui'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'

export default function ActionsTab({ caseId, refreshToken }: { caseId: string; refreshToken: number }) {
  const { t } = useLang()
  const report = useAsync(() => api.report(caseId, 'latest').catch(() => null),
    [caseId, refreshToken])
  const payload = report.data?.payload
  const plan = payload?.section_12_action_plan ?? []
  const questions = payload?.section_11_questions ?? []

  if (report.loading) return <Loading />
  if (!payload) return <Empty title={t('actions.none')} />

  const groups: Record<string, any[]> = {}
  plan.forEach((a: any) => { (groups[a.group] ||= []).push(a) })

  return (
    <div className="space-y-5">
      <Card title={t('actions.plan')}>
        {Object.entries(groups).map(([group, actions]) => (
          <div key={group} className="mb-5 last:mb-0">
            <h4 className="label mb-2">{group}</h4>
            <ol className="space-y-2">
              {actions.map((a: any) => (
                <li key={a.order} className="flex gap-3 text-[13px]">
                  <span className="mt-0.5 font-mono text-[11px] text-muted">{a.order}</span>
                  <div>
                    <div className="font-medium">{a.action}</div>
                    <div className="text-[12px] text-muted">
                      {a.severity && <><Badge severity={a.severity} /> </>}
                      {a.reason}
                      {a.authority && <> · {a.authority}</>}
                    </div>
                    {a.depends_on?.length > 0 && (
                      <div className="text-[12px] text-muted">{t('actions.dependsOn')}: {a.depends_on.join('; ')}</div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </Card>

      <Card title={t('actions.questions')}>
        {questions.length === 0 ? (
          <p className="text-[13px] text-muted">{t('actions.noQuestions')}</p>
        ) : (
          <ol className="list-decimal space-y-3 pl-5">
            {questions.map((q: any, i: number) => (
              <li key={i} className="text-[13px]">
                {q.question}
                <div className="text-[12px] text-muted">
                  {t('common.why')}: {q.reason}{q.risk_ref && ` (${q.risk_ref})`}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  )
}
