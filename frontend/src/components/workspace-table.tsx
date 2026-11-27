import { useState } from "react"
import { ChevronDownIcon, ChevronRightIcon } from "lucide-react"

import type { WorkspaceRow } from "@/api/client"
import { ToneBadge } from "@/components/tone-badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { KIND_ORDER, KIND_SECTION, KIND_TONE, STAGE_INFO, goal } from "@/lib/labels"
import { usePrefs } from "@/lib/prefs"
import { rowTitle, shown } from "@/lib/rows"
import { cn } from "@/lib/utils"

type Props = {
  rows: WorkspaceRow[]
  cursor: number | null
  selected: Set<number>
  onOpen: (id: number) => void
  onSelectMany: (ids: number[], on: boolean) => void
}

// One header for the whole table, kept on screen while the rows scroll under it.
const HEAD = "sticky top-0 z-10 h-9 bg-secondary text-xs font-semibold tracking-wide text-secondary-foreground uppercase"

/** The commitments in one table: a single sticky header, with a collapsible group per kind. */
export function WorkspaceTable({ rows, cursor, selected, onOpen, onSelectMany }: Props) {
  const { lang, density } = usePrefs()
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const sections = KIND_ORDER.map((kind) => ({ kind, rows: rows.filter((r) => r.kind === kind) })).filter((s) => s.rows.length)

  if (!sections.length) return <p className="p-6 text-muted-foreground">Nothing matches these filters.</p>

  const toggle = (kind: string) =>
    setCollapsed((s) => {
      const next = new Set(s)
      if (!next.delete(kind)) next.add(kind)
      return next
    })

  return (
    // overflow-visible: the page's scroll area is what the sticky header sticks to
    <Table containerClassName="overflow-visible">
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className={cn(HEAD, "w-10")}>
            <span className="sr-only">Select</span>
          </TableHead>
          <TableHead scope="col" className={HEAD}>Commitment</TableHead>
          <TableHead scope="col" className={HEAD}>Stage</TableHead>
          <TableHead scope="col" className={cn(HEAD, "hidden md:table-cell")}>Evidence</TableHead>
          <TableHead scope="col" className={cn(HEAD, "hidden md:table-cell")}>Page</TableHead>
          <TableHead scope="col" className={cn(HEAD, "hidden md:table-cell")}>Goal</TableHead>
        </TableRow>
      </TableHeader>
      {sections.map(({ kind, rows: group }) => {
        const ids = group.map((r) => r.id)
        const all = ids.every((id) => selected.has(id))
        const some = ids.some((id) => selected.has(id))
        const isCollapsed = collapsed.has(kind)
        return (
          <TableBody key={kind}>
            <TableRow className="bg-muted/60 hover:bg-muted/60">
              <TableCell>
                <Checkbox
                  aria-label={`Select all ${KIND_SECTION[kind].toLowerCase()}`}
                  checked={all}
                  indeterminate={some && !all}
                  onCheckedChange={(on) => onSelectMany(ids, on)}
                />
              </TableCell>
              <TableCell colSpan={5} className="py-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-2 gap-1.5 font-semibold"
                  aria-expanded={!isCollapsed}
                  onClick={() => toggle(kind)}
                >
                  {isCollapsed ? <ChevronRightIcon /> : <ChevronDownIcon />}
                  {KIND_SECTION[kind]}
                  <ToneBadge tone={KIND_TONE[kind]}>{group.length}</ToneBadge>
                </Button>
              </TableCell>
            </TableRow>
            {!isCollapsed &&
              group.map((r) => {
                const c = shown(r)
                const stage = STAGE_INFO[r.stage]
                const evidence = [r.evidence ? `✓${r.evidence}` : "", r.pending.length ? `${r.pending.length} to review` : ""]
                  .filter(Boolean)
                  .join(" ")
                const isCursor = cursor === r.id
                return (
                  <TableRow
                    key={r.id}
                    data-state={selected.has(r.id) ? "selected" : undefined}
                    className={cn(
                      density === "compact" ? "[&_td]:py-1" : "[&_td]:py-2.5",
                      isCursor && "bg-accent shadow-[inset_3px_0_0_var(--primary)] hover:bg-accent",
                    )}
                  >
                    <TableCell>
                      <Checkbox
                        aria-label={`Select ${rowTitle(r, false)}`}
                        checked={selected.has(r.id)}
                        onCheckedChange={(on) => onSelectMany([r.id], on)}
                      />
                    </TableCell>
                    <TableCell className="max-w-md whitespace-normal">
                      <Button
                        variant="link"
                        className="h-auto justify-start p-0 text-left font-medium whitespace-normal text-foreground"
                        aria-current={isCursor ? "true" : undefined}
                        onClick={() => onOpen(r.id)}
                      >
                        {rowTitle(r, lang === "en")}
                      </Button>
                    </TableCell>
                    <TableCell>
                      <ToneBadge tone={stage.tone} title={stage.hint}>
                        {stage.label}
                      </ToneBadge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{evidence || "–"}</TableCell>
                    <TableCell className="hidden tabular-nums md:table-cell">{c.source_page}</TableCell>
                    <TableCell className="hidden md:table-cell">{goal(c)}</TableCell>
                  </TableRow>
                )
              })}
          </TableBody>
        )
      })}
    </Table>
  )
}
