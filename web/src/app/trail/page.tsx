"use client";

import { Suspense, useMemo, useState, type ReactNode } from "react";
import { useQueryState, parseAsString } from "nuqs";
import { ExternalLink, Link2, Link2Off } from "lucide-react";
import { QueryError } from "@/components/query-error";
import { PageHeader } from "@/components/page-header";
import { En } from "@/components/en";
import { Chip } from "@/components/queue";
import {
  KIND_ICON,
  KIND_TONE,
  STATUS_ICON,
  STATUS_TONE,
  TONE_TEXT,
  type Tone,
} from "@/lib/tones";
import type { Commitment, EvidenceItem, TrailRow } from "@/lib/api";
import {
  BUDGET_LABEL,
  KIND_LABEL,
  STATUS_LABEL,
  displayTitle,
  huf,
  titleGroups,
} from "@/lib/labels";
import {
  useCandidates,
  useCommitments,
  useLinks,
  useTrail,
} from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const FILTER_OPTS = ["All", "Has evidence", "Missing evidence", "Measurable target"];
const MAX_BUDGET_LINES = 6;

function matches(row: TrailRow, flt: string): boolean {
  if (flt === "Has evidence") return row.evidence.length > 0;
  if (flt === "Missing evidence") return row.evidence.length === 0;
  if (flt === "Measurable target") return !!row.commitment.is_measurable;
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

function TrailPage() {
  const { data: rows, isLoading, error, refetch } = useTrail();
  const { data: commitments } = useCommitments();
  const { data: links } = useLinks();
  const { data: candidates } = useCandidates();
  const [flt, setFlt] = useQueryState(
    "show",
    parseAsString.withDefault("All"),
  );
  const [selId, setSelId] = useState<number | null>(null);
  const [mentionSel, setMentionSel] = useState<Record<number, number>>({});

  const groups = useMemo(
    () =>
      titleGroups(
        rows ?? [],
        (r) => r.commitment.title,
        (r) => r.commitment.kind,
      ),
    [rows],
  );
  const { grouped, byId } = useMemo(() => objectiveGroups(groups), [groups]);

  const ordered = useMemo(
    () =>
      [...grouped.entries()].sort(([a], [b]) =>
        a === null ? 1 : b === null ? -1 : 0,
      ),
    [grouped],
  );

  if (error) return <div className="p-4 sm:p-8"><QueryError error={error} retry={refetch} /></div>;

  if (isLoading)
    return (
      <div className="mx-auto w-full max-w-[1320px] p-4 sm:p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-6 h-96 w-full" />
      </div>
    );

  if (!rows?.length)
    return (
      <div className="mx-auto w-full max-w-[1320px] p-4 sm:p-8">
        <PageHeader title="Paper trail" guide="trail" />
        <p className="mt-8 text-sm text-muted-foreground">
          Nothing here yet — confirm some commitments and matches first.
        </p>
      </div>
    );

  const withEvidence = groups.filter((g) =>
    g.some((r) => r.evidence.length > 0),
  ).length;
  const shown = ordered.flatMap(([, children]) =>
    children.filter((g) => g.some((r) => matches(r, flt))),
  );
  const shownIds = new Set(shown.map((g) => g[0].commitment.id));
  const selected =
    selId != null && shownIds.has(selId) ? selId : shown[0]?.[0].commitment.id;
  const selGroup = shown.find((g) => g[0].commitment.id === selected);
  const selRow = selGroup
    ? (selGroup.find(
        (r) => r.commitment.id === mentionSel[selected ?? -1],
      ) ?? selGroup[0])
    : null;

  return (
    <div className="mx-auto w-full max-w-[1320px] p-4 sm:p-8">
      <PageHeader title="Paper trail" guide="trail" />
      <p className="mt-2 text-xs text-muted-foreground">
        {groups.length} commitments · {withEvidence} with evidence · Read-only
      </p>

      <ToggleGroup
        className="mt-4"
        value={[flt]}
        onValueChange={(v) => v[0] && setFlt(v[0] === "All" ? null : v[0])}
        variant="outline"
        size="sm"
      >
        {FILTER_OPTS.map((f) => (
          <ToggleGroupItem key={f} value={f}>
            {f}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {!shown.length ? (
        <p className="mt-6 text-sm text-muted-foreground">
          Nothing matches this filter.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
            {ordered.map(([rootId, children]) => {
              const visible = children.filter((g) =>
                shownIds.has(g[0].commitment.id),
              );
              if (!visible.length) return null;
              const root = rootId ? byId.get(rootId)?.[0].commitment : null;
              return (
                <div key={rootId ?? "other"}>
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    {root ? (
                      <KIND_ICON.objective className="size-4 shrink-0 text-sky-600 dark:text-sky-400" />
                    ) : null}
                    {root
                      ? `${root.code ? root.code + " · " : ""}${displayTitle(root.title)}`
                      : "Other commitments"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {visible.length} commitments ·{" "}
                    {
                      visible.filter((g) => g.some((r) => r.evidence.length))
                        .length
                    }{" "}
                    with evidence
                  </p>
                  <div className="mt-1.5 divide-y rounded-md border">
                    {visible.map((g) => {
                      const row = g[0];
                      const com = row.commitment;
                      const sources = new Set(
                        g.flatMap((r) => r.evidence.map((e) => e.url)),
                      );
                      const statuses = [
                        ...new Set(
                          g
                            .filter((r) => r.status !== "unknown")
                            .map((r) => r.status),
                        ),
                      ];
                      return (
                        <button
                          key={com.id}
                          className={cn(
                            "block w-full px-3 py-2.5 text-left",
                            selected === com.id && "bg-primary/5",
                          )}
                          onClick={() => setSelId(com.id)}
                        >
                          <span className="block truncate text-sm font-medium hover:underline">
                            {displayTitle(com.title)}
                          </span>
                          <span className="mt-0.5 block text-xs text-muted-foreground">
                            {[
                              com.source_page
                                ? `p.${com.source_page}`
                                : "Strategy",
                              com.deadline_year
                                ? `deadline ${com.deadline_year}`
                                : null,
                              g.length > 1
                                ? `${g.length} source mentions`
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                          <span className="mt-1 flex flex-wrap gap-1">
                            <Chip
                              label={
                                sources.size
                                  ? `${sources.size} evidence source${sources.size === 1 ? "" : "s"}`
                                  : "No evidence yet"
                              }
                              tone={sources.size ? "green" : "gray"}
                              icon={sources.size ? Link2 : Link2Off}
                            />
                            {statuses.map((s) => (
                              <Chip
                                key={s}
                                label={STATUS_LABEL[s]}
                                tone={STATUS_TONE[s]}
                                icon={STATUS_ICON[s]}
                              />
                            ))}
                            <Chip
                              label={KIND_LABEL[com.kind]}
                              tone={KIND_TONE[com.kind]}
                            />
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-md border p-4">
            {selGroup && selRow && (
              <TrailDetail
                row={selRow}
                mentions={selGroup.length}
                mentionValue={mentionSel[selected ?? -1]}
                onMention={(id) =>
                  setMentionSel((prev) => ({ ...prev, [selected ?? -1]: id }))
                }
                group={selGroup}
                promise={
                  candidates?.find(
                    (c) => c.id === selRow.commitment.candidate_id,
                  )?.source_excerpt ?? selRow.commitment.summary
                }
              />
            )}
          </div>
        </div>
      )}

      <Timeline commitments={commitments ?? []} links={links ?? []} />
    </div>
  );
}

function TrailDetail({
  row,
  mentions,
  group,
  mentionValue,
  onMention,
  promise,
}: {
  row: TrailRow;
  mentions: number;
  group: TrailRow[];
  mentionValue?: number;
  onMention: (id: number) => void;
  promise?: string | null;
}) {
  const com = row.commitment;

  const byRel = new Map<string, EvidenceItem[]>();
  row.evidence.forEach((ev, i) => {
    const rel = row.relationships[i] ?? "supporting";
    byRel.set(rel, [...(byRel.get(rel) ?? []), ev]);
  });
  const impl = byRel.get("direct_implementation") ?? [];
  const support = [
    ...(byRel.get("supporting") ?? []),
    ...(byRel.get("related_but_indirect") ?? []),
  ];
  const budgetItems = byRel.get("budget") ?? [];

  return (
    <div className="space-y-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Selected paper trail
      </p>
      <div>
        <h2 className="text-lg font-semibold leading-snug">
          {displayTitle(com.title)}
        </h2>
        <En text={displayTitle(com.title)} />
      </div>

      {mentions > 1 && (
        <Select
          value={String(mentionValue ?? com.id)}
          onValueChange={(v) => onMention(Number(v))}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {group.map((r) => (
              <SelectItem key={r.commitment.id} value={String(r.commitment.id)}>
                p.{r.commitment.source_page} · {r.evidence.length} evidence
                source{r.evidence.length === 1 ? "" : "s"} · mention{" "}
                {r.commitment.id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <p className="text-xs text-muted-foreground">
        {[
          KIND_LABEL[com.kind].toUpperCase(),
          com.source_page ? `Strategy · p.${com.source_page}` : null,
          com.deadline_year ? `Deadline ${com.deadline_year}` : null,
          com.is_measurable && com.target_value != null
            ? `Target ${com.target_value} ${com.unit ?? ""}`
            : null,
          com.responsible_org ? `who: ${com.responsible_org}` : null,
          mentions > 1 ? `${mentions} source mentions` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {row.status !== "unknown" && (
        <div>
          <Chip
            label={`Source says: ${STATUS_LABEL[row.status]}`}
            tone={STATUS_TONE[row.status]}
            icon={STATUS_ICON[row.status]}
          />
        </div>
      )}

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Promise
        </p>
        {promise ? (
          <>
            <blockquote className="mt-1 border-l-2 pl-3 text-sm text-muted-foreground">
              {promise}
            </blockquote>
            <En text={promise} />
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            No source wording stored for this commitment.
          </p>
        )}
      </div>

      {impl.length > 0 && (
        <div>
          <SectionLabel tone="green">Implementation</SectionLabel>
          {impl.map((ev) => (
            <EvidenceLine key={ev.id} ev={ev} />
          ))}
          {row.status_excerpt && (
            <p className="mt-1 text-xs text-muted-foreground">
              “{row.status_excerpt}”
            </p>
          )}
        </div>
      )}

      {support.length > 0 && (
        <div>
          <SectionLabel tone="blue">Supporting evidence</SectionLabel>
          {support.map((ev) => (
            <EvidenceLine key={ev.id} ev={ev} />
          ))}
        </div>
      )}

      {(budgetItems.length > 0 || row.budgets.length > 0) && (
        <div>
          <SectionLabel tone="purple">Budget</SectionLabel>
          {budgetItems.map((ev) => (
            <EvidenceLine key={ev.id} ev={ev} />
          ))}
          {row.budgets.slice(0, MAX_BUDGET_LINES).map((b) => (
            <p key={b.id} className="mt-1 text-xs text-muted-foreground">
              {huf(b.amount_huf)} — {BUDGET_LABEL[b.kind]} (
              {b.fiscal_year ?? "year unknown"}) — “{b.description}”{" "}
              <a
                className="underline"
                href={b.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                source
              </a>
            </p>
          ))}
          {row.budgets.length > MAX_BUDGET_LINES && (
            <p className="text-xs text-muted-foreground">
              … and {row.budgets.length - MAX_BUDGET_LINES} more figures in the
              sources
            </p>
          )}
        </div>
      )}

      {row.gaps.length > 0 && (
        <div>
          <SectionLabel tone="amber">Still missing</SectionLabel>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {row.gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SectionLabel({
  tone,
  children,
}: {
  tone: Tone;
  children: ReactNode;
}) {
  return (
    <p
      className={cn(
        "flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide",
        TONE_TEXT[tone],
      )}
    >
      <span
        className={cn(
          "inline-block size-2 rounded-full",
          tone === "green" && "bg-emerald-500",
          tone === "blue" && "bg-sky-500",
          tone === "teal" && "bg-teal-500",
          tone === "amber" && "bg-amber-500",
          tone === "purple" && "bg-violet-500",
          tone === "red" && "bg-red-500",
          tone === "gray" && "bg-muted-foreground",
        )}
      />
      {children}
    </p>
  );
}

function EvidenceLine({ ev }: { ev: EvidenceItem }) {
  return (
    <div className="mt-1.5">
      <a
        href={ev.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-sm font-medium underline-offset-4 hover:underline"
      >
        <ExternalLink className="size-3.5" />
        {displayTitle(ev.title)}
      </a>
      <p className="text-xs text-muted-foreground">
        {[
          ev.publisher ?? "official source",
          ev.published_on,
          STATUS_LABEL[ev.status_hint],
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </div>
  );
}

function Timeline({
  commitments,
  links,
}: {
  commitments: Commitment[];
  links: { link: { review_status: string }; evidence: { published_on: string | null; title: string } | null }[];
}) {
  const events = new Set<string>();
  for (const c of commitments)
    if (c.deadline_year)
      events.add(`${c.deadline_year}deadline — ${c.title}`);
  for (const l of links)
    if (l.link.review_status === "accepted" && l.evidence?.published_on)
      events.add(
        `${l.evidence.published_on.slice(0, 4)}published — ${l.evidence.title}`,
      );
  if (!events.size) return null;
  return (
    <Popover>
      <PopoverTrigger
        render={<Button variant="outline" size="sm" className="mt-6" />}
      >
        Dates we know
      </PopoverTrigger>
      <PopoverContent className="w-96">
        <p className="mb-2 font-medium">Dates we know</p>
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {[...events].sort().map((e) => (
            <p key={e} className="text-xs">
              <span className="font-medium">{e.slice(0, 4)}</span> —{" "}
              {e.slice(4)}
            </p>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default function Page() {
  return (
    <Suspense>
      <TrailPage />
    </Suspense>
  );
}
