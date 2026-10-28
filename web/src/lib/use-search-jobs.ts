"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, errorMessage } from "./api";
import { keys, useInvalidateDomain, useJobs } from "./hooks";

// starts evidence searches and follows them, the server is the source of truth
// for what is running so a reload or another tab keeps following in-flight jobs
export function useSearchJobs() {
  const invalidate = useInvalidateDomain();
  const [startedIds, setStartedIds] = useState<string[]>([]);
  const { data: inFlight } = useQuery({
    queryKey: keys.activeJobs("find_evidence"),
    queryFn: () => api.activeJobs("find_evidence"),
  });
  const jobIds = startedIds.length ? startedIds : (inFlight ?? []).map((j) => j.id);
  const { jobs, settled, error, retry } = useJobs(jobIds);

  const notified = useRef("");
  useEffect(() => {
    const batch = jobIds.join(",");
    if (!settled || notified.current === batch) return;
    notified.current = batch;
    const total = jobs.reduce((n, j) => n + (j.result?.links ?? 0), 0);
    const failed = jobs.filter((j) => j.status === "failed");
    if (failed.length) toast.error(`${failed.length} search(es) failed: ${failed[0].error ?? "unknown"}`);
    else toast.success(total ? `Search done: ${total} possible matches.` : "Search done: nothing useful on the official sites.");
    jobs.flatMap((j) => j.result?.warnings ?? []).forEach((w) => toast.warning(w));
    setStartedIds([]);
    invalidate();
  }, [settled, jobs, jobIds, invalidate]);

  const start = useMutation({
    mutationFn: async (commitmentIds: number[]) => {
      const ids: string[] = [];
      for (const id of commitmentIds) {
        try {
          ids.push((await api.findEvidence(id)).id);
        } catch (e) {
          toast.error(`Could not start search: ${errorMessage(e)}`);
          break;
        }
      }
      return ids;
    },
    onSuccess: (ids) => setStartedIds(ids),
    onError: (e) => toast.error(errorMessage(e)),
  });

  return {
    start,
    jobs,
    running: jobIds.length > 0 && !settled,
    error,
    retry,
  };
}
