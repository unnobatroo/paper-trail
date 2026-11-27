import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

import { REVIEW_KEY } from "@/api/client"

type Lang = "en" | "orig"
type Density = "comfortable" | "compact"
const LANG_KEY = "paper-trail.lang"
const DENSITY_KEY = "paper-trail.density"

type Prefs = {
  /** "en" shows the plain-English notes; "orig" shows the source language only. */
  lang: Lang
  setLang: (lang: Lang) => void
  /** Row height of the commitments table; compact fits more rows on screen. */
  density: Density
  setDensity: (density: Density) => void
  reviewKey: string
  setReviewKey: (key: string) => void
}

const PrefsContext = createContext<Prefs | null>(null)

/** Per-browser preferences, kept in localStorage. */
export function PrefsProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem(LANG_KEY) === "orig" ? "orig" : "en"))
  const [density, setDensityState] = useState<Density>(() =>
    localStorage.getItem(DENSITY_KEY) === "compact" ? "compact" : "comfortable",
  )
  const [reviewKey, setKeyState] = useState(() => localStorage.getItem(REVIEW_KEY) ?? "")

  const setLang = useCallback((next: Lang) => {
    localStorage.setItem(LANG_KEY, next)
    setLangState(next)
  }, [])
  const setDensity = useCallback((next: Density) => {
    localStorage.setItem(DENSITY_KEY, next)
    setDensityState(next)
  }, [])
  const setReviewKey = useCallback((key: string) => {
    if (key) localStorage.setItem(REVIEW_KEY, key)
    else localStorage.removeItem(REVIEW_KEY)
    setKeyState(key)
  }, [])

  const value = useMemo(
    () => ({ lang, setLang, density, setDensity, reviewKey, setReviewKey }),
    [lang, setLang, density, setDensity, reviewKey, setReviewKey],
  )
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext)
  if (!ctx) throw new Error("usePrefs needs a PrefsProvider")
  return ctx
}
