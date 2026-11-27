import type { ReactNode } from "react"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { KIND_ORDER, KIND_SECTION } from "@/lib/labels"

type Props = {
  /** How many commitments each kind has in the current stage and search. */
  counts: Record<string, number>
  kind: string
  onKind: (kind: string) => void
  /** What to do with the selection, shown on the same line when there is one. */
  children?: ReactNode
}

/** The list's own toolbar: narrow it to one kind (counts stay whole), or act on the selection. */
export function KindFilter({ counts, kind, onKind, children }: Props) {
  const total = Object.values(counts).reduce((n, c) => n + c, 0)
  const facets = [{ value: "all", label: "All", count: total }].concat(
    KIND_ORDER.filter((k) => counts[k]).map((k) => ({ value: k, label: KIND_SECTION[k], count: counts[k] })),
  )

  // "All" plus a single kind is no choice at all
  const choosable = facets.length > 2
  if (!choosable && !children) return null

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 pt-3 pb-2">
      {choosable && <Tabs value={kind} onValueChange={(v) => onKind(String(v))}>
        <TabsList variant="line" aria-label="Filter by type" className="gap-4 p-0">
          {facets.map((f) => (
            <TabsTrigger key={f.value} value={f.value} className="type-label flex-none px-0 data-active:text-foreground group-data-horizontal/tabs:after:bottom-0">
              {f.label}{" "}
              <span className="type-num">{f.count}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>}
      {children}
    </div>
  )
}
