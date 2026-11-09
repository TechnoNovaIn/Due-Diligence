import { ReactNode, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { api, setApiKey } from '../api'
import { useAsync } from '../hooks'
import { LANGUAGES, useLang } from '../i18n'
import type { Lang } from '../i18n'

export default function Layout({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useLang()
  const status = useAsync(() => api.systemStatus(), [])
  const [showKey, setShowKey] = useState(false)
  const [key, setKey] = useState('')
  const location = useLocation()

  const ai = status.data?.ai
  const remote = Boolean(ai?.sends_document_text_off_device)

  return (
    <div className="min-h-screen bg-panel/40">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
          <Link to="/" className="font-serif text-[17px] font-bold tracking-tight">
            {t('app.title')}
          </Link>
          <nav className="flex gap-1">
            <NavLink to="/" className={({ isActive }) => `tab ${isActive ? 'tab-active' : ''}`} end>
              {t('nav.dashboard')}
            </NavLink>
            <NavLink to="/cases" className={({ isActive }) =>
              `tab ${isActive || location.pathname.startsWith('/cases/') ? 'tab-active' : ''}`}>
              {t('nav.cases')}
            </NavLink>
            <NavLink to="/cases/new" className={({ isActive }) => `tab ${isActive ? 'tab-active' : ''}`}>
              {t('nav.newCase')}
            </NavLink>
            <NavLink to="/system" className={({ isActive }) => `tab ${isActive ? 'tab-active' : ''}`}>
              {t('nav.system')}
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-[12px] text-muted">
            {status.data && (
              <>
                <span title={String(ai?.note ?? '')}>
                  {t('chrome.ai')}: <strong className={remote ? 'text-high' : 'text-low'}>
                    {remote ? `${ai?.provider} (${t('chrome.aiRemote')})` : t('chrome.aiLocal')}
                  </strong>
                </span>
                <span title={String(status.data.ocr.note ?? '')}>
                  {t('chrome.ocr')}: <strong className={status.data.ocr.available ? 'text-low' : 'text-medium'}>
                    {status.data.ocr.available ? t('chrome.ocrReady') : t('chrome.ocrMissing')}
                  </strong>
                </span>
                <span>
                  {t('chrome.watcher')}: <strong className={status.data.watcher.running ? 'text-low' : 'text-critical'}>
                    {status.data.watcher.running ? t('chrome.running') : t('chrome.stopped')}
                  </strong>
                </span>
              </>
            )}
            <div className="flex overflow-hidden rounded-md border border-line" role="group"
                 aria-label={t('chrome.language')}>
              {LANGUAGES.map((option) => (
                <button
                  key={option.code}
                  onClick={() => setLang(option.code as Lang)}
                  aria-pressed={lang === option.code}
                  className={`px-2.5 py-1 text-[12px] font-medium transition ${
                    lang === option.code ? 'bg-ink text-white' : 'bg-white hover:bg-panel'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            {status.data?.security?.auth_enabled && (
              <button className="btn" onClick={() => setShowKey((v) => !v)}>{t('chrome.apiKey')}</button>
            )}
          </div>
        </div>
        {showKey && (
          <div className="border-t border-line bg-panel px-6 py-3">
            <div className="mx-auto flex max-w-[1400px] items-center gap-2">
              <input
                className="input max-w-sm"
                placeholder="X-API-Key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
              />
              <button className="btn btn-primary"
                      onClick={() => { setApiKey(key); status.reload(); setShowKey(false) }}>
                {t('common.save')}
              </button>
              <button className="btn" onClick={() => { setApiKey(''); setKey(''); status.reload() }}>
                {t('common.clear')}
              </button>
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-6">{children}</main>

      <footer className="mx-auto max-w-[1400px] px-6 pb-10 pt-2 text-[11.5px] text-muted">
        {t('chrome.disclaimer')}
        {status.data && ` · v${status.data.version} · ruleset ${status.data.ruleset_version}`}
      </footer>
    </div>
  )
}
