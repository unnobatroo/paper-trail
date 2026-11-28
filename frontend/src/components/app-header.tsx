import type { Ref } from "react"
import {
  BanIcon,
  BookOpenIcon,
  CircleCheckIcon,
  ClipboardCheckIcon,
  InboxIcon,
  KeyboardIcon,
  ListIcon,
  Loader2Icon,
  SearchIcon,
  Settings2Icon,
  UploadIcon,
  type LucideIcon,
} from "lucide-react"

import { useMeta } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCanReview } from "@/lib/can-review"
import { STAGE_INFO, STAGES, type Stage } from "@/lib/labels"

// One icon per stage, so the same word always comes with the same picture.
const STAGE_ICON: Record<Stage | "all", LucideIcon> = {
  all: ListIcon,
  confirm: ClipboardCheckIcon,
  search: SearchIcon,
  review: InboxIcon,
  done: CircleCheckIcon,
  rejected: BanIcon,
}

type Props = {
  stage: string
  counts: Record<string, number>
  onStage: (stage: string) => void
  q: string
  onQ: (q: string) => void
  searchRef: Ref<HTMLInputElement>
  /** What running jobs are doing, shown while there are any. */
  progress: string | null
  ingesting: boolean
  onIngest: () => void
  onGlossary: () => void
  onShortcuts: () => void
  onSettings: () => void
}

/** A header action: icon and word where there is room, the icon alone (with the word as its name) where there is not. */
function Action({ icon: Icon, label, ...props }: { icon: LucideIcon; label: string } & React.ComponentProps<typeof Button>) {
  return (
    <Button variant="ghost" size="sm" title={label} {...props}>
      <Icon data-icon="inline-start" />
      <span className="max-2xl:sr-only">{label}</span>
    </Button>
  )
}

/**
 * The top of the page. A commitment travels confirm, search, review, done, so the stages are
 * laid out in that order as the page's own navigation, each with how many wait there.
 */
export function AppHeader({
  stage, counts, onStage, q, onQ, searchRef, progress, ingesting, onIngest, onGlossary, onShortcuts, onSettings,
}: Props) {
  const meta = useMeta()
  const canReview = useCanReview()
  const all = Object.entries(counts).reduce((n, [s, c]) => n + (s === "rejected" ? 0 : c), 0)

  return (
    <header className="layer-panel relative z-20 flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-3">
      <div className="flex items-baseline gap-2">
        <h1 className="type-title">Paper Trail</h1>
        {meta.data?.deployment && <span className="type-label">{meta.data.deployment}</span>}
      </div>

      <Tabs value={stage} onValueChange={(v) => onStage(String(v))} className="max-md:w-full">
        <TabsList aria-label="Review stages" className="group-data-horizontal/tabs:h-auto md:flex-wrap max-md:w-full max-md:justify-start max-md:overflow-x-auto max-md:[scrollbar-width:none]">
          {(["all", ...STAGES] as const).map((s) => {
            const Icon = STAGE_ICON[s]
            return (
              <TabsTrigger key={s} value={s} title={s === "all" ? "Everything except rejected" : STAGE_INFO[s].hint}>
                <Icon aria-hidden="true" className="max-2xl:hidden" />
                {s === "all" ? "All" : STAGE_INFO[s].label}{" "}
                <span className="type-num text-muted-foreground in-data-active:text-brand-ink">{s === "all" ? all : (counts[s] ?? 0)}</span>
              </TabsTrigger>
            )
          })}
        </TabsList>
      </Tabs>

      <div className="flex items-center gap-1 max-md:w-full md:ml-auto">
        {progress && (
          <p role="status" className="type-label mr-2 flex items-center gap-1.5">
            <Loader2Icon className="size-3.5 animate-spin text-brand-ink" aria-hidden="true" />
            {progress}
          </p>
        )}
        <div className="relative mr-1 max-md:flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            ref={searchRef}
            type="search"
            aria-label="Search commitments"
            placeholder="Search…"
            className="layer-raised h-9 w-full rounded-full border-0 pl-9 md:w-44 2xl:w-60"
            value={q}
            onChange={(e) => onQ(e.target.value)}
          />
        </div>
        <Action icon={UploadIcon} label={ingesting ? "Reading…" : "Ingest"} onClick={onIngest} disabled={!canReview || ingesting} />
        {!!meta.data?.glossary.length && <Action icon={BookOpenIcon} label="Glossary" onClick={onGlossary} />}
        <Action icon={KeyboardIcon} label="Shortcuts" onClick={onShortcuts} className="max-md:hidden" />
        <Action icon={Settings2Icon} label="Settings" onClick={onSettings} />
      </div>
    </header>
  )
}
