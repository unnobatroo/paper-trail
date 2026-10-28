"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useMutation } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Check, X, FileText, SquarePen, Clock, CircleHelp } from "lucide-react";
import { En } from "@/components/en";
import { Chip, type RowChip } from "@/components/chip";
import { Kbd } from "@/components/ui/kbd";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { KIND_ICON, KIND_TONE, TONE_TEXT } from "@/lib/tones";
import { api, errorMessage, type CandidateType, type PolicyCandidate } from "@/lib/api";
import { KIND_LABEL, displayTitle } from "@/lib/labels";
import { useInvalidateDomain } from "@/lib/hooks";

export function statusText(c: PolicyCandidate): string {
  if (c.review_status === "accepted") return "Confirmed";
  if (c.review_status === "rejected") return "Rejected";
  return c.excerpt_on_page === false ? "Unclear" : "Needs review";
}

export function statusChip(c: PolicyCandidate): RowChip {
  if (c.review_status === "accepted")
    return { label: "Confirmed", tone: "green", icon: Check };
  if (c.review_status === "rejected")
    return { label: "Rejected", tone: "red", icon: X };
  if (c.excerpt_on_page === false)
    return { label: "Unclear", tone: "gray", icon: CircleHelp };
  return { label: "Needs review", tone: "amber", icon: Clock };
}

const editSchema = z.object({
  kind: z.string(),
  title: z.string().min(1, "Enter a short name"),
  parent_id: z.string(),
});
type EditValues = z.infer<typeof editSchema>;

export function CandidateDetail({
  group,
  commitments,
  documents,
  mentionId,
  onMention,
}: {
  group: PolicyCandidate[];
  commitments: { id: number; code: string | null; title: string }[];
  documents: { id: number; url: string | null }[];
  mentionId: number;
  onMention: (id: number) => void;
}) {
  const invalidate = useInvalidateDomain();
  const cand = group.find((c) => c.id === mentionId) ?? group[0];
  // each mention links to its own document, groups can span several
  const docUrl = documents.find((d) => d.id === cand.document_id)?.url;
  const [editing, setEditing] = useState(false);

  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    values: {
      kind: cand.suggested_type,
      title: displayTitle(cand.normalized_title),
      parent_id: "none",
    },
  });

  const [editKind, editParent] = useWatch({ control: form.control, name: ["kind", "parent_id"] });

  const decide = useMutation({
    mutationFn: async (action: "accept" | "reject" | "edit") => {
      if (action === "reject") {
        await api.rejectCandidate(cand.id);
        return;
      }
      const v = form.getValues();
      await api.acceptCandidate(
        cand.id,
        action === "edit"
          ? {
              kind: v.kind as CandidateType,
              title: v.title.trim(),
              parent_id: v.parent_id === "none" ? null : Number(v.parent_id),
            }
          : undefined,
      );
    },
    onSuccess: (_r, action) => {
      toast.success(
        action === "reject"
          ? "Rejected."
          : action === "edit"
            ? "Saved as a commitment."
            : "Confirmed as a commitment.",
      );
      invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold leading-snug">
          {displayTitle(cand.normalized_title)}
        </h2>
        <En text={displayTitle(cand.normalized_title)} />
      </div>

      {group.length > 1 && (
        <Select
          value={String(cand.id)}
          onValueChange={(v) => onMention(Number(v))}
          items={Object.fromEntries(
            group.map((c) => [
              String(c.id),
              `p.${c.source_page} · ${statusText(c)} · mention ${c.id}`,
            ]),
          )}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {group.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                p.{c.source_page} · {statusText(c)} · mention {c.id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <div className="flex items-center gap-2">
        <Chip {...statusChip(cand)} />
        <Chip
          label={KIND_LABEL[cand.suggested_type]}
          tone={KIND_TONE[cand.suggested_type]}
          icon={KIND_ICON[cand.suggested_type]}
        />
        <span className="text-xs text-muted-foreground">
          Page {cand.source_page}
        </span>
      </div>

      {(cand.deadline_year || cand.timeframe) && (
        <p className="text-sm">
          <span className="font-medium">Deadline</span> ·{" "}
          {cand.deadline_year ?? cand.timeframe}
        </p>
      )}
      {cand.target_value != null && (
        <p className="text-sm">
          <span className="font-medium">Target</span> · {cand.target_value}{" "}
          {cand.unit ?? ""}
        </p>
      )}
      {cand.responsible_org && (
        <p className="text-xs text-muted-foreground">{cand.responsible_org}</p>
      )}

      <div>
        <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          <FileText className="size-3.5" />
          Official source text
        </p>
        <blockquote className="mt-1 border-l-2 pl-3 text-sm text-muted-foreground">
          {cand.source_excerpt}
        </blockquote>
        <En text={cand.source_excerpt} />
      </div>

      {cand.excerpt_on_page === false && (
        <p className={`text-xs ${TONE_TEXT.amber}`}>
          We couldn&apos;t re-find this quote on the page — worth a closer
          look.
        </p>
      )}

      {docUrl ? (
        <Button
          variant="outline"
          size="sm"
          nativeButton={false}
          render={
            <a
              href={`${docUrl.split("#")[0]}#page=${cand.source_page}`}
              target="_blank"
              rel="noopener noreferrer"
            />
          }
        >
          Strategy · page {cand.source_page}
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">
          Source · page {cand.source_page}
        </p>
      )}

      {cand.review_status === "unreviewed" && (
        <div className="space-y-2 border-t pt-3">
          {!editing ? (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => decide.mutate("accept")}
                disabled={decide.isPending}
              >
                <Check className="mr-1 size-3.5" /> Confirm <Kbd>C</Kbd>
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => decide.mutate("reject")}
                disabled={decide.isPending}
              >
                <X className="mr-1 size-3.5" /> Reject <Kbd>R</Kbd>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditing(true)}
              >
                <SquarePen className="mr-1 size-3.5" /> Edit…
              </Button>
            </div>
          ) : (
            <form
              className="space-y-3 rounded-md border p-3"
              onSubmit={form.handleSubmit(() => decide.mutate("edit"))}
            >
              <p className="text-xs text-muted-foreground">
                Saving confirms this source mention as a commitment.
              </p>
              <div className="space-y-1.5">
                <Label>Commitment type</Label>
                <Select
                  value={editKind}
                  onValueChange={(v) => form.setValue("kind", v as string)}
                  items={KIND_LABEL}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(KIND_LABEL).map(([k, l]) => (
                      <SelectItem key={k} value={k}>
                        {l}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Short name</Label>
                <Input {...form.register("title")} />
                {form.formState.errors.title && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.title.message}
                  </p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>Part of</Label>
                <Select
                  value={editParent}
                  onValueChange={(v) => form.setValue("parent_id", v as string)}
                  items={{
                    none: "— on its own —",
                    ...Object.fromEntries(
                      commitments.map((c) => [
                        String(c.id),
                        `${c.code ? c.code + " · " : ""}${displayTitle(c.title)} [${c.id}]`,
                      ]),
                    ),
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— on its own —</SelectItem>
                    {commitments.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.code ? `${c.code} · ` : ""}
                        {displayTitle(c.title)} [{c.id}]
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" disabled={decide.isPending}>
                  Save as commitment
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setEditing(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
