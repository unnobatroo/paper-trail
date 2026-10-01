/** Display helpers — labels, phrasing and grouping for review UI. */
import type {
  BudgetKind,
  CandidateType,
  RelationshipType,
  Status,
} from "./api";

export const KIND_LABEL: Record<CandidateType, string> = {
  objective: "objective",
  measure: "measure",
  target: "target",
  indicator: "indicator",
  background: "background text",
  unclear: "unclear",
};

export const STATUS_LABEL: Record<Status, string> = {
  announced: "announced",
  planned: "planned",
  in_preparation: "in preparation",
  in_implementation: "in progress",
  completed: "completed",
  budget_evidence: "budget evidence",
  background_only: "background only",
  unknown: "unclear",
};

export const STATUS_SENTENCE: Record<Status, string> = {
  announced: "This source announces the work.",
  planned: "This source describes a planned project.",
  in_preparation: "This source says the work is being prepared.",
  in_implementation: "This source says the work is underway.",
  completed: "This source says the work was completed.",
  budget_evidence: "This source reports money figures.",
  background_only: "This looks related, but it's background material.",
  unknown: "This looks related, but it doesn't confirm implementation.",
};

export const REL_LABEL: Record<RelationshipType, string> = {
  direct_implementation: "evidence it happened",
  supporting: "supporting evidence",
  budget: "budget information",
  related_but_indirect: "related, but indirect",
  probably_unrelated: "probably unrelated",
};

export const REL_HELP: Record<RelationshipType, string> = {
  direct_implementation:
    "The source directly documents work on this commitment. It may describe planned, ongoing or completed work; check the excerpt.",
  supporting:
    "The source adds relevant context or supporting detail, but does not directly establish implementation.",
  budget:
    "The source records an estimated cost, approved funding or reported spending. A money figure alone does not prove completion.",
  related_but_indirect:
    "The source concerns related work, but its connection to this commitment is indirect.",
  probably_unrelated:
    "The source does not establish a useful relationship to this commitment.",
};

export const BUDGET_LABEL: Record<BudgetKind, string> = {
  estimated_cost: "estimated cost",
  approved_allocation: "approved funding",
  reported_expenditure: "reported spending",
};

export function displayTitle(title: string | null | undefined): string {
  return (title ?? "")
    .replace(/[*_#`>]+/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^[.:–—\-\s]+|[.:–—\-\s]+$/g, "");
}

export function huf(amount: number | null | undefined): string {
  if (amount == null) return "";
  return `${Math.round(amount).toLocaleString("en-US").replace(/,/g, " ")} Ft`;
}

/** Exact-title + kind grouping — presentation only, every record kept. */
export function titleGroups<T>(
  records: T[],
  title: (r: T) => string | null | undefined,
  kind: (r: T) => string,
): T[][] {
  const groups = new Map<string, T[]>();
  for (const r of records) {
    const key = `${displayTitle(title(r)).toLowerCase()}${kind(r)}`;
    const g = groups.get(key);
    if (g) g.push(r);
    else groups.set(key, [r]);
  }
  return [...groups.values()];
}

/** Broad planning docs vs concrete project pages (matches ml/entities.py). */
const REPORT_CUES = /strateg|strategy|jelent|report|action.?plan|program/i;
export function evidenceKind(url: string, title: string): string {
  return REPORT_CUES.test(url) || REPORT_CUES.test(title)
    ? "Strategy / report"
    : "Project / update";
}

/** Page guides — short explainer copy shown on each route. */
export const PAGE_GUIDES: Record<
  string,
  { description: string; terms: [string, string][] }
> = {
  commitments: {
    description:
      "Check the promise against the original strategy before confirming it.",
    terms: [
      [
        "Inspect or select",
        "Click a title to read it. Check a box to include it in a batch action. These actions are independent.",
      ],
      [
        "Objective · measure · target",
        "An objective states an intended outcome. A measure describes an action. A target states a specific result to aim for, often with a value or deadline.",
      ],
      [
        "Confirmed",
        "Accepted as a commitment from the strategy. This does not mean the work is complete.",
      ],
      [
        "Source mentions",
        "Repeated, identically titled records share a display row. Each original passage remains available in the inspector.",
      ],
    ],
  },
  evidence: {
    description:
      "Search official sources, then review how each match relates to a commitment.",
    terms: [
      [
        "Choose → search → review",
        "Select commitments and run one batch search. Review the resulting matches before they appear in the paper trail.",
      ],
      [
        "Match",
        "A suggested connection for you to check, not a confirmed finding. Read the matched excerpt and the official source.",
      ],
      [
        "Status",
        "What the matched source text reports: announced, planned, in preparation, in progress or completed. Background and unclear do not establish implementation.",
      ],
      [
        "Relationship",
        "How the source relates to the commitment. Your choice is saved when you confirm the selected match.",
      ],
    ],
  },
  trail: {
    description:
      "Read confirmed commitments and their reviewed evidence, grouped by policy objective.",
    terms: [
      [
        "Read-only",
        "Click a commitment to inspect its trail. Review decisions are made in Check commitments and Find evidence.",
      ],
      [
        "Implementation",
        "Reviewed sources linked directly to the commitment. The displayed status describes what those sources report.",
      ],
      [
        "Supporting evidence",
        "Relevant context and indirect links, separate from direct implementation evidence.",
      ],
      [
        "Still missing",
        "Gaps in the records reviewed so far. Missing evidence does not establish that no work took place.",
      ],
    ],
  },
};
