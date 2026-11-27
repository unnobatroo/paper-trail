import { useEffect } from "react"
import type { WorkspaceRow } from "@/api/client"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { KIND_LABEL, STAGE_INFO, goal } from "@/lib/labels"
import { usePrefs } from "@/lib/prefs"
import { rowTitle, shown } from "@/lib/rows"
import { cn } from "@/lib/utils"

type Props = {
  rows: WorkspaceRow[]
  /** Whether the stage is shown on each row: only when the list mixes stages. */
  showStage: boolean
  cursor: number | null
  selected: Set<number>
  onOpen: (id: number) => void
  onSelectMany: (ids: number[], on: boolean) => void
}

// One header for the whole ledger, kept on screen while the rows scroll under it.
const HEAD = "sticky top-0 z-10 h-9 border-b bg-background/70 font-semibold text-foreground backdrop-blur-xl"

/** The strategy's page numbers of a row, as it would be cited: "p. 6", or "p. 6, 138" for a repeated passage. */
export function folio(row: WorkspaceRow): string {
  const pages = [...new Set(row.group.map((m) => m.source_page))].sort((a, b) => a - b)
  return `p. ${pages.join(", ")}`
}

/** What is left to do on this row, in words. */
function pending(row: WorkspaceRow): string {
  if (row.stage === "review") return `${row.pending.length} to review`
  if (row.stage === "done") return `${row.evidence} ${row.evidence === 1 ? "source" : "sources"}`
  return ""
}

/**
 * The commitments in the order of the strategy, one entry each: page, title, and under it the
 * quote that makes it a commitment, so most can be judged without opening anything.
 */
export function Ledger({ rows, showStage, cursor, selected, onOpen, onSelectMany }: Props) {
  const { lang } = usePrefs()
  // moving with the keyboard must never leave the row out of sight
  useEffect(() => {
    document.querySelector("tr[data-cursor]")?.scrollIntoView?.({ block: "nearest" })
  }, [cursor])
  if (!rows.length) return <p className="p-6 text-muted-foreground">Nothing matches these filters.</p>

  // the last column says what is left to do; it only exists when some row has something to say
  const trailing = showStage || rows.some((r) => pending(r))
  const ids = rows.map((r) => r.id)
  const all = ids.every((id) => selected.has(id))
  const some = ids.some((id) => selected.has(id))

  return (
    // overflow-visible: the page's scroll area is what the sticky header sticks to
    <Table containerClassName="overflow-visible" className="table-fixed border-separate border-spacing-0">
      <TableHeader>
        <TableRow className="border-0 hover:bg-transparent">
          <TableHead className={cn(HEAD, "w-11 pl-5")}>
            <Checkbox
              aria-label="Select all shown"
              checked={all}
              indeterminate={some && !all}
              onCheckedChange={(on) => onSelectMany(ids, on)}
            />
          </TableHead>
          <TableHead scope="col" className={cn(HEAD, "w-28")}>Page</TableHead>
          <TableHead scope="col" className={HEAD}>Commitment</TableHead>
          <TableHead scope="col" className={cn(HEAD, "hidden w-28 md:table-cell")}>Type</TableHead>
          {trailing && (
            <TableHead scope="col" className={cn(HEAD, "hidden w-28 pr-5 text-right lg:table-cell")}>
              {showStage ? "Stage" : "Open"}
            </TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const c = shown(r)
          const isCursor = cursor === r.id
          const aim = goal(c) === "–" ? "" : goal(c)
          const left = showStage ? STAGE_INFO[r.stage].label : pending(r)
          return (
            <TableRow
              key={r.id}
              data-state={selected.has(r.id) ? "selected" : undefined}
              data-cursor={isCursor ? "" : undefined}
              onClick={() => onOpen(r.id)}
              className={cn(
                "group/row scroll-mt-9 cursor-pointer transition-colors [&>td]:border-b [&>td]:py-2 [&>td]:align-top",
                isCursor ? "bg-primary/10 hover:bg-primary/15" : "hover:bg-foreground/5",
              )}
            >
              <TableCell className="pl-5" onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  aria-label={`Select ${rowTitle(r, false)}`}
                  className={cn("transition-opacity", !selected.has(r.id) && !isCursor && "opacity-30 group-hover/row:opacity-100")}
                  checked={selected.has(r.id)}
                  onCheckedChange={(on) => onSelectMany([r.id], on)}
                />
              </TableCell>
              <TableCell className="whitespace-normal text-muted-foreground tabular-nums">{folio(r)}</TableCell>
              <TableCell className="whitespace-normal">
                <button
                  type="button"
                  className="text-left font-medium underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2"
                  aria-current={isCursor ? "true" : undefined}
                >
                  {rowTitle(r, lang === "en")}
                </button>
                {aim && <span className="ml-2 text-xs text-muted-foreground">{aim}</span>}
                {c.source_excerpt && (
                  <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">
                    {c.source_excerpt.replace(/\s+/g, " ")}
                  </p>
                )}
              </TableCell>
              <TableCell className="hidden text-muted-foreground md:table-cell">
                {KIND_LABEL[r.kind]}
              </TableCell>
              {trailing && (
                <TableCell className="hidden pr-5 text-right text-muted-foreground lg:table-cell">{left}</TableCell>
              )}
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
