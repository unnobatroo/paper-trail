"use client";

import { Suspense, useMemo, useState } from "react";
import { useQueryState, parseAsString } from "nuqs";
import { Chip, EmptyState } from "@/components/chip";
import { DataTable, useRowKeys, type Columns } from "@/components/data-table";
import { DetailSheet } from "@/components/detail-sheet";
import { TrailDetail, Timeline } from "@/components/detail/trail-detail";
import { En } from "@/components/en";
import { QueryError } from "@/components/query-error";
import { PageTitle, Toolbar } from "@/components/toolbar";
import { Kbd } from "@/components/ui/kbd";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Commitment, TrailRow } from "@/lib/api";
import { useCandidates, useCommitments, useDocuments, useLinks, useTrail } from "@/lib/hooks";
import { KIND_LABEL, STATUS_LABEL, displayTitle, titleGroups } from "@/lib/labels";
import { KIND_ICON, KIND_TONE, STATUS_ICON, STATUS_TONE } from "@/lib/tones";
import { cn } from "@/lib/utils";

const FILTER_OPTS = ["All", "Has evidence", "Missing evidence", "Measurable target"];

const measurable = (c: Commitment) =>
  c.target_value != null && c.unit != null;

function matches(row: TrailRow, flt: string): boolean {
  if (flt === "Has evidence") return row.evidence.length > 0;
  if (flt === "Missing evidence") return row.evidence.length === 0;
  if (flt === "Measurable target") return measurable(row.commitment);
  return true;
}

/** Objective grouping: recorded parents or code ancestry — never guessing. */
function objectiveGroups(groups: TrailRow[][]) {
  const byId = new Map<number, TrailRow[]>();
  for (const g of groups) for (const r of g) byId.set(r.commitment.id, g);
  const objectives = groups.filter(
    (g) => g[0].commitment.kind === "objective",
  );

  const parent = (group: TrailRow[]): TrailRow[] | null => {
    for (const row of group) {
      const p = row.commitment.parent_id
        ? byId.get(row.commitment.parent_id)
        : undefined;
      if (p && p !== group) return p;
    }
    const code = group[0].commitment.code ?? "";
    const ancestors = objectives.filter(
      (g) =>
        g !== group &&
        g[0].commitment.code &&
        code.startsWith(g[0].commitment.code + "."),
    );
    return ancestors.length
      ? ancestors.reduce((a, b) =>
          (a[0].commitment.code ?? "").length >=
          (b[0].commitment.code ?? "").length
            ? a
            : b,
        )
      : null;
  };

  const grouped = new Map<number | null, TrailRow[][]>();
  for (const group of groups) {
    let root = group;
    const seen = new Set<number>();
    while (!seen.has(root[0].commitment.id)) {
      seen.add(root[0].commitment.id);
      const p = parent(root);
      if (!p) break;
      root = p;
    }
    const key =
      root[0].commitment.kind === "objective" ? root[0].commitment.id : null;
    const list = grouped.get(key) ?? [];
    list.push(group);
    grouped.set(key, list);
  }
  return { grouped, byId };
}

type Group = TrailRow[];

const columns: Columns<Group> = [
  {
    id: "title",
    header: "Commitment",
    cell: ({ row }) => {
      const c = row.original[0].commitment;
      return (
        <div className={cn("max-w-xl", c.kind !== "objective" && "pl-4")}>
          <p className={cn("leading-snug", c.kind === "objective" ? "font-semibold" : "font-medium")}>
            {displayTitle(c.title)}
          </p>
          <En text={displayTitle(c.title)} />
        </div>
      );
    },
  },
  {
    id: "kind",
    header: "Type",
    cell: ({ row }) => {
      const k = row.original[0].commitment.kind;
      return <Chip label={KIND_LABEL[k]} tone={KIND_TONE[k]} icon={KIND_ICON[k]} />;
    },
  },
  {
    id: "says",
    header: "Sources say",
    cell: ({ row }) => {
      const all = [...new Set(row.original.map((r) => r.status))].filter((s) => s !== "unknown");
      return all.length ? (
        <div className="flex flex-wrap gap-1">
          {all.map((s) => (
            <Chip key={s} label={STATUS_LABEL[s]} tone={STATUS_TONE[s]} icon={STATUS_ICON[s]} />
          ))}
        </div>
      ) : (
        <span className="text-xs text-muted-foreground">–</span>
      );
    },
  },
  {
    id: "evidence",
    header: "Evidence",
    cell: ({ row }) => {
      const n = row.original.reduce((s, r) => s + r.evidence.length, 0);
      return (
        <span className={cn("tabular-nums", n ? "text-foreground" : "text-muted-foreground")}>
          {n || "none"}
        </span>
      );
    },
  },
  {
    id: "gaps",
    header: "Gaps",
    cell: ({ row }) => {
      const gaps = [...new Set(row.original.flatMap((r) => r.gaps))];
      return (
        <span className="line-clamp-2 max-w-64 text-xs text-muted-foreground">
          {gaps.join(" · ") || "–"}
        </span>
      );
    },
  },
];

function TrailPage() {
  const { data: rows, isLoading, error, refetch } = useTrail();
  const { data: commitments } = useCommitments();
  const { data: links } = useLinks();
  const { data: candidates } = useCandidates();
  const { data: documents } = useDocuments();
  const [flt, setFlt] = useQueryState("show", parseAsString.withDefault("All"));
  const [cursor, setCursor] = useState(0);
  const [open, setOpen] = useState(false);
  const [mentionSel, setMentionSel] = useState<Record<number, number>>({});

  const groups = useMemo(
    () => titleGroups(rows ?? [], (r) => r.commitment.title, (r) => r.commitment.kind),
    [rows],
  );

  // objectives first, their children right under them, loose items last
  const shown = useMemo(() => {
    const { grouped } = objectiveGroups(groups);
    return [...grouped.entries()]
      .sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : 0))
      .flatMap(([, children]) =>
        [...children]
          .filter((g) => g.some((r) => matches(r, flt)))
          .sort((a, b) =>
            Number(b[0].commitment.kind === "objective") - Number(a[0].commitment.kind === "objective"),
          ),
      );
  }, [groups, flt]);

  const at = Math.min(cursor, Math.max(0, shown.length - 1));
  const current = shown[at] ?? null;
  useRowKeys(shown.length, at, setCursor, { onOpen: () => current && setOpen(true) });

  if (error) return <QueryError error={error} retry={refetch} />;
  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (!rows?.length)
    return (
      <>
        <PageTitle title="Trail" hint="The confirmed record: promise, evidence, money, gaps." />
        <EmptyState className="mt-6">Nothing here yet. Confirm some commitments and matches first.</EmptyState>
      </>
    );

  const withEvidence = groups.filter((g) => g.some((r) => r.evidence.length > 0)).length;
  const selId = current?.[0].commitment.id ?? -1;
  const selRow = current ? (current.find((r) => r.commitment.id === mentionSel[selId]) ?? current[0]) : null;
  const cand = candidates?.find((c) => c.id === selRow?.commitment.candidate_id);

  return (
    <>
      <PageTitle
        title="Trail"
        hint={`${groups.length} commitments, ${withEvidence} with confirmed evidence. Read-only.`}
        guide="trail"
      />
      <Toolbar>
        <ToggleGroup
          value={[flt]}
          onValueChange={(v) => v[0] && setFlt(v[0] === "All" ? null : v[0])}
          variant="outline"
          size="sm"
        >
          {FILTER_OPTS.map((f) => (
            <ToggleGroupItem key={f} value={f}>{f}</ToggleGroupItem>
          ))}
        </ToggleGroup>
        <span className="ml-auto text-xs text-muted-foreground">
          <Kbd>j</Kbd> <Kbd>k</Kbd> move <Kbd>enter</Kbd> open
        </span>
      </Toolbar>

      {shown.length ? (
        <DataTable
          columns={columns}
          data={shown}
          getId={(g) => String(g[0].commitment.id)}
          cursor={at}
          onCursor={setCursor}
          onOpen={() => setOpen(true)}
        />
      ) : (
        <EmptyState>No commitments match this filter.</EmptyState>
      )}

      <DetailSheet open={open && !!selRow} onClose={() => setOpen(false)} label="Paper trail detail">
        {current && selRow && (
          <TrailDetail
            key={selRow.commitment.id}
            row={selRow}
            mentions={current.length}
            mentionValue={mentionSel[selId]}
            onMention={(id) => setMentionSel((p) => ({ ...p, [selId]: id }))}
            group={current}
            promise={cand?.source_excerpt ?? selRow.commitment.summary}
            docUrl={documents?.find((d) => d.id === cand?.document_id)?.url}
          />
        )}
      </DetailSheet>

      <div className="mt-8">
        <Timeline commitments={(commitments ?? []) as Commitment[]} links={links ?? []} />
      </div>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <TrailPage />
    </Suspense>
  );
}
