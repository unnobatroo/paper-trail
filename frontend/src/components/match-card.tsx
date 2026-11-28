import { useState } from "react"
import { CheckIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import type { LinkView, Schemas } from "@/api/client"
import { useLinkDetail, useReviewActions } from "@/api/hooks"
import { NoteCard } from "@/components/bilingual"
import { BudgetLine, EvidenceWarnings } from "@/components/evidence-bits"
import { Receipt } from "@/components/receipt"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import { useCanReview } from "@/lib/can-review"
import { FLAG_HELP, FLAG_LABEL, REL_HELP, REL_LABEL, STATUS_SENTENCE, evidenceKind } from "@/lib/labels"

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
    <article className="flex flex-col gap-3 border-t pt-4 first:border-t-0 first:pt-0">
      {ev ? (
        <>
          <header className="flex flex-col gap-0.5">
            <a href={ev.url} target="_blank" rel="noreferrer" className="type-body font-medium underline-offset-4 hover:underline">
              {ev.title || ev.url}
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
            <p className="type-label">
              {[ev.publisher, ev.published_on, evidenceKind(ev.url, ev.title)].filter(Boolean).join(" · ")}
            </p>
          </header>
          <Progress value={Math.round(link.score * 100)} aria-label="Match score">
            <ProgressLabel className="type-label font-normal">Match score</ProgressLabel>
            <ProgressValue className="type-label" />
          </Progress>
          <EvidenceWarnings ev={ev} />
          <p className="type-secondary">{STATUS_SENTENCE[ev.status_hint]}</p>
          {(ev.status_excerpt || ev.snippet) && <Receipt>{ev.status_excerpt || ev.snippet}</Receipt>}
        </>
      ) : (
        <Skeleton className="h-10 w-full" />
      )}

      <NoteCard note={lv.note} />

      <fieldset className="flex flex-col gap-1.5">
        <legend className="type-label mb-1">How does it relate?</legend>
        <RadioGroup value={relationship} onValueChange={setRelationship} className="gap-1.5">
          {Object.entries(REL_LABEL).map(([value, label]) => (
            <Label key={value} className="type-body flex items-center gap-2 font-normal">
              <RadioGroupItem value={value} />
              {label}
              {value === link.suggested_relationship && <span className="type-label">suggested</span>}
            </Label>
          ))}
        </RadioGroup>
        <p className="type-label">{REL_HELP[relationship]}</p>
      </fieldset>

      <div className="flex gap-2">
        <Button onClick={() => decide("accept")} disabled={!canReview || decideLink.isPending}>
          <CheckIcon data-icon="inline-start" />
          Confirm match
        </Button>
        <Button variant="outline" onClick={() => decide("reject")} disabled={!canReview || decideLink.isPending}>
          <XIcon data-icon="inline-start" />
          Reject
        </Button>
        <Button variant="ghost" className="ml-auto" aria-expanded={showDetails} onClick={() => setShowDetails((v) => !v)}>
          Why matched
        </Button>
      </div>

      {showDetails && (
        <div className="layer-surface flex flex-col gap-2 p-3">
          <p className="type-body">{link.reasons.join("; ") || "No matching explanation stored."}</p>
          {ev?.flags.map((flag) => (
            <p key={flag} className="type-body text-destructive">
              {FLAG_LABEL[flag]}: {FLAG_HELP[flag]}
            </p>
          ))}
          {lv.budgets.length > 0 && (
            <>
              <h4 className="type-label">Money mentioned</h4>
              {lv.budgets.slice(0, 4).map((b, i) => (
                <BudgetLine key={i} b={b} />
              ))}
            </>
          )}
        </div>
      )}
    </article>
  )
}
