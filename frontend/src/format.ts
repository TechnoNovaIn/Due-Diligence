import type { Severity } from './types'

export const SEVERITY_CLASS: Record<Severity, string> = {
  critical: 'bg-critical text-white',
  high: 'bg-high text-white',
  medium: 'bg-medium text-white',
  low: 'bg-low text-white',
  informational: 'bg-info text-white',
}

export function titleCase(value?: string | null): string {
  if (!value) return '—'
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function percent(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const STATUS_TONE: Record<string, string> = {
  analysed: 'text-low',
  needs_manual_review: 'text-medium',
  failed: 'text-critical',
  quarantined: 'text-critical',
  removed: 'text-muted',
  superseded: 'text-muted',
  processing: 'text-info',
  queued: 'text-info',
  discovered: 'text-info',
}
