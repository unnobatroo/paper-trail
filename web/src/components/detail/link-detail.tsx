"use client";

import {ExternalLink} from "lucide-react";
import {En} from "@/components/en";
import {Chip} from "@/components/chip";
import {Button} from "@/components/ui/button";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {REL_ICON, REL_TONE, STATUS_ICON, STATUS_TONE} from "@/lib/tones";
import {type Commitment, type EvidenceItem, type LinkView, type RelationshipType} from "@/lib/api";
import {
    BUDGET_LABEL,
    displayTitle,
    evidenceKind,
    huf,
    REL_HELP,
    REL_LABEL,
    STATUS_LABEL,
    STATUS_SENTENCE
} from "@/lib/labels";

export function LinkDetail({
                               view,
                               commitment,
                               rel,
                               onRel,
                           }: {
    view: LinkView & { evidence: EvidenceItem };
    commitment?: Commitment;
    rel: RelationshipType;
    onRel: (r: RelationshipType) => void;
}) {
    const ev = view.evidence;
    return (
        <div className="space-y-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Evidence inspector
            </p>
            <div>
                <h2 className="text-lg font-semibold leading-snug">
                    {displayTitle(ev.title)}
                </h2>
                <En text={displayTitle(ev.title)}/>
            </div>
            <p className="text-xs text-muted-foreground">
                {[
                    ev.publisher ?? "Official source",
                    ev.published_on ?? "Date unknown",
                    evidenceKind(ev.url, ev.title),
                ].join(" · ")}
            </p>

            <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Linked commitment
                </p>
                <p className="text-sm">{displayTitle(commitment?.title ?? "")}</p>
            </div>

            <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Matched excerpt
                </p>
                <blockquote className="mt-1 max-h-56 overflow-y-auto border-l-2 pl-3 text-sm text-muted-foreground">
                    {ev.snippet}
                </blockquote>
                <En text={ev.snippet}/>
            </div>

            <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    What this source reports
                </p>
                <div className="mt-1">
                    <Chip
                        label={STATUS_LABEL[ev.status_hint]}
                        tone={STATUS_TONE[ev.status_hint]}
                        icon={STATUS_ICON[ev.status_hint]}
                    />
                </div>
                <p className="mt-1 text-sm">{STATUS_SENTENCE[ev.status_hint]}</p>
                {ev.status_excerpt && (
                    <blockquote className="mt-1 border-l-2 pl-3 text-sm text-muted-foreground">
                        {ev.status_excerpt}
                    </blockquote>
                )}
            </div>

            <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Why Paper Trail matched it
                </p>
                <p className="text-xs text-muted-foreground">
                    {view.link.reasons.length
                        ? view.link.reasons.join("; ")
                        : "No matching explanation stored."}
                </p>
            </div>

            {view.budgets.length > 0 && (
                <p className="text-xs text-muted-foreground">
                    Money mentioned:{" "}
                    {view.budgets
                        .slice(0, 4)
                        .map((b) => `${huf(b.amount_huf)} (${BUDGET_LABEL[b.kind]})`)
                        .join(" · ")}
                </p>
            )}

            <Button
                variant="outline"
                size="sm"
                nativeButton={false}
                render={
                    <a href={ev.url} target="_blank" rel="noopener noreferrer"/>
                }
            >
                <ExternalLink className="mr-1 size-3.5"/> Read official source
            </Button>

            <div className="space-y-1.5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Relationship
                </p>
                <Select
                    value={rel}
                    onValueChange={(v) => onRel(v as RelationshipType)}
                    items={REL_LABEL}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue/>
                    </SelectTrigger>
                    <SelectContent>
                        {Object.entries(REL_LABEL).map(([k, l]) => {
                            const Icon = REL_ICON[k as RelationshipType];
                            return (
                                <SelectItem key={k} value={k}>
                  <span className="flex items-center gap-1.5">
                    <Icon className="size-3.5"/>
                      {l}
                  </span>
                                </SelectItem>
                            );
                        })}
                    </SelectContent>
                </Select>
                <div className="mt-1">
                    <Chip label={REL_LABEL[rel]} tone={REL_TONE[rel]} icon={REL_ICON[rel]}/>
                </div>
                <p className="text-xs text-muted-foreground">{REL_HELP[rel]}</p>
                <p className="text-xs text-muted-foreground">
                    Applied when you confirm this selected match.
                </p>
            </div>
        </div>
    );
}
