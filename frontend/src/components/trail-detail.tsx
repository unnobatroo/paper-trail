import { toast } from "sonner"

import type { Schemas, TrailRow } from "@/api/client"
import { useReviewActions } from "@/api/hooks"
import { useCanReview } from "@/lib/can-review"
import { BudgetLine, EvidenceWarnings } from "@/components/evidence-bits"
import { Receipt } from "@/components/receipt"
import { SimpleSelect } from "@/components/simple-select"
import { ToneBadge } from "@/components/tone-badge"
import {
  BUCKET,
  BUCKET_ORDER,
  BUCKET_TONE,
  BUDGET_LABEL,
  JURISDICTION_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  goal,
} from "@/lib/labels"

/** One step of the trail: a node on the line, what it is, and what backs it. */
function Group({ title, tone, children }: { title: string; tone: string; children: React.ReactNode }) {
  return (
    <li className="relative flex flex-col gap-2 border-l pb-5 pl-5 last:border-l-transparent last:pb-0">
      <span
        aria-hidden="true"
        className={`absolute top-1 -left-[5px] size-2.5 rounded-full bg-background ring-2 ${tone === "red" ? "ring-destructive" : "ring-brand-line"}`}
      />
      <h4 className="type-body font-medium">{title}</h4>
      {children}
    </li>
  )
}

/** A commitment's paper trail: status, money, evidence grouped by relationship, findings and gaps. */
export function TrailDetail({ t }: { t: TrailRow }) {
  const { setJurisdiction } = useReviewActions()
  const canReview = useCanReview()
  const com = t.commitment
  const meta = [
    com.kind.toUpperCase(),
    com.deadline_year ? `Deadline ${com.deadline_year}` : "",
    com.target_value != null && com.unit ? `Target ${com.target_value} ${com.unit}` : "",
    com.responsible_org ? `who: ${com.responsible_org}` : "",
  ].filter(Boolean)

  // Evidence and its relationships run in step; a relationship the API hasn't sent counts as supporting.
  const buckets: Record<string, Schemas["EvidenceItem"][]> = Object.fromEntries(BUCKET_ORDER.map((b) => [b, []]))
  t.evidence.forEach((ev, i) => buckets[BUCKET[t.relationships[i] ?? ""] ?? "Supporting"].push(ev))

  return (
    <div className="flex flex-col gap-3">
      <p className="type-label">{meta.join(" · ")}</p>
      <div className="flex flex-wrap items-center gap-2">
        {t.status !== "unknown" && (
          <ToneBadge tone={STATUS_TONE[t.status] ?? "grey"}>Source says: {STATUS_LABEL[t.status]}</ToneBadge>
        )}
        <SimpleSelect
          label="Asset owner"
          disabled={!canReview}
          value={com.asset_owner_jurisdiction}
          onChange={(v) =>
            setJurisdiction.mutate(
              { id: com.id!, jurisdiction: v as Schemas["Jurisdiction"] },
              { onSuccess: () => toast.success("Owner updated. The next evidence search covers their sites.") },
            )
          }
          options={Object.entries(JURISDICTION_LABEL).map(([value, label]) => ({ value, label }))}
        />
      </div>
      <p className="type-label">Goal: {goal(com)}</p>

      {t.financial_states.length > 0 && (
        <p className="type-body">
          Money on record: {t.financial_states.map((s) => BUDGET_LABEL[s]).join(" → ")} ·{" "}
          {t.financially_executed ? "spending confirmed" : "spending not confirmed"}
        </p>
      )}

      <ol className="flex flex-col">
      {BUCKET_ORDER.filter((name) => buckets[name].length > 0 || (name === "Budget" && t.budgets.length > 0)).map((name) => (
        <Group key={name} title={name} tone={BUCKET_TONE[name]}>
          {name === "Implementation" && t.status_excerpt && <Receipt>{t.status_excerpt}</Receipt>}
          {buckets[name].map((ev) => (
            <div key={ev.id} className="flex flex-col gap-1">
              <a href={ev.url} target="_blank" rel="noreferrer" className="type-body underline-offset-4 hover:underline">
                {ev.title || ev.url}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
              <EvidenceWarnings ev={ev} />
            </div>
          ))}
          {name === "Budget" && (
            <>
              {t.budgets.slice(0, 6).map((b, i) => (
                <BudgetLine key={i} b={b} />
              ))}
              {t.budgets.length > 6 && (
                <p className="type-label">… and {t.budgets.length - 6} more figures in the sources</p>
              )}
            </>
          )}
        </Group>
      ))}

      {t.findings.length > 0 && (
        <Group title="Audit findings" tone="red">
          {t.findings.map((x) => (
            <p key={x} className="type-body">{x}</p>
          ))}
        </Group>
      )}
      {t.gaps.length > 0 && (
        <Group title="Still missing" tone="amber">
          {t.gaps.map((x) => (
            <p key={x} className="type-body">{x}</p>
          ))}
        </Group>
      )}
      </ol>
    </div>
  )
}
