"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useQueryState, parseAsString } from "nuqs";
import { Check, Loader2, Search, X } from "lucide-react";
import { Chip, EmptyState } from "@/components/chip";
import { DataTable, useRowKeys, type Columns } from "@/components/data-table";
import { DetailSheet } from "@/components/detail-sheet";
import { LinkDetail } from "@/components/detail/link-detail";
import { En } from "@/components/en";
import { QueryError } from "@/components/query-error";
import { PageTitle, Toolbar } from "@/components/toolbar";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  api,
  errorMessage,
  type Commitment,
  type EvidenceItem,
  type LinkView,
  type RelationshipType,
} from "@/lib/api";
import { keys, useCommitments, useInvalidateDomain, useJobs, useLink, useLinks } from "@/lib/hooks";
import { KIND_LABEL, REL_LABEL, STATUS_LABEL, displayTitle, evidenceKind, titleGroups } from "@/lib/labels";
import { KIND_ICON, KIND_TONE, REL_ICON, REL_TONE, STATUS_ICON, STATUS_TONE } from "@/lib/tones";

const SEARCHABLE = new Set(["objective", "measure", "target"]);
const KIND_ORDER = ["objective", "target", "measure"];

type Pending = LinkView & { evidence: EvidenceItem };

function EvidencePage() {
  const { data: commitments, isLoading, error, refetch } = useCommitments();
  const { data: links, error: linksError, refetch: refetchLinks } = useLinks();
  const invalidate = useInvalidateDomain();
  const [view, setView] = useQueryState("view", parseAsString);
  const [startedIds, setStartedIds] = useState<string[]>([]);

  // the server is the source of truth for what's running, so a reload or
  // another tab keeps following in-flight searches instead of orphaning them
  const { data: inFlight } = useQuery({
    queryKey: keys.activeJobs("find_evidence"),
    queryFn: () => api.activeJobs("find_evidence"),
  });
  const jobIds = startedIds.length ? startedIds : (inFlight ?? []).map((j) => j.id);
  const { jobs, settled, error: jobError, retry: retryJobs } = useJobs(jobIds);

  const searchable = useMemo(
    () => (commitments ?? []).filter((c) => SEARCHABLE.has(c.kind)),
    [commitments],
  );
  const pending = useMemo(
    () =>
      (links ?? []).filter(
        (l): l is Pending => l.link.review_status === "unreviewed" && !!l.evidence,
      ),
    [links],
  );

  const notified = useRef("");
  useEffect(() => {
    const batch = jobIds.join(",");
    if (!settled || notified.current === batch) return;
    notified.current = batch;
    const total = jobs.reduce((n, j) => n + (j.result?.links ?? 0), 0);
    const failed = jobs.filter((j) => j.status === "failed");
    if (failed.length) toast.error(`${failed.length} search(es) failed: ${failed[0].error ?? "unknown"}`);
    else toast.success(total ? `Search done: ${total} possible matches.` : "Search done: nothing useful on the official sites.");
    jobs.flatMap((j) => j.result?.warnings ?? []).forEach((w) => toast.warning(w));
    invalidate();
  }, [settled, jobs, jobIds, invalidate]);

  if (linksError) return <QueryError error={linksError} retry={refetchLinks} />;
  if (error) return <QueryError error={error} retry={refetch} />;
  if (isLoading) return <Skeleton className="h-96 w-full" />;

  const hint = "Find official sources for each commitment, then confirm or reject the matches.";
  if (!searchable.length)
    return (
      <>
        <PageTitle title="Evidence" hint={hint} guide="evidence" />
        <EmptyState className="mt-6">Nothing to check yet. Confirm some commitments first.</EmptyState>
      </>
    );

  const running = jobIds.length > 0 && !settled;
  const active = settled ? "review" : view ?? (pending.length ? "review" : "find");

  return (
    <>
      <PageTitle title="Evidence" hint={hint} guide="evidence" />

      {running && (
        <div role="status" aria-live="polite" className="mt-4 rounded-lg border bg-card p-3 text-sm">
          <div className="flex items-center gap-2 font-medium">
            <Loader2 className="size-4 animate-spin" />
            Finding evidence ({jobIds.length} job{jobIds.length > 1 ? "s" : ""})
          </div>
          {jobs.filter((j) => j.progress).map((j) => (
            <p key={j.id} className="mt-1 text-xs text-muted-foreground">{j.progress}</p>
          ))}
          {jobError && (
            <p role="alert" className="mt-2 text-destructive">
              Cannot check progress, the search may still be running.
              <Button variant="outline" size="sm" className="ml-2" onClick={() => retryJobs()}>Retry</Button>
            </p>
          )}
        </div>
      )}

      {!running && (
        <>
          <Toolbar>
            <ToggleGroup
              value={[active]}
              onValueChange={(v) => { if (v[0]) { setStartedIds([]); setView(v[0]); } }}
              variant="outline"
              size="sm"
            >
              <ToggleGroupItem value="find">Find</ToggleGroupItem>
              <ToggleGroupItem value="review">
                Review matches{pending.length > 0 ? ` (${pending.length})` : ""}
              </ToggleGroupItem>
            </ToggleGroup>
            <span className="ml-auto text-xs text-muted-foreground">
              <Kbd>j</Kbd> <Kbd>k</Kbd> move <Kbd>x</Kbd> select{active === "review" && <> <Kbd>c</Kbd> confirm <Kbd>r</Kbd> reject</>}
            </span>
          </Toolbar>
          {active === "find" ? (
            <FindTable commitments={searchable} links={links ?? []} onStarted={setStartedIds} />
          ) : (
            <ReviewTable pending={pending} commitments={searchable} />
          )}
        </>
      )}
    </>
  );
}

/* find: pick commitments, start searches */

const findColumns = (matches: Map<number, number>): Columns<Commitment[]> => [
  {
    id: "title",
    header: "Commitment",
    cell: ({ row }) => (
      <div className="max-w-xl">
        <p className="font-medium leading-snug">{displayTitle(row.original[0].title)}</p>
        <En text={displayTitle(row.original[0].title)} />
      </div>
    ),
  },
  {
    id: "kind",
    header: "Type",
    cell: ({ row }) => {
      const k = row.original[0].kind;
      return <Chip label={KIND_LABEL[k]} tone={KIND_TONE[k]} icon={KIND_ICON[k]} />;
    },
  },
  {
    id: "page",
    header: "Page",
    cell: ({ row }) => <span className="tabular-nums text-muted-foreground">{row.original[0].source_page ?? ""}</span>,
  },
  {
    id: "matches",
    header: "Matches",
    cell: ({ row }) => {
      const n = row.original.reduce((s, c) => s + (matches.get(c.id) ?? 0), 0);
      return <span className="tabular-nums text-muted-foreground">{n || "not searched"}</span>;
    },
  },
];

function FindTable({
  commitments,
  links,
  onStarted,
}: {
  commitments: Commitment[];
  links: LinkView[];
  onStarted: (ids: string[]) => void;
}) {
  const matches = useMemo(() => {
    const m = new Map<number, number>();
    links.forEach((l) => m.set(l.link.commitment_id, (m.get(l.link.commitment_id) ?? 0) + 1));
    return m;
  }, [links]);
  const groups = useMemo(
    () =>
      titleGroups(commitments, (c) => c.title, (c) => c.kind).sort(
        (a, b) => KIND_ORDER.indexOf(a[0].kind) - KIND_ORDER.indexOf(b[0].kind),
      ),
    [commitments],
  );
  const columns = useMemo(() => findColumns(matches), [matches]);
  const [cursor, setCursor] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const gid = (g: Commitment[]) => String(g[0].id);
  const at = Math.min(cursor, Math.max(0, groups.length - 1));

  const search = useMutation({
    mutationFn: async (ids: number[]) => {
      const jobIds: string[] = [];
      for (const id of ids) {
        try {
          jobIds.push((await api.findEvidence(id)).id);
        } catch (e) {
          toast.error(`Could not start search: ${errorMessage(e)}`);
          break;
        }
      }
      return jobIds;
    },
    onSuccess: (ids) => { setSelected(new Set()); onStarted(ids); },
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
  useRowKeys(groups.length, at, setCursor, { onToggle: () => groups[at] && toggle(gid(groups[at])) });

  return (
    <>
      <div className="mb-3 flex items-center gap-2">
        <Button
          size="sm"
          disabled={!selected.size || search.isPending}
          onClick={() =>
            search.mutate(groups.filter((g) => selected.has(gid(g))).flatMap((g) => g.map((c) => c.id)))
          }
        >
          {search.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Search className="size-3.5" />}
          Search {selected.size || ""} selected
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            setSelected(new Set(groups.filter((g) => !g.some((c) => matches.has(c.id))).map(gid)))
          }
        >
          Select all not searched
        </Button>
        {selected.size > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button>
        )}
      </div>
      <DataTable
        columns={columns}
        data={groups}
        getId={gid}
        cursor={at}
        onCursor={setCursor}
        onOpen={(g) => toggle(gid(g))}
        selected={selected}
        onToggle={toggle}
        onToggleAll={(on) => setSelected(on ? new Set(groups.map(gid)) : new Set())}
      />
    </>
  );
}

/* review: confirm or reject suggested matches */

function ReviewTable({ pending, commitments }: { pending: Pending[]; commitments: Commitment[] }) {
  const invalidate = useInvalidateDomain();
  const [cursor, setCursor] = useState(0);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [relChoice, setRelChoice] = useState<Map<number, RelationshipType>>(new Map());

  const comById = useMemo(() => new Map(commitments.map((c) => [c.id, c])), [commitments]);
  const rows = useMemo(
    () =>
      [...pending].sort((a, b) => {
        const ta = displayTitle(comById.get(a.link.commitment_id)?.title ?? "");
        const tb = displayTitle(comById.get(b.link.commitment_id)?.title ?? "");
        return ta.localeCompare(tb) || b.link.score - a.link.score;
      }),
    [pending, comById],
  );
  const lid = (r: Pending) => String(r.link.id);
  const at = Math.min(cursor, Math.max(0, rows.length - 1));
  const current = rows[at] ?? null;
  const rel = (r: Pending) => relChoice.get(r.link.id) ?? r.link.suggested_relationship;

  // rows are fetched lite, the panel hydrates the selected link
  const full = useLink(open && current ? current.link.id : null);
  const detail = (full.data ?? current) as Pending | null;

  const columns: Columns<Pending> = useMemo(
    () => [
      {
        id: "commitment",
        header: "Commitment",
        cell: ({ row }) => (
          <p className="max-w-sm font-medium leading-snug">
            {displayTitle(comById.get(row.original.link.commitment_id)?.title ?? "")}
          </p>
        ),
      },
      {
        id: "source",
        header: "Source",
        cell: ({ row }) => {
          const ev = row.original.evidence;
          return (
            <div className="max-w-md">
              <p className="line-clamp-1">{displayTitle(ev.title)}</p>
              <p className="text-xs text-muted-foreground">
                {[ev.publisher ?? "Official source", ev.published_on, evidenceKind(ev.url, ev.title)].filter(Boolean).join(" · ")}
              </p>
            </div>
          );
        },
      },
      {
        id: "says",
        header: "Source says",
        cell: ({ row }) => {
          const s = row.original.evidence.status_hint;
          return <Chip label={STATUS_LABEL[s]} tone={STATUS_TONE[s]} icon={STATUS_ICON[s]} />;
        },
      },
      {
        id: "rel",
        header: "Relationship",
        cell: ({ row }) => {
          const r = rel(row.original);
          return <Chip label={REL_LABEL[r]} tone={REL_TONE[r]} icon={REL_ICON[r]} />;
        },
      },
      {
        id: "score",
        header: "Score",
        cell: ({ row }) => <span className="tabular-nums text-muted-foreground">{row.original.link.score.toFixed(2)}</span>,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [comById, relChoice],
  );

  const bulk = useMutation({
    mutationFn: (accept: boolean) => {
      const ids = [...selected].map(Number);
      const relationships = accept
        ? Object.fromEntries(ids.filter((id) => relChoice.has(id)).map((id) => [id, relChoice.get(id)!]))
        : undefined;
      return api.bulkLinks(accept ? { accept: ids, relationships } : { reject: ids });
    },
    onSuccess: (res, accept) => {
      toast.success(`${accept ? res.accepted : res.rejected} match(es) ${accept ? "confirmed" : "rejected"}.`);
      setSelected(new Set());
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const single = useMutation({
    mutationFn: async (accept: boolean) => {
      if (!current) return;
      await api.decideLink(current.link.id, accept, accept ? relChoice.get(current.link.id) : undefined);
    },
    onSuccess: (_r, accept) => {
      toast.success(accept ? "Match confirmed." : "Match rejected.");
      setOpen(false);
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
  useRowKeys(rows.length, at, setCursor, {
    onOpen: () => current && setOpen(true),
    onToggle: () => current && toggle(lid(current)),
    onAccept: () => current && single.mutate(true),
    onReject: () => current && single.mutate(false),
  });

  if (!rows.length)
    return <EmptyState>No matches waiting. Search a commitment on the Find tab.</EmptyState>;

  return (
    <>
      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border bg-card px-3 py-2">
          <span className="text-sm">{selected.size} selected</span>
          <Button size="sm" disabled={bulk.isPending} onClick={() => bulk.mutate(true)}>
            <Check className="size-3.5" /> Confirm
          </Button>
          <Button size="sm" variant="outline" disabled={bulk.isPending} onClick={() => bulk.mutate(false)}>
            <X className="size-3.5" /> Reject
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button>
        </div>
      )}
      <DataTable
        columns={columns}
        data={rows}
        getId={lid}
        cursor={at}
        onCursor={setCursor}
        onOpen={() => setOpen(true)}
        selected={selected}
        onToggle={toggle}
        onToggleAll={(on) => setSelected(on ? new Set(rows.map(lid)) : new Set())}
      />
      <DetailSheet open={open && !!current} onClose={() => setOpen(false)} label="Match detail">
        {current && detail && (
          <div className="space-y-4">
            <LinkDetail
              view={detail}
              commitment={comById.get(current.link.commitment_id)}
              rel={rel(current)}
              onRel={(r) => setRelChoice((m) => new Map(m).set(current.link.id, r))}
            />
            <div className="flex gap-2 border-t pt-3">
              <Button size="sm" disabled={single.isPending} onClick={() => single.mutate(true)}>
                <Check className="size-3.5" /> Confirm <Kbd>C</Kbd>
              </Button>
              <Button size="sm" variant="outline" disabled={single.isPending} onClick={() => single.mutate(false)}>
                <X className="size-3.5" /> Reject <Kbd>R</Kbd>
              </Button>
            </div>
          </div>
        )}
      </DetailSheet>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <EvidencePage />
    </Suspense>
  );
}
