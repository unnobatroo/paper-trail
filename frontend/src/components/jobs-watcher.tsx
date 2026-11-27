import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, unwrap, type Job } from "@/api/client"
import { useActiveJobs } from "@/api/hooks"

/** Fires `onFinish` once for each job of `kind` that stops being queued or running. */
function useFinishedJobs(kind: "ingest" | "find_evidence", onFinish: (job: Job) => void) {
  const active = useActiveJobs(kind).data
  const before = useRef<Set<string> | null>(null)
  const handler = useRef(onFinish)
  useEffect(() => {
    handler.current = onFinish
  })

  useEffect(() => {
    if (!active) return
    const now = new Set(active.map((j) => j.id))
    for (const id of before.current ?? []) {
      if (!now.has(id)) {
        void api.GET("/api/jobs/{job_id}", { params: { path: { job_id: id } } }).then((r) => handler.current(unwrap(r)))
          .catch((e: Error) => toast.error(`Could not read a finished job: ${e.message}`))
      }
    }
    before.current = now
  }, [active])
}

type Result = { links?: number; candidates?: number; warnings?: string[] }

/** Turns finished background jobs into notifications and refreshes the workspace. Renders nothing. */
export function JobsWatcher() {
  const qc = useQueryClient()
  const refresh = () => void qc.invalidateQueries({ queryKey: ["workspace"] })

  useFinishedJobs("find_evidence", (job) => {
    refresh()
    const result = (job.result ?? {}) as Result
    if (job.status === "failed") toast.error(`Search failed: ${job.error ?? "unknown error"}`)
    else toast.success(result.links ? `Search done: ${result.links} possible matches.` : "Search done: nothing useful on the official sites.")
    result.warnings?.forEach((w) => toast.warning(w))
  })

  useFinishedJobs("ingest", (job) => {
    refresh()
    const result = (job.result ?? {}) as Result
    if (job.status === "failed") toast.error(`Ingest failed: ${job.error ?? "unknown error"}`)
    else toast.success("Strategy read. Review the commitments it produced.")
    result.warnings?.forEach((w) => toast.warning(w))
  })

  return null
}
