"use client";

import type {ElementType} from "react";
import {useLocalStorage} from "usehooks-ts";
import {useQuery} from "@tanstack/react-query";
import {BookOpen, Sparkles} from "lucide-react";
import {api, type Note} from "@/lib/api";
import {keys, useMeta} from "@/lib/hooks";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Alert, AlertDescription, AlertTitle} from "@/components/ui/alert";
import {ToggleGroup, ToggleGroupItem} from "@/components/ui/toggle-group";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import {TONE_CHIP, type Tone} from "@/lib/tones";

// english vs the source language. english = the ai note, else machine translation,
// else the original with a "not translated yet" tag. quotes always stay verbatim
export type Lang = "en" | "orig";
const LS_LANG = "pt-lang";

export function useLang() {
    // usehooks-ts keeps every hook instance in sync and survives storage that throws;
    // no initial read so the server render (english) matches the first client render
    const [lang, setLang] = useLocalStorage<Lang>(LS_LANG, "en", {initializeWithValue: false});
    return {lang, setLang};
}

// machine translation, only asked for when english is on and nothing better exists
function useMachine(text: string | null | undefined, wanted: boolean) {
    const {data: meta} = useMeta();
    const {data} = useQuery({
        queryKey: keys.translate(text ?? ""),
        queryFn: () => api.translate([text!]).then((r) => r.translations[0]),
        enabled: wanted && !!text && !!meta?.translation,
        staleTime: Infinity,
        retry: false,
    });
    return data;
}

// a name or title: english first, the original underneath so nothing is hidden
export function Bi({text, en, as: Tag = "p", className}: {
    text: string | null | undefined;
    en?: string | null;
    as?: ElementType;
    className?: string;
}) {
    const {lang} = useLang();
    const machine = useMachine(text, lang === "en" && !en);
    if (!text) return null;
    if (lang === "orig") return <Tag className={className}>{text}</Tag>;
    const english = en || machine;
    if (!english) {
        return (
            <>
                <Tag className={className}>{text}</Tag>
                <span className="text-xs text-muted-foreground">not translated yet</span>
            </>
        );
    }
    return (
        <>
            <Tag className={className}>
                {english}{" "}
                <Badge variant="outline" className="align-middle text-[10px] font-normal"
                       title={en ? "written by our AI model, check it against the original"
                           : "machine translation, for orientation only"}>
                    {en ? "AI" : "MT"}
                </Badge>
            </Tag>
            <span className="block text-xs text-muted-foreground">
                <span className="uppercase tracking-wide">original</span> {text}
            </span>
        </>
    );
}

// under a verbatim quote: machine translation in english mode, nothing otherwise
export function En({text}: { text: string | null | undefined }) {
    const {lang} = useLang();
    const machine = useMachine(text, lang === "en");
    if (lang !== "en" || !text || !machine) return null;
    return (
        <span className="mt-1 block text-sm italic text-muted-foreground">
            {machine} <span className="not-italic">(machine translation)</span>
        </span>
    );
}

const SUGGESTION_TONE: Record<Note["suggestion"], Tone> = {accept: "green", reject: "red", unsure: "amber"};

// the ai's plain-english take. a hint for the reviewer, the buttons still decide
export function NoteCard({note}: { note: Note | null | undefined }) {
    if (!note) return null;
    return (
        <Alert>
            <Sparkles/>
            <AlertTitle>In plain English</AlertTitle>
            <AlertDescription>
                <p>{note.summary_en}</p>
                <p className="mt-1 text-xs">
                    <Badge variant="outline" className={TONE_CHIP[SUGGESTION_TONE[note.suggestion]]}>
                        AI suggests: {note.suggestion}
                    </Badge>
                    {note.reason_en && <span className="ml-1">{note.reason_en}</span>}
                </p>
                <p className="mt-1 text-[11px]">written by {note.author}. a suggestion only, you decide</p>
            </AlertDescription>
        </Alert>
    );
}

// "M1.2.1" -> what the letter means, from the profile's glossary, on hover
export function CodeHint({code}: { code: string | null | undefined }) {
    const {data: meta} = useMeta();
    const m = code?.match(/^([A-Za-z]+)(\d+(?:\.\d+)*)/);
    const meaning = m && meta?.glossary?.find((g) => g.term === m[1])?.meaning;
    if (!m || !meaning) return null;
    return (
        <Tooltip>
            <TooltipTrigger render={<span className="cursor-help text-xs text-muted-foreground underline decoration-dotted"/>}>
                what does {code} mean?
            </TooltipTrigger>
            <TooltipContent>
                {m[1]} = {meaning}. {m[2].split(".").length} levels deep in the plan
            </TooltipContent>
        </Tooltip>
    );
}

// every term the documents use, one click from anywhere
export function GlossaryButton() {
    const {data: meta} = useMeta();
    const terms = meta?.glossary ?? [];
    if (!terms.length) return null;
    return (
        <Popover>
            <PopoverTrigger render={<Button variant="ghost" size="sm" className="gap-1.5"/>}>
                <BookOpen className="size-4"/> Glossary
            </PopoverTrigger>
            <PopoverContent align="end" className="max-h-96 w-96 overflow-y-auto">
                <dl className="space-y-2 text-sm">
                    {terms.map((t) => (
                        <div key={t.term}>
                            <dt className="font-medium">{t.term}</dt>
                            <dd className="text-muted-foreground">{t.meaning}</dd>
                        </div>
                    ))}
                </dl>
            </PopoverContent>
        </Popover>
    );
}

// top-nav switch, labelled with the profile's language name when we know it
export function LangToggle({original = "Original"}: { original?: string }) {
    const {lang, setLang} = useLang();
    return (
        <ToggleGroup aria-label="Content language" variant="outline" size="sm" value={[lang]}
                     onValueChange={(v) => v[0] && setLang(v[0] as Lang)}>
            <ToggleGroupItem value="en">English</ToggleGroupItem>
            <ToggleGroupItem value="orig">{original}</ToggleGroupItem>
        </ToggleGroup>
    );
}
