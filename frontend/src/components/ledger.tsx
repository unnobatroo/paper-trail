import { useEffect } from "react"
import { InboxIcon, SearchIcon } from "lucide-react"

import type { WorkspaceRow } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { STAGE_INFO } from "@/lib/labels"
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
  /** Start the evidence search for one row, from the list itself. */
  onSearch?: (row: WorkspaceRow) => void
  searchDisabled?: boolean
}

/** Letters and digits only, so a quote that merely repeats the title can be told apart. */
const plain = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "")

// One header for the whole list, kept on screen while the rows scroll under it.
const HEAD = "sticky top-0 z-10 h-9 border-b bg-(--panel) type-label backdrop-blur-md"

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
 * quote that makes it a commitment, so most can be judged without opening anything. A thin
 * trail runs down the page column, one node per commitment.
 */
export function Ledger({ rows, showStage, cursor, selected, onOpen, onSelectMany, onSearch, searchDisabled }: Props) {
  const { lang } = usePrefs()
  // moving with the keyboard must never leave the row out of sight
  useEffect(() => {
    document.querySelector("tr[data-cursor]")?.scrollIntoView?.({ block: "nearest" })
  }, [cursor])
  if (!rows.length) {
    return (
      <div className="type-secondary flex flex-col items-center gap-2 p-10 text-center">
        <InboxIcon className="size-8 text-muted-foreground/60" aria-hidden="true" />
        Nothing matches these filters.
      </div>
    )
  }

  // the last column says what is left to do; it only exists when some row has something to say
  const trailing = showStage || rows.some((r) => pending(r) || (onSearch && !showStage && r.stage === "search"))
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
          <TableHead scope="col" className={cn(HEAD, "w-24")}>Page</TableHead>
          <TableHead scope="col" className={HEAD}>Commitment</TableHead>
          {trailing && (
            <TableHead scope="col" className={cn(HEAD, "hidden w-32 pr-5 text-right lg:table-cell")}>
              {showStage ? "Stage" : "To do"}
            </TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const c = shown(r)
          const isCursor = cursor === r.id
          const left = showStage ? STAGE_INFO[r.stage].label : pending(r)
          return (
            <TableRow
              key={r.id}
              data-state={selected.has(r.id) ? "selected" : undefined}
              data-cursor={isCursor ? "" : undefined}
              onClick={() => onOpen(r.id)}
              className={cn(
                "group/row scroll-mt-9 cursor-pointer transition-colors [&>td]:py-2 [&>td]:align-top",
                isCursor ? "layer-raised hover:bg-raised" : "hover:bg-accent",
                selected.has(r.id) && !isCursor && "bg-surface",
              )}
            >
              <TableCell
                className="cursor-default pl-5"
                onClick={(e) => {
                  e.stopPropagation()
                  // a click on the cell around the box counts as a click on the box
                  if (e.target === e.currentTarget) onSelectMany([r.id], !selected.has(r.id))
                }}
              >
                <Checkbox
                  aria-label={`Select ${rowTitle(r, false)}`}
                  className={cn("transition-opacity", !selected.has(r.id) && !isCursor && "opacity-30 group-hover/row:opacity-100")}
                  checked={selected.has(r.id)}
                  onCheckedChange={(on) => onSelectMany([r.id], on)}
                />
              </TableCell>
              <TableCell className="type-label type-num whitespace-normal">{folio(r)}</TableCell>
              <TableCell className="whitespace-normal">
                <button
                  type="button"
                  className="type-body text-left font-medium underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2"
                  aria-current={isCursor ? "true" : undefined}
                >
                  {rowTitle(r, lang === "en")}
                </button>
                {c.source_excerpt && plain(c.source_excerpt) !== plain(r.title) && (
                  <p className="type-secondary line-clamp-2">{c.source_excerpt.replace(/\s+/g, " ")}</p>
                )}
              </TableCell>
              {trailing && (
                <TableCell className="type-label hidden pr-5 text-right lg:table-cell">
                  {onSearch && r.stage === "search" && !showStage ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={searchDisabled}
                      onClick={(e) => {
                        e.stopPropagation()
                        onSearch(r)
                      }}
                    >
                      <SearchIcon data-icon="inline-start" />
                      Find evidence
                    </Button>
                  ) : (
                    left
                  )}
                </TableCell>
              )}
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
