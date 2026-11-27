import type { Schemas } from "@/api/client"
import { ToneBadge } from "@/components/tone-badge"
import { Card, CardContent } from "@/components/ui/card"
import { usePrefs } from "@/lib/prefs"
import { cn } from "@/lib/utils"

/** The original text and its plain-English reading aid, the English always labelled as AI-written. */
export function Bilingual({ text, en, className }: { text: string; en?: string | null; className?: string }) {
  const { lang } = usePrefs()
  if (lang === "orig") return <span className={className}>{text}</span>
  if (!en) {
    return (
      <span className="flex flex-col">
        <span className={className}>{text}</span>
        <span className="text-xs text-muted-foreground">not translated yet</span>
      </span>
    )
  }
  return (
    <span className="flex flex-col gap-0.5">
      <span className="flex flex-wrap items-center gap-1.5">
        <span className={className}>{en}</span>
        <ToneBadge title="Written by the model, a reading aid">AI</ToneBadge>
      </span>
      <span className="text-xs text-muted-foreground">
        <span className="sr-only">Original: </span>
        <span aria-hidden="true">ORIGINAL </span>
        {text}
      </span>
    </span>
  )
}

const SUGGESTION_TONE = { accept: "green", reject: "red", unsure: "amber" } as const

/** The model's plain-English take on an item. It only suggests; the reviewer decides. */
export function NoteCard({ note }: { note?: Schemas["Note"] | null }) {
  if (!note) return null
  return (
    <Card size="sm" className={cn("bg-muted/40")}>
      <CardContent className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">In plain English</h3>
        <p className="text-sm">{note.summary_en}</p>
        <div>
          <ToneBadge tone={SUGGESTION_TONE[note.suggestion]}>AI suggests: {note.suggestion}</ToneBadge>
        </div>
        {note.reason_en && <p className="text-sm">{note.reason_en}</p>}
        <p className="text-xs text-muted-foreground">Written by {note.author}. A suggestion only, you decide.</p>
      </CardContent>
    </Card>
  )
}
