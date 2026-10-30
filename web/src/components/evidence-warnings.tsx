"use client";

import {AlertTriangle, Ban, FileText, Wrench} from "lucide-react";
import {Chip} from "@/components/chip";
import type {EvidenceFlag, EvidenceItem} from "@/lib/api";
import {FLAG_HELP, FLAG_LABEL, POLARITY_LABEL} from "@/lib/labels";

const FLAG_ICON = {regression_warning: AlertTriangle, maintenance_only_suspect: Wrench} as const;

// stuff a reviewer must see before trusting a passage, none of it decides anything
export function EvidenceWarnings({ev, explain = false}: { ev: EvidenceItem; explain?: boolean }) {
    const flags = (ev.flags ?? []) as EvidenceFlag[];
    const polarity = ev.polarity && ev.polarity !== "affirmative" ? ev.polarity : null;
    const ids = ev.procurement_ids ?? [];
    if (!flags.length && !polarity && !ids.length) return null;
    return (
        <div className="space-y-1">
            <div className="flex flex-wrap gap-1">
                {polarity && <Chip label={POLARITY_LABEL[polarity]} tone="red" icon={Ban}/>}
                {flags.map((f) => (
                    <Chip key={f} label={FLAG_LABEL[f]}
                          tone={f === "regression_warning" ? "red" : "amber"} icon={FLAG_ICON[f]}/>
                ))}
                {ids.map((id) => <Chip key={id} label={id} tone="gray" icon={FileText}/>)}
            </div>
            {explain && flags.map((f) => (
                <p key={f} className="text-xs text-muted-foreground">{FLAG_HELP[f]}</p>
            ))}
        </div>
    );
}
