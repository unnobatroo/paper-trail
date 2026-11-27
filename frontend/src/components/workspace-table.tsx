import type { WorkspaceRow } from "@/api/client"
import { ToneBadge } from "@/components/tone-badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { KIND_ORDER, KIND_SECTION, STAGE_INFO, goal } from "@/lib/labels"
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

/** The commitments, one table per kind. Each row title is a button, so the keyboard can open it. */
export function WorkspaceTable({ rows, cursor, selected, onOpen, onSelectMany }: Props) {
  const { lang } = usePrefs()
  const sections = KIND_ORDER.map((kind) => ({ kind, rows: rows.filter((r) => r.kind === kind) })).filter((s) => s.rows.length)

  if (!sections.length) return <p className="p-6 text-muted-foreground">Nothing matches these filters.</p>

  return (
    <div className="flex flex-col gap-6">
      {sections.map(({ kind, rows: group }) => {
        const ids = group.map((r) => r.id)
        const all = ids.every((id) => selected.has(id))
        const some = ids.some((id) => selected.has(id))
        return (
          <section key={kind} aria-labelledby={`section-${kind}`}>
            <h2 id={`section-${kind}`} className="mb-2 text-sm font-medium">
              {KIND_SECTION[kind]} <span className="text-muted-foreground">({group.length})</span>
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      aria-label={`Select all ${KIND_SECTION[kind].toLowerCase()}`}
                      checked={all}
                      indeterminate={some && !all}
                      onCheckedChange={(on) => onSelectMany(ids, on)}
                    />
                  </TableHead>
                  <TableHead scope="col">Commitment</TableHead>
                  <TableHead scope="col">Stage</TableHead>
                  <TableHead scope="col" className="hidden md:table-cell">Evidence</TableHead>
                  <TableHead scope="col" className="hidden md:table-cell">Page</TableHead>
                  <TableHead scope="col" className="hidden md:table-cell">Goal</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.map((r) => {
                  const c = shown(r)
                  const stage = STAGE_INFO[r.stage]
                  const evidence = [r.evidence ? `✓${r.evidence}` : "", r.pending.length ? `${r.pending.length} to review` : ""]
                    .filter(Boolean)
                    .join(" ")
                  return (
                    <TableRow key={r.id} data-state={selected.has(r.id) ? "selected" : undefined} className={cn(cursor === r.id && "bg-muted")}>
                      <TableCell>
                        <Checkbox
                          aria-label={`Select ${rowTitle(r, false)}`}
                          checked={selected.has(r.id)}
                          onCheckedChange={(on) => onSelectMany([r.id], on)}
                        />
                      </TableCell>
                      <TableCell className="max-w-md whitespace-normal">
                        <button
                          type="button"
                          className="rounded-sm text-left font-medium underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2"
                          aria-current={cursor === r.id ? "true" : undefined}
                          onClick={() => onOpen(r.id)}
                        >
                          {rowTitle(r, lang === "en")}
                        </button>
                      </TableCell>
                      <TableCell>
                        <ToneBadge tone={stage.tone} title={stage.hint}>
                          {stage.label}
                        </ToneBadge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">{evidence || "–"}</TableCell>
                      <TableCell className="hidden md:table-cell">{c.source_page}</TableCell>
                      <TableCell className="hidden md:table-cell">{goal(c)}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </section>
        )
      })}
    </div>
  )
}
