import { useState } from "react"
import { SearchIcon } from "lucide-react"

import type { Commitment, WorkspaceRow } from "@/api/client"
import { useMeta } from "@/api/hooks"
import { Bilingual } from "@/components/bilingual"
import { CandidateDetail } from "@/components/candidate-detail"
import { MatchCard } from "@/components/match-card"
import { SimpleSelect } from "@/components/simple-select"
import { ToneBadge } from "@/components/tone-badge"
import { TrailDetail } from "@/components/trail-detail"
import { Button } from "@/components/ui/button"
import { KIND_LABEL, STAGE_INFO, displayTitle, pageLink } from "@/lib/labels"
import { useCanReview } from "@/lib/can-review"
import { parseCode, shown } from "@/lib/rows"

type Props = {
  row: WorkspaceRow
  documents: Record<string, string>
  commitments: Commitment[]
  searching: boolean
  onSearch: (commitmentIds: number[]) => void
  /** A mention was confirmed or rejected here; the workspace moves on to the next row. */
  onDecided?: () => void
}

/** Everything about one commitment: where it came from, what's left to do, and its paper trail. */
export function DetailPane({ row, documents, commitments, searching, onSearch, onDecided }: Props) {
  const [picked, setPicked] = useState<number | undefined>()
  const meta = useMeta()
  const canReview = useCanReview()
  const c = shown(row, picked)
  const stage = STAGE_INFO[row.stage]
  const page = pageLink(documents[String(c.document_id)], c.source_page)
  const code = parseCode(c.code)
  const meaning = code && meta.data?.glossary.find((g) => g.term === code.letters)?.meaning
  const searchable = row.searchable && row.commitments.length > 0
  const searchedBefore = row.pending.length > 0 || row.evidence > 0

  return (
    <div className="flex min-h-full flex-col gap-3 p-5">
      <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
        <span>{KIND_LABEL[row.kind]}</span>
        {c.code && <span className="normal-case">{c.code}</span>}
        <ToneBadge tone={stage.tone} title={stage.hint}>{stage.label}</ToneBadge>
        {page.href ? (
          <a href={page.href} target="_blank" rel="noreferrer" className="underline-offset-4 hover:underline">
            {page.text}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <span>{page.text}</span>
        )}
      </p>

      <h2 className="text-lg leading-snug font-semibold">
        <Bilingual text={displayTitle(row.title)} en={c.note?.title_en} />
      </h2>
      {code && meaning && (
        <p className="text-xs text-muted-foreground">
          {c.code}: {code.letters} = {meaning}. {code.depth} {code.depth === 1 ? "level" : "levels"} deep in the plan.
        </p>
      )}

      {row.group.length > 1 && (
        <SimpleSelect
          label="Source mention"
          value={String(c.id)}
          onChange={(v) => setPicked(Number(v))}
          options={row.group.map((m) => ({
            value: String(m.id),
            label: `p.${m.source_page} · ${m.review_status === "accepted" ? "confirmed" : m.review_status === "rejected" ? "rejected" : "needs review"} · mention ${m.id}`,
          }))}
        />
      )}

      {row.stage === "confirm" ? (
        <CandidateDetail key={c.id} c={c} commitments={commitments} pdfUrl={documents[String(c.document_id)]} onDecided={onDecided} />
      ) : (
        <>
          {searchable && (
            <Button
              size="sm"
              variant="outline"
              className="self-start"
              disabled={!canReview || searching}
              onClick={() => onSearch(row.commitments.map((m) => m.id!))}
            >
              <SearchIcon data-icon="inline-start" />
              {searchedBefore ? "Search again" : "Find evidence"}
            </Button>
          )}
          {row.pending.length > 0 && (
            <section aria-labelledby="matches-heading" className="flex flex-col gap-2">
              <h3 id="matches-heading" className="text-sm font-medium">
                Matches to review
              </h3>
              {[...row.pending]
                .sort((a, b) => b.link.score - a.link.score)
                .map((lv) => (
                  <MatchCard key={lv.link.id} linkId={lv.link.id!} preview={lv} />
                ))}
            </section>
          )}
          <section aria-labelledby="trail-heading" className="flex flex-col gap-3">
            <h3 id="trail-heading" className="text-sm font-medium">
              Paper trail ({row.evidence})
            </h3>
            {row.trail.length ? (
              row.trail.map((t) => <TrailDetail key={t.commitment.id} t={t} />)
            ) : (
              <p className="text-muted-foreground">Nothing recorded for this commitment.</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
