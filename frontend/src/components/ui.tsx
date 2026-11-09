import { ReactNode } from 'react'
import { SEVERITY_CLASS, titleCase } from '../format'
import { useLang } from '../i18n'
import type { Severity } from '../types'

export function Badge({ severity, label, children }: {
  severity?: Severity | null; label?: string | null; children?: ReactNode
}) {
  const { t } = useLang()
  const cls = severity ? SEVERITY_CLASS[severity] : 'bg-panel text-muted border border-line'
  // An explicit label (from the API) wins; otherwise translate the severity here
  // so every badge in the interface reads in the chosen language.
  const text = children ?? label ?? (severity ? t(`severity.${severity}`) : '—')
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${cls}`}>
      {text}
    </span>
  )
}

export function Pill({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return (
    <span className={`inline-block rounded-md border border-line bg-panel px-2 py-0.5 text-[11px] ${tone}`}>
      {children}
    </span>
  )
}

export function Card({ title, actions, children, className = '' }: {
  title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h3 className="text-[15px] font-semibold">{title}</h3>
          {actions}
        </header>
      )}
      <div className="card-pad">{children}</div>
    </section>
  )
}

export function Stat({ value, label, tone = '' }: { value: ReactNode; label: string; tone?: string }) {
  return (
    <div className="card px-4 py-3">
      <div className={`text-2xl font-semibold leading-tight ${tone}`}>{value}</div>
      <div className="label mt-0.5">{label}</div>
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      {hint && <p className="mt-1 text-[13px] text-muted">{hint}</p>}
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <p className="px-1 py-6 text-[13px] text-muted">{label}</p>
}

export function ErrorNote({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="rounded-md border border-critical/30 bg-critical/5 px-4 py-3 text-[13px]">
      <strong className="text-critical">Could not load.</strong> {error}
      {onRetry && (
        <button className="btn ml-3" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="border-b border-line py-2 last:border-0">
      <div className="label">{label}</div>
      <div className="mt-0.5">{value ?? '—'}</div>
    </div>
  )
}

export function Callout({ tone = 'neutral', children }: { tone?: 'neutral' | 'warn'; children: ReactNode }) {
  const border = tone === 'warn' ? 'border-l-critical' : 'border-l-ink'
  return (
    <div className={`rounded-r-md border-l-4 ${border} bg-panel px-4 py-3 text-[13px]`}>{children}</div>
  )
}

export function StatusText({ status }: { status: string }) {
  return <span>{titleCase(status)}</span>
}
