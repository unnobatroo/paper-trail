/** Display wording for the values the API returns. Presentation only: no rules live here. */

export type Tone = "grey" | "blue" | "amber" | "green" | "purple" | "teal" | "red"

export const KIND_LABEL: Record<string, string> = {
  objective: "objective",
  measure: "measure",
  target: "target",
  indicator: "indicator",
  background: "background text",
  unclear: "unclear",
}

export const KIND_SECTION: Record<string, string> = {
  objective: "Objectives",
  target: "Targets",
  measure: "Measures",
  indicator: "Indicators",
  background: "Background",
  unclear: "Unclear",
}

export const KIND_ORDER = ["objective", "target", "measure", "indicator", "background", "unclear"]

export const KIND_TONE: Record<string, Tone> = {
  objective: "blue",
  target: "purple",
  measure: "teal",
  indicator: "amber",
  background: "grey",
  unclear: "grey",
}

export const STAGES = ["confirm", "search", "review", "done", "rejected"] as const
export type Stage = (typeof STAGES)[number]

export const STAGE_INFO: Record<Stage, { label: string; hint: string; tone: Tone }> = {
  confirm: { label: "To confirm", hint: "Check the promise against the strategy", tone: "amber" },
  search: { label: "To search", hint: "Find official sources", tone: "blue" },
  review: { label: "To review", hint: "Confirm or reject suggested matches", tone: "purple" },
  done: { label: "Done", hint: "Nothing left to do", tone: "green" },
  rejected: { label: "Rejected", hint: "Not a commitment", tone: "grey" },
}

export const STATUS_LABEL: Record<string, string> = {
  announced: "announced",
  planned: "planned",
  in_preparation: "in preparation",
  in_implementation: "in progress",
  completed: "completed",
  budget_evidence: "budget evidence",
  background_only: "background only",
  unknown: "unclear",
}

export const STATUS_SENTENCE: Record<string, string> = {
  announced: "This source announces the work.",
  planned: "This source describes a planned project.",
  in_preparation: "This source says the work is being prepared.",
  in_implementation: "This source says the work is underway.",
  completed: "This source says the work was completed.",
  budget_evidence: "This source reports money figures.",
  background_only: "This looks related, but it's background material.",
  unknown: "This looks related, but it doesn't confirm implementation.",
}

export const STATUS_TONE: Record<string, Tone> = {
  announced: "grey",
  planned: "amber",
  in_preparation: "amber",
  in_implementation: "blue",
  completed: "green",
  budget_evidence: "purple",
}

export const REL_LABEL: Record<string, string> = {
  direct_implementation: "evidence it happened",
  supporting: "supporting evidence",
  budget: "budget information",
  related_but_indirect: "related, but indirect",
  probably_unrelated: "probably unrelated",
}

export const REL_HELP: Record<string, string> = {
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
}

export const REL_TONE: Record<string, Tone> = {
  direct_implementation: "green",
  supporting: "blue",
  budget: "purple",
  related_but_indirect: "amber",
  probably_unrelated: "grey",
}

/** Which trail group a relationship belongs to; anything unknown counts as supporting. */
export const BUCKET: Record<string, string> = {
  direct_implementation: "Implementation",
  budget: "Budget",
  probably_unrelated: "Probably unrelated",
}
export const BUCKET_ORDER = ["Implementation", "Supporting", "Budget", "Probably unrelated"]
export const BUCKET_TONE: Record<string, Tone> = {
  Implementation: "green",
  Supporting: "blue",
  Budget: "purple",
  "Probably unrelated": "grey",
}

export const BUDGET_LABEL: Record<string, string> = {
  estimated_cost: "estimated cost",
  initial_appropriation: "budget appropriation",
  amended_appropriation: "amended appropriation",
  contracted_price: "contracted price",
  actual_expenditure: "spent (final accounts)",
  reported_expenditure: "reported spending, unverified",
}

export const FLAG_LABEL: Record<string, string> = {
  regression_warning: "Later amended or cancelled",
  maintenance_only_suspect: "Maybe routine maintenance",
}

export const FLAG_HELP: Record<string, string> = {
  regression_warning:
    "Another official source says the contract or project behind this passage was amended or cancelled. Check before relying on it.",
  maintenance_only_suspect:
    "The passage talks about repairs or maintenance and never about an upgrade. Routine upkeep may not count as climate action.",
}

export const POLARITY_LABEL: Record<string, string> = {
  affirmative: "",
  amendment: "Reports an amendment",
  termination: "Reports a cancellation",
}

export const JURISDICTION_LABEL: Record<string, string> = {
  district_municipality: "District municipality",
  metropolitan_municipality: "City government",
  public_utility_water: "Water utility",
  public_utility_heating: "District heating",
  national_government: "National government",
}

/** Strip the Markdown characters and edge punctuation a model leaves in titles. */
export function displayTitle(title: string | null | undefined): string {
  const text = (title ?? "").replace(/[*_#`>]+/g, "").replace(/\s+/g, " ").trim()
  return text.replace(/^[.:–—\-\s]+|[.:–—\-\s]+$/g, "")
}

/** "100 fa by 2027", or a dash when the target and deadline are unknown. */
export function goal(c: {
  target_value?: number | null
  unit?: string | null
  deadline_year?: number | null
  timeframe?: string | null
}): string {
  const value = [c.target_value ?? null, c.unit || null].filter((x) => x !== null).join(" ")
  const when = c.deadline_year ?? c.timeframe ?? null
  return [value, when].filter((x) => x !== "" && x !== null).join(" by ") || "–"
}

/** A label and a link that opens the strategy PDF at the page. */
export function pageLink(docUrl: string | undefined, page: number): { text: string; href?: string } {
  if (!docUrl) return { text: `Source · page ${page}` }
  return { text: `Strategy · page ${page}`, href: `${docUrl.split("#")[0]}#page=${page}` }
}

/** Forints with spaces between thousands. */
export function huf(amount: number | null | undefined): string {
  return amount == null ? "" : `${Math.round(amount).toLocaleString("en").replaceAll(",", " ")} Ft`
}

const REPORT_CUES = /strateg|strategy|jelent|report|action.?plan|program/i

/** Planning documents versus concrete project pages. */
export function evidenceKind(url: string, title: string): string {
  return REPORT_CUES.test(url) || REPORT_CUES.test(title) ? "Strategy / report" : "Project / update"
}
