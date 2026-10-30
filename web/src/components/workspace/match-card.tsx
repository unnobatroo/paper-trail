"use client";

import {useState} from "react";
import {toast} from "sonner";
import {useMutation} from "@tanstack/react-query";
import {Check, ChevronDown, ChevronUp, ExternalLink, X} from "lucide-react";
import {Chip} from "@/components/chip";
import {EvidenceWarnings} from "@/components/evidence-warnings";
import {LinkDetail} from "@/components/detail/link-detail";
import {Button} from "@/components/ui/button";
import {Collapsible, CollapsibleContent, CollapsibleTrigger} from "@/components/ui/collapsible";
import {api, type Commitment, errorMessage, type EvidenceItem, type LinkView, type RelationshipType,} from "@/lib/api";
import {useInvalidateDomain, useLink} from "@/lib/hooks";
import {displayTitle, evidenceKind, REL_LABEL, STATUS_LABEL} from "@/lib/labels";
import {REL_ICON, REL_TONE, STATUS_ICON, STATUS_TONE} from "@/lib/tones";

type Full = LinkView & { evidence: EvidenceItem };

// one suggested match: skim, decide right here, or open the full record
export function MatchCard({view, commitment}: { view: Full; commitment?: Commitment }) {
    const invalidate = useInvalidateDomain();
    const [open, setOpen] = useState(false);
    const [rel, setRel] = useState<RelationshipType>(view.link.suggested_relationship);
    // the list comes lite (no snippet, no budgets), each card loads its own full record
    const full = useLink(view.link.id);
    const detail = (full.data ?? view) as Full;
    const ev = detail.evidence;

    const decide = useMutation({
        mutationFn: (accept: boolean) => api.decideLink(view.link.id, accept, accept ? rel : undefined),
        onSuccess: (_r, accept) => {
            toast.success(accept ? "Match confirmed." : "Match rejected.");
            invalidate();
        },
        onError: (e) => toast.error(errorMessage(e)),
    });

    return (
        <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border bg-background">
            <div className="space-y-2 p-3">
                <div className="flex items-start justify-between gap-2">
                    <p className="line-clamp-2 text-sm font-medium leading-snug">{displayTitle(ev.title)}</p>
                    <span
                        className="shrink-0 text-xs tabular-nums text-muted-foreground">{view.link.score.toFixed(2)}</span>
                </div>
                <EvidenceWarnings ev={ev}/>
                <p className="text-xs text-muted-foreground">
                    {[ev.publisher ?? "Official source", ev.published_on, evidenceKind(ev.url, ev.title)].filter(Boolean).join(" · ")}
                </p>
                <div className="flex flex-wrap gap-1">
                    <Chip label={STATUS_LABEL[ev.status_hint]} tone={STATUS_TONE[ev.status_hint]}
                          icon={STATUS_ICON[ev.status_hint]}/>
                    <Chip label={REL_LABEL[rel]} tone={REL_TONE[rel]} icon={REL_ICON[rel]}/>
                </div>
                <p className="line-clamp-3 border-l-2 pl-2 text-xs text-muted-foreground">{ev.snippet}</p>
            </div>

            <div className="flex items-center gap-1 border-t bg-muted/30 px-2 py-1.5">
                <div className="flex">
                    <Button size="sm" className="rounded-r-none" disabled={decide.isPending}
                            onClick={() => decide.mutate(true)}>
                        <Check className="size-3.5"/> Confirm
                    </Button>
                    <Button
                        size="sm"
                        variant="outline"
                        className="rounded-l-none border-l-0"
                        disabled={decide.isPending}
                        onClick={() => decide.mutate(false)}
                    >
                        <X className="size-3.5"/> Reject
                    </Button>
                </div>
                <Button
                    size="icon-sm"
                    variant="ghost"
                    className="ml-auto"
                    nativeButton={false}
                    render={<a href={ev.url} target="_blank" rel="noopener noreferrer" aria-label="Read official source"
                               title="Read official source"/>}
                >
                    <ExternalLink className="size-3.5"/>
                </Button>
                <CollapsibleTrigger render={<Button size="sm" variant="ghost"/>}>
                    {open ? <ChevronUp className="size-3.5"/> : <ChevronDown className="size-3.5"/>}
                    Details
                </CollapsibleTrigger>
            </div>

            <CollapsibleContent className="border-t p-3">
                <LinkDetail view={detail} commitment={commitment} rel={rel} onRel={setRel}/>
            </CollapsibleContent>
        </Collapsible>
    );
}
