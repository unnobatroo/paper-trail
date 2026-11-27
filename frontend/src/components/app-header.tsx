import type { Ref } from "react"
import {
  BanIcon,
  BookOpenIcon,
  CircleCheckIcon,
  ClipboardCheckIcon,
  InboxIcon,
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
  onSettings: () => void
}

/**
 * The top of the page. A commitment travels confirm, search, review, done, so the stages are
 * laid out in that order as the page's own navigation, each with how many wait there.
 */
export function AppHeader({ stage, counts, onStage, q, onQ, searchRef, progress, ingesting, onIngest, onGlossary, onSettings }: Props) {
  const meta = useMeta()
  const canReview = useCanReview()
  const all = Object.entries(counts).reduce((n, [s, c]) => n + (s === "rejected" ? 0 : c), 0)

  return (
    <header className="sticky top-0 z-20 flex flex-col gap-2 border-b bg-background/60 px-5 pt-3 backdrop-blur-md">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <h1 className="text-lg leading-none font-semibold">Paper Trail</h1>
        {meta.data?.deployment && <span className="text-xs text-muted-foreground">{meta.data.deployment}</span>}
        {progress && (
          <p role="status" className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
            {progress}
          </p>
        )}
        <div className="ml-auto flex items-center gap-1">
          <div className="relative mr-2">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              ref={searchRef}
              type="search"
              aria-label="Search commitments"
              placeholder="Search commitments"
              className="h-8 w-64 pl-8"
              value={q}
              onChange={(e) => onQ(e.target.value)}
            />
          </div>
          <Button variant="ghost" size="sm" onClick={onIngest} disabled={!canReview || ingesting}>
            <UploadIcon data-icon="inline-start" />
            {ingesting ? "Reading…" : "Ingest"}
          </Button>
          {!!meta.data?.glossary.length && (
            <Button variant="ghost" size="sm" onClick={onGlossary}>
              <BookOpenIcon data-icon="inline-start" />
              Glossary
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onSettings}>
            <Settings2Icon data-icon="inline-start" />
            Settings
          </Button>
        </div>
      </div>

      <Tabs value={stage} onValueChange={(v) => onStage(String(v))}>
        <TabsList variant="line" className="h-9 gap-5 p-0" aria-label="Review stages">
          {(["all", ...STAGES] as const).map((s, i) => {
            const Icon = STAGE_ICON[s]
            return (
            <TabsTrigger
              key={s}
              value={s}
              title={s === "all" ? "Everything except rejected" : STAGE_INFO[s].hint}
              className={i === 1 ? "ml-3 flex-none px-0" : "flex-none px-0"}
            >
              <Icon className="text-muted-foreground" aria-hidden="true" />
              {s === "all" ? "All" : STAGE_INFO[s].label}{" "}
              <span className="ml-1 text-muted-foreground tabular-nums">{s === "all" ? all : (counts[s] ?? 0)}</span>
            </TabsTrigger>
            )
          })}
        </TabsList>
      </Tabs>
    </header>
  )
}
