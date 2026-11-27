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
    <Tabs value={kind} onValueChange={(v) => onKind(String(v))} className="border-b px-5 py-2">
      <TabsList variant="line" className="h-7 gap-4 p-0" aria-label="Filter by type">
        {facets.map((f) => (
          <TabsTrigger key={f.value} value={f.value} className="flex-none px-0">
            {f.label}{" "}
            <span className="text-muted-foreground tabular-nums">{f.count}</span>
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
