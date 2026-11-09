import { api } from '../api'
import { Callout, Card, ErrorNote, Field, Loading } from '../components/ui'
import { formatDateTime } from '../format'
import { useAsync, usePolling } from '../hooks'
import { missingKannada, useLang } from '../i18n'

export default function SystemPage() {
  const { t } = useLang()
  const status = useAsync(() => api.systemStatus(), [])
  usePolling(status.reload, 10000)

  if (status.loading && !status.data) return <Loading />
  if (status.error) return <ErrorNote error={status.error} onRetry={status.reload} />
  const s = status.data
  if (!s) return null

  const remote = Boolean(s.ai.sends_document_text_off_device)

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">{t('system.title')}</h1>

      <Callout tone={remote ? 'warn' : 'neutral'}>
        <strong>{t('system.whatLeaves')}</strong> {s.ai.data_leaving_device}
        {s.ai.note && <div className="mt-1 text-[12.5px] text-muted">{s.ai.note}</div>}
      </Callout>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t('system.aiProcessing')}>
          <Field label="Configured provider" value={s.ai.configured_provider} />
          <Field label="Active provider" value={`${s.ai.provider} (${s.ai.model})`} />
          <Field label="Available" value={s.ai.available ? 'yes' : 'no'} />
          <Field label="Remote processing permitted" value={s.ai.allow_remote_ai ? 'yes' : 'no'} />
          <Field label="Calls made" value={`${s.ai.calls} (${s.ai.errors} error(s))`} />
          {s.ai.last_error && <Field label="Last error" value={<span className="text-critical">{s.ai.last_error}</span>} />}
        </Card>

        <Card title={t('system.textExtraction')}>
          <Field label="OCR engine" value={s.ocr.engine} />
          <Field label="Available" value={s.ocr.available ? 'yes' : 'no'} />
          <Field label={t('system.ocrLanguages')} value={
            s.ocr.languages
              ? <span>
                  {s.ocr.languages.readable.join(', ') || '\u2014'}
                  {s.ocr.languages.unreadable.length > 0 &&
                    <span className="text-critical">
                      {' '}({t('system.cannotRead')}: {s.ocr.languages.unreadable.join(', ')})
                    </span>}
                </span>
              : '\u2014'} />
          <Field label="Note" value={<span className="text-[12.5px]">{s.ocr.note}</span>} />
          <Field label={t('system.maxFileSize')}
                 value={s.limits.max_file_mb ? `${s.limits.max_file_mb} MB` : t('system.noLimit')} />
          <Field label={t('system.maxPages')}
                 value={s.limits.max_pages_per_document || t('system.noLimit')} />
        </Card>

        <Card title={t('system.folderMonitoring')}>
          <Field label="Running" value={s.watcher.running ? 'yes' : 'no'} />
          <Field label="Watched cases" value={s.watcher.watched_cases} />
          <Field label="Files waiting to settle" value={s.watcher.pending_settle} />
          <Field label="Settle delay" value={`${s.limits.file_settle_seconds}s`} />
          <Field label="Reconciliation sweep" value={`every ${s.limits.reconcile_interval_seconds}s`} />
          <Field label="Last sweep" value={s.watcher.last_reconcile_at
            ? formatDateTime(new Date(s.watcher.last_reconcile_at * 1000).toISOString()) : '—'} />
        </Card>

        <Card title={t('system.backgroundJobs')}>
          <Field label="Runner" value={s.jobs.running ? `running (${s.jobs.workers} worker(s))` : 'stopped'} />
          {Object.entries(s.jobs.queue).map(([k, v]) => <Field key={k} label={k} value={v} />)}
          {Object.keys(s.jobs.queue).length === 0 && <Field label="Queue" value="empty" />}
        </Card>

        <Card title={t('system.storage')}>
          {Object.entries(s.storage).map(([k, v]) => (
            <Field key={k} label={k.replace(/_/g, ' ')} value={<code className="text-[11.5px]">{v}</code>} />
          ))}
        </Card>

        <Card title={t('system.security')}>
          <Field label="Authentication" value={s.security.auth_enabled ? 'enabled' : 'disabled (local use)'} />
          <Field label="Remote AI allowed" value={s.security.remote_ai_allowed ? 'yes' : 'no'} />
          <Field label="Malware scanner" value={s.security.malware_scan_configured ? 'configured' : 'not configured'} />
          <Field label="Signed in as" value={`${s.principal.username} (${s.principal.role})`} />
        </Card>

        <Card title={t('system.languages')}>
          <Field label="Interface" value="English · ಕನ್ನಡ" />
          <Field label="Document type names"
                 value={`${s.languages?.document_type_labels?.translated ?? 0} / ${
                   s.languages?.document_type_labels?.total ?? 0} translated`} />
          <Field label="Requirement templates"
                 value={`${s.languages?.requirement_templates?.translated ?? 0} / ${
                   s.languages?.requirement_templates?.total ?? 0} translated`} />
          <Field label="Finding types with Kannada text"
                 value={s.languages?.detectors_translated ?? 0} />
          <Field label="Interface strings awaiting Kannada"
                 value={missingKannada().length || 'none'} />
          <Field label="Note" value={<span className="text-[12.5px]">{s.languages?.note}</span>} />
        </Card>
      </div>
    </div>
  )
}
