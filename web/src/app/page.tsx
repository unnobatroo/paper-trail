"use client";

import {Suspense, useMemo, useRef, useState} from "react";
import {toast} from "sonner";
import {useMutation} from "@tanstack/react-query";
import {parseAsString, useQueryState} from "nuqs";
import {useHotkeys} from "react-hotkeys-hook";
import {Check, CircleCheck, ListChecks, Loader2, MousePointerClick, Search, X} from "lucide-react";
import {Chip} from "@/components/chip";
import {Empty, EmptyDescription, EmptyHeader, EmptyTitle} from "@/components/ui/empty";
import {type Columns, DataTable, useRowKeys} from "@/components/data-table";
import {DetailSheet} from "@/components/detail-sheet";
import {Bi} from "@/components/en";
import {QueryError} from "@/components/query-error";
import {PageTitle} from "@/components/toolbar";
import {Button} from "@/components/ui/button";
import {InputGroup, InputGroupAddon, InputGroupInput} from "@/components/ui/input-group";
import {Kbd} from "@/components/ui/kbd";
import {ResizableHandle, ResizablePanel, ResizablePanelGroup} from "@/components/ui/resizable";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Skeleton} from "@/components/ui/skeleton";
import {ToggleGroup, ToggleGroupItem} from "@/components/ui/toggle-group";
import {WorkDetail} from "@/components/workspace/work-detail";
import {api, type CandidateType, errorMessage} from "@/lib/api";
import {useCommitments, useDocuments, useInvalidateDomain} from "@/lib/hooks";
import {displayTitle, KIND_LABEL} from "@/lib/labels";
import {KIND_ICON, KIND_TONE} from "@/lib/tones";
import {useMediaQuery} from "usehooks-ts";
import {useSearchJobs} from "@/lib/use-search-jobs";
import {cn} from "@/lib/utils";
import {type Stage, STAGE_ORDER, STAGES, useWorkspace, type WorkRow} from "@/lib/workspace";

const KIND_SECTION: Record<CandidateType, string> = {
    objective: "Objectives",
    target: "Targets",
    measure: "Measures",
    indicator: "Indicators",
    background: "Background text",
    unclear: "Unclear",
};
const TYPE_FILTER: CandidateType[] = ["objective", "target", "measure", "indicator"];

// drop extra columns as the screen shrinks, the panel takes the room on xl
const COL_CLASS = {
    kind: "hidden md:table-cell",
    evidence: "hidden sm:table-cell",
    page: "hidden 2xl:table-cell",
    goal: "hidden 2xl:table-cell",
};

const columns: Columns<WorkRow> = [
    {
        id: "title",
        header: "Commitment",
        cell: ({row}) => {
            const r = row.original;
            return (
                <div className="max-w-xl min-w-0">
                    <Bi text={displayTitle(r.title)} en={r.group[0].note?.title_en}
                        className="font-medium leading-snug"/>
                    <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{r.group[0].source_excerpt}</p>
                </div>
            );
        },
    },
    {
        id: "kind",
        header: "Type",
        cell: ({row}) => {
            const k = row.original.kind;
            return <Chip label={KIND_LABEL[k]} tone={KIND_TONE[k]} icon={KIND_ICON[k]}/>;
        },
    },
    {
        id: "stage",
        header: "Stage",
        cell: ({row}) => {
            const s = STAGES[row.original.stage];
            return <Chip label={s.label} tone={s.tone} icon={s.icon}/>;
        },
    },
    {
        id: "evidence",
        header: "Evidence",
        cell: ({row}) => {
            const r = row.original;
            return (
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    {r.evidence > 0 && (
                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
              <CircleCheck className="size-3.5"/>
                            {r.evidence}
            </span>
                    )}
                    {r.pending.length > 0 && (
                        <span
                            className="inline-flex items-center gap-1 whitespace-nowrap text-violet-700 dark:text-violet-400">
              <ListChecks className="size-3.5"/>
                            {r.pending.length} to review
            </span>
                    )}
                    {!r.evidence && !r.pending.length && <span className="text-muted-foreground">–</span>}
                </div>
            );
        },
    },
    {
        id: "page",
        header: "Page",
        cell: ({row}) => <span
            className="tabular-nums text-muted-foreground">{row.original.group[0].source_page}</span>,
    },
    {
        id: "goal",
        header: "Goal",
        cell: ({row}) => {
            const c = row.original.group[0];
            const goal = [c.target_value != null ? `${c.target_value} ${c.unit ?? ""}`.trim() : null, c.deadline_year ?? c.timeframe]
                .filter(Boolean)
                .join(" by ");
            return <span className="text-xs text-muted-foreground">{goal || "–"}</span>;
        },
    },
];

function WorkspacePage() {
    const {rows, isLoading, error, refetch} = useWorkspace();
    const {data: commitments} = useCommitments();
    const {data: documents} = useDocuments();
    const invalidate = useInvalidateDomain();
    const search = useSearchJobs();
    const docked = useMediaQuery("(min-width: 1280px)", {initializeWithValue: false});
    const searchRef = useRef<HTMLInputElement>(null);

    const [query, setQuery] = useQueryState("q", parseAsString.withDefault(""));
    const [stage, setStage] = useQueryState("stage", parseAsString.withDefault("all"));
    const [type, setType] = useQueryState("type", parseAsString.withDefault("all"));
    const [cursor, setCursor] = useState(0);
    const [open, setOpen] = useState(false);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
    // the mention shown in the panel, so c/r act on what the reviewer actually sees
    const [mentionSel, setMentionSel] = useState<Record<string, number>>({});

    const counts = useMemo(() => {
        const c: Record<Stage, number> = {confirm: 0, search: 0, review: 0, done: 0, rejected: 0};
        rows.forEach((r) => (c[r.stage] += 1));
        return c;
    }, [rows]);

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase();
        return rows.filter(
            (r) =>
                (stage === "all" ? r.stage !== "rejected" : r.stage === stage) &&
                (type === "all" || r.kind === type) &&
                (!q ||
                    r.title.toLowerCase().includes(q) ||
                    r.group.some((c) => (c.text ?? "").toLowerCase().includes(q) || (c.code ?? "").toLowerCase().includes(q))),
        );
    }, [rows, query, stage, type]);

    const groupOf = (r: WorkRow) => ({key: r.kind, label: KIND_SECTION[r.kind], icon: KIND_ICON[r.kind]});
    const visible = useMemo(() => filtered.filter((r) => !collapsed.has(r.kind)), [filtered, collapsed]);
    const at = Math.min(cursor, Math.max(0, visible.length - 1));
    const current = visible[at] ?? null;
    const shown = current
        ? (current.group.find((c) => c.id === mentionSel[current.id]) ??
            current.group.find((c) => c.review_status === "unreviewed") ??
            current.group[0])
        : null;

    const decide = useMutation({
        mutationFn: async (action: "accept" | "reject") => {
            if (action === "accept") await api.acceptCandidate(shown!.id);
            else await api.rejectCandidate(shown!.id);
        },
        onSuccess: (_r, action) => {
            toast.success(action === "accept" ? "Confirmed as a commitment." : "Rejected.");
            invalidate();
        },
        onError: (e) => toast.error(errorMessage(e)),
    });

    const selRows = useMemo(() => rows.filter((r) => selected.has(r.id)), [rows, selected]);
    const by = (s: Stage) => selRows.filter((r) => r.stage === s);

    const bulk = useMutation({
        mutationFn: async (action: "confirm" | "reject" | "match-confirm" | "match-reject") => {
            if (action === "confirm" || action === "reject") {
                const ids = by("confirm").flatMap((r) => r.group.filter((c) => c.review_status === "unreviewed").map((c) => c.id));
                const res = await api.bulkCandidates(action === "confirm" ? {accept: ids} : {reject: ids});
                return `${action === "confirm" ? res.accepted : res.rejected} source mentions ${action === "confirm" ? "confirmed" : "rejected"}.`;
            }
            const ids = by("review").flatMap((r) => r.pending.map((v) => v.link.id));
            const accept = action === "match-confirm";
            const res = await api.bulkLinks(accept ? {accept: ids} : {reject: ids});
            return `${accept ? res.accepted : res.rejected} match(es) ${accept ? "confirmed" : "rejected"}.`;
        },
        onSuccess: (msg) => {
            toast.success(msg);
            setSelected(new Set());
            invalidate();
        },
        onError: (e) => toast.error(errorMessage(e)),
    });

    function toggle(id: string) {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }

    const confirmable = current?.stage === "confirm" && shown?.review_status === "unreviewed";
    useRowKeys(visible.length, at, setCursor, {
        onOpen: () => current && !docked && setOpen(true),
        onToggle: () => current && toggle(current.id),
        onAccept: () => confirmable && decide.mutate("accept"),
        onReject: () => confirmable && decide.mutate("reject"),
    });
    useHotkeys("s", () => {
        if (current?.stage === "search" && !search.running) search.start.mutate(current.commitments.map((c) => c.id));
    }, [current, search.running]);
    useHotkeys("/", (e) => {
        e.preventDefault();
        searchRef.current?.focus();
    }, []);

    if (error) return <QueryError error={error} retry={refetch}/>;
    if (isLoading) return <Skeleton className="h-96 w-full"/>;

    const hint = "Check each promise against the strategy, find official sources, confirm what they show.";
    if (!rows.length)
        return (
            <>
                <PageTitle title="Workspace" hint={hint} guide={["commitments", "evidence", "trail"]}/>
                <Empty className="mt-6 border">
                    <EmptyHeader>
                        <EmptyTitle>Nothing extracted yet</EmptyTitle>
                        <EmptyDescription>
                            Use <strong>Ingest</strong> in the top bar to read the strategy PDF.
                        </EmptyDescription>
                    </EmptyHeader>
                </Empty>
            </>
        );

    const detail = current && (
        <WorkDetail
            key={current.id}
            row={current}
            commitments={commitments ?? []}
            documents={documents ?? []}
            mentionId={shown!.id}
            onMention={(id) => setMentionSel((p) => ({...p, [current.id]: id}))}
            onSearch={(ids) => search.start.mutate(ids)}
            searching={search.running || search.start.isPending}
        />
    );

    const nConfirm = by("confirm").length;
    const nSearch = by("search").length;
    const nReview = by("review").length;

    const tableView = filtered.length ? (
        <DataTable
            columns={columns}
            data={filtered}
            getId={(r) => r.id}
            cursor={at}
            onCursor={setCursor}
            onOpen={() => !docked && setOpen(true)}
            selected={selected}
            onToggle={toggle}
            onToggleAll={(on) => setSelected(on ? new Set(visible.map((r) => r.id)) : new Set())}
            groupOf={groupOf}
            collapsed={collapsed}
            onToggleGroup={(k) =>
                setCollapsed((prev) => {
                    const next = new Set(prev);
                    if (next.has(k)) next.delete(k);
                    else next.add(k);
                    return next;
                })
            }
            colClass={COL_CLASS}
        />
    ) : (
        <Empty className="border">
            <EmptyHeader><EmptyDescription>Nothing matches these filters.</EmptyDescription></EmptyHeader>
        </Empty>
    );

    return (
        <>
            <PageTitle title="Workspace" hint={hint} guide={["commitments", "evidence", "trail"]}/>

            {search.running && (
                <div role="status" aria-live="polite" className="mt-4 rounded-lg border bg-card p-3 text-sm">
                    <div className="flex items-center gap-2 font-medium">
                        <Loader2 className="size-4 animate-spin"/>
                        Finding evidence ({search.jobs.length} job{search.jobs.length === 1 ? "" : "s"})
                    </div>
                    {search.jobs.filter((j) => j.progress).map((j) => (
                        <p key={j.id} className="mt-1 text-xs text-muted-foreground">{j.progress}</p>
                    ))}
                    {search.error && (
                        <p role="alert" className="mt-2 text-destructive">
                            Cannot check progress, the search may still be running.
                            <Button variant="outline" size="sm" className="ml-2"
                                    onClick={() => search.retry()}>Retry</Button>
                        </p>
                    )}
                </div>
            )}

            <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                    <InputGroup className="w-full sm:w-64">
                        <InputGroupAddon>
                            <Search className="size-3.5"/>
                        </InputGroupAddon>
                        <InputGroupInput
                            ref={searchRef}
                            value={query}
                            onChange={(e) => setQuery(e.target.value || null)}
                            placeholder="Search commitments"
                            aria-label="Search commitments"
                        />
                    </InputGroup>
                    <Select value={type} onValueChange={(v) => setType(v === "all" ? null : (v as string))}
                            items={{all: "All types", ...Object.fromEntries(TYPE_FILTER.map((t) => [t, KIND_SECTION[t]]))}}>
                        <SelectTrigger size="sm" className="w-40" aria-label="Filter by type">
                            <SelectValue/>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All types</SelectItem>
                            {TYPE_FILTER.map((t) => (
                                <SelectItem key={t} value={t}>{KIND_SECTION[t]}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <span className="ml-auto hidden text-xs text-muted-foreground lg:block">
            <Kbd>j</Kbd> <Kbd>k</Kbd> move <Kbd>x</Kbd> select <Kbd>c</Kbd> confirm <Kbd>r</Kbd> reject <Kbd>s</Kbd> search
          </span>
                </div>

                <ToggleGroup
                    value={[stage]}
                    onValueChange={(vals) => {
                        const next = vals[vals.length - 1] as string | undefined;
                        if (next) setStage(next === "all" ? null : next);
                    }}
                    spacing={1.5}
                    size="sm"
                    aria-label="Filter by stage"
                    className="-mx-4 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0"
                >
                    {(["all", ...STAGE_ORDER] as const).map((s) => {
                        const on = stage === s;
                        const Icon = s === "all" ? null : STAGES[s].icon;
                        const n = s === "all" ? rows.length - counts.rejected : counts[s];
                        return (
                            <ToggleGroupItem
                                key={s}
                                value={s}
                                title={s === "all" ? "Everything except rejected" : STAGES[s].hint}
                                className={cn(
                                    "h-auto rounded-full border px-3 py-1 text-xs",
                                    on
                                        ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground aria-pressed:bg-primary aria-pressed:text-primary-foreground"
                                        : "bg-card text-muted-foreground hover:text-foreground",
                                )}
                            >
                                {Icon && <Icon className="size-3.5"/>}
                                {s === "all" ? "All" : STAGES[s].label}
                                <span className={cn("tabular-nums", on ? "opacity-80" : "opacity-60")}>{n}</span>
                            </ToggleGroupItem>
                        );
                    })}
                </ToggleGroup>

                {selected.size > 0 && (
                    <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card px-3 py-2">
                        <span className="text-sm font-medium">{selected.size} selected</span>
                        {nConfirm > 0 && (
                            <div className="flex">
                                <Button size="sm" className="rounded-r-none" disabled={bulk.isPending}
                                        onClick={() => bulk.mutate("confirm")}>
                                    <Check className="size-3.5"/> Confirm {nConfirm}
                                </Button>
                                <Button size="sm" variant="outline" className="rounded-l-none border-l-0"
                                        disabled={bulk.isPending} onClick={() => bulk.mutate("reject")}>
                                    <X className="size-3.5"/> Reject
                                </Button>
                            </div>
                        )}
                        {nSearch > 0 && (
                            <Button size="sm" variant="secondary" disabled={search.running || search.start.isPending}
                                    onClick={() => search.start.mutate(by("search").flatMap((r) => r.commitments.map((c) => c.id)))}>
                                <Search className="size-3.5"/> Find evidence {nSearch}
                            </Button>
                        )}
                        {nReview > 0 && (
                            <div className="flex">
                                <Button size="sm" variant="secondary" className="rounded-r-none"
                                        disabled={bulk.isPending} onClick={() => bulk.mutate("match-confirm")}>
                                    <ListChecks className="size-3.5"/> Confirm matches
                                </Button>
                                <Button size="sm" variant="outline" className="rounded-l-none border-l-0"
                                        disabled={bulk.isPending} onClick={() => bulk.mutate("match-reject")}>
                                    <X className="size-3.5"/> Reject
                                </Button>
                            </div>
                        )}
                        <Button size="sm" variant="ghost" className="ml-auto"
                                onClick={() => setSelected(new Set())}>Clear</Button>
                    </div>
                )}
            </div>

            {docked ? (
                <ResizablePanelGroup orientation="horizontal" className="mt-3 items-start gap-2">
                    <ResizablePanel defaultSize="68%" minSize="45%" className="min-w-0">
                        {tableView}
                    </ResizablePanel>
                    <ResizableHandle withHandle className="my-2 self-stretch"/>
                    <ResizablePanel defaultSize="32%" minSize="22%">
                        <aside className="sticky top-16 max-h-[calc(100vh-5rem)] overflow-y-auto rounded-lg border bg-card p-4">
                            {detail ?? (
                                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <MousePointerClick className="size-4"/> Select a commitment to see its detail.
                                </p>
                            )}
                        </aside>
                    </ResizablePanel>
                </ResizablePanelGroup>
            ) : (
                <div className="mt-3 min-w-0">
                    {tableView}
                    <DetailSheet open={open && !!current} onClose={() => setOpen(false)} label="Commitment detail">
                        {detail}
                    </DetailSheet>
                </div>
            )}
        </>
    );
}

export default function Page() {
    return (
        <Suspense>
            <WorkspacePage/>
        </Suspense>
    );
}
