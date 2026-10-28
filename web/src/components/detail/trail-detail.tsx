"use client";

import { Fragment, type ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import { En } from "@/components/en";
import { Chip } from "@/components/chip";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { STATUS_ICON, STATUS_TONE, TONE_TEXT, type Tone } from "@/lib/tones";
import { type Commitment, type EvidenceItem, type TrailRow } from "@/lib/api";
import { BUDGET_LABEL, KIND_LABEL, STATUS_LABEL, displayTitle, huf } from "@/lib/labels";
import { cn } from "@/lib/utils";


const measurable = (c: Commitment) =>
  c.target_value != null && c.unit != null;

const MAX_BUDGET_LINES = 6;

export function TrailDetail({
  row,
  mentions,
  group,
  mentionValue,
  onMention,
  promise,
  docUrl,
}: {
  row: TrailRow;
  mentions: number;
  group: TrailRow[];
  mentionValue?: number;
  onMention: (id: number) => void;
  promise?: string | null;
  docUrl?: string | null;
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
  const unrelated = byRel.get("probably_unrelated") ?? [];

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
          items={Object.fromEntries(
            group.map((r) => [
              String(r.commitment.id),
              `p.${r.commitment.source_page} · ${r.evidence.length} evidence source${r.evidence.length === 1 ? "" : "s"} · mention ${r.commitment.id}`,
            ]),
          )}
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
          com.source_page
            ? docUrl ? (
                <a
                  href={`${docUrl.split("#")[0]}#page=${com.source_page}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-2 hover:text-foreground"
                >
                  Strategy · p.{com.source_page}
                </a>
              ) : (
                `Strategy · p.${com.source_page}`
              )
            : null,
          com.deadline_year ? `Deadline ${com.deadline_year}` : null,
          measurable(com)
            ? `Target ${com.target_value} ${com.unit}`
            : null,
          com.responsible_org ? `who: ${com.responsible_org}` : null,
          mentions > 1 ? `${mentions} source mentions` : null,
        ]
          .filter(Boolean)
          .map((part, i) => (
            <Fragment key={i}>
              {i > 0 ? " · " : ""}
              {part}
            </Fragment>
          ))}
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

      {unrelated.length > 0 && (
        <div>
          <SectionLabel tone="gray">Probably unrelated</SectionLabel>
          {unrelated.map((ev) => (
            <EvidenceLine key={ev.id} ev={ev} />
          ))}
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

export function Timeline({
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
