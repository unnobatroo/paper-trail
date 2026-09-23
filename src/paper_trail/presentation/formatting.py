"""Tiny display helpers shared by the views."""

from __future__ import annotations

import re

from ..domain.enums import (
    BudgetKind,
    CandidateType,
    RelationshipType,
    Status,
)
from ..ml.entities import is_report_doc

KIND_LABEL = {
    CandidateType.OBJECTIVE: "objective",
    CandidateType.MEASURE: "measure",
    CandidateType.TARGET: "target",
    CandidateType.INDICATOR: "indicator",
    CandidateType.BACKGROUND: "background text",
    CandidateType.UNCLEAR: "unclear",
}

STATUS_LABEL = {
    Status.ANNOUNCED: "announced",
    Status.PLANNED: "planned",
    Status.IN_PREPARATION: "in preparation",
    Status.IN_IMPLEMENTATION: "in progress",
    Status.COMPLETED: "completed",
    Status.BUDGET: "budget evidence",
    Status.BACKGROUND: "background only",
    Status.UNKNOWN: "unclear",
}

# One humane sentence per status — used in review and the trail.
STATUS_SENTENCE = {
    Status.ANNOUNCED: "This source announces the work.",
    Status.PLANNED: "This source describes a planned project.",
    Status.IN_PREPARATION: "This source says the work is being prepared.",
    Status.IN_IMPLEMENTATION: "This source says the work is underway.",
    Status.COMPLETED: "This source says the work was completed.",
    Status.BUDGET: "This source reports money figures.",
    Status.BACKGROUND:
        "This looks related, but it's background material.",
    Status.UNKNOWN:
        "This looks related, but it doesn't confirm implementation.",
}

REL_LABEL = {
    RelationshipType.DIRECT_IMPLEMENTATION: "evidence it happened",
    RelationshipType.SUPPORTING: "supporting evidence",
    RelationshipType.BUDGET: "budget information",
    RelationshipType.INDIRECT: "related, but indirect",
    RelationshipType.UNRELATED: "probably unrelated",
}

BUDGET_LABEL = {
    BudgetKind.ESTIMATED_COST: "estimated cost",
    BudgetKind.APPROVED_ALLOCATION: "approved funding",
    BudgetKind.REPORTED_EXPENDITURE: "reported spending",
}


def display_title(title: str) -> str:
    """Strip stray markdown/heading markers from extracted titles so
    they read cleanly as button labels — provenance text is untouched."""
    t = re.sub(r"[*_#`>]+", "", title or "")
    return re.sub(r"\s+", " ", t).strip()


def huf(amount: float | int | None) -> str:
    if amount is None:
        return ""
    return f"{amount:,.0f} Ft".replace(",", " ")


def evidence_kind(url: str, title: str) -> str:
    """Broad planning documents are labelled differently from concrete
    project pages so reports don't read like project updates."""
    return "Strategy / report" if is_report_doc(url, title) \
        else "Project / update"
