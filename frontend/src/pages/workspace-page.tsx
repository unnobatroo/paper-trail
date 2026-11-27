import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router"
import { toast } from "sonner"

import type { WorkspaceRow } from "@/api/client"
import { useActiveJobs, useReviewActions, useWorkspace } from "@/api/hooks"
import { AppSidebar } from "@/components/app-sidebar"
import { DetailPane } from "@/components/detail-pane"
import { GlossaryDialog, IngestDialog, SettingsDialog } from "@/components/dialogs"
import { SiteHeader } from "@/components/site-header"
import { Button } from "@/components/ui/button"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { WorkspaceTable } from "@/components/workspace-table"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useIsMobile } from "@/hooks/use-mobile"
import { useCanReview } from "@/lib/can-review"
import { STAGE_INFO, displayTitle, type Stage } from "@/lib/labels"
import { shown } from "@/lib/rows"

const TYPING = /^(INPUT|TEXTAREA|SELECT)$/

/** The review workspace: stages in the sidebar, the commitments in the middle, the detail beside them. */
export function WorkspacePage() {
  const [params, setParams] = useSearchParams()
  const stage = params.get("stage") ?? "all"
  const type = params.get("type") ?? "all"
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
  useEffect(() => {
    const t = setTimeout(() => setParam("q", text.trim()), 250)
    return () => clearTimeout(t)
  }, [text, setParam])

  const ws = useWorkspace({ stage, type, q })
  const rows: WorkspaceRow[] = useMemo(() => ws.data?.rows ?? [], [ws.data])
  const counts = ws.data?.stage_counts ?? {}
  const current = rows.find((r) => r.id === cursor) ?? null

  const { accept, reject, bulkCandidates, bulkLinks, findEvidence } = useReviewActions()
  const ingestJobs = useActiveJobs("ingest").data ?? []
  const searchJobs = useActiveJobs("find_evidence").data ?? []
  const searching = searchJobs.length > 0

  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [dialog, setDialog] = useState<"settings" | "ingest" | "glossary" | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const isMobile = useIsMobile()
  const canReview = useCanReview()

  const open = (id: number | null) => setParam("row", id === null ? null : String(id))
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

  const confirmRow = useCallback(
    (row: WorkspaceRow) => {
      const c = shown(row)
      if (canReview && row.stage === "confirm" && c.review_status === "unreviewed")
        accept.mutate({ id: c.id! }, { onSuccess: () => toast.success("Confirmed as a commitment.") })
    },
    [accept, canReview],
  )
  const rejectRow = useCallback(
    (row: WorkspaceRow) => {
      const c = shown(row)
      if (canReview && row.stage === "confirm" && c.review_status === "unreviewed")
        reject.mutate(c.id!, { onSuccess: () => toast.success("Rejected.") })
    },
    [reject, canReview],
  )

  // Keyboard shortcuts, off while typing or while a dialog is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || TYPING.test(el.tagName) || el.isContentEditable) return
      // a select's popup uses letters for typeahead
      if (el.closest("[role=listbox],[role=option],[role=combobox]")) return
      if (document.querySelector("[role=dialog]")) return
      const ids = rows.map((r) => r.id)
      if ((e.key === "j" || e.key === "k") && ids.length) {
        const i = cursor !== null ? ids.indexOf(cursor) : -1
        open(ids[e.key === "j" ? Math.min(i + 1, ids.length - 1) : Math.max(i - 1, 0)])
      } else if (e.key === "/") {
        e.preventDefault()
        searchRef.current?.focus()
      } else if (current) {
        if (e.key === "x") selectMany([current.id], !selected.has(current.id))
        else if (e.key === "c") confirmRow(current)
        else if (e.key === "r") rejectRow(current)
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
    <div className="flex flex-col gap-4 p-4">
      {ws.data && !canReview && (
        <Alert>
          <AlertDescription>
            Read-only. You can browse everything; confirming, rejecting and searching need the review key, which you add in Settings.
          </AlertDescription>
        </Alert>
      )}
      <p className="text-xs text-muted-foreground">
        <kbd>j</kbd> <kbd>k</kbd> move · <kbd>x</kbd> select · <kbd>c</kbd> confirm · <kbd>r</kbd> reject · <kbd>s</kbd> search ·{" "}
        <kbd>/</kbd> find
      </p>

      {selected.size > 0 && (
        <div role="region" aria-label="Bulk actions" className="flex flex-wrap items-center gap-2 rounded-lg bg-muted p-2">
          <span className="text-sm">{selected.size} selected</span>
          {mentionIds.length > 0 && (
            <>
              <Button size="sm" onClick={() => bulkCandidates.mutate({ accept: mentionIds, reject: [] }, { onSuccess: () => { toast.success(`${mentionIds.length} source mentions confirmed.`); clear() } })}>
                Confirm {byStage("confirm").length}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => bulkCandidates.mutate({ accept: [], reject: mentionIds }, { onSuccess: () => { toast.success(`${mentionIds.length} source mentions rejected.`); clear() } })}>
                Reject
              </Button>
            </>
          )}
          {searchIds.length > 0 && (
            <Button size="sm" onClick={async () => { if (await startSearch(searchIds)) clear() }}>
              Find evidence {byStage("search").length}
            </Button>
          )}
          {matchIds.length > 0 && (
            <>
              <Button size="sm" onClick={() => bulkLinks.mutate({ accept: matchIds, reject: [] }, { onSuccess: () => { toast.success("Matches confirmed."); clear() } })}>
                Confirm matches
              </Button>
              <Button size="sm" variant="ghost" onClick={() => bulkLinks.mutate({ accept: [], reject: matchIds }, { onSuccess: () => { toast.success("Matches rejected."); clear() } })}>
                Reject
              </Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={clear}>Clear</Button>
        </div>
      )}

      {ws.isError ? (
        <p role="alert" className="text-destructive">Could not load the workspace: {(ws.error as Error).message}</p>
      ) : !ws.data ? (
        <p className="text-muted-foreground" role="status">Loading…</p>
      ) : (counts.confirm ?? 0) + (counts.search ?? 0) + (counts.review ?? 0) + (counts.done ?? 0) + (counts.rejected ?? 0) === 0 ? (
        <div className="flex flex-col items-center gap-2 p-12 text-center">
          <p className="text-lg">Nothing extracted yet</p>
          <p className="text-muted-foreground">Use Ingest in the sidebar to read a strategy PDF.</p>
        </div>
      ) : (
        <WorkspaceTable rows={rows} cursor={cursor} selected={selected} onOpen={open} onSelectMany={selectMany} />
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
    />
  )

  return (
    <SidebarProvider style={{ "--header-height": "3.5rem" } as React.CSSProperties}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        Skip to commitments
      </a>
      <AppSidebar
        stage={stage}
        counts={counts}
        ingesting={ingestJobs.length > 0}
        onStage={(s) => setParam("stage", s, "all")}
        onIngest={() => setDialog("ingest")}
        onGlossary={() => setDialog("glossary")}
        onSettings={() => setDialog("settings")}
      />
      <SidebarInset className="h-svh overflow-hidden">
        <SiteHeader
          title={stage in STAGE_INFO ? STAGE_INFO[stage as Stage].label : "All commitments"}
          q={text}
          onQ={setText}
          type={type}
          onType={(t) => setParam("type", t, "all")}
          searchRef={searchRef}
          progress={progress}
        />
        {isMobile ? (
          <>
            <div id="main" tabIndex={-1} className="min-h-0 flex-1 overflow-y-auto outline-none">{table}</div>
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
          <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
            <ResizablePanel defaultSize="62%" minSize="30%">
              <div id="main" tabIndex={-1} className="h-full overflow-y-auto outline-none">{table}</div>
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel defaultSize="38%" minSize="25%">
              <aside aria-label="Details" className="h-full overflow-y-auto">
                {detail ?? <p className="p-6 text-muted-foreground">Select a commitment to see its detail.</p>}
              </aside>
            </ResizablePanel>
          </ResizablePanelGroup>
        )}
      </SidebarInset>

      <SettingsDialog open={dialog === "settings"} onOpenChange={(o) => setDialog(o ? "settings" : null)} />
      <IngestDialog open={dialog === "ingest"} onOpenChange={(o) => setDialog(o ? "ingest" : null)} />
      <GlossaryDialog open={dialog === "glossary"} onOpenChange={(o) => setDialog(o ? "glossary" : null)} />
    </SidebarProvider>
  )
}
