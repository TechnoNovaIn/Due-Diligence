import { useCallback, useEffect, useRef, useState } from 'react'
import { useLang } from './i18n'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

/** Fetch on mount and whenever a dependency changes, with manual reload.
 *
 * The current language is always part of the dependency list. The API answers in
 * the requested language, so a response fetched in one language is stale in the
 * other; making that implicit here means no call site can forget it.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const { lang } = useLang()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    setLoading(true)
    fn()
      .then((result) => {
        if (!alive.current) return
        setData(result)
        setError(null)
      })
      .catch((err: Error) => {
        if (!alive.current) return
        setError(err.message)
      })
      .finally(() => {
        if (alive.current) setLoading(false)
      })
    return () => {
      alive.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, lang, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}

/** Re-run a callback on an interval while `enabled` is true. */
export function usePolling(callback: () => void, intervalMs: number, enabled = true) {
  const saved = useRef(callback)
  useEffect(() => {
    saved.current = callback
  }, [callback])
  useEffect(() => {
    if (!enabled) return
    const id = window.setInterval(() => saved.current(), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs, enabled])
}
