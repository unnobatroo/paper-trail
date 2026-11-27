import type { Candidate, WorkspaceOut, WorkspaceRow } from "@/api/client"

/** A candidate with sensible defaults; override what the test cares about. */
export function candidate(over: Partial<Candidate> = {}): Candidate {
  return {
    id: 1,
    document_id: 1,
    suggested_type: "measure",
    text: "Fák ültetése a kerületben",
    normalized_title: "Fák ültetése",
    source_page: 6,
    source_excerpt: "Fák ültetése a kerületben",
    review_status: "unreviewed",
    excerpt_on_page: true,
    code: null,
    responsible_org: null,
    timeframe: null,
    deadline_year: null,
    unit: null,
    target_value: null,
    note: null,
    ...over,
  } as Candidate
}

/** A workspace row in the "to confirm" stage. */
export function row(over: Partial<WorkspaceRow> = {}): WorkspaceRow {
  const group = over.group ?? [candidate()]
  return {
    id: group[0].id!,
    title: group[0].normalized_title,
    kind: "measure",
    stage: "confirm",
    group,
    commitments: [],
    trail: [],
    pending: [],
    evidence: 0,
    searchable: true,
    ...over,
  } as WorkspaceRow
}

export function workspace(rows: WorkspaceRow[]): WorkspaceOut {
  const counts = { confirm: 0, search: 0, review: 0, done: 0, rejected: 0 }
  rows.forEach((r) => (counts[r.stage] += 1))
  return { rows, stage_counts: counts, commitments: [], documents: { "1": "https://example.org/strategy.pdf" } }
}
