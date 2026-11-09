import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Lang, STRINGS, translate } from './strings'

export { LANGUAGES, missingKannada } from './strings'
export type { Lang } from './strings'

const STORAGE_KEY = 'dd_lang'

interface LanguageContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  /** Translate an interface string. */
  t: (key: string) => string
  /** Pick a localised label returned by the API, falling back to the English one. */
  pick: (en?: string | null, kn?: string | null) => string
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: 'en',
  setLang: () => undefined,
  t: (key) => translate(key, 'en'),
  pick: (en) => en ?? '—',
})

function readStored(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'en' || stored === 'kn') return stored
  } catch {
    /* storage unavailable - fall through to the browser preference */
  }
  return typeof navigator !== 'undefined' && navigator.language?.startsWith('kn') ? 'kn' : 'en'
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStored)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* the choice simply is not remembered */
    }
  }, [])

  const value = useMemo<LanguageContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => translate(key, lang),
      pick: (en?: string | null, kn?: string | null) => (lang === 'kn' ? kn || en : en) || '—',
    }),
    [lang, setLang],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLang() {
  return useContext(LanguageContext)
}

/** The language the API should answer in, read by the fetch client. */
export function currentApiLang(): Lang {
  return readStored()
}

export { STRINGS }
