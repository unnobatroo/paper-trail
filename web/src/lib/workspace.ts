"use client";

import {useMemo} from "react";
import type {LucideIcon} from "lucide-react";
import {CircleCheck, CircleX, FileCheck2, ListChecks, Search} from "lucide-react";
import type {CandidateType, Commitment, LinkView, PolicyCandidate, TrailRow} from "./api";
import {useCandidates, useCommitments, useLinks, useTrail} from "./hooks";
import {titleGroups} from "./labels";
import type {Tone} from "./tones";

// where a commitment is in the pipeline, one row = one commitment across all of it
export type Stage = "confirm" | "search" | "review" | "done" | "rejected";

export const STAGES: Record<Stage, { label: string; hint: string; icon: LucideIcon; tone: Tone }> = {
    confirm: {label: "To confirm", hint: "Check the promise against the strategy", icon: FileCheck2, tone: "amber"},
    search: {label: "To search", hint: "Find official sources", icon: Search, tone: "blue"},
    review: {label: "To review", hint: "Confirm or reject suggested matches", icon: ListChecks, tone: "purple"},
    done: {label: "Done", hint: "Nothing left to do", icon: CircleCheck, tone: "green"},
    rejected: {label: "Rejected", hint: "Not a commitment", icon: CircleX, tone: "gray"},
};
export const STAGE_ORDER: Stage[] = ["confirm", "search", "review", "done", "rejected"];

export const KIND_ORDER: CandidateType[] = ["objective", "target", "measure", "indicator", "background", "unclear"];
const SEARCHABLE = new Set<CandidateType>(["objective", "measure", "target"]);

export interface WorkRow {
    id: string;
    title: string;
    kind: CandidateType;
    group: PolicyCandidate[];
    commitments: Commitment[];
    trail: TrailRow[];
    pending: LinkView[];
    stage: Stage;
    evidence: number;
    searchable: boolean;
}

function stageOf(r: Omit<WorkRow, "stage" | "id">): Stage {
    if (r.group.some((c) => c.review_status === "unreviewed")) return "confirm";
    if (!r.commitments.length) return "rejected";
    if (r.pending.length) return "review";
    if (r.evidence > 0 || !r.searchable) return "done";
    return "search";
}

export function buildRows(
    cands: PolicyCandidate[],
    commitments: Commitment[],
    links: LinkView[],
    trail: TrailRow[],
): WorkRow[] {
    const comByCand = new Map<number, Commitment[]>();
    commitments.forEach((c) => {
        if (c.candidate_id != null) comByCand.set(c.candidate_id, [...(comByCand.get(c.candidate_id) ?? []), c]);
    });
    const trailById = new Map(trail.map((t) => [t.commitment.id, t]));
    const pendingByCom = new Map<number, LinkView[]>();
    links.forEach((l) => {
        if (l.link.review_status !== "unreviewed" || !l.evidence) return;
        pendingByCom.set(l.link.commitment_id, [...(pendingByCom.get(l.link.commitment_id) ?? []), l]);
    });

    return titleGroups(cands, (c) => c.normalized_title, (c) => c.suggested_type)
        .map((group) => {
            const coms = group.flatMap((c) => comByCand.get(c.id) ?? []);
            const rows = coms.map((c) => trailById.get(c.id)).filter((t): t is TrailRow => !!t);
            const base = {
                title: group[0].normalized_title,
                kind: group[0].suggested_type,
                group,
                commitments: coms,
                trail: rows,
                pending: coms.flatMap((c) => pendingByCom.get(c.id) ?? []),
                evidence: rows.reduce((n, t) => n + t.evidence.length, 0),
                searchable: SEARCHABLE.has(group[0].suggested_type),
            };
            return {...base, id: String(group[0].id), stage: stageOf(base)};
        })
        .sort(
            (a, b) =>
                KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) ||
                a.group[0].source_page - b.group[0].source_page,
        );
}

export function useWorkspace() {
    const c = useCandidates();
    const m = useCommitments();
    const l = useLinks();
    const t = useTrail();
    const rows = useMemo(
        () => buildRows(c.data ?? [], m.data ?? [], l.data ?? [], t.data ?? []),
        [c.data, m.data, l.data, t.data],
    );
    return {
        rows,
        isLoading: c.isLoading || m.isLoading || l.isLoading || t.isLoading,
        error: c.error ?? m.error ?? l.error ?? t.error ?? null,
        refetch: () => Promise.all([c.refetch(), m.refetch(), l.refetch(), t.refetch()]),
    };
}
