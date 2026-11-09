import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { Card, ErrorNote, Loading, Pill } from '../components/ui'
import { fileSize, formatDate, formatDateTime, percent, titleCase } from '../format'
import { useAsync } from '../hooks'
import { useLang } from '../i18n'

export default function DocumentViewer() {
  const { documentId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const page = Number(params.get('page') ?? 1)
  const { t, lang, pick } = useLang()
  const doc = useAsync(() => api.document(documentId), [documentId])
  const reference = useAsync(() => api.reference(), [])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    if (!doc.data) return
    api.pageText(documentId, page).then(setText).catch(() => setText('(no text for this page)'))
  }, [documentId, page, doc.data])

  if (doc.loading && !doc.data) return <Loading />
  if (doc.error) return <ErrorNote error={doc.error} onRetry={doc.reload} />
  const d = doc.data
  if (!d) return null

  const fieldLabel = (key: string) =>
    (lang === 'kn' && reference.data?.vocabularies?.field_title?.[key]?.kn) || titleCase(key)

  const grouped: Record<string, typeof d.fields> = {}
  d.fields.forEach((f) => { (grouped[f.field_key] ||= []).push(f) })

  async function saveCorrection(fieldId: number) {
    setBusy(true)
    try {
      await api.correctField(fieldId, draft, 'Corrected in the document viewer')
      setEditing(null)
      doc.reload()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function changeType(value: string) {
    setBusy(true)
    try {
      await api.setDocumentType(documentId, value)
      doc.reload()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">{d.filename}</h1>
          <p className="mt-1 text-[12.5px] text-muted">
            <Link className="underline decoration-line underline-offset-2" to={`/cases/${d.case_id}/documents`}>
              {t('viewer.backToCase')}
            </Link>{' · '}
            {d.relative_path} · {fileSize(d.size_bytes)} · version {d.version} ·{' '}
            received {formatDateTime(d.first_seen_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className="btn" href={api.fileUrl(documentId)} target="_blank" rel="noreferrer">
            {t('viewer.openOriginal')}
          </a>
          <button className="btn" disabled={busy} onClick={async () => {
            setBusy(true)
            try { await api.reprocess(documentId); doc.reload() } finally { setBusy(false) }
          }}>{t('viewer.reprocess')}</button>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-5">
          <Card title={t('viewer.classification')}>
            <div className="flex flex-wrap items-center gap-2">
              <select className="input max-w-sm" value={d.doc_type ?? 'unknown'} disabled={busy}
                      onChange={(e) => changeType(e.target.value)}>
                {(reference.data?.document_types ?? []).map((item) => (
                  <option key={item.key} value={item.key}>{pick(item.label, item.label_kn)}</option>
                ))}
              </select>
              <Pill>{percent(d.classification_confidence)}</Pill>
              <Pill>{d.classification_method ?? '—'}</Pill>
              <Pill>{d.status_label || titleCase(d.status)}</Pill>
            </div>
            {d.classification_rationale && (
              <p className="mt-2 text-[12.5px] text-muted">{d.classification_rationale}</p>
            )}
            <p className="mt-2 text-[12.5px]">
              {t('viewer.documentDate')} {formatDate(d.document_date)} ·{' '}
              {d.pages_analysed}/{d.page_count} {t('viewer.pagesRead')} ·{' '}
              {t('col.extraction')} {percent(d.extraction_confidence)} · {d.extraction_method}
              {d.ocr_used && ` · ${t('viewer.ocrUsed')}`}
            </p>
            {d.error && <p className="mt-2 text-[13px] text-critical">{d.error}</p>}
            {(d.issues ?? []).length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-[13px] text-high">
                {(d.issues ?? []).map((i, k) => <li key={k}>{i.detail}</li>)}
              </ul>
            )}
            {d.summary && <p className="mt-3 text-[13px]">{d.summary}</p>}
          </Card>

          <Card title={t('viewer.extractedInfo')}
                actions={<span className="text-[12px] text-muted">
                  {d.fields.length} {t('viewer.fields')}
                </span>}>
            <p className="mb-3 text-[12px] text-muted">{t('common.sourceScript')}</p>
            {d.fields.length === 0 ? (
              <p className="text-[13px] text-muted">{t('viewer.nothingExtracted')}</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(grouped).map(([key, values]) => (
                  <div key={key} className="border-b border-line pb-3 last:border-0">
                    <div className="label">{fieldLabel(key)}</div>
                    {values.map((f) => (
                      <div key={f.id} className="mt-1 text-[13px]">
                        {editing === f.id ? (
                          <div className="flex gap-2">
                            <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} />
                            <button className="btn btn-primary" disabled={busy}
                                    onClick={() => saveCorrection(f.id)}>{t('common.save')}</button>
                            <button className="btn" onClick={() => setEditing(null)}>{t('common.cancel')}</button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{f.value_norm || f.value_raw}</span>
                            {f.page_no && (
                              <button className="text-[11.5px] text-muted underline"
                                      onClick={() => setParams({ page: String(f.page_no) })}>
                                {t('common.page')} {f.page_no}
                              </button>
                            )}
                            <Pill>{percent(f.confidence)}</Pill>
                            <Pill>{titleCase(f.provenance)}</Pill>
                            <button className="text-[11.5px] underline"
                                    onClick={() => { setEditing(f.id); setDraft(f.value_norm || f.value_raw || '') }}>
                              {t('viewer.correct')}
                            </button>
                          </div>
                        )}
                        {f.original_value && (
                          <div className="text-[11.5px] text-muted">
                            {t('viewer.originallyExtracted')}: {f.original_value}
                          </div>
                        )}
                        {f.evidence_text && <div className="evidence">“{f.evidence_text}”</div>}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <Card title={`${t('viewer.extractedText')} ${page} ${t('viewer.of')} ${d.page_count || 1}`}
              actions={
                <span className="flex items-center gap-1">
                  <button className="btn" disabled={page <= 1}
                          onClick={() => setParams({ page: String(page - 1) })}>{t('viewer.previous')}</button>
                  <button className="btn" disabled={page >= d.page_count}
                          onClick={() => setParams({ page: String(page + 1) })}>{t('viewer.next')}</button>
                </span>}>
          <pre className="max-h-[700px] overflow-auto whitespace-pre-wrap rounded-md bg-panel p-4
                          font-mono text-[12px] leading-relaxed">{text}</pre>
        </Card>
      </div>
    </div>
  )
}
