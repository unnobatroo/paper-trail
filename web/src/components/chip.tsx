import type {LucideIcon} from "lucide-react";
import type {ReactNode} from "react";
import {Badge} from "@/components/ui/badge";
import {cn} from "@/lib/utils";
import {type Tone, TONE_CHIP} from "@/lib/tones";

export interface RowChip {
    label: string;
    tone: Tone;
    icon?: LucideIcon;
}

export function Chip({label, tone, icon: Icon}: RowChip) {
    return (
        <Badge
            variant="outline"
            className={cn(
                "h-auto rounded-md px-1.5 py-px text-[11px] leading-4",
                TONE_CHIP[tone],
            )}
        >
            {Icon && <Icon className="size-3"/>}
            {label}
        </Badge>
    );
}

export function EmptyState({children, className}: { children: ReactNode; className?: string }) {
    return (
        <div className={cn("rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground", className)}>
            {children}
        </div>
    );
}
