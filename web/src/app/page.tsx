"use client";

import Link from "next/link";
import {
  FileCheck2,
  SearchCheck,
  Route,
  ArrowRight,
  FileText,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCandidates,
  useCommitments,
  useDocuments,
  useLinks,
  useTrail,
} from "@/lib/hooks";

export default function Dashboard() {
  const { data: docs, isLoading: l0 } = useDocuments();
  const { data: cands, isLoading: l1 } = useCandidates();
  const { data: commitments, isLoading: l2 } = useCommitments();
  const { data: links, isLoading: l3 } = useLinks();
  const { data: trail } = useTrail();

  const loading = l0 || l1 || l2 || l3;

  const unreviewed =
    cands?.filter((c) => c.review_status === "unreviewed").length ?? 0;
  const pendingLinks =
    links?.filter((l) => l.link.review_status === "unreviewed").length ?? 0;
  const withEvidence =
    trail?.filter((r) => r.evidence.length > 0).length ?? 0;
  const reviewedPct = cands?.length
    ? Math.round(((cands.length - unreviewed) / cands.length) * 100)
    : 0;
  const evidencePct = trail?.length
    ? Math.round((withEvidence / trail.length) * 100)
    : 0;

  const nextStep = !docs?.length
    ? {
        title: "Read the strategy",
        desc: "No documents ingested yet — start with the source PDF from the sidebar.",
        href: "/commitments",
        cta: "Open",
      }
    : unreviewed > 0
      ? {
          title: "Check commitments",
          desc: `${unreviewed} source mentions still need review.`,
          href: "/commitments",
          cta: "Review",
        }
      : pendingLinks > 0
        ? {
            title: "Review evidence matches",
            desc: `${pendingLinks} suggested matches are waiting.`,
            href: "/evidence?phase=review",
            cta: "Review matches",
          }
        : {
            title: "Find evidence",
            desc: "Search official sources for the confirmed commitments.",
            href: "/evidence",
            cta: "Search",
          };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Paper Trail</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Check a municipality&apos;s climate promises against evidence from its
        own official sources. Nothing counts until a human confirms it.
      </p>

      {loading ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Source mentions reviewed</CardDescription>
              <CardTitle className="text-3xl">
                {(cands?.length ?? 0) - unreviewed}
                <span className="text-base font-normal text-muted-foreground">
                  {" "}
                  / {cands?.length ?? 0}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Progress value={reviewedPct} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Confirmed commitments</CardDescription>
              <CardTitle className="text-3xl">
                {commitments?.length ?? 0}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                {pendingLinks} matches awaiting review
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>With confirmed evidence</CardDescription>
              <CardTitle className="text-3xl">
                {withEvidence}
                <span className="text-base font-normal text-muted-foreground">
                  {" "}
                  / {trail?.length ?? 0}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Progress value={evidencePct} />
            </CardContent>
          </Card>
        </div>
      )}

      <Card className="mt-6 border-primary/30 bg-primary/5">
        <CardContent className="flex items-center justify-between gap-4 pt-6">
          <div className="flex items-center gap-3">
            <FileText className="size-5 text-primary" />
            <div>
              <p className="font-medium">{nextStep.title}</p>
              <p className="text-sm text-muted-foreground">{nextStep.desc}</p>
            </div>
          </div>
          <Link
            href={nextStep.href}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {nextStep.cta} <ArrowRight className="size-3.5" />
          </Link>
        </CardContent>
      </Card>

      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {[
          {
            href: "/commitments",
            icon: FileCheck2,
            n: 1,
            t: "Check commitments",
            d: "Confirm or reject what the strategy actually promises.",
            badge: unreviewed ? `${unreviewed} left` : "done",
          },
          {
            href: "/evidence",
            icon: SearchCheck,
            n: 2,
            t: "Find evidence",
            d: "Search official sites, review each suggested match.",
            badge: pendingLinks ? `${pendingLinks} pending` : null,
          },
          {
            href: "/trail",
            icon: Route,
            n: 3,
            t: "Paper trail",
            d: "Read the confirmed record — evidence, budgets, gaps.",
            badge: null,
          },
        ].map(({ href, icon: Icon, n, t, d, badge }) => (
          <Link
            key={href}
            href={href}
            className="group rounded-md border p-4 transition-colors hover:bg-muted/50"
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm font-medium">
                <span className="flex size-5 items-center justify-center rounded-full border text-[10px]">
                  {n}
                </span>
                <Icon className="size-4 text-muted-foreground" />
                {t}
              </span>
              {badge && <Badge variant="secondary">{badge}</Badge>}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{d}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
