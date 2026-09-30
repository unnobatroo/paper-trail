/** Semantic colouring + icons for domain states — one place for the
 * "what does this colour mean" vocabulary, so a green chip always means
 * the same thing across the queue, inspectors and the paper trail.
 */
import type { LucideIcon } from "lucide-react";
import {
  Banknote,
  CalendarClock,
  CircleCheck,
  CircleHelp,
  Crosshair,
  FileText,
  Gauge,
  Hammer,
  LifeBuoy,
  Link2,
  Link2Off,
  Megaphone,
  Target,
  Wrench,
} from "lucide-react";
import type {
  CandidateType,
  RelationshipType,
  ReviewStatus,
  Status,
} from "./api";

export type Tone =
  | "green"
  | "blue"
  | "teal"
  | "amber"
  | "purple"
  | "red"
  | "gray";

/** Chip/badge classes per tone — static strings so Tailwind keeps them. */
export const TONE_CHIP: Record<Tone, string> = {
  green:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  blue: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  teal: "border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-400",
  amber:
    "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  purple:
    "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-400",
  red: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
  gray: "border-border bg-muted text-muted-foreground",
};

/** Text-only version for section labels etc. */
export const TONE_TEXT: Record<Tone, string> = {
  green: "text-emerald-700 dark:text-emerald-400",
  blue: "text-sky-700 dark:text-sky-400",
  teal: "text-teal-700 dark:text-teal-400",
  amber: "text-amber-700 dark:text-amber-400",
  purple: "text-violet-700 dark:text-violet-400",
  red: "text-red-700 dark:text-red-400",
  gray: "text-muted-foreground",
};

/** What the commitment is — objective / target / measure … */
export const KIND_TONE: Record<CandidateType, Tone> = {
  objective: "blue",
  target: "purple",
  measure: "teal",
  indicator: "amber",
  background: "gray",
  unclear: "gray",
};

export const KIND_ICON: Record<CandidateType, LucideIcon> = {
  objective: Target,
  target: Crosshair,
  measure: Wrench,
  indicator: Gauge,
  background: FileText,
  unclear: CircleHelp,
};

/** What a source reports — greener = stronger implementation signal. */
export const STATUS_TONE: Record<Status, Tone> = {
  announced: "gray",
  planned: "amber",
  in_preparation: "amber",
  in_implementation: "blue",
  completed: "green",
  budget_evidence: "purple",
  background_only: "gray",
  unknown: "gray",
};

export const STATUS_ICON: Record<Status, LucideIcon> = {
  announced: Megaphone,
  planned: CalendarClock,
  in_preparation: Hammer,
  in_implementation: Wrench,
  completed: CircleCheck,
  budget_evidence: Banknote,
  background_only: FileText,
  unknown: CircleHelp,
};

/** How a matched source relates to the commitment. */
export const REL_TONE: Record<RelationshipType, Tone> = {
  direct_implementation: "green",
  supporting: "blue",
  budget: "purple",
  related_but_indirect: "amber",
  probably_unrelated: "gray",
};

export const REL_ICON: Record<RelationshipType, LucideIcon> = {
  direct_implementation: CircleCheck,
  supporting: LifeBuoy,
  budget: Banknote,
  related_but_indirect: Link2,
  probably_unrelated: Link2Off,
};

/** Review state of a candidate or match. */
export const REVIEW_TONE: Record<ReviewStatus, Tone> = {
  accepted: "green",
  rejected: "red",
  unreviewed: "amber",
};
