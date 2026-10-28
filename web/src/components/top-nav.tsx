"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Languages, Loader2, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { IngestDialog } from "@/components/ingest-dialog";
import { ReviewKeyDialog } from "@/components/review-key-dialog";
import { ThemeToggle } from "@/components/theme-toggle";
import { useTranslate } from "@/components/en";
import {
  keys,
  useCandidates,
  useDocuments,
  useJobs,
  useLinks,
  useMeta,
} from "@/lib/hooks";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/commitments", label: "Commitments" },
  { href: "/evidence", label: "Evidence" },
  { href: "/trail", label: "Trail" },
];

export function TopNav() {
  const pathname = usePathname();
  const qc = useQueryClient();
  const { data: meta, isError: metaError } = useMeta();
  const { data: documents } = useDocuments();
  const { data: cands } = useCandidates();
  const { data: links } = useLinks();
  const { on: translateOn, setOn: setTranslateOn } = useTranslate();
  const [jobIds, setJobIds] = useState<string[]>([]);
  const { jobs, settled } = useJobs(jobIds);

  // open work per queue, shown on the tab
  const counts: Record<string, number> = {
    "/commitments":
      cands?.filter((c) => c.review_status === "unreviewed").length ?? 0,
    "/evidence":
      links?.filter((l) => l.link.review_status === "unreviewed").length ?? 0,
  };

  const notified = useRef("");
  useEffect(() => {
    const batch = jobIds.join(",");
    if (!settled || notified.current === batch) return;
    notified.current = batch;
    qc.invalidateQueries({ queryKey: keys.documents });
    qc.invalidateQueries({ queryKey: keys.candidates });
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
      <div className="mx-auto flex h-12 max-w-[1400px] items-center gap-6 px-4">
        <Link href="/commitments" className="flex items-center gap-2">
          <span className="text-sm font-semibold tracking-tight">Paper Trail</span>
          {meta?.deployment && (
            <Badge variant="outline" className="text-[10px]">
              {meta.deployment}
            </Badge>
          )}
        </Link>

        <nav className="flex h-full items-stretch gap-1" aria-label="Stages">
          {TABS.map(({ href, label }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-1.5 border-b-2 px-2 text-sm transition-colors",
                  active
                    ? "border-primary font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
                {counts[href] ? (
                  <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">
                    {counts[href]}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          {running.length > 0 && (
            <span
              role="status"
              className="mr-2 flex max-w-64 items-center gap-1.5 truncate text-xs text-muted-foreground"
              title={running[0].progress}
            >
              <Loader2 className="size-3 shrink-0 animate-spin" />
              {running[0].progress || "Reading strategy…"}
            </span>
          )}
          {documents !== undefined && !documents.length && (
            <IngestDialog onJob={setJobIds} />
          )}
          <Button
            variant={translateOn ? "secondary" : "ghost"}
            size="sm"
            className="gap-1.5"
            disabled={!meta?.translation}
            onClick={() => setTranslateOn(!translateOn)}
            title={meta && !meta.translation ? "Translation is unavailable" : undefined}
          >
            <Languages className="size-4" />
            EN
          </Button>
          {meta?.review_required && <ReviewKeyDialog />}
          <ThemeToggle />
          <Button
            variant="outline"
            size="sm"
            className="ml-1 gap-2 text-muted-foreground"
            onClick={() =>
              window.dispatchEvent(
                new KeyboardEvent("keydown", { key: "k", metaKey: true }),
              )
            }
          >
            <Search className="size-3.5" />
            <Kbd>⌘K</Kbd>
          </Button>
        </div>
      </div>
      <div className="sr-only" aria-live="polite">{status}</div>
    </header>
  );
}
