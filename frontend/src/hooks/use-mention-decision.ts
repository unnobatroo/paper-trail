import { useCallback } from "react"
import { useIsMutating, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import type { Schemas } from "@/api/client"
import { MENTION_DECISION, useReviewActions } from "@/api/hooks"

type Edit = { kind?: Schemas["CandidateType"]; title?: string; parentId?: number }

/**
 * Confirm or reject one source mention: the one way to do it, for the buttons and the keyboard
 * alike. While any decision is on its way, from anywhere in the app, another is ignored, so a
 * click and a key press can't decide the same mention twice. The check asks the mutation cache
 * at the moment of the call, not a rendered value, so two presses in one frame are caught too.
 */
export function useMentionDecision() {
  const queryClient = useQueryClient()
  const { accept, reject } = useReviewActions()
  const pending = useIsMutating({ mutationKey: MENTION_DECISION }) > 0
  const acceptMention = accept.mutate
  const rejectMention = reject.mutate

  const decide = useCallback(
    (id: number, decision: "accept" | "reject", { edit, onDone }: { edit?: Edit; onDone?: () => void } = {}) => {
      if (queryClient.isMutating({ mutationKey: MENTION_DECISION }) > 0) return
      const done = (message: string) => () => {
        toast.success(message)
        onDone?.()
      }
      if (decision === "accept")
        acceptMention({ id, ...edit }, { onSuccess: done(edit ? "Saved as a commitment." : "Confirmed as a commitment.") })
      else rejectMention(id, { onSuccess: done("Rejected.") })
    },
    [queryClient, acceptMention, rejectMention],
  )

  return { decide, pending }
}
