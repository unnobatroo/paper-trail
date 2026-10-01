"use client";

/** Shared triage primitives — the list/inspector pattern both review
 * steps use. Items are grouped display rows; selection is per group. */

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { TONE_CHIP, type Tone } from "@/lib/tones";
import type { LucideIcon } from "lucide-react";
import { Check, X } from "lucide-react";
import type { ReactNode } from "react";

export interface RowChip {
  label: string;
  tone: Tone;
  icon?: LucideIcon;
}

export interface QueueRow {
  key: string;
  title: string;
  meta: string[];
  sub?: string;
  /** Section header rendered once when it changes — order rows so
   * same-section rows are contiguous. */
  section?: string;
  sectionIcon?: LucideIcon;
  chips?: RowChip[];
}

export function Chip({ label, tone, icon: Icon }: RowChip) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-px text-[10px] font-medium leading-4",
        TONE_CHIP[tone],
      )}
    >
      {Icon && <Icon className="size-3" />}
      {label}
    </span>
  );
}

export function QueueList({
  rows,
  activeKey,
  selected,
  onInspect,
  onToggle,
  onToggleAll,
  maxH = "max-h-[60vh]",
}: {
  rows: QueueRow[];
  activeKey?: string | null;
  selected?: Set<string>;
  onInspect: (key: string) => void;
  onToggle?: (key: string, on: boolean) => void;
  /** When set, a header row offers a select-all/none checkbox for the
   * rows currently shown. */
  onToggleAll?: (keys: string[], on: boolean) => void;
  maxH?: string;
}) {
  const keys = rows.map((r) => r.key);
  const chosen = keys.filter((k) => selected?.has(k));
  const all = keys.length > 0 && chosen.length === keys.length;
  const some = chosen.length > 0 && !all;

  return (
    <div className={cn("overflow-y-auto rounded-md border", maxH)}>
      {onToggleAll && rows.length > 0 && (
        <label className="flex cursor-pointer items-center gap-2 border-b bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/60">
          <Checkbox
            checked={all}
            indeterminate={some}
            onCheckedChange={() => onToggleAll(keys, !all)}
            aria-label={all ? "Deselect all" : "Select all"}
          />
          {all
            ? `${chosen.length} selected — click to clear`
            : some
              ? `${chosen.length} of ${keys.length} selected`
              : "Select all"}
        </label>
      )}
      <div className="divide-y">
        {rows.map((r, i) => {
          const header =
            r.section !== undefined &&
            (i === 0 || rows[i - 1].section !== r.section) ? (
              <SectionHeader
                label={r.section}
                icon={r.sectionIcon}
              />
            ) : null;
          return (
            <div key={r.key}>
              {header}
              <div
                className={cn(
                  "flex gap-3 border-l-2 border-transparent px-3 py-2.5",
                  activeKey === r.key && "border-l-primary bg-primary/5",
                )}
              >
                {onToggle && (
                  <Checkbox
                    className="mt-1"
                    checked={selected?.has(r.key) ?? false}
                    onCheckedChange={(v) => onToggle(r.key, !!v)}
                    aria-label={`Select ${r.title}`}
                  />
                )}
                <Button
                  variant="ghost"
                  className="block h-auto min-w-0 flex-1 whitespace-normal rounded-sm p-0 text-left hover:bg-transparent"
                  onClick={() => onInspect(r.key)}
                >
                  <span className="block truncate text-sm font-medium hover:underline">
                    {r.title}
                  </span>
                  {r.sub && (
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {r.sub}
                    </span>
                  )}
                  {r.chips && r.chips.length > 0 && (
                    <span className="mt-1 flex flex-wrap gap-1">
                      {r.chips.map((c, i) => (
                        <Chip key={i} {...c} />
                      ))}
                    </span>
                  )}
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {r.meta.join(" · ")}
                  </span>
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SectionHeader({
  label,
  icon: Icon,
}: {
  label: string;
  icon?: LucideIcon;
}) {
  return (
    <div className="flex items-center gap-1.5 border-b bg-muted/30 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
      {Icon && <Icon className="size-3.5 shrink-0" />}
      <span className="min-w-0 truncate" title={label}>{label}</span>
    </div>
  );
}

export function Pager({
  page,
  pages,
  onPage,
}: {
  page: number;
  pages: number;
  onPage: (p: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <nav aria-label="Review pages" className="mt-3 flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span className="text-xs text-muted-foreground" aria-live="polite">Page {page} of {pages}</span>
      <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </nav>
  );
}

export function BatchBar({
  count,
  onConfirm,
  onReject,
  onClear,
  busy,
  confirmLabel = "Confirm selected",
  rejectLabel = "Reject selected",
}: {
  count: number;
  onConfirm: () => void;
  onReject: () => void;
  onClear?: () => void;
  busy?: boolean;
  confirmLabel?: string;
  rejectLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">{count} selected</span>
      <Button size="sm"
        disabled={!count || busy}
        onClick={onConfirm}
      >
        <Check className="size-3.5" />
        {confirmLabel}
      </Button>
      <Button size="sm" variant="destructive"
        disabled={!count || busy}
        onClick={onReject}
      >
        <X className="size-3.5" />
        {rejectLabel}
      </Button>
      {count > 0 && onClear && (
        <Button size="sm" variant="ghost"
          onClick={onClear}
        >
          Clear
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-md border border-dashed p-6 text-sm text-muted-foreground",
        className,
      )}
    >
      {children}
    </div>
  );
}
