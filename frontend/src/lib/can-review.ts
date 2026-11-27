import { useMeta } from "@/api/hooks"
import { usePrefs } from "@/lib/prefs"

/** Whether this browser may change anything: a deployment that needs a review key needs one saved first. */
export function useCanReview(): boolean {
  const meta = useMeta()
  const { reviewKey } = usePrefs()
  return !!meta.data && (!meta.data.review_required || reviewKey !== "")
}
