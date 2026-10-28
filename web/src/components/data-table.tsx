"use client";

import { useEffect, useRef } from "react";
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
}) {
  const table = useTable({ features, columns, data, getRowId: getId });
  const rows = table.getRowModel().rows;
  const activeRef = useRef<HTMLTableRowElement>(null);

  // keep the cursor row visible while j/k walks the list
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  const ids = rows.map((r) => r.id);
  const chosen = ids.filter((id) => selected?.has(id)).length;
  const all = ids.length > 0 && chosen === ids.length;

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
                  className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
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
          {rows.map((row, i) => {
            const active = i === cursor;
            return (
              <tr
                key={row.id}
                ref={active ? activeRef : undefined}
                onClick={() => {
                  onCursor(i);
                  onOpen(row.original);
                }}
                className={cn(
                  "cursor-pointer border-b last:border-0 transition-colors hover:bg-muted/40",
                  active && "bg-accent hover:bg-accent",
                )}
              >
                {onToggle && (
                  <td
                    className="w-10 px-3 py-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={selected?.has(row.id) ?? false}
                      onCheckedChange={() => onToggle(row.id)}
                      aria-label="Select row"
                    />
                  </td>
                )}
                {row.getAllCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 align-top">
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
