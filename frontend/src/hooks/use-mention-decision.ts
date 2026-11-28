import { useCallback } from "react"
import { toast } from "sonner"

import type { Schemas } from "@/api/client"
import { useReviewActions } from "@/api/hooks"

type Edit = { kind?: Schemas["CandidateType"]; title?: string; parentId?: number }

/**
 * Confirm or reject one source mention: the one way to do it, for the buttons and the keyboard
 * alike. A second decision while the first is still on its way is ignored, so a double press
 * can't decide the same mention twice.
 */
export function useMentionDecision() {
  const { accept, reject } = useReviewActions()
  const pending = accept.isPending || reject.isPending

  const decide = useCallback(
    (id: number, decision: "accept" | "reject", { edit, onDone }: { edit?: Edit; onDone?: () => void } = {}) => {
      if (pending) return
      const done = (message: string) => () => {
        toast.success(message)
        onDone?.()
      }
      if (decision === "accept")
        accept.mutate({ id, ...edit }, { onSuccess: done(edit ? "Saved as a commitment." : "Confirmed as a commitment.") })
      else reject.mutate(id, { onSuccess: done("Rejected.") })
    },
    [accept, reject, pending],
  )

  return { decide, pending }
}
