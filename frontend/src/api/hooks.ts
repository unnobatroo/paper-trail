import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, unwrap, type Schemas } from "./client"

export type Filters = { stage: string; type: string; q: string }

export const useMeta = () =>
  useQuery({
    queryKey: ["meta"],
    queryFn: async () => unwrap(await api.GET("/api/meta")),
    staleTime: Infinity,
  })

export const useWorkspace = (f: Filters) =>
  useQuery({
    queryKey: ["workspace", f],
    queryFn: async () =>
      unwrap(await api.GET("/api/workspace", { params: { query: { stage: f.stage, type: f.type, q: f.q } } })),
    placeholderData: keepPreviousData,
  })

export const useLinkDetail = (linkId: number) =>
  useQuery({
    queryKey: ["link", linkId],
    queryFn: async () => unwrap(await api.GET("/api/links/{link_id}", { params: { path: { link_id: linkId } } })),
  })

export const useAvailableDocuments = (enabled: boolean) =>
  useQuery({
    queryKey: ["documents", "available"],
    queryFn: async () => unwrap(await api.GET("/api/documents/available")),
    enabled,
  })

/** Jobs of one kind that are queued or running; polled so a reload finds work in flight. */
export const useActiveJobs = (kind: "ingest" | "find_evidence") =>
  useQuery({
    queryKey: ["jobs", kind],
    queryFn: async () => unwrap(await api.GET("/api/jobs", { params: { query: { kind } } })),
    refetchInterval: 2000,
  })

/** Every review action, each refreshing the workspace when it succeeds. */
export function useReviewActions() {
  const qc = useQueryClient()
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["workspace"] })
    void qc.invalidateQueries({ queryKey: ["link"] })
  }
  const useAction = <V, R>(fn: (v: V) => Promise<R>) => useMutation({ mutationFn: fn, onSuccess: refresh })

  return {
    accept: useAction(
      async (v: { id: number; kind?: Schemas["CandidateType"]; title?: string; parentId?: number }) =>
        unwrap(
          await api.POST("/api/candidates/{candidate_id}/accept", {
            params: { path: { candidate_id: v.id } },
            body: { kind: v.kind ?? null, title: v.title ?? null, parent_id: v.parentId ?? null },
          }),
        ),
    ),
    reject: useAction(async (id: number) =>
      unwrap(await api.POST("/api/candidates/{candidate_id}/reject", { params: { path: { candidate_id: id } } })),
    ),
    bulkCandidates: useAction(async (v: { accept: number[]; reject: number[] }) =>
      unwrap(await api.POST("/api/candidates/bulk", { body: { ...v, reject_rest: false } })),
    ),
    decideLink: useAction(
      async (v: { id: number; decision: "accept" | "reject"; relationship?: Schemas["RelationshipType"] }) =>
        unwrap(
          await api.POST("/api/links/{link_id}/decide", {
            params: { path: { link_id: v.id } },
            body: { decision: v.decision, relationship: v.relationship ?? null },
          }),
        ),
    ),
    bulkLinks: useAction(async (v: { accept: number[]; reject: number[] }) =>
      unwrap(await api.POST("/api/links/bulk", { body: { ...v, relationships: {} } })),
    ),
    setJurisdiction: useAction(async (v: { id: number; jurisdiction: Schemas["Jurisdiction"] }) =>
      unwrap(
        await api.POST("/api/commitments/{commitment_id}/jurisdiction", {
          params: { path: { commitment_id: v.id } },
          body: { jurisdiction: v.jurisdiction },
        }),
      ),
    ),
    findEvidence: useAction(async (commitmentId: number) =>
      unwrap(
        await api.POST("/api/commitments/{commitment_id}/find-evidence", {
          params: { path: { commitment_id: commitmentId } },
        }),
      ),
    ),
    ingest: useAction(async (v: { name: string; title: string; publisher: string; url: string }) =>
      unwrap(await api.POST("/api/documents/ingest", { body: v })),
    ),
  }
}
