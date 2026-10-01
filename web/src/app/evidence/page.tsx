"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useMutation } from "@tanstack/react-query";
import { useQueryState, parseAsInteger, parseAsString } from "nuqs";
import { useHotkeys } from "react-hotkeys-hook";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { QueryError } from "@/components/query-error";
import { PageHeader } from "@/components/page-header";
import { En } from "@/components/en";
import {
  QueueList,
  Pager,
  BatchBar,
  EmptyState,
  Chip,
} from "@/components/queue";
import {
  KIND_ICON,
  KIND_TONE,
  REL_ICON,
  REL_TONE,
  STATUS_ICON,
  STATUS_TONE,
} from "@/lib/tones";
import { Kbd } from "@/components/ui/kbd";
import {
  api,
  type Commitment,
  type EvidenceItem,
  type LinkView,
  type RelationshipType,
} from "@/lib/api";
import {
  BUDGET_LABEL,
  KIND_LABEL,
  REL_HELP,
  REL_LABEL,
  STATUS_LABEL,
  STATUS_SENTENCE,
  displayTitle,
  evidenceKind,
  huf,
  titleGroups,
} from "@/lib/labels";
import {
  useCandidates,
  useCommitments,
  useInvalidateDomain,
  useJobs,
  useLink,
  useLinks,
} from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

const EVIDENCE_KINDS = new Set(["objective", "measure", "target"]);
const PAGE = 10;
const KIND_ORDER = ["objective", "target", "measure"];
const KIND_SECTION: Record<string, string> = {
  objective: "Objectives",
  target: "Targets",
  measure: "Measures",
};

const editable = () =>
  ["INPUT", "TEXTAREA", "SELECT"].includes(
    document.activeElement?.tagName ?? "",
  );

function EvidencePage() {
  const { data: commitments, isLoading, error, refetch } = useCommitments();
  const { data: links, error: linksError, refetch: refetchLinks } = useLinks();
  const invalidate = useInvalidateDomain();
  const [phase, setPhase] = useQueryState("phase", parseAsString);
  const [jobIds, setJobIds] = useState<string[]>([]);
  const { jobs, settled, error: jobError, retry: retryJobs } = useJobs(jobIds);

  const searchable = (commitments ?? []).filter((c) =>
    EVIDENCE_KINDS.has(c.kind),
  );
  const pendingLinks = (links ?? []).filter(
    (l) => l.link.review_status === "unreviewed" && l.evidence,
  );

  const notifiedBatch = useRef<string>("");
  useEffect(() => {
    const batch = jobIds.join(",");
    if (!settled || notifiedBatch.current === batch) return;
    notifiedBatch.current = batch;
    const total = jobs.reduce((acc, j) => acc + (j.result?.links ?? 0), 0);
    const failed = jobs.filter((j) => j.status === "failed");
    if (failed.length)
      toast.error(
        `${failed.length} search(es) failed: ${failed[0].error ?? "unknown"}`,
      );
    else
      toast.success(
        total
          ? `Search done — ${total} possible matches.`
          : "Search done — nothing useful on the official sites.",
      );
    jobs
      .flatMap((j) => j.result?.warnings ?? [])
      .forEach((w) => toast.warning(w));
    invalidate();
  }, [settled, jobs, jobIds, invalidate]);

  const activePhase = settled ? "review" : phase ?? (pendingLinks.length ? "review" : "choose");

  if (linksError) return <div className="p-4 sm:p-8"><QueryError error={linksError} retry={refetchLinks} /></div>;

  if (error) return <div className="p-4 sm:p-8"><QueryError error={error} retry={refetch} /></div>;

  if (isLoading)
    return (
      <div className="mx-auto w-full max-w-[1320px] p-4 sm:p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-6 h-96 w-full" />
      </div>
    );

  if (!searchable.length)
    return (
      <div className="mx-auto w-full max-w-[1320px] p-4 sm:p-8">
        <PageHeader title="Find evidence" guide="evidence" />
        <EmptyState className="mt-8">
          Nothing to check yet — confirm some commitments first.
        </EmptyState>
      </div>
    );

  return (
    <div className="mx-auto w-full max-w-[1320px] p-4 sm:p-8">
      <PageHeader title="Find evidence" guide="evidence" />

      {jobIds.length > 0 && !settled && (
        <div className="mt-4 rounded-md border p-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Loader2 className="size-4 animate-spin" />
            Finding evidence ({jobIds.length} job
            {jobIds.length > 1 ? "s" : ""})
          </div>
          {jobError && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              Cannot check search progress. Your search may still be running.
              <Button variant="outline" size="sm" className="ml-2" onClick={() => retryJobs()}>Retry</Button>
            </p>
          )}
          <div className="mt-2 space-y-1" role="status" aria-live="polite">
            {jobs
              .filter((j) => j.progress)
              .map((j) => (
                <p key={j.id} className="text-xs text-muted-foreground">
                  {j.progress}
                </p>
              ))}
          </div>
        </div>
      )}

      {(jobIds.length === 0 || settled) && <>
      <ToggleGroup
        className="mt-4"
        value={[activePhase]}
        onValueChange={(v) => { if (v[0]) { setJobIds([]); setPhase(v[0]); } }}
        variant="outline"
        size="sm"
      >
        <ToggleGroupItem value="choose">Choose commitments</ToggleGroupItem>
        <ToggleGroupItem value="review">
          Review matches
          {pendingLinks.length > 0 && (
            <Badge variant="secondary" className="ml-1.5">
              {pendingLinks.length}
            </Badge>
          )}
        </ToggleGroupItem>
      </ToggleGroup>

      {activePhase === "choose" ? (
        <PickList
          commitments={searchable}
          links={links ?? []}
          onSearch={setJobIds}
        />
      ) : (
        <ReviewMatches pending={pendingLinks} commitments={searchable} />
      )}
      </>}
    </div>
  );
}

/* ---------- phase 1: choose commitments ---------------------------------- */

function PickList({
  commitments,
  links,
  onSearch,
}: {
  commitments: Commitment[];
  links: LinkView[];
  onSearch: (jobIds: string[]) => void;
}) {
  const { data: candidates } = useCandidates();
  const linkedIds = useMemo(
    () => new Set(links.map((l) => l.link.commitment_id)),
    [links],
  );
  const unsearched = commitments.filter((c) => !linkedIds.has(c.id));
  const groups = useMemo(
    () =>
      titleGroups(unsearched, (c) => c.title, (c) => c.kind).sort(
        (a, b) => KIND_ORDER.indexOf(a[0].kind) - KIND_ORDER.indexOf(b[0].kind),
      ),
    [unsearched],
  );
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [cursor, setCursor] = useState(0);
  const [requestedPage, setPage] = useQueryState("spage", parseAsInteger.withDefault(1));

  const search = useMutation({
    mutationFn: async (ids: number[]) => {
      const jobIds: string[] = [];
      for (const id of ids) {
        try {
          const job = await api.findEvidence(id);
          jobIds.push(job.id);
        } catch (error) {
          toast.error(`Could not start search: ${String(error)}`);
          break;
        }
      }
      return jobIds;
    },
    onSuccess: (jobIds) => {
      setSelected(new Set());
      onSearch(jobIds);
    },
    onError: (e) => toast.error(String(e)),
  });

  useHotkeys("j", () => !editable() && setCursor((c) => Math.min(c + 1, PAGE - 1)));
  useHotkeys("k", () => !editable() && setCursor((c) => Math.max(c - 1, 0)));

  if (!unsearched.length)
    return (
      <p className="mt-8 rounded-md border border-green-500/30 bg-green-500/5 p-6 font-medium text-green-700 dark:text-green-400">
        All commitments searched. Review the matches to continue.
      </p>
    );

  const pages = Math.max(1, Math.ceil(groups.length / PAGE));
  const page = Math.max(1, Math.min(requestedPage, pages));
  const pageGroups = groups.slice((page - 1) * PAGE, page * PAGE);
  const detail = pageGroups[Math.min(cursor, pageGroups.length - 1)] ?? null;
  const detailCandidates = detail
    ? [
        ...new Map(
          detail
            .map((c) => candidates?.find((x) => x.id === c.candidate_id))
            .filter((x): x is NonNullable<typeof x> => !!x)
            .map((c) => [c.id, c] as const),
        ).values(),
      ]
    : [];

  return (
    <div className="mt-4">
      <p className="text-xs text-muted-foreground">
        {groups.length} commitments available to search · Click a title to
        inspect; check a box to select.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSelected(new Set(groups.map((g) => g[0].id)))}
            >
              Select all not searched
            </Button>
            {selected.size > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelected(new Set())}
              >
                Clear
              </Button>
            )}
          </div>
          <Button
            className="mt-2"
            size="sm"
            disabled={!selected.size || search.isPending}
            onClick={() =>
              search.mutate(
                groups
                  .filter((g) => selected.has(g[0].id))
                  .flatMap((g) => g.map((c) => c.id)),
              )
            }
          >
            {search.isPending ? (
              <Loader2 className="mr-1 size-3.5 animate-spin" />
            ) : (
              <Search className="mr-1 size-3.5" />
            )}
            Find evidence for {selected.size} selected
          </Button>

          <div className="mt-3">
            <QueueList
              maxH="max-h-[55vh]"
              rows={pageGroups.map((g) => ({
                key: String(g[0].id),
                title: displayTitle(g[0].title),
                section: KIND_SECTION[g[0].kind] ?? g[0].kind,
                sectionIcon: KIND_ICON[g[0].kind],
                chips: [
                  {
                    label: KIND_LABEL[g[0].kind],
                    tone: KIND_TONE[g[0].kind],
                    icon: KIND_ICON[g[0].kind],
                  },
                  { label: "Not searched", tone: "gray" },
                ],
                meta: [
                  `p.${g[0].source_page}`,
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
          <Pager page={page} pages={pages} onPage={(p) => { setPage(p); setCursor(0); }} />
        </div>

        <div className="rounded-md border p-4">
          {detail && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold leading-snug">
                {displayTitle(detail[0].title)}
              </h2>
              <En text={displayTitle(detail[0].title)} />
              {detailCandidates.length > 0 ? (
                detailCandidates.map((c) => (
                  <blockquote
                    key={c.id}
                    className="border-l-2 pl-3 text-sm text-muted-foreground"
                  >
                    {c.source_excerpt}
                    <En text={c.source_excerpt} />
                  </blockquote>
                ))
              ) : (
                <blockquote className="border-l-2 pl-3 text-sm text-muted-foreground">
                  {detail[0].summary}
                </blockquote>
              )}
              {detail[0].deadline_year && (
                <p className="text-sm">
                  <span className="font-medium">Deadline</span> ·{" "}
                  {detail[0].deadline_year}
                </p>
              )}
              {detail[0].target_value != null && (
                <p className="text-sm">
                  <span className="font-medium">Target</span> ·{" "}
                  {detail[0].target_value} {detail[0].unit ?? ""}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- phase 2: review pending matches ------------------------------- */

function ReviewMatches({
  pending,
  commitments,
}: {
  pending: LinkView[];
  commitments: Commitment[];
}) {
  const invalidate = useInvalidateDomain();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [cursor, setCursor] = useState(0);
  const [relChoice, setRelChoice] = useState<Map<number, RelationshipType>>(
    new Map(),
  );
  const [requestedPage, setPage] = useQueryState("epage", parseAsInteger.withDefault(1));

  const comById = useMemo(
    () => new Map(commitments.map((c) => [c.id, c])),
    [commitments],
  );

  const orderedPending = useMemo(
    () =>
      [...pending].sort((a, b) => {
        const ta = displayTitle(
          comById.get(a.link.commitment_id)?.title ?? "",
        );
        const tb = displayTitle(
          comById.get(b.link.commitment_id)?.title ?? "",
        );
        return ta.localeCompare(tb) || b.link.score - a.link.score;
      }),
    [pending, comById],
  );

  const apply = useMutation({
    mutationFn: (accept: boolean) => {
      const ids = [...selected];
      const relationships = accept
        ? Object.fromEntries(
            ids
              .filter((id) => relChoice.has(id))
              .map((id) => [id, relChoice.get(id)!]),
          )
        : undefined;
      return api.bulkLinks(
        accept ? { accept: ids, relationships } : { reject: ids },
      );
    },
    onSuccess: (res, accept) => {
      toast.success(
        `${accept ? res.accepted : res.rejected} match(es) ${accept ? "confirmed" : "rejected"}.`,
      );
      setSelected(new Set());
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  const single = useMutation({
    mutationFn: async (accept: boolean) => {
      const link = detail?.link;
      if (!link) return;
      await api.decideLink(
        link.id,
        accept,
        accept ? relChoice.get(link.id) : undefined,
      );
    },
    onSuccess: (_r, accept) => {
      toast.success(accept ? "Match confirmed." : "Match rejected.");
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  const pages = Math.max(1, Math.ceil(orderedPending.length / PAGE));
  const page = Math.max(1, Math.min(requestedPage, pages));
  const pageItems = orderedPending.slice((page - 1) * PAGE, page * PAGE);
  const detail =
    pageItems[Math.min(cursor, Math.max(0, pageItems.length - 1))] ?? null;
  // rows are fetched lite; the inspector hydrates the selected link
  const detailQuery = useLink(detail?.link.id ?? null);
  const detailView = detailQuery.data ?? detail;

  useHotkeys("j", () => !editable() && setCursor((c) => Math.min(c + 1, pageItems.length - 1)), [pageItems.length]);
  useHotkeys("k", () => !editable() && setCursor((c) => Math.max(c - 1, 0)), []);
  useHotkeys("x", () => {
    if (editable() || !detail) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(detail.link.id)) next.delete(detail.link.id);
      else next.add(detail.link.id);
      return next;
    });
  }, [detail]);
  useHotkeys("c", () => !editable() && detail && single.mutate(true), [detail]);
  useHotkeys("r", () => !editable() && detail && single.mutate(false), [detail]);

  if (!pending.length)
    return (
      <div className="mt-8">
        <p className="font-medium text-green-700 dark:text-green-400">
          No matches waiting for review.
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Choose commitments to search for more evidence, or read the confirmed
          paper trail.
        </p>
      </div>
    );

  return (
    <div className="mt-4">
      <p className="text-xs text-muted-foreground">
        {pending.length} matches waiting for review · Inspect the source before
        confirming a relationship.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div>
          <BatchBar
            count={selected.size}
            busy={apply.isPending}
            onConfirm={() => apply.mutate(true)}
            onReject={() => apply.mutate(false)}
            onClear={() => setSelected(new Set())}
          />

          <div className="mt-3">
            <QueueList
              maxH="max-h-[55vh]"
              rows={pageItems.map((lv) => {
                const com = comById.get(lv.link.commitment_id);
                const rel = lv.link.suggested_relationship;
                return {
                  key: String(lv.link.id),
                  title: displayTitle(lv.evidence?.title),
                  section: `For · ${displayTitle(com?.title ?? "")}`,
                  chips: lv.evidence
                    ? [
                        {
                          label: STATUS_LABEL[lv.evidence.status_hint],
                          tone: STATUS_TONE[lv.evidence.status_hint],
                          icon: STATUS_ICON[lv.evidence.status_hint],
                        },
                        {
                          label: `suggested: ${REL_LABEL[rel]}`,
                          tone: REL_TONE[rel],
                          icon: REL_ICON[rel],
                        },
                      ]
                    : [],
                  meta: [
                    lv.evidence?.publisher ?? "Official source",
                    lv.evidence?.published_on ?? "Date unknown",
                  ],
                };
              })}
              activeKey={detail ? String(detail.link.id) : null}
              selected={new Set([...selected].map(String))}
              onInspect={(key) =>
                setCursor(
                  pageItems.findIndex((l) => String(l.link.id) === key),
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
            <Kbd>J</Kbd>/<Kbd>K</Kbd> move · <Kbd>X</Kbd> select ·{" "}
            <Kbd>C</Kbd> confirm · <Kbd>R</Kbd> reject
          </p>
          <Pager page={page} pages={pages} onPage={(p) => { setPage(p); setCursor(0); }} />
        </div>

        <div className="rounded-md border p-4">
          {detailView?.evidence && (
            <LinkInspector
              view={detailView as LinkView & { evidence: EvidenceItem }}
              commitment={comById.get(detail.link.commitment_id)}
              rel={
                relChoice.get(detail.link.id) ??
                detail.link.suggested_relationship
              }
              onRel={(r) =>
                setRelChoice((prev) => new Map(prev).set(detail.link.id, r))
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}

function LinkInspector({
  view,
  commitment,
  rel,
  onRel,
}: {
  view: LinkView & { evidence: EvidenceItem };
  commitment?: Commitment;
  rel: RelationshipType;
  onRel: (r: RelationshipType) => void;
}) {
  const ev = view.evidence;
  return (
    <div className="space-y-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Evidence inspector
      </p>
      <div>
        <h2 className="text-lg font-semibold leading-snug">
          {displayTitle(ev.title)}
        </h2>
        <En text={displayTitle(ev.title)} />
      </div>
      <p className="text-xs text-muted-foreground">
        {[
          ev.publisher ?? "Official source",
          ev.published_on ?? "Date unknown",
          evidenceKind(ev.url, ev.title),
        ].join(" · ")}
      </p>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Linked commitment
        </p>
        <p className="text-sm">{displayTitle(commitment?.title ?? "")}</p>
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Matched excerpt
        </p>
        <blockquote className="mt-1 max-h-56 overflow-y-auto border-l-2 pl-3 text-sm text-muted-foreground">
          {ev.snippet}
        </blockquote>
        <En text={ev.snippet} />
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          What this source reports
        </p>
        <div className="mt-1">
          <Chip
            label={STATUS_LABEL[ev.status_hint]}
            tone={STATUS_TONE[ev.status_hint]}
            icon={STATUS_ICON[ev.status_hint]}
          />
        </div>
        <p className="mt-1 text-sm">{STATUS_SENTENCE[ev.status_hint]}</p>
        {ev.status_excerpt && (
          <blockquote className="mt-1 border-l-2 pl-3 text-sm text-muted-foreground">
            {ev.status_excerpt}
          </blockquote>
        )}
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Why Paper Trail matched it
        </p>
        <p className="text-xs text-muted-foreground">
          {view.link.reasons.length
            ? view.link.reasons.join("; ")
            : "No matching explanation stored."}
        </p>
      </div>

      {view.budgets.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Money mentioned:{" "}
          {view.budgets
            .slice(0, 4)
            .map((b) => `${huf(b.amount_huf)} (${BUDGET_LABEL[b.kind]})`)
            .join(" · ")}
        </p>
      )}

      <Button
        variant="outline"
        size="sm"
        nativeButton={false}
        render={
          <a href={ev.url} target="_blank" rel="noopener noreferrer" />
        }
      >
        <ExternalLink className="mr-1 size-3.5" /> Read official source
      </Button>

      <div className="space-y-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Relationship
        </p>
        <Select
          value={rel}
          onValueChange={(v) => onRel(v as RelationshipType)}
          items={REL_LABEL}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(REL_LABEL).map(([k, l]) => {
              const Icon = REL_ICON[k as RelationshipType];
              return (
                <SelectItem key={k} value={k}>
                  <span className="flex items-center gap-1.5">
                    <Icon className="size-3.5" />
                    {l}
                  </span>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        <div className="mt-1">
          <Chip label={REL_LABEL[rel]} tone={REL_TONE[rel]} icon={REL_ICON[rel]} />
        </div>
        <p className="text-xs text-muted-foreground">{REL_HELP[rel]}</p>
        <p className="text-xs text-muted-foreground">
          Applied when you confirm this selected match.
        </p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <EvidencePage />
    </Suspense>
  );
}
