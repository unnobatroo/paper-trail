"use client";

import {useState} from "react";
import {FileText, ListChecks, Loader2, Route, Search} from "lucide-react";
import {Chip} from "@/components/chip";
import {CandidateDetail} from "@/components/detail/candidate-detail";
import {TrailDetail} from "@/components/detail/trail-detail";
import {Bi, CodeHint} from "@/components/en";
import {MatchCard} from "@/components/workspace/match-card";
import {Section} from "@/components/workspace/section";
import {Button} from "@/components/ui/button";
import type {Commitment, EvidenceItem, LinkView} from "@/lib/api";
import {displayTitle, KIND_LABEL} from "@/lib/labels";
import {KIND_ICON, KIND_TONE} from "@/lib/tones";
import {STAGES, type WorkRow} from "@/lib/workspace";

export function WorkDetail({
                               row,
                               commitments,
                               documents,
                               mentionId,
                               onMention,
                               onSearch,
                               searching,
                           }: {
    row: WorkRow;
    commitments: Commitment[];
    documents: { id: number; url: string | null }[];
    mentionId: number;
    onMention: (id: number) => void;
    onSearch: (commitmentIds: number[]) => void;
    searching: boolean;
}) {
    const [trailSel, setTrailSel] = useState<number | undefined>();

    // before confirmation the panel is the review form
    if (row.stage === "confirm")
        return (
            <CandidateDetail
                key={row.id}
                group={row.group}
                commitments={commitments}
                documents={documents}
                mentionId={mentionId}
                onMention={onMention}
            />
        );

    const stage = STAGES[row.stage];
    const tr = row.trail.find((t) => t.commitment.id === trailSel) ?? row.trail[0];
    const cand = row.group.find((c) => c.id === tr?.commitment.candidate_id) ?? row.group[0];
    const docUrl = documents.find((d) => d.id === cand.document_id)?.url;
    const comById = new Map(commitments.map((c) => [c.id, c]));

    return (
        <div className="space-y-5">
            <header className="space-y-2">
                <div className="flex flex-wrap items-center gap-1.5">
                    <Chip label={KIND_LABEL[row.kind]} tone={KIND_TONE[row.kind]} icon={KIND_ICON[row.kind]}/>
                    <Chip label={stage.label} tone={stage.tone} icon={stage.icon}/>
                    <span className="text-xs text-muted-foreground">Page {cand.source_page}</span>
                </div>
                <Bi as="h2" text={displayTitle(row.title)} en={cand.note?.title_en}
                    className="text-lg leading-snug font-semibold"/>
                <CodeHint code={cand.code}/>
                {row.searchable && row.commitments.length > 0 && (
                    <Button
                        size="sm"
                        variant={row.stage === "search" ? "default" : "outline"}
                        disabled={searching}
                        onClick={() => onSearch(row.commitments.map((c) => c.id))}
                    >
                        {searching ? <Loader2 className="size-3.5 animate-spin"/> : <Search className="size-3.5"/>}
                        {row.pending.length || row.evidence ? "Search again" : "Find evidence"}
                    </Button>
                )}
            </header>

            {row.pending.length > 0 && (
                <Section icon={ListChecks} title="Matches to review" count={row.pending.length}>
                    <div className="space-y-3">
                        {[...row.pending]
                            .sort((a, b) => b.link.score - a.link.score)
                            .map((v) => (
                                <MatchCard
                                    key={v.link.id}
                                    view={v as LinkView & { evidence: EvidenceItem }}
                                    commitment={comById.get(v.link.commitment_id)}
                                />
                            ))}
                    </div>
                </Section>
            )}

            <Section icon={Route} title="Paper trail" count={row.evidence}>
                {tr ? (
                    <TrailDetail
                        key={tr.commitment.id}
                        row={tr}
                        mentions={row.trail.length}
                        mentionValue={trailSel}
                        onMention={setTrailSel}
                        group={row.trail}
                        promise={cand.source_excerpt || tr.commitment.summary}
                        docUrl={docUrl}
                        hideHeader
                    />
                ) : (
                    <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        <FileText className="size-4"/> Nothing recorded for this commitment.
                    </p>
                )}
            </Section>
        </div>
    );
}
