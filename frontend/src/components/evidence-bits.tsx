import type { Schemas } from "@/api/client"
import { ToneBadge } from "@/components/tone-badge"
import { BUDGET_LABEL, FLAG_HELP, FLAG_LABEL, POLARITY_LABEL, huf } from "@/lib/labels"

/** Chips for an evidence item's polarity, flags and procurement ids. */
export function EvidenceWarnings({ ev }: { ev: Schemas["EvidenceItem"] }) {
  const polarity = POLARITY_LABEL[ev.polarity]
  return (
    <div className="flex flex-wrap gap-1.5">
      {polarity && <ToneBadge tone="red">{polarity}</ToneBadge>}
      {ev.flags.map((flag) => (
        <ToneBadge key={flag} tone={flag === "regression_warning" ? "red" : "amber"} title={FLAG_HELP[flag]}>
          {FLAG_LABEL[flag]}
        </ToneBadge>
      ))}
      {ev.procurement_ids.map((id) => (
        <ToneBadge key={id}>{id}</ToneBadge>
      ))}
    </div>
  )
}

/** One budget figure as "kind · amount · year". */
export function BudgetLine({ b }: { b: Schemas["BudgetRecord"] }) {
  const amount = b.currency === "HUF" ? huf(b.amount_huf) : b.amount_raw
  return (
    <p className="type-body">
      {[BUDGET_LABEL[b.kind], amount, b.fiscal_year ? String(b.fiscal_year) : ""].filter(Boolean).join(" · ")}
    </p>
  )
}
