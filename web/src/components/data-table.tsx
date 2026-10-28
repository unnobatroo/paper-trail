"use client";

import { useEffect, useRef, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useHotkeys } from "react-hotkeys-hook";
import {
  tableFeatures,
  useTable,
  type ColumnDef,
  type RowData,
} from "@tanstack/react-table";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

const features = tableFeatures({});
export type Columns<T extends RowData> = ColumnDef<typeof features, T>[];

export interface RowGroup {
  key: string;
  label: string;
  icon?: LucideIcon;
}

export interface RowKeys {
  onOpen?: () => void;
  onToggle?: () => void;
  onAccept?: () => void;
  onReject?: () => void;
}

// j/k move the cursor, enter opens, x selects, c/r decide.
// react-hotkeys-hook ignores form fields by default
export function useRowKeys(
  count: number,
  cursor: number,
  setCursor: (n: number) => void,
  keys: RowKeys,
) {
  const move = (d: number) =>
    setCursor(Math.max(0, Math.min(count - 1, cursor + d)));
  useHotkeys("j", () => move(1), [count, cursor]);
  useHotkeys("k", () => move(-1), [count, cursor]);
  useHotkeys("enter", () => keys.onOpen?.(), [keys.onOpen]);
  useHotkeys("x", () => keys.onToggle?.(), [keys.onToggle]);
  useHotkeys("c", () => keys.onAccept?.(), [keys.onAccept]);
  useHotkeys("r", () => keys.onReject?.(), [keys.onReject]);
}

export function DataTable<T extends RowData>({
  columns,
  data,
  getId,
  cursor,
  onCursor,
  onOpen,
  selected,
  onToggle,
  onToggleAll,
  groupOf,
  collapsed,
  onToggleGroup,
  colClass,
}: {
  columns: Columns<T>;
  data: T[];
  getId: (row: T) => string;
  cursor: number;
  onCursor: (i: number) => void;
  onOpen: (row: T) => void;
  selected?: Set<string>;
  onToggle?: (id: string) => void;
  onToggleAll?: (on: boolean) => void;
  // rows must arrive ordered by group, collapsed groups keep their header only
  groupOf?: (row: T) => RowGroup;
  collapsed?: Set<string>;
  onToggleGroup?: (key: string) => void;
  // column id -> classes, e.g. "hidden lg:table-cell" to drop a column on small screens
  colClass?: Record<string, string>;
}) {
  const table = useTable({ features, columns, data, getRowId: getId });
  const rows = table.getRowModel().rows;
  const activeRef = useRef<HTMLTableRowElement>(null);

  // keep the cursor row visible while j/k walks the list
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  const ids = rows
    .filter((r) => !(groupOf && collapsed?.has(groupOf(r.original).key)))
    .map((r) => r.id);
  const chosen = ids.filter((id) => selected?.has(id)).length;
  const all = ids.length > 0 && chosen === ids.length;

  // plain loop so the group/cursor counters stay local to this function
  function renderBody() {
    const counts = new Map<string, number>();
    if (groupOf)
      for (const r of rows) {
        const k = groupOf(r.original).key;
        counts.set(k, (counts.get(k) ?? 0) + 1);
      }
    const out: ReactNode[] = [];
    let lastGroup = "";
    let visibleIndex = -1;
    const span = columns.length + (onToggle ? 1 : 0);
    for (const row of rows) {
      const g = groupOf?.(row.original);
      const shut = g ? (collapsed?.has(g.key) ?? false) : false;
      if (g && g.key !== lastGroup) {
        lastGroup = g.key;
        out.push(
          <tr key={`g-${g.key}`} className="border-b bg-muted/40">
            <td colSpan={span} className="px-3 py-1.5">
              <button
                type="button"
                onClick={() => onToggleGroup?.(g.key)}
                aria-expanded={!shut}
                className="flex w-full items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                {shut ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                {g.icon && <g.icon className="size-3.5" />}
                {g.label}
                <span className="rounded-full bg-background px-1.5 font-normal tabular-nums">{counts.get(g.key)}</span>
              </button>
            </td>
          </tr>,
        );
      }
      if (shut) continue;
      visibleIndex += 1;
      const i = visibleIndex;
      const active = i === cursor;
      out.push(
        <tr
          key={row.id}
          ref={active ? activeRef : undefined}
          tabIndex={active ? 0 : -1}
          onKeyDown={(e) => {
            // not for keys that bubble up from the row's checkbox
            if (e.key === "Enter" && e.target === e.currentTarget) {
              e.preventDefault();
              onOpen(row.original);
            }
          }}
          onClick={() => {
            onCursor(i);
            onOpen(row.original);
          }}
          className={cn(
            "cursor-pointer border-b last:border-0 transition-colors hover:bg-muted/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
            active && "bg-accent hover:bg-accent",
          )}
        >
          {onToggle && (
            <td className="w-10 px-3 py-2" onClick={(e) => e.stopPropagation()}>
              <Checkbox
                checked={selected?.has(row.id) ?? false}
                onCheckedChange={() => onToggle(row.id)}
                aria-label="Select row"
              />
            </td>
          )}
          {row.getAllCells().map((cell) => (
            <td key={cell.id} className={cn("px-3 py-2 align-top", colClass?.[cell.column.id])}>
              <table.FlexRender cell={cell} />
            </td>
          ))}
        </tr>,
      );
    }
    return out;
  }

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-muted/60 backdrop-blur">
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id} className="border-b">
              {onToggle && (
                <th className="w-10 px-3 py-2">
                  <Checkbox
                    checked={all}
                    indeterminate={chosen > 0 && !all}
                    onCheckedChange={() => onToggleAll?.(!all)}
                    aria-label={all ? "Deselect all" : "Select all"}
                  />
                </th>
              )}
              {group.headers.map((header) => (
                <th
                  key={header.id}
                  className={cn("px-3 py-2 text-left text-xs font-medium text-muted-foreground", colClass?.[header.column.id])}
                >
                  {header.isPlaceholder ? null : (
                    <table.FlexRender header={header} />
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {renderBody()}
        </tbody>
      </table>
    </div>
  );
}
