import { useState } from "react"
import { CheckIcon, PencilIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import type { Candidate, Commitment, Schemas } from "@/api/client"
import { useReviewActions } from "@/api/hooks"
import { NoteCard } from "@/components/bilingual"
import { SimpleSelect } from "@/components/simple-select"
import { Button } from "@/components/ui/button"
import { SourcePage } from "@/components/source-page"
import { Receipt } from "@/components/receipt"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCanReview } from "@/lib/can-review"
import { KIND_LABEL, KIND_ORDER, displayTitle } from "@/lib/labels"

type Kind = Schemas["CandidateType"]

/** One source mention of a commitment: its status, the quote, and the confirm, reject and edit controls. */
export function CandidateDetail({
  c,
  commitments,
  pdfUrl,
  onDecided,
}: {
  c: Candidate
  commitments: Commitment[]
  /** The strategy PDF this mention was read from, shown at its page next to the decision. */
  pdfUrl?: string
  /** Called once a confirm or reject has gone through, so the workspace can move on to the next row. */
  onDecided?: () => void
}) {
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
      {
        onSuccess: () => {
          toast.success(editing ? "Saved as a commitment." : "Confirmed as a commitment.")
          onDecided?.()
        },
      },
    )

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {!open && (
        <p className="type-label">{c.review_status === "accepted" ? "Confirmed as a commitment" : "Rejected"}</p>
      )}
      {open && c.excerpt_on_page === false && (
        <p className="type-secondary text-destructive" role="note">
          We couldn't re-find this quote on the page. It's worth a closer look.
        </p>
      )}

      <Receipt>{c.source_excerpt}</Receipt>

      {open && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button title="Confirm (c)" aria-keyshortcuts="c" onClick={confirm} disabled={!canReview || accept.isPending}>
              <CheckIcon data-icon="inline-start" />
              Confirm
            </Button>
            <Button
              variant="outline"
              title="Reject (r)"
              aria-keyshortcuts="r"
              disabled={!canReview || reject.isPending}
              onClick={() =>
                reject.mutate(c.id!, {
                  onSuccess: () => {
                    toast.success("Rejected.")
                    onDecided?.()
                  },
                })
              }
            >
              <XIcon data-icon="inline-start" />
              Reject
            </Button>
            <Button variant="ghost" disabled={!canReview} aria-expanded={editing} onClick={() => setEditing((v) => !v)}>
              <PencilIcon data-icon="inline-start" />
              Edit
            </Button>
          </div>

          {editing && (
            <form
              className="layer-surface flex flex-col gap-3 p-3"
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

      <NoteCard note={c.note} />

      <SourcePage candidateId={c.id!} pdfUrl={pdfUrl} page={c.source_page} />
    </div>
  )
}
