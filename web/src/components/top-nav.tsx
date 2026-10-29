"use client";

import {useEffect, useRef, useState} from "react";
import Link from "next/link";
import {toast} from "sonner";
import {useQuery, useQueryClient} from "@tanstack/react-query";
import {Languages, Loader2, Search} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Kbd} from "@/components/ui/kbd";
import {IngestDialog} from "@/components/ingest-dialog";
import {ReviewKeyDialog} from "@/components/review-key-dialog";
import {ThemeToggle} from "@/components/theme-toggle";
import {useTranslate} from "@/components/en";
import {keys, useDocuments, useJobs, useMeta,} from "@/lib/hooks";
import {api} from "@/lib/api";

export function TopNav() {
    const qc = useQueryClient();
    const {data: meta, isError: metaError} = useMeta();
    const {data: documents} = useDocuments();
    const {on: translateOn, setOn: setTranslateOn} = useTranslate();
    const [startedIds, setJobIds] = useState<string[]>([]);
    // the server knows what is running, so a reload keeps following an ingest
    const {data: inFlight} = useQuery({
        queryKey: keys.activeJobs("ingest"),
        queryFn: () => api.activeJobs("ingest"),
    });
    const jobIds = startedIds.length ? startedIds : (inFlight ?? []).map((j) => j.id);
    const {jobs, settled} = useJobs(jobIds);


    const notified = useRef("");
    useEffect(() => {
        const batch = jobIds.join(",");
        if (!settled || notified.current === batch) return;
        notified.current = batch;
        qc.invalidateQueries({queryKey: keys.documents});
        qc.invalidateQueries({queryKey: keys.candidates});
        const failed = jobs.filter((j) => j.status === "failed");
        if (failed.length) {
            toast.error(`Ingest failed: ${failed[0].error ?? "unknown error"}`);
        } else {
            toast.success("Strategy read. Review the commitments it produced.");
            jobs.flatMap((j) => j.result?.warnings ?? []).forEach((w) => toast.warning(w));
        }
    }, [settled, jobs, jobIds, qc]);

    const running = jobs.filter((j) => j.status === "queued" || j.status === "running");
    const status = meta
        ? `${documents?.length ?? 0} doc · ${meta.storage}`
        : metaError
            ? "API unreachable"
            : "connecting…";

    return (
        <header className="sticky top-0 z-30 border-b bg-background/90 backdrop-blur">
            <div className="mx-auto flex min-h-12 max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-1 px-4 py-1">
                <Link href="/" className="flex items-center gap-2">
                    <span className="text-sm font-semibold tracking-tight">Paper Trail</span>
                    {meta?.deployment && (
                        <Badge variant="outline" className="text-[10px]">
                            {meta.deployment}
                        </Badge>
                    )}
                </Link>


                <div className="ml-auto flex items-center gap-1">
                    {running.length > 0 && (
                        <span
                            role="status"
                            className="mr-2 flex max-w-64 items-center gap-1.5 truncate text-xs text-muted-foreground"
                            title={running[0].progress}
                        >
              <Loader2 className="size-3 shrink-0 animate-spin"/>
                            {running[0].progress || "Reading strategy…"}
            </span>
                    )}
                    {documents !== undefined && !documents.length && (
                        <IngestDialog onJob={setJobIds}/>
                    )}
                    <Button
                        variant={translateOn ? "secondary" : "ghost"}
                        size="sm"
                        className="gap-1.5"
                        disabled={!meta?.translation}
                        onClick={() => setTranslateOn(!translateOn)}
                        title={meta && !meta.translation ? "Translation is unavailable" : undefined}
                    >
                        <Languages className="size-4"/>
                        EN
                    </Button>
                    {meta?.review_required && <ReviewKeyDialog/>}
                    <ThemeToggle/>
                    <Button
                        variant="outline"
                        size="sm"
                        className="ml-1 gap-2 text-muted-foreground"
                        onClick={() =>
                            window.dispatchEvent(
                                new KeyboardEvent("keydown", {key: "k", metaKey: true}),
                            )
                        }
                    >
                        <Search className="size-3.5"/>
                        <Kbd>⌘K</Kbd>
                    </Button>
                </div>
            </div>
            <div className="sr-only" aria-live="polite">{status}</div>
        </header>
    );
}
