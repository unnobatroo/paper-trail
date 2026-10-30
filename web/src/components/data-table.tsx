"use client";

import {type ReactNode, useEffect, useRef} from "react";
import type {LucideIcon} from "lucide-react";
import {ChevronDown, ChevronRight} from "lucide-react";
import {useHotkeys} from "react-hotkeys-hook";
import {type ColumnDef, type RowData, tableFeatures, useTable,} from "@tanstack/react-table";
import {Checkbox} from "@/components/ui/checkbox";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {cn} from "@/lib/utils";

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

// j/k move, enter opens, x selects, c/r decide
// react-hotkeys-hook skips form fields by default
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
    // rows have to come in grouped, collapsed groups only keep their header
    groupOf?: (row: T) => RowGroup;
    collapsed?: Set<string>;
    onToggleGroup?: (key: string) => void;
    // column id -> classes, e.g. "hidden lg:table-cell" hides it on small screens
    colClass?: Record<string, string>;
}) {
    const table = useTable({features, columns, data, getRowId: getId});
    const rows = table.getRowModel().rows;
    const activeRef = useRef<HTMLTableRowElement>(null);

    // keep the cursor row in view while j/k walks
    useEffect(() => {
        activeRef.current?.scrollIntoView({block: "nearest"});
    }, [cursor]);

    const ids = rows
        .filter((r) => !(groupOf && collapsed?.has(groupOf(r.original).key)))
        .map((r) => r.id);
    const chosen = ids.filter((id) => selected?.has(id)).length;
    const all = ids.length > 0 && chosen === ids.length;

    // plain loop so the group/cursor counters stay local
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
                    <TableRow key={`g-${g.key}`} className="bg-muted/40 hover:bg-muted/40">
                        <TableCell colSpan={span} className="py-1.5">
                            <button
                                type="button"
                                onClick={() => onToggleGroup?.(g.key)}
                                aria-expanded={!shut}
                                className="flex w-full items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground"
                            >
                                {shut ? <ChevronRight className="size-3.5"/> : <ChevronDown className="size-3.5"/>}
                                {g.icon && <g.icon className="size-3.5"/>}
                                {g.label}
                                <span
                                    className="rounded-full bg-background px-1.5 font-normal tabular-nums">{counts.get(g.key)}</span>
                            </button>
                        </TableCell>
                    </TableRow>,
                );
            }
            if (shut) continue;
            visibleIndex += 1;
            const i = visibleIndex;
            const active = i === cursor;
            out.push(
                <TableRow
                    key={row.id}
                    ref={active ? activeRef : undefined}
                    tabIndex={active ? 0 : -1}
                    data-state={selected?.has(row.id) ? "selected" : undefined}
                    onKeyDown={(e) => {
                        // not for keys bubbling up from the row checkbox
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
                        "cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                        active && "bg-accent hover:bg-accent",
                    )}
                >
                    {onToggle && (
                        <TableCell className="w-10" onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                                checked={selected?.has(row.id) ?? false}
                                onCheckedChange={() => onToggle(row.id)}
                                aria-label="Select row"
                            />
                        </TableCell>
                    )}
                    {row.getAllCells().map((cell) => (
                        <TableCell key={cell.id} className={colClass?.[cell.column.id]}>
                            <table.FlexRender cell={cell}/>
                        </TableCell>
                    ))}
                </TableRow>,
            );
        }
        return out;
    }

    return (
        <div className="rounded-lg border bg-card">
            <Table>
                <TableHeader className="sticky top-0 z-10 bg-muted/60 backdrop-blur">
                    {table.getHeaderGroups().map((group) => (
                        <TableRow key={group.id} className="hover:bg-transparent">
                            {onToggle && (
                                <TableHead className="w-10">
                                    <Checkbox
                                        checked={all}
                                        indeterminate={chosen > 0 && !all}
                                        onCheckedChange={() => onToggleAll?.(!all)}
                                        aria-label={all ? "Deselect all" : "Select all"}
                                    />
                                </TableHead>
                            )}
                            {group.headers.map((header) => (
                                <TableHead
                                    key={header.id}
                                    className={colClass?.[header.column.id]}
                                >
                                    {header.isPlaceholder ? null : (
                                        <table.FlexRender header={header}/>
                                    )}
                                </TableHead>
                            ))}
                        </TableRow>
                    ))}
                </TableHeader>
                <TableBody>
                    {renderBody()}
                </TableBody>
            </Table>
        </div>
    );
}
