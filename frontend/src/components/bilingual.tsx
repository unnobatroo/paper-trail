import type { Schemas } from "@/api/client"
import { ToneBadge } from "@/components/tone-badge"
import { usePrefs } from "@/lib/prefs"

/** The original text and its plain-English reading aid, the English always labelled as AI-written. */
export function Bilingual({ text, en, className }: { text: string; en?: string | null; className?: string }) {
  const { lang } = usePrefs()
  if (lang === "orig" || !en) return <span className={className}>{text}</span>
  return (
    <span className="flex flex-col gap-0.5">
      <span className="flex flex-wrap items-center gap-1.5">
        <span className={className}>{en}</span>
        <ToneBadge title="Written by the model, a reading aid">AI</ToneBadge>
      </span>
      <span className="type-secondary font-normal">
        <span className="sr-only">Original: </span>
        {text}
      </span>
    </span>
  )
}

/** The model's plain-English take on an item. It only suggests; the reviewer decides. */
export function NoteCard({ note }: { note?: Schemas["Note"] | null }) {
  if (!note) return null
  return (
    <div className="layer-surface flex flex-col gap-1.5 p-3">
      <h3 className="type-label" title={`Written by ${note.author}. A suggestion only, you decide.`}>
        AI suggests: {note.suggestion}
      </h3>
      <p className="type-body">{note.summary_en}</p>
      {note.reason_en && <p className="type-secondary">{note.reason_en}</p>}
    </div>
  )
}
