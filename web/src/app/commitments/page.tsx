"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useMutation } from "@tanstack/react-query";
import { useQueryState, parseAsInteger, parseAsString } from "nuqs";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useHotkeys } from "react-hotkeys-hook";
import { Check, X, Search, SquarePen, Clock, CircleHelp } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { En } from "@/components/en";
import {
  QueueList,
  Pager,
  BatchBar,
  EmptyState,
  Chip,
  type RowChip,
} from "@/components/queue";
import { Kbd } from "@/components/ui/kbd";
import { KIND_ICON, KIND_TONE } from "@/lib/tones";
import {
  api,
  type CandidateType,
  type PolicyCandidate,
  type ReviewStatus,
} from "@/lib/api";
import { KIND_LABEL, displayTitle, titleGroups } from "@/lib/labels";
import {
  useCandidates,
  useCommitments,
  useDocuments,
  useInvalidateDomain,
} from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { Label } from "@/components/ui/label";

const PAGE = 10;
const TYPE_OPTS = ["All", "Objectives", "Measures", "Targets"];
const TYPE_MAP: Record<string, CandidateType> = {
  Objectives: "objective",
  Measures: "measure",
  Targets: "target",
};
const STATUS_OPTS = ["Needs review", "Confirmed", "Rejected", "All"];
const STATUS_MAP: Record<string, ReviewStatus> = {
  "Needs review": "unreviewed",
  Confirmed: "accepted",
  Rejected: "rejected",
};

function statusText(c: PolicyCandidate): string {
  if (c.review_status === "accepted") return "Confirmed";
  if (c.review_status === "rejected") return "Rejected";
  return c.excerpt_on_page === false ? "Unclear" : "Needs review";
}

function statusChip(c: PolicyCandidate): RowChip {
  if (c.review_status === "accepted")
    return { label: "Confirmed", tone: "green", icon: Check };
  if (c.review_status === "rejected")
    return { label: "Rejected", tone: "red", icon: X };
  if (c.excerpt_on_page === false)
    return { label: "Unclear", tone: "gray", icon: CircleHelp };
  return { label: "Needs review", tone: "amber", icon: Clock };
}

const KIND_ORDER: CandidateType[] = [
  "objective",
  "target",
  "measure",
  "indicator",
  "background",
  "unclear",
];
const KIND_SECTION: Record<CandidateType, string> = {
  objective: "Objectives",
  target: "Targets",
  measure: "Measures",
  indicator: "Indicators",
  background: "Background text",
  unclear: "Unclear",
};

function CommitmentsPage() {
  const { data: cands, isLoading } = useCandidates();
  const { data: commitments } = useCommitments();
  const { data: documents } = useDocuments();
  const invalidate = useInvalidateDomain();
  const searchRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useQueryState("q", parseAsString.withDefault(""));
  const [typeLabel, setTypeLabel] = useQueryState(
    "type",
    parseAsString.withDefault("All"),
  );
  const [status, setStatus] = useQueryState(
    "status",
    parseAsString.withDefault("Needs review"),
  );
  const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
  const [cursor, setCursor] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const visible = useMemo(() => {
    let out = cands ?? [];
    const want = STATUS_MAP[status];
    if (want) out = out.filter((c) => c.review_status === want);
    const t = TYPE_MAP[typeLabel];
    if (t) out = out.filter((c) => c.suggested_type === t);
    const q = query.trim().toLowerCase();
    if (q)
      out = out.filter(
        (c) =>
          (c.normalized_title ?? "").toLowerCase().includes(q) ||
          (c.text ?? "").toLowerCase().includes(q) ||
          (c.code ?? "").toLowerCase().includes(q),
      );
    return out;
  }, [cands, query, typeLabel, status]);

  const groups = useMemo(() => {
    const gs = titleGroups(
      visible,
      (c) => c.normalized_title,
      (c) => c.suggested_type,
    );
    return gs.sort(
      (a, b) =>
        KIND_ORDER.indexOf(a[0].suggested_type) -
        KIND_ORDER.indexOf(b[0].suggested_type),
    );
  }, [visible]);
  const pages = Math.max(1, Math.ceil(groups.length / PAGE));
  const pageGroups = groups.slice((page - 1) * PAGE, page * PAGE);
  const clamped = Math.min(cursor, Math.max(0, pageGroups.length - 1));
  const detail = pageGroups[clamped] ?? null;

  const bulk = useMutation({
    mutationFn: (action: "confirm" | "reject") => {
      const ids = groups
        .filter((g) => selected.has(g[0].id))
        .flatMap((g) => g.map((c) => c.id));
      return api.bulkCandidates(
        action === "confirm" ? { accept: ids } : { reject: ids },
      );
    },
    onSuccess: (res, action) => {
      toast.success(
        `${action === "confirm" ? res.accepted : res.rejected} source mentions ${action === "confirm" ? "confirmed" : "rejected"}.`,
      );
      setSelected(new Set());
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  const single = useMutation({
    mutationFn: async (action: "accept" | "reject") => {
      if (action === "accept") await api.acceptCandidate(detail![0].id);
      else await api.rejectCandidate(detail![0].id);
    },
    onSuccess: (_r, action) => {
      toast.success(
        action === "accept" ? "Confirmed as a commitment." : "Rejected.",
      );
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  // triage keyboard shortcuts — j/k move, x select, c confirm, r reject, / search
  const editable = () =>
    ["INPUT", "TEXTAREA", "SELECT"].includes(
      (document.activeElement?.tagName ?? ""),
    );
  useHotkeys("j", () => !editable() && setCursor((c) => Math.min(c + 1, pageGroups.length - 1)), [pageGroups.length]);
  useHotkeys("k", () => !editable() && setCursor((c) => Math.max(c - 1, 0)), []);
  useHotkeys("x", () => {
    if (editable() || !detail) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(detail[0].id)) next.delete(detail[0].id);
      else next.add(detail[0].id);
      return next;
    });
  }, [detail]);
  useHotkeys("c", () => {
    if (editable() || !detail || detail[0].review_status !== "unreviewed") return;
    single.mutate("accept");
  }, [detail]);
  useHotkeys("r", () => {
    if (editable() || !detail || detail[0].review_status !== "unreviewed") return;
    single.mutate("reject");
  }, [detail]);
  useHotkeys("/", (e) => {
    e.preventDefault();
    searchRef.current?.focus();
  }, []);

  if (isLoading)
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-6 h-96 w-full" />
      </div>
    );

  if (!cands?.length)
    return (
      <div className="p-8">
        <PageHeader title="Check commitments" guide="commitments" />
        <EmptyState className="mt-8">
          Nothing to check yet — read the strategy from the sidebar.
        </EmptyState>
      </div>
    );

  const remaining = cands.filter(
    (c) => c.review_status === "unreviewed",
  ).length;

  return (
    <div className="p-8">
      <PageHeader title="Check commitments" guide="commitments" />
      <p className="mt-2 text-xs text-muted-foreground">
        {cands.length} source mentions · {cands.length - remaining} reviewed ·{" "}
        {remaining} left
      </p>

      {remaining === 0 && status === "Needs review" ? (
        <div className="mt-8 rounded-md border border-green-500/30 bg-green-500/5 p-6">
          <p className="font-medium text-green-700 dark:text-green-400">
            All commitments reviewed.
          </p>
          <div className="mt-3 flex gap-2">
            {STATUS_OPTS.slice(1).map((s) => (
              <Button
                key={s}
                variant="outline"
                size="sm"
                onClick={() => setStatus(s)}
              >
                View {s.toLowerCase()}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <Input
                ref={searchRef}
                className="pl-9"
                placeholder="Search commitments…  ( / )"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value || null);
                  setPage(1);
                  setCursor(0);
                }}
              />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ToggleGroup
                value={[typeLabel]}
                onValueChange={(v) => {
                  if (v[0]) {
                    setTypeLabel(v[0] === "All" ? null : v[0]);
                    setPage(1);
                    setCursor(0);
                  }
                }}
                variant="outline"
                size="sm"
              >
                {TYPE_OPTS.map((t) => (
                  <ToggleGroupItem key={t} value={t}>
                    {t}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              <ToggleGroup
                value={[status]}
                onValueChange={(v) => {
                  if (v[0]) {
                    setStatus(v[0] === "Needs review" ? null : v[0]);
                    setPage(1);
                    setCursor(0);
                  }
                }}
                variant="outline"
                size="sm"
              >
                {STATUS_OPTS.map((s) => (
                  <ToggleGroupItem key={s} value={s}>
                    {s}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>

            {!groups.length && (
              <EmptyState className="mt-6">
                Nothing matches these filters.
              </EmptyState>
            )}

            <div className="mt-3">
              <BatchBar
                count={selected.size}
                busy={bulk.isPending}
                onConfirm={() => bulk.mutate("confirm")}
                onReject={() => bulk.mutate("reject")}
                onClear={() => setSelected(new Set())}
              />
            </div>

            <div className="mt-3">
              <QueueList
                rows={pageGroups.map((g) => ({
                  key: String(g[0].id),
                  title: displayTitle(g[0].normalized_title),
                  section: KIND_SECTION[g[0].suggested_type],
                  sectionIcon: KIND_ICON[g[0].suggested_type],
                  chips: [
                    ...new Map(
                      g.map((c) => [statusText(c), statusChip(c)]),
                    ).values(),
                  ],
                  meta: [
                    "p." +
                      [...new Set(g.map((c) => c.source_page))].join(", "),
                    ...(g.length > 1 ? [`${g.length} source mentions`] : []),
                  ],
                }))}
                activeKey={detail ? String(detail[0].id) : null}
                selected={new Set([...selected].map(String))}
                onInspect={(key) =>
                  setCursor(
                    pageGroups.findIndex((g) => String(g[0].id) === key),
                  )
                }
                onToggle={(key, on) =>
                  setSelected((prev) => {
                    const next = new Set(prev);
                    if (on) next.add(Number(key));
                    else next.delete(Number(key));
                    return next;
                  })
                }
                onToggleAll={(keys, on) =>
                  setSelected((prev) => {
                    const next = new Set(prev);
                    for (const k of keys) {
                      if (on) next.add(Number(k));
                      else next.delete(Number(k));
                    }
                    return next;
                  })
                }
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Page {page} of {pages} · <Kbd>J</Kbd>/<Kbd>K</Kbd> move ·{" "}
              <Kbd>X</Kbd> select · <Kbd>C</Kbd> confirm · <Kbd>R</Kbd> reject
            </p>
            <Pager page={page} pages={pages} onPage={(p) => { setPage(p); setCursor(0); }} />
          </div>

          <div className="rounded-md border p-4">
            {detail && (
              <CandidateInspector
                key={detail[0].id}
                group={detail}
                commitments={commitments ?? []}
                docUrl={
                  documents?.find((d) => d.id === detail[0].document_id)?.url
                }
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const editSchema = z.object({
  kind: z.string(),
  title: z.string().min(1, "Enter a short name"),
  parent_id: z.string(),
});
type EditValues = z.infer<typeof editSchema>;

function CandidateInspector({
  group,
  commitments,
  docUrl,
}: {
  group: PolicyCandidate[];
  commitments: { id: number; code: string | null; title: string }[];
  docUrl?: string | null;
}) {
  const invalidate = useInvalidateDomain();
  const [mentionId, setMentionId] = useState<number>(group[0].id);
  const cand = group.find((c) => c.id === mentionId) ?? group[0];
  const [editing, setEditing] = useState(false);

  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    values: {
      kind: cand.suggested_type,
      title: displayTitle(cand.normalized_title),
      parent_id: "none",
    },
  });

  const decide = useMutation({
    mutationFn: async (action: "accept" | "reject" | "edit") => {
      if (action === "reject") {
        await api.rejectCandidate(cand.id);
        return;
      }
      const v = form.getValues();
      await api.acceptCandidate(
        cand.id,
        action === "edit"
          ? {
              kind: v.kind as CandidateType,
              title: v.title.trim(),
              parent_id: v.parent_id === "none" ? null : Number(v.parent_id),
            }
          : undefined,
      );
    },
    onSuccess: (_r, action) => {
      toast.success(
        action === "reject"
          ? "Rejected."
          : action === "edit"
            ? "Saved as a commitment."
            : "Confirmed as a commitment.",
      );
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  return (
    <div className="space-y-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Commitment inspector
      </p>
      <div>
        <h2 className="text-lg font-semibold leading-snug">
          {displayTitle(cand.normalized_title)}
        </h2>
        <En text={displayTitle(cand.normalized_title)} />
      </div>

      {group.length > 1 && (
        <Select
          value={String(cand.id)}
          onValueChange={(v) => setMentionId(Number(v))}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {group.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                p.{c.source_page} · {statusText(c)} · mention {c.id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <div className="flex items-center gap-2">
        <Chip {...statusChip(cand)} />
        <Chip
          label={KIND_LABEL[cand.suggested_type]}
          tone={KIND_TONE[cand.suggested_type]}
          icon={KIND_ICON[cand.suggested_type]}
        />
        <span className="text-xs text-muted-foreground">
          Page {cand.source_page}
        </span>
      </div>

      {(cand.deadline_year || cand.timeframe) && (
        <p className="text-sm">
          <span className="font-medium">Deadline</span> ·{" "}
          {cand.deadline_year ?? cand.timeframe}
        </p>
      )}
      {cand.target_value != null && (
        <p className="text-sm">
          <span className="font-medium">Target</span> · {cand.target_value}{" "}
          {cand.unit ?? ""}
        </p>
      )}
      {cand.responsible_org && (
        <p className="text-xs text-muted-foreground">{cand.responsible_org}</p>
      )}

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Official Hungarian text
        </p>
        <blockquote className="mt-1 border-l-2 pl-3 text-sm text-muted-foreground">
          {cand.source_excerpt}
        </blockquote>
        <En text={cand.source_excerpt} />
      </div>

      {cand.excerpt_on_page === false && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          We couldn&apos;t re-find this quote on the page — worth a closer
          look.
        </p>
      )}

      {docUrl ? (
        <Button
          variant="outline"
          size="sm"
          render={
            <a
              href={`${docUrl.split("#")[0]}#page=${cand.source_page}`}
              target="_blank"
              rel="noopener noreferrer"
            />
          }
        >
          Strategy · page {cand.source_page}
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">
          Source · Józsefváros Climate Strategy · page {cand.source_page}
        </p>
      )}

      {cand.review_status === "unreviewed" && (
        <div className="space-y-2 border-t pt-3">
          {!editing ? (
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => decide.mutate("accept")}
                disabled={decide.isPending}
              >
                <Check className="mr-1 size-3.5" /> Confirm <Kbd>C</Kbd>
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => decide.mutate("reject")}
                disabled={decide.isPending}
              >
                <X className="mr-1 size-3.5" /> Reject <Kbd>R</Kbd>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditing(true)}
              >
                <SquarePen className="mr-1 size-3.5" /> Edit…
              </Button>
            </div>
          ) : (
            <form
              className="space-y-3 rounded-md border p-3"
              onSubmit={form.handleSubmit(() => decide.mutate("edit"))}
            >
              <p className="text-xs text-muted-foreground">
                Saving confirms this source mention as a commitment.
              </p>
              <div className="space-y-1.5">
                <Label>Commitment type</Label>
                <Select
                  value={form.watch("kind")}
                  onValueChange={(v) => form.setValue("kind", v as string)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(KIND_LABEL).map(([k, l]) => (
                      <SelectItem key={k} value={k}>
                        {l}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Short name</Label>
                <Input {...form.register("title")} />
                {form.formState.errors.title && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.title.message}
                  </p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>Part of</Label>
                <Select
                  value={form.watch("parent_id")}
                  onValueChange={(v) => form.setValue("parent_id", v as string)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— on its own —</SelectItem>
                    {commitments.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.code ? `${c.code} · ` : ""}
                        {displayTitle(c.title)} [{c.id}]
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" disabled={decide.isPending}>
                  Save as commitment
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setEditing(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <CommitmentsPage />
    </Suspense>
  );
}
