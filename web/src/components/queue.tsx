"use client";

/** Shared triage primitives — the list/inspector pattern both review
 * steps use. Items are grouped display rows; selection is per group. */

import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface QueueRow {
  key: string;
  title: string;
  meta: string[];
  sub?: string;
}

export function QueueList({
  rows,
  activeKey,
  selected,
  onInspect,
  onToggle,
  maxH = "max-h-[60vh]",
}: {
  rows: QueueRow[];
  activeKey?: string | null;
  selected?: Set<string>;
  onInspect: (key: string) => void;
  onToggle?: (key: string, on: boolean) => void;
  maxH?: string;
}) {
  return (
    <div className={cn("divide-y overflow-y-auto rounded-md border", maxH)}>
      {rows.map((r) => (
        <div
          key={r.key}
          className={cn(
            "flex gap-3 px-3 py-2.5",
            activeKey === r.key && "bg-primary/5",
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
          <button
            className="min-w-0 flex-1 text-left"
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
            <span className="mt-0.5 block text-xs text-muted-foreground">
              {r.meta.join(" · ")}
            </span>
          </button>
        </div>
      ))}
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
    <div className="mt-2 flex gap-1">
      {Array.from({ length: pages }, (_, i) => (
        <button
          key={i}
          onClick={() => onPage(i + 1)}
          className={cn(
            "size-7 rounded-md border text-xs",
            page === i + 1
              ? "border-primary bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted",
          )}
        >
          {i + 1}
        </button>
      ))}
    </div>
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
      <button
        className="inline-flex h-7 items-center gap-1.5 rounded-md bg-primary px-2.5 text-[0.8rem] font-medium text-primary-foreground disabled:opacity-50"
        disabled={!count || busy}
        onClick={onConfirm}
      >
        {confirmLabel}
      </button>
      <button
        className="inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-[0.8rem] font-medium disabled:opacity-50"
        disabled={!count || busy}
        onClick={onReject}
      >
        {rejectLabel}
      </button>
      {count > 0 && onClear && (
        <button
          className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          onClick={onClear}
        >
          Clear
        </button>
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
