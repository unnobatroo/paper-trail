import { useEffect, useRef, useState } from "react"

import { useCandidateHighlight } from "@/api/hooks"
import { SourceFrame } from "@/components/source-frame"
import { Skeleton } from "@/components/ui/skeleton"

type Props = {
  candidateId: number
  /** The strategy's own address, used when the page can't be drawn here. */
  pdfUrl?: string
  page: number
}

/**
 * The page a quote was read from, drawn by the API, with the quote marked: a reviewer checks it
 * where it was written, and sees at once which words are meant. If the page can't be drawn (the
 * source is down, or isn't a pdf) the strategy's own viewer takes its place.
 */
export function SourcePage({ candidateId, pdfUrl, page }: Props) {
  const highlight = useCandidateHighlight(candidateId)
  const scroller = useRef<HTMLDivElement>(null)
  const [drawn, setDrawn] = useState(false)
  const [broken, setBroken] = useState(false)

  // once the page has its size, bring the marked words into view, a little below the top
  useEffect(() => {
    const first = highlight.data?.boxes[0]
    const el = scroller.current
    if (drawn && first && el) el.scrollTo({ top: first.y * el.scrollHeight - el.clientHeight / 3, behavior: "smooth" })
  }, [drawn, highlight.data])

  // the page could not be drawn, or the drawing could not be fetched: the pdf's own viewer instead
  if (highlight.isError || broken) return pdfUrl ? <SourceFrame url={pdfUrl} page={page} /> : null
  if (!highlight.data) return <Skeleton className="min-h-96 w-full flex-1 rounded-xl" />

  return (
    <section aria-label={`Source page ${page}`} className="flex min-h-0 flex-1 flex-col gap-2">
      <div ref={scroller} className="relative min-h-96 flex-1 overflow-auto rounded-xl bg-surface ring-1 ring-border">
        <div className="relative">
          <img
            src={highlight.data.image_url}
            alt={`Page ${page} of the strategy`}
            onLoad={() => setDrawn(true)}
            onError={() => setBroken(true)}
            className="block w-full"
          />
          {highlight.data.boxes.map((b, i) => (
            <span
              key={i}
              data-slot="highlight"
              aria-hidden="true"
              className="pointer-events-none absolute rounded-[2px] bg-yellow-300/45 mix-blend-multiply ring-1 ring-yellow-600/50"
              style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
            />
          ))}
        </div>
      </div>
      {!highlight.data.found && (
        <p role="note" className="type-label">
          The words of this quote aren't in the page's text, so none are marked.
        </p>
      )}
    </section>
  )
}
