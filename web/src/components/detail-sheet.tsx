"use client";

import type {ReactNode} from "react";
import {Sheet, SheetContent, SheetDescription, SheetTitle} from "@/components/ui/sheet";

// slide-over for one row, the table stays visible behind it
export function DetailSheet({
                                open,
                                onClose,
                                label,
                                children,
                            }: {
    open: boolean;
    onClose: () => void;
    label: string;
    children: ReactNode;
}) {
    return (
        <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
            <SheetContent className="overflow-y-auto p-5 data-[side=right]:w-full sm:data-[side=right]:max-w-xl">
                <SheetTitle className="sr-only">{label}</SheetTitle>
                <SheetDescription className="sr-only">{label}</SheetDescription>
                {children}
            </SheetContent>
        </Sheet>
    );
}
