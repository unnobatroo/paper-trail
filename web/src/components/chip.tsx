import type {LucideIcon} from "lucide-react";
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
