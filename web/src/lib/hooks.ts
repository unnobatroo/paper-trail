"use client";

// shared tanstack query hooks + openapi-react-query client

import {useCallback} from "react";
import createQueryClient from "openapi-react-query";
import {useQueries, useQuery, useQueryClient} from "@tanstack/react-query";
import {api, client, type Job} from "./api";

export const $api = createQueryClient(client);

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
    activeJobs: (kind: string) => ["jobs", "active", kind] as const,
    translate: (text: string) => ["translate", text] as const,
};

export function useMeta() {
    return useQuery({queryKey: keys.meta, queryFn: api.meta, retry: 0});
}

export function useDocuments() {
    return useQuery({queryKey: keys.documents, queryFn: api.documents});
}

export function useCandidates() {
    return useQuery({queryKey: keys.candidates, queryFn: () => api.candidates()});
}

export function useCommitments() {
    return useQuery({queryKey: keys.commitments, queryFn: api.commitments});
}

export function useLinks() {
    // lite=1 keeps the queue small, the inspector grabs the full record via useLink
    return useQuery({queryKey: keys.links, queryFn: () => api.links(true)});
}

export function useLink(id: number | null) {
    return useQuery({
        queryKey: keys.link(id ?? -1),
        queryFn: () => api.link(id!),
        enabled: id != null,
    });
}

export function useTrail() {
    return useQuery({queryKey: keys.trail, queryFn: api.trail});
}

// refetch every domain list after a review mutation
export function useInvalidateDomain() {
    const qc = useQueryClient();
    return useCallback(() =>
        qc.invalidateQueries({
            predicate: (q) =>
                // "jobs" so a finished batch leaves the in-flight list
                ["candidates", "commitments", "links", "link", "trail", "documents", "jobs", "get"].includes(
                    q.queryKey[0] as string,
                ),
        }), [qc]);
}

// poll durable jobs until they're all done/failed
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
    return {
        jobs,
        running,
        error: results.find((r) => r.error)?.error ?? null,
        retry: () => Promise.all(results.map((r) => r.refetch())),
        settled: jobIds.length > 0 && results.every((r) =>
            r.isSuccess && (r.data.status === "done" || r.data.status === "failed")),
    };
}
