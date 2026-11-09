import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Card, Empty, ErrorNote, Loading, Pill } from '../../components/ui'
import { STATUS_TONE, fileSize, formatDate, formatDateTime, percent, titleCase } from '../../format'
import { useAsync } from '../../hooks'
import { useLang } from '../../i18n'

export default function DocumentsTab({ caseId, refreshToken, onChange }: {
  caseId: string; refreshToken: number; onChange: () => void
}) {
  const { t } = useLang()
  const docs = useAsync(() => api.documents(caseId), [caseId, refreshToken])
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const search = useAsync(
    () => (query.length > 2 ? api.searchCase(caseId, query) : Promise.resolve({ pages: [], fields: [] })),
    [caseId, query],
  )

  async function upload(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) await api.upload(caseId, file)
      onChange()
      docs.reload()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const rows = (docs.data ?? []).filter(
    (d) => !statusFilter || d.status === statusFilter,
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <input className="input max-w-sm" placeholder={t('docs.search')}
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <select className="input max-w-[200px]" value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">{t('docs.anyStatus')}</option>
          {['analysed', 'needs_manual_review', 'failed', 'quarantined', 'queued', 'processing', 'removed']
            .map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
        </select>
        <input ref={fileInput} type="file" multiple className="hidden"
               onChange={(e) => upload(e.target.files)} />
        <button className="btn" onClick={() => fileInput.current?.click()} disabled={uploading}>
          {uploading ? t('docs.uploading') : t('docs.addFile')}
        </button>
      </div>

      {query.length > 2 && (
        <Card title={`${t('docs.searchResults')} “${query}”`}>
          {search.loading && <Loading />}
          {search.data && search.data.pages.length === 0 && search.data.fields.length === 0 && (
            <p className="text-[13px] text-muted">{t('docs.noMatch')}</p>
          )}
          <ul className="space-y-3">
            {(search.data?.pages ?? []).map((hit: any, i: number) => (
              <li key={i} className="text-[13px]">
                <Link className="font-medium underline decoration-line underline-offset-2"
                      to={`/documents/${hit.document_id}?page=${hit.page_no}`}>
                  {hit.filename} — page {hit.page_no}
                </Link>
                <div className="evidence">…{hit.excerpt}…</div>
              </li>
            ))}
            {(search.data?.fields ?? []).map((hit: any, i: number) => (
              <li key={`f${i}`} className="text-[13px]">
                <Link className="font-medium underline decoration-line underline-offset-2"
                      to={`/documents/${hit.document_id}?page=${hit.page_no ?? 1}`}>
                  {hit.filename} — {titleCase(hit.field_key)}: {hit.value}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {docs.loading && !docs.data && <Loading />}
      {docs.error && <ErrorNote error={docs.error} onRetry={docs.reload} />}
      {docs.data && rows.length === 0 && (
        <Empty title={t('docs.none')} hint={t('docs.noneHint')} />
      )}

      {rows.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">{t('col.file')}</th><th className="th">{t('col.type')}</th>
                  <th className="th">{t('col.documentDate')}</th>
                  <th className="th">{t('col.status')}</th><th className="th">{t('col.pages')}</th>
                  <th className="th">{t('col.extraction')}</th>
                  <th className="th">{t('col.received')}</th><th className="th">{t('col.issues')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id} className="hover:bg-panel/60">
                    <td className="td">
                      <Link className="font-medium underline decoration-line underline-offset-2"
                            to={`/documents/${d.id}`}>{d.filename}</Link>
                      <div className="text-[11.5px] text-muted">{d.relative_path} · {fileSize(d.size_bytes)}
                        {d.version > 1 && <> · version {d.version}</>}</div>
                    </td>
                    <td className="td">
                      {d.doc_type_label ?? '—'}
                      <div className="text-[11.5px] text-muted">
                        {t('docs.confidence')} {percent(d.classification_confidence)} · {d.classification_method ?? '—'}
                      </div>
                    </td>
                    <td className="td">{formatDate(d.document_date)}</td>
                    <td className={`td font-medium ${STATUS_TONE[d.status] ?? ''}`}>
                      {d.status_label || titleCase(d.status)}
                    </td>
                    <td className="td">{d.pages_analysed}/{d.page_count}</td>
                    <td className="td">
                      {percent(d.extraction_confidence)}{' '}
                      {d.ocr_used && <Pill>OCR</Pill>}
                    </td>
                    <td className="td text-[12px] text-muted">{formatDateTime(d.first_seen_at)}</td>
                    <td className="td text-[12px]">
                      {d.error && <div className="text-critical">{d.error}</div>}
                      {(d.issues ?? []).map((i, idx) => <div key={idx} className="text-muted">{i.detail}</div>)}
                      {!d.error && !(d.issues ?? []).length && '—'}
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
