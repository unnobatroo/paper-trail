import { useState } from "react"
import { CheckIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import type { Candidate, Commitment, Schemas } from "@/api/client"
import { useReviewActions } from "@/api/hooks"
import { NoteCard } from "@/components/bilingual"
import { SimpleSelect } from "@/components/simple-select"
import { ToneBadge } from "@/components/tone-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCanReview } from "@/lib/can-review"
import { KIND_LABEL, KIND_ORDER, displayTitle } from "@/lib/labels"

type Kind = Schemas["CandidateType"]

/** One source mention of a commitment: its status, the quote, and the confirm, reject and edit controls. */
export function CandidateDetail({ c, commitments }: { c: Candidate; commitments: Commitment[] }) {
  const { accept, reject } = useReviewActions()
  const canReview = useCanReview()
  const [editing, setEditing] = useState(false)
  const [kind, setKind] = useState<string>(c.suggested_type)
  const [title, setTitle] = useState(displayTitle(c.normalized_title))
  const [parent, setParent] = useState("0")
  const open = c.review_status === "unreviewed"

  // Quick confirm takes the suggestion as it is; the edit form's values count only while it is open.
  const confirm = () =>
    accept.mutate(
      editing
        ? { id: c.id!, kind: kind as Kind, title: title.trim() || undefined, parentId: Number(parent) || undefined }
        : { id: c.id! },
      { onSuccess: () => toast.success(editing ? "Saved as a commitment." : "Confirmed as a commitment.") },
    )

  return (
    <div className="flex flex-col gap-3">
      {c.review_status === "accepted" && <ToneBadge tone="green">Confirmed</ToneBadge>}
      {c.review_status === "rejected" && <ToneBadge tone="red">Rejected</ToneBadge>}
      {open && c.excerpt_on_page === false && (
        <>
          <ToneBadge>Unclear</ToneBadge>
          <p className="text-sm text-amber-900 dark:text-amber-300" role="note">
            We couldn't re-find this quote on the page. It's worth a closer look.
          </p>
        </>
      )}
      {open && c.excerpt_on_page !== false && <ToneBadge tone="amber">Needs review</ToneBadge>}

      <NoteCard note={c.note} />

      <Card size="sm">
        <CardContent className="flex flex-col gap-1">
          <h3 className="text-xs text-muted-foreground">The strategy says</h3>
          <blockquote className="italic">“{c.source_excerpt}”</blockquote>
        </CardContent>
      </Card>

      {open && (
        <>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={confirm} disabled={!canReview || accept.isPending}>
              <CheckIcon data-icon="inline-start" /> Confirm
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!canReview || reject.isPending}
              onClick={() => reject.mutate(c.id!, { onSuccess: () => toast.success("Rejected.") })}
            >
              <XIcon data-icon="inline-start" /> Reject
            </Button>
            <Button size="sm" variant="ghost" disabled={!canReview} aria-expanded={editing} onClick={() => setEditing((v) => !v)}>
              Edit before confirming
            </Button>
          </div>

          {editing && (
            <form
              className="flex flex-col gap-3 rounded-lg border p-3"
              onSubmit={(e) => {
                e.preventDefault()
                if (title.trim()) confirm()
              }}
            >
              <div className="flex flex-col gap-1.5">
                <Label>Type</Label>
                <SimpleSelect
                  label="Type"
                  value={kind}
                  onChange={setKind}
                  options={KIND_ORDER.map((k) => ({ value: k, label: KIND_LABEL[k] }))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="edit-title">Title</Label>
                <Input id="edit-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Part of</Label>
                <SimpleSelect
                  label="Part of"
                  value={parent}
                  onChange={setParent}
                  options={[
                    { value: "0", label: "— on its own —" },
                    ...commitments.map((m) => ({
                      value: String(m.id),
                      label: `${m.code ? m.code + " · " : ""}${displayTitle(m.title)} [${m.id}]`,
                    })),
                  ]}
                />
              </div>
              <div>
                <Button type="submit" size="sm" disabled={accept.isPending || !title.trim()}>
                  Save as commitment
                </Button>
              </div>
            </form>
          )}
        </>
      )}
    </div>
  )
}
