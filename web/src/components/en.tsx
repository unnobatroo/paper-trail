"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/hooks";

/** Translation toggle context — EN is always visibly secondary. */
const TranslateCtx = createContext<{
  on: boolean;
  setOn: (v: boolean) => void;
}>({ on: false, setOn: () => {} });

export function TranslateProvider({ children }: { children: ReactNode }) {
  const [on, setOn] = useState(false);
  return (
    <TranslateCtx.Provider value={{ on, setOn }}>
      {children}
    </TranslateCtx.Provider>
  );
}

export function useTranslate() {
  return useContext(TranslateCtx);
}

/** Renders the machine translation of the source text when enabled —
 * cached per-text forever via TanStack Query. */
export function En({ text }: { text: string | null | undefined }) {
  const { on } = useTranslate();
  const { data } = useQuery({
    queryKey: keys.translate(text ?? ""),
    queryFn: () => api.translate([text!]).then((r) => r.translations[0]),
    enabled: on && !!text,
    staleTime: Infinity,
    retry: false,
  });
  if (!on || !text || !data) return null;
  return (
    <span className="block text-sm italic text-muted-foreground">{data}</span>
  );
}
