"use client";

import {createContext, type ReactNode, useContext, useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/lib/api";
import {keys} from "@/lib/hooks";

// translation toggle, english always looks secondary
const TranslateCtx = createContext<{
    on: boolean;
    setOn: (v: boolean) => void;
}>({
    on: false, setOn: () => {
    }
});

export function TranslateProvider({children}: { children: ReactNode }) {
    const [on, setOn] = useState(false);
    return (
        <TranslateCtx.Provider value={{on, setOn}}>
            {children}
        </TranslateCtx.Provider>
    );
}

export function useTranslate() {
    return useContext(TranslateCtx);
}

// machine translation under the source text when on, cached per text forever
export function En({text}: { text: string | null | undefined }) {
    const {on} = useTranslate();
    const {data} = useQuery({
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
