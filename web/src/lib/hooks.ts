"use client";

/** Shared TanStack Query hooks + query keys for the Paper Trail API. */

import {
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, type Job } from "./api";

export const keys = {
  meta: ["meta"] as const,
  documents: ["documents"] as const,
  availableDocs: ["available-docs"] as const,
  candidates: ["candidates"] as const,
  commitments: ["commitments"] as const,
  links: ["links"] as const,
  link: (id: number) => ["link", id] as const,
  trail: ["trail"] as const,
  job: (id: string) => ["job", id] as const,
  translate: (text: string) => ["translate", text] as const,
};

export function useMeta() {
  return useQuery({ queryKey: keys.meta, queryFn: api.meta, retry: 0 });
}

export function useDocuments() {
  return useQuery({ queryKey: keys.documents, queryFn: api.documents });
}

export function useCandidates() {
  return useQuery({ queryKey: keys.candidates, queryFn: () => api.candidates() });
}

export function useCommitments() {
  return useQuery({ queryKey: keys.commitments, queryFn: api.commitments });
}

export function useLinks() {
  // lite=1 keeps the queue payload small — the inspector fetches the
  // full evidence record on demand via useLink
  return useQuery({ queryKey: keys.links, queryFn: () => api.links(true) });
}

export function useLink(id: number | null) {
  return useQuery({
    queryKey: keys.link(id ?? -1),
    queryFn: () => api.link(id!),
    enabled: id != null,
  });
}

export function useTrail() {
  return useQuery({ queryKey: keys.trail, queryFn: api.trail });
}

/** Invalidate every domain list after a review mutation. */
export function useInvalidateDomain() {
  const qc = useQueryClient();
  return () =>
    qc.invalidateQueries({
      predicate: (q) =>
        ["candidates", "commitments", "links", "trail", "documents"].includes(
          q.queryKey[0] as string,
        ),
    });
}

/** Poll a set of durable jobs until all reach done/failed. */
export function useJobs(jobIds: string[]) {
  const results = useQueries({
    queries: jobIds.map((id) => ({
      queryKey: keys.job(id),
      queryFn: () => api.job(id),
      refetchInterval: (q: { state: { data?: Job } }) =>
        q.state.data &&
        (q.state.data.status === "done" || q.state.data.status === "failed")
          ? false
          : 2000,
    })),
  });
  const jobs = results
    .map((r) => r.data)
    .filter((j): j is Job => !!j);
  const running = jobs.some(
    (j) => j.status === "queued" || j.status === "running",
  );
  return { jobs, running, settled: jobIds.length > 0 && !running };
}
