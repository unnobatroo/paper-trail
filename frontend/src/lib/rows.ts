import type { Candidate, WorkspaceRow } from "@/api/client"
import { displayTitle } from "@/lib/labels"

/** The source mention the panel shows: the one picked, else the first still open, else the first. */
export function shown(row: WorkspaceRow, picked?: number): Candidate {
  return (
    row.group.find((c) => c.id === picked) ??
    row.group.find((c) => c.review_status === "unreviewed") ??
    row.group[0]
  )
}

/** The lowest page any mention of the row sits on: where the row belongs in the strategy's order. */
export function firstPage(row: WorkspaceRow): number {
  return Math.min(...row.group.map((m) => m.source_page))
}

/** The title a row shows in the table: the English reading aid first when the reader wants English. */
export function rowTitle(row: WorkspaceRow, english: boolean): string {
  const title = displayTitle(row.title)
  const en = shown(row).note?.title_en
  return english && en ? `${en} · ${title}` : title
}

/** Split "M1.2" into its letters and its depth, for the glossary hint; null when it isn't a code. */
export function parseCode(code: string | null | undefined): { letters: string; depth: number } | null {
  const m = /^([A-Za-z]+)(\d+(?:\.\d+)*)/.exec(code ?? "")
  return m ? { letters: m[1], depth: m[2].split(".").length } : null
}
