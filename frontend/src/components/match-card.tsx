import { useState } from "react"
import { CheckIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import type { LinkView, Schemas } from "@/api/client"
import { useLinkDetail, useReviewActions } from "@/api/hooks"
import { NoteCard } from "@/components/bilingual"
import { BudgetLine, EvidenceWarnings } from "@/components/evidence-bits"
import { Receipt } from "@/components/receipt"
import { SimpleSelect } from "@/components/simple-select"
import { ToneBadge } from "@/components/tone-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useCanReview } from "@/lib/can-review"
import { FLAG_HELP, FLAG_LABEL, REL_HELP, REL_LABEL, REL_TONE, STATUS_SENTENCE, evidenceKind } from "@/lib/labels"

/** One suggested match: its evidence, why it matched, and the confirm and reject buttons. */
export function MatchCard({ linkId, preview }: { linkId: number; preview: LinkView }) {
  const detail = useLinkDetail(linkId)
  const lv = detail.data ?? preview
  const { decideLink } = useReviewActions()
  const canReview = useCanReview()
  const link = lv.link
  const ev = lv.evidence
  const [relationship, setRelationship] = useState<string>(link.suggested_relationship)
  const [showDetails, setShowDetails] = useState(false)

  const decide = (decision: "accept" | "reject") =>
    decideLink.mutate(
      { id: link.id!, decision, relationship: decision === "accept" ? (relationship as Schemas["RelationshipType"]) : undefined },
      { onSuccess: () => toast.success(decision === "accept" ? "Match confirmed." : "Match rejected.") },
    )

  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <ToneBadge title="Match score">{link.score.toFixed(2)}</ToneBadge>
          <ToneBadge tone={REL_TONE[link.suggested_relationship]}>{REL_LABEL[link.suggested_relationship]}</ToneBadge>
          {ev && <ToneBadge>{evidenceKind(ev.url, ev.title)}</ToneBadge>}
        </div>

        {ev ? (
          <>
            <a href={ev.url} target="_blank" rel="noreferrer" className="font-medium underline-offset-4 hover:underline">
              {ev.title || ev.url}
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
            {(ev.publisher || ev.published_on) && (
              <p className="text-xs text-muted-foreground">{[ev.publisher, ev.published_on].filter(Boolean).join(" · ")}</p>
            )}
            <EvidenceWarnings ev={ev} />
            <p className="text-sm">{STATUS_SENTENCE[ev.status_hint]}</p>
            {(ev.status_excerpt || ev.snippet) && (
              <Receipt caption="The source says" className="text-sm">{ev.status_excerpt || ev.snippet}</Receipt>
            )}
          </>
        ) : (
          <Skeleton className="h-10 w-full" />
        )}

        <NoteCard note={lv.note} />

        <Button size="sm" variant="ghost" className="self-start" aria-expanded={showDetails} onClick={() => setShowDetails((v) => !v)}>
          Details
        </Button>
        {showDetails && (
          <div className="flex flex-col gap-2 rounded-lg border p-3">
            <h4 className="text-xs text-muted-foreground">Why Paper Trail matched it</h4>
            <p className="text-sm">{link.reasons.join("; ") || "No matching explanation stored."}</p>
            {ev?.flags.map((flag) => (
              <p key={flag} className="text-sm text-amber-900 dark:text-amber-300">
                {FLAG_LABEL[flag]}: {FLAG_HELP[flag]}
              </p>
            ))}
            {lv.budgets.length > 0 && (
              <>
                <h4 className="text-xs text-muted-foreground">Money mentioned</h4>
                {lv.budgets.slice(0, 4).map((b, i) => (
                  <BudgetLine key={i} b={b} />
                ))}
              </>
            )}
            <SimpleSelect
              label="Relationship"
              value={relationship}
              onChange={setRelationship}
              options={Object.entries(REL_LABEL).map(([value, label]) => ({ value, label }))}
            />
            <p className="text-xs text-muted-foreground">{REL_HELP[relationship]}</p>
            <p className="text-xs text-muted-foreground">Applied when you confirm this match.</p>
          </div>
        )}

        <div className="flex gap-2">
          <Button size="sm" onClick={() => decide("accept")} disabled={!canReview || decideLink.isPending}>
            <CheckIcon data-icon="inline-start" /> Confirm
          </Button>
          <Button size="sm" variant="outline" onClick={() => decide("reject")} disabled={!canReview || decideLink.isPending}>
            <XIcon data-icon="inline-start" /> Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
