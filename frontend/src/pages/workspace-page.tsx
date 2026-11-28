import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { CheckIcon, SearchIcon, XIcon } from "lucide-react"
import { useSearchParams } from "react-router"
import { toast } from "sonner"

import type { WorkspaceRow } from "@/api/client"
import { useActiveJobs, useReviewActions, useWorkspace } from "@/api/hooks"
import { AppHeader } from "@/components/app-header"
import { DetailPane } from "@/components/detail-pane"
import { GlossaryDialog, IngestDialog, SettingsDialog, ShortcutsDialog } from "@/components/dialogs"
import { KindFilter } from "@/components/kind-filter"
import { Ledger } from "@/components/ledger"
import { Button } from "@/components/ui/button"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useMentionDecision } from "@/hooks/use-mention-decision"
import { useIsMobile } from "@/hooks/use-mobile"
import { useCanReview } from "@/lib/can-review"
import { displayTitle, type Stage } from "@/lib/labels"
import { firstPage, shown } from "@/lib/rows"

const TYPING = /^(INPUT|TEXTAREA|SELECT)$/

/** The review workspace: stages along the top, the commitments in the middle, the detail beside them. */
export function WorkspacePage() {
  const [params, setParams] = useSearchParams()
  const stage = params.get("stage") ?? "all"
  const kind = params.get("type") ?? "all"
  const q = params.get("q") ?? ""
  const cursor = params.get("row") ? Number(params.get("row")) : null

  const setParam = useCallback(
    (key: string, value: string | null, fallback = "") =>
      setParams((p) => {
        if (value === null || value === fallback) p.delete(key)
        else p.set(key, value)
        return p
      }, { replace: true }),
    [setParams],
  )

  // The search box keeps its own text, so typing isn't held back by the request; the URL follows.
  const [text, setText] = useState(q)
  // Only when the text differs from the URL: writing an unchanged q would rebuild the URL from
  // stale params and wipe whatever was set since, such as the open row.
  useEffect(() => {
    if (text.trim() === q) return
    const t = setTimeout(() => setParam("q", text.trim()), 250)
    return () => clearTimeout(t)
  }, [text, q, setParam])

  // The server filters by stage and search; the kind filter is applied here, so the kind
  // counts stay whole while one kind is selected.
  const ws = useWorkspace({ stage, type: "all", q })
  // In the order of the strategy: by the row's first page (the one its folio starts with), then as listed.
  const stageRows: WorkspaceRow[] = useMemo(
    () => [...(ws.data?.rows ?? [])].sort((a, b) => firstPage(a) - firstPage(b) || a.id - b.id),
    [ws.data],
  )
  const kindCounts = useMemo(() => {
    const n: Record<string, number> = {}
    for (const r of stageRows) n[r.kind] = (n[r.kind] ?? 0) + 1
    return n
  }, [stageRows])
  const rows = useMemo(() => (kind === "all" ? stageRows : stageRows.filter((r) => r.kind === kind)), [stageRows, kind])
  const counts = ws.data?.stage_counts ?? {}
  const current = rows.find((r) => r.id === cursor) ?? null

  const { bulkCandidates, bulkLinks, findEvidence } = useReviewActions()
  const { decide } = useMentionDecision()
  const ingestJobs = useActiveJobs("ingest").data ?? []
  const searchJobs = useActiveJobs("find_evidence").data ?? []
  const searching = searchJobs.length > 0

  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [dialog, setDialog] = useState<"settings" | "ingest" | "glossary" | "shortcuts" | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const isMobile = useIsMobile()
  const canReview = useCanReview()

  const open = useCallback((id: number | null) => setParam("row", id === null ? null : String(id)), [setParam])
  /** After a decision on a row, the next one (or the one before, at the end) takes its place. */
  const moveOnFrom = useCallback(
    (id: number) => {
      const i = rows.findIndex((r) => r.id === id)
      open((rows[i + 1] ?? rows[i - 1])?.id ?? null)
    },
    [rows, open],
  )
  const selectMany = (ids: number[], on: boolean) =>
    setSelected((s) => {
      const next = new Set(s)
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)))
      return next
    })

  /** One search after another; the first failure stops the rest. */
  const startSearch = useCallback(
    async (ids: number[]) => {
      for (const id of ids) {
        try {
          await findEvidence.mutateAsync(id)
        } catch (e) {
          toast.error(`Could not start search: ${(e as Error).message}`)
          return false
        }
      }
      return true
    },
    [findEvidence],
  )

  /** A keyboard decision on a row: only an open mention in To confirm, then on to the next row. */
  const decideRow = useCallback(
    (row: WorkspaceRow, decision: "accept" | "reject") => {
      const c = shown(row)
      if (canReview && row.stage === "confirm" && c.review_status === "unreviewed")
        decide(c.id!, decision, { onDone: () => moveOnFrom(row.id) })
    },
    [decide, canReview, moveOnFrom],
  )

  // A wide screen always has something in the detail pane: the first row, until one is picked.
  useEffect(() => {
    if (!isMobile && ws.data && !current && rows.length) open(rows[0].id)
  }, [isMobile, ws.data, current, rows, open])

  // Keyboard shortcuts, off while typing or while a dialog is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || TYPING.test(el.tagName) || el.isContentEditable) return
      // a select's popup uses letters for typeahead
      if (el.closest("[role=listbox],[role=option],[role=combobox]")) return
      if (document.querySelector("[role=dialog]")) return
      const ids = rows.map((r) => r.id)
      if (e.key === "?") {
        setDialog("shortcuts")
      } else if ((e.key === "j" || e.key === "k") && ids.length) {
        const i = cursor !== null ? ids.indexOf(cursor) : -1
        open(ids[e.key === "j" ? Math.min(i + 1, ids.length - 1) : Math.max(i - 1, 0)])
      } else if (e.key === "/") {
        e.preventDefault()
        searchRef.current?.focus()
      } else if (current) {
        if (e.key === "x") selectMany([current.id], !selected.has(current.id))
        else if (e.key === "c") decideRow(current, "accept")
        else if (e.key === "r") decideRow(current, "reject")
        else if (e.key === "s" && canReview && current.stage === "search" && !searching) void startSearch(current.commitments.map((m) => m.id!))
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  const picked = rows.filter((r) => selected.has(r.id))
  const byStage = (s: Stage) => picked.filter((r) => r.stage === s)
  const mentionIds = byStage("confirm").flatMap((r) => r.group.filter((c) => c.review_status === "unreviewed").map((c) => c.id!))
  const matchIds = byStage("review").flatMap((r) => r.pending.map((lv) => lv.link.id!))
  const searchIds = byStage("search").flatMap((r) => r.commitments.map((m) => m.id!))
  const clear = () => setSelected(new Set())

  const progress = ingestJobs[0]
    ? ingestJobs[0].progress || "Reading strategy…"
    : searching
      ? `Finding evidence (${searchJobs.length} ${searchJobs.length === 1 ? "job" : "jobs"})`
      : null

  const table = (
    <div className="flex flex-col">
      <KindFilter counts={kindCounts} kind={kind} onKind={(k) => setParam("type", k, "all")}>
        {selected.size > 0 && (
          <div role="region" aria-label="Bulk actions" className="layer-surface flex flex-wrap items-center gap-2 px-2 py-1">
            <span className="type-label px-1">{selected.size} selected</span>
            {mentionIds.length > 0 && (
              <>
                <Button size="sm" disabled={!canReview} onClick={() => bulkCandidates.mutate({ accept: mentionIds, reject: [] }, { onSuccess: () => { toast.success(`${mentionIds.length} source mentions confirmed.`); clear() } })}>
                  <CheckIcon data-icon="inline-start" />
                  Confirm {byStage("confirm").length}
                </Button>
                <Button size="sm" variant="ghost" disabled={!canReview} onClick={() => bulkCandidates.mutate({ accept: [], reject: mentionIds }, { onSuccess: () => { toast.success(`${mentionIds.length} source mentions rejected.`); clear() } })}>
                  <XIcon data-icon="inline-start" />
                  Reject
                </Button>
              </>
            )}
            {searchIds.length > 0 && (
              <Button size="sm" disabled={!canReview} onClick={async () => { if (await startSearch(searchIds)) clear() }}>
                <SearchIcon data-icon="inline-start" />
                Find evidence {byStage("search").length}
              </Button>
            )}
            {matchIds.length > 0 && (
              <>
                <Button size="sm" disabled={!canReview} onClick={() => bulkLinks.mutate({ accept: matchIds, reject: [] }, { onSuccess: () => { toast.success("Matches confirmed."); clear() } })}>
                  <CheckIcon data-icon="inline-start" />
                  Confirm matches
                </Button>
                <Button size="sm" variant="ghost" disabled={!canReview} onClick={() => bulkLinks.mutate({ accept: [], reject: matchIds }, { onSuccess: () => { toast.success("Matches rejected."); clear() } })}>
                  <XIcon data-icon="inline-start" />
                  Reject
                </Button>
              </>
            )}
            <Button size="sm" variant="ghost" onClick={clear}>Clear</Button>
          </div>
        )}
      </KindFilter>

      {ws.isError ? (
        <p role="alert" className="p-5 text-destructive">Could not load the workspace: {(ws.error as Error).message}</p>
      ) : !ws.data ? (
        <p className="p-5 text-muted-foreground" role="status">Loading…</p>
      ) : (counts.confirm ?? 0) + (counts.search ?? 0) + (counts.review ?? 0) + (counts.done ?? 0) + (counts.rejected ?? 0) === 0 ? (
        <div className="flex flex-col items-center gap-2 p-12 text-center">
          <p className="type-title">Nothing extracted yet</p>
          <p className="text-muted-foreground">Use Ingest at the top to read a strategy PDF.</p>
        </div>
      ) : (
        <Ledger
          rows={rows}
          showStage={stage === "all" || stage === "rejected"}
          cursor={cursor}
          selected={selected}
          onOpen={open}
          onSelectMany={selectMany}
          onSearch={(r) => void startSearch(r.commitments.map((m) => m.id!))}
          searchDisabled={!canReview || searching}
        />
      )}
    </div>
  )

  const detail = current && ws.data && (
    <DetailPane
      key={current.id}
      row={current}
      documents={ws.data.documents}
      commitments={ws.data.commitments}
      searching={searching}
      onSearch={(ids) => void startSearch(ids)}
      onDecided={() => moveOnFrom(current.id)}
    />
  )

  return (
    <div className="flex h-svh flex-col gap-2 p-2 md:gap-3 md:p-3">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        Skip to commitments
      </a>
      <AppHeader
        stage={stage}
        counts={counts}
        onStage={(s) => setParam("stage", s, "all")}
        q={text}
        onQ={setText}
        searchRef={searchRef}
        progress={progress}
        ingesting={ingestJobs.length > 0}
        onIngest={() => setDialog("ingest")}
        onGlossary={() => setDialog("glossary")}
        onShortcuts={() => setDialog("shortcuts")}
        onSettings={() => setDialog("settings")}
      />
      {isMobile ? (
        <>
          <div id="main" tabIndex={-1} className="layer-panel min-h-0 flex-1 overflow-y-auto outline-none">{table}</div>
          <Sheet open={!!detail} onOpenChange={(o) => !o && open(null)}>
            <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
              <SheetHeader>
                <SheetTitle>{current ? displayTitle(current.title) : "Details"}</SheetTitle>
                <SheetDescription className="sr-only">Details of the selected commitment</SheetDescription>
              </SheetHeader>
              {detail}
            </SheetContent>
          </Sheet>
        </>
      ) : (
        <>
          <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
            <ResizablePanel defaultSize="55%" minSize="30%">
              <div id="main" tabIndex={-1} className="layer-panel h-full overflow-y-auto outline-none">{table}</div>
            </ResizablePanel>
            <ResizableHandle className="mx-1 w-2 rounded-full bg-transparent transition-colors hover:bg-foreground/10 focus-visible:bg-foreground/10" />
            <ResizablePanel defaultSize="45%" minSize="28%">
              <aside aria-label="Details" className="layer-panel h-full overflow-y-auto">
                {detail ?? <p className="p-6 text-muted-foreground">Select a commitment to see its detail.</p>}
              </aside>
            </ResizablePanel>
          </ResizablePanelGroup>
        </>
      )}

      <SettingsDialog open={dialog === "settings"} onOpenChange={(o) => setDialog(o ? "settings" : null)} />
      <IngestDialog open={dialog === "ingest"} onOpenChange={(o) => setDialog(o ? "ingest" : null)} />
      <ShortcutsDialog open={dialog === "shortcuts"} onOpenChange={(o) => setDialog(o ? "shortcuts" : null)} />
      <GlossaryDialog open={dialog === "glossary"} onOpenChange={(o) => setDialog(o ? "glossary" : null)} />
    </div>
  )
}
