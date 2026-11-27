import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { KIND_ORDER, KIND_SECTION } from "@/lib/labels"

type Props = {
  /** How many commitments each kind has in the current stage and search. */
  counts: Record<string, number>
  kind: string
  onKind: (kind: string) => void
}

/** Narrow the list to one kind; the counts stay whole while one is selected. */
export function KindFilter({ counts, kind, onKind }: Props) {
  const total = Object.values(counts).reduce((n, c) => n + c, 0)
  const facets = [{ value: "all", label: "All", count: total }].concat(
    KIND_ORDER.filter((k) => counts[k]).map((k) => ({ value: k, label: KIND_SECTION[k], count: counts[k] })),
  )

  return (
    <Tabs value={kind} onValueChange={(v) => onKind(String(v))} className="px-4 pt-3 pb-1">
      <TabsList className="h-auto flex-wrap rounded-full bg-foreground/5 p-1" aria-label="Filter by type">
        {facets.map((f) => (
          <TabsTrigger key={f.value} value={f.value} className="flex-none rounded-full px-3 py-1 data-active:bg-background data-active:shadow-sm">
            {f.label}{" "}
            <span className="text-muted-foreground tabular-nums">{f.count}</span>
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
