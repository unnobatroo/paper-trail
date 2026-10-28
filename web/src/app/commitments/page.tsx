"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useMutation } from "@tanstack/react-query";
import { useQueryState, parseAsString } from "nuqs";
import { useHotkeys } from "react-hotkeys-hook";
import { Check, X, Search } from "lucide-react";
import { Chip, EmptyState } from "@/components/chip";
import { CandidateDetail, statusChip } from "@/components/detail/candidate-detail";
import { DataTable, useRowKeys, type Columns } from "@/components/data-table";
import { DetailSheet } from "@/components/detail-sheet";
import { En } from "@/components/en";
import { QueryError } from "@/components/query-error";
import { PageTitle, Toolbar } from "@/components/toolbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api, errorMessage, type CandidateType, type PolicyCandidate, type ReviewStatus } from "@/lib/api";
import { useCandidates, useCommitments, useDocuments, useInvalidateDomain } from "@/lib/hooks";
import { KIND_LABEL, displayTitle, titleGroups } from "@/lib/labels";
import { KIND_ICON, KIND_TONE } from "@/lib/tones";

const STATUS_OPTS: Record<string, ReviewStatus | null> = {
  "Needs review": "unreviewed",
  Confirmed: "accepted",
  Rejected: "rejected",
  All: null,
};
const TYPE_OPTS: (CandidateType | "all")[] = ["all", "objective", "target", "measure", "indicator"];
const KIND_ORDER: CandidateType[] = ["objective", "target", "measure", "indicator", "background", "unclear"];

type Group = PolicyCandidate[];

const columns: Columns<Group> = [
  {
    id: "title",
    header: "Commitment",
    cell: ({ row }) => {
      const c = row.original[0];
      return (
        <div className="max-w-xl">
          <p className="font-medium leading-snug">{displayTitle(c.normalized_title)}</p>
          <En text={displayTitle(c.normalized_title)} />
          <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{c.source_excerpt}</p>
        </div>
      );
    },
  },
  {
    id: "type",
    header: "Type",
    cell: ({ row }) => {
      const k = row.original[0].suggested_type;
      return <Chip label={KIND_LABEL[k]} tone={KIND_TONE[k]} icon={KIND_ICON[k]} />;
    },
  },
  {
    id: "page",
    header: "Page",
    cell: ({ row }) => <span className="tabular-nums text-muted-foreground">{row.original[0].source_page}</span>,
  },
  {
    id: "goal",
    header: "Goal",
    cell: ({ row }) => {
      const c = row.original[0];
      const goal = [c.target_value != null ? `${c.target_value} ${c.unit ?? ""}`.trim() : null, c.deadline_year ?? c.timeframe]
        .filter(Boolean)
        .join(" by ");
      return <span className="text-xs text-muted-foreground">{goal || "–"}</span>;
    },
  },
  {
    id: "mentions",
    header: "Mentions",
    cell: ({ row }) => (
      <span className="tabular-nums text-muted-foreground">{row.original.length > 1 ? `×${row.original.length}` : ""}</span>
    ),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => <Chip {...statusChip(row.original[0])} />,
  },
];

function CommitmentsPage() {
  const { data: cands, isLoading, error, refetch } = useCandidates();
  const { data: commitments } = useCommitments();
  const { data: documents } = useDocuments();
  const invalidate = useInvalidateDomain();
  const searchRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useQueryState("q", parseAsString.withDefault(""));
  const [type, setType] = useQueryState("type", parseAsString.withDefault("all"));
  const [status, setStatus] = useQueryState("status", parseAsString.withDefault("Needs review"));
  const [cursor, setCursor] = useState(0);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const groups = useMemo(() => {
    const want = STATUS_OPTS[status] ?? null;
    const q = query.trim().toLowerCase();
    const visible = (cands ?? []).filter(
      (c) =>
        (!want || c.review_status === want) &&
        (type === "all" || c.suggested_type === type) &&
        (!q ||
          (c.normalized_title ?? "").toLowerCase().includes(q) ||
          (c.text ?? "").toLowerCase().includes(q) ||
          (c.code ?? "").toLowerCase().includes(q)),
    );
    return titleGroups(visible, (c) => c.normalized_title, (c) => c.suggested_type).sort(
      (a, b) => KIND_ORDER.indexOf(a[0].suggested_type) - KIND_ORDER.indexOf(b[0].suggested_type),
    );
  }, [cands, query, type, status]);

  const at = Math.min(cursor, Math.max(0, groups.length - 1));
  const current = groups[at] ?? null;
  const gid = (g: Group) => String(g[0].id);

  const bulk = useMutation({
    mutationFn: (action: "confirm" | "reject") => {
      const ids = groups.filter((g) => selected.has(gid(g))).flatMap((g) => g.map((c) => c.id));
      return api.bulkCandidates(action === "confirm" ? { accept: ids } : { reject: ids });
    },
    onSuccess: (res, action) => {
      toast.success(`${action === "confirm" ? res.accepted : res.rejected} source mentions ${action === "confirm" ? "confirmed" : "rejected"}.`);
      setSelected(new Set());
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const single = useMutation({
    mutationFn: async (action: "accept" | "reject") => {
      const id = current![0].id;
      if (action === "accept") await api.acceptCandidate(id);
      else await api.rejectCandidate(id);
    },
    onSuccess: (_r, action) => {
      toast.success(action === "accept" ? "Confirmed as a commitment." : "Rejected.");
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const pending = current?.[0].review_status === "unreviewed";
  useRowKeys(groups.length, at, setCursor, {
    onOpen: () => current && setOpen(true),
    onToggle: () => current && toggle(gid(current)),
    onAccept: () => pending && single.mutate("accept"),
    onReject: () => pending && single.mutate("reject"),
  });
  useHotkeys("/", (e) => { e.preventDefault(); searchRef.current?.focus(); }, []);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (error) return <QueryError error={error} retry={refetch} />;
  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (!cands?.length)
    return (
      <>
        <PageTitle title="Commitments" hint="Confirm or reject what the strategy promises." />
        <EmptyState className="mt-6">
          Nothing extracted yet. Use <strong>Ingest</strong> in the top bar to read the strategy PDF.
        </EmptyState>
      </>
    );

  const docUrl = documents?.[0]?.url;

  return (
    <>
      <PageTitle title="Commitments" hint="Check each promise against the original strategy before confirming it." guide="commitments" />
      <Toolbar>
        <div className="relative">
          <Search className="pointer-events-none absolute top-2 left-2.5 size-3.5 text-muted-foreground" />
          <Input
            ref={searchRef}
            value={query}
            onChange={(e) => setQuery(e.target.value || null)}
            placeholder="Search commitments"
            className="h-8 w-64 pl-8"
            aria-label="Search commitments"
          />
        </div>
        <ToggleGroup
          value={[status]}
          onValueChange={(v) => v[0] && setStatus(v[0])}
          variant="outline"
          size="sm"
        >
          {Object.keys(STATUS_OPTS).map((s) => (
            <ToggleGroupItem key={s} value={s}>{s}</ToggleGroupItem>
          ))}
        </ToggleGroup>
        <ToggleGroup
          value={[type]}
          onValueChange={(v) => v[0] && setType(v[0])}
          variant="outline"
          size="sm"
        >
          {TYPE_OPTS.map((t) => (
            <ToggleGroupItem key={t} value={t}>{t === "all" ? "All types" : KIND_LABEL[t]}</ToggleGroupItem>
          ))}
        </ToggleGroup>
        <span className="ml-auto text-xs text-muted-foreground">
          {groups.length} shown · <Kbd>j</Kbd> <Kbd>k</Kbd> move <Kbd>x</Kbd> select <Kbd>c</Kbd> confirm <Kbd>r</Kbd> reject
        </span>
      </Toolbar>

      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border bg-card px-3 py-2">
          <span className="text-sm">{selected.size} selected</span>
          <Button size="sm" disabled={bulk.isPending} onClick={() => bulk.mutate("confirm")}>
            <Check className="size-3.5" /> Confirm
          </Button>
          <Button size="sm" variant="outline" disabled={bulk.isPending} onClick={() => bulk.mutate("reject")}>
            <X className="size-3.5" /> Reject
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button>
        </div>
      )}

      {groups.length ? (
        <DataTable
          columns={columns}
          data={groups}
          getId={gid}
          cursor={at}
          onCursor={setCursor}
          onOpen={() => setOpen(true)}
          selected={selected}
          onToggle={toggle}
          onToggleAll={(on) => setSelected(on ? new Set(groups.map(gid)) : new Set())}
        />
      ) : (
        <EmptyState>No commitments match these filters.</EmptyState>
      )}

      <DetailSheet open={open && !!current} onClose={() => setOpen(false)} label="Commitment detail">
        {current && (
          <CandidateDetail
            key={current[0].id}
            group={current}
            commitments={commitments ?? []}
            docUrl={docUrl}
          />
        )}
      </DetailSheet>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <CommitmentsPage />
    </Suspense>
  );
}
