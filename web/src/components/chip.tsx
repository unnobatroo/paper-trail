import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TONE_CHIP, type Tone } from "@/lib/tones";

export interface RowChip {
  label: string;
  tone: Tone;
  icon?: LucideIcon;
}

export function Chip({ label, tone, icon: Icon }: RowChip) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-px text-[11px] font-medium leading-4",
        TONE_CHIP[tone],
      )}
    >
      {Icon && <Icon className="size-3" />}
      {label}
    </span>
  );
}

export function EmptyState({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground", className)}>
      {children}
    </div>
  );
}
