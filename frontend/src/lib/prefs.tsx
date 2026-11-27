import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

import { REVIEW_KEY } from "@/api/client"

type Lang = "en" | "orig"
const LANG_KEY = "paper-trail.lang"

type Prefs = {
  /** "en" shows the plain-English notes; "orig" shows the source language only. */
  lang: Lang
  setLang: (lang: Lang) => void
  reviewKey: string
  setReviewKey: (key: string) => void
}

const PrefsContext = createContext<Prefs | null>(null)

/** Per-browser preferences, kept in localStorage. */
export function PrefsProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem(LANG_KEY) === "orig" ? "orig" : "en"))
  const [reviewKey, setKeyState] = useState(() => localStorage.getItem(REVIEW_KEY) ?? "")

  const setLang = useCallback((next: Lang) => {
    localStorage.setItem(LANG_KEY, next)
    setLangState(next)
  }, [])
  const setReviewKey = useCallback((key: string) => {
    if (key) localStorage.setItem(REVIEW_KEY, key)
    else localStorage.removeItem(REVIEW_KEY)
    setKeyState(key)
  }, [])

  const value = useMemo(() => ({ lang, setLang, reviewKey, setReviewKey }), [lang, setLang, reviewKey, setReviewKey])
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext)
  if (!ctx) throw new Error("usePrefs needs a PrefsProvider")
  return ctx
}
