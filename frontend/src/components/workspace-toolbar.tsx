import { Rows2Icon, Rows3Icon } from "lucide-react"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { KIND_ORDER, KIND_SECTION } from "@/lib/labels"
import { usePrefs } from "@/lib/prefs"

type Props = {
  /** How many commitments each kind has in the current stage and search. */
  counts: Record<string, number>
  kind: string
  onKind: (kind: string) => void
}

/** Filter by kind, with counts, and the table's row density. Both are single-choice groups. */
export function WorkspaceToolbar({ counts, kind, onKind }: Props) {
  const { density, setDensity } = usePrefs()
  const total = Object.values(counts).reduce((n, c) => n + c, 0)
  const facets = [{ value: "all", label: "All", count: total }].concat(
    KIND_ORDER.filter((k) => counts[k]).map((k) => ({ value: k, label: KIND_SECTION[k], count: counts[k] })),
  )

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <ToggleGroup
        aria-label="Filter by type"
        variant="outline"
        size="sm"
        spacing={0}
        value={[kind]}
        onValueChange={(v) => onKind(v[0] ?? "all")}
      >
        {facets.map((f) => (
          <ToggleGroupItem key={f.value} value={f.value} className="gap-1.5">
            {f.label} <span className="text-muted-foreground tabular-nums">{f.count}</span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <ToggleGroup
        aria-label="Row density"
        variant="outline"
        size="sm"
        spacing={0}
        value={[density]}
        onValueChange={(v) => v[0] && setDensity(v[0] as "comfortable" | "compact")}
      >
        <ToggleGroupItem value="comfortable" aria-label="Comfortable rows"><Rows2Icon /></ToggleGroupItem>
        <ToggleGroupItem value="compact" aria-label="Compact rows"><Rows3Icon /></ToggleGroupItem>
      </ToggleGroup>
    </div>
  )
}
