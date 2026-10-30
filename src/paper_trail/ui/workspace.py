"""row model + display wording for the workspace. pure functions, no nicegui in here"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain.enums import CandidateType, ReviewStatus
from ..domain.models import Commitment, PolicyCandidate

KIND_LABEL = {
    "objective": "objective", "measure": "measure", "target": "target",
    "indicator": "indicator", "background": "background text", "unclear": "unclear",
}
KIND_SECTION = {
    "objective": "Objectives", "target": "Targets", "measure": "Measures",
    "indicator": "Indicators", "background": "Background", "unclear": "Unclear",
}
STATUS_LABEL = {
    "announced": "announced", "planned": "planned", "in_preparation": "in preparation",
    "in_implementation": "in progress", "completed": "completed",
    "budget_evidence": "budget evidence", "background_only": "background only",
    "unknown": "unclear",
}
STATUS_SENTENCE = {
    "announced": "This source announces the work.",
    "planned": "This source describes a planned project.",
    "in_preparation": "This source says the work is being prepared.",
    "in_implementation": "This source says the work is underway.",
    "completed": "This source says the work was completed.",
    "budget_evidence": "This source reports money figures.",
    "background_only": "This looks related, but it's background material.",
    "unknown": "This looks related, but it doesn't confirm implementation.",
}
REL_LABEL = {
    "direct_implementation": "evidence it happened",
    "supporting": "supporting evidence",
    "budget": "budget information",
    "related_but_indirect": "related, but indirect",
    "probably_unrelated": "probably unrelated",
}
REL_HELP = {
    "direct_implementation": "The source directly documents work on this commitment. It may "
                             "describe planned, ongoing or completed work; check the excerpt.",
    "supporting": "The source adds relevant context or supporting detail, but does not "
                  "directly establish implementation.",
    "budget": "The source records an estimated cost, approved funding or reported spending. "
              "A money figure alone does not prove completion.",
    "related_but_indirect": "The source concerns related work, but its connection to this "
                            "commitment is indirect.",
    "probably_unrelated": "The source does not establish a useful relationship to this "
                          "commitment.",
}
BUDGET_LABEL = {
    "estimated_cost": "estimated cost", "initial_appropriation": "budget appropriation",
    "amended_appropriation": "amended appropriation", "contracted_price": "contracted price",
    "actual_expenditure": "spent (final accounts)",
    "reported_expenditure": "reported spending, unverified",
}
FLAG_LABEL = {
    "regression_warning": "Later amended or cancelled",
    "maintenance_only_suspect": "Maybe routine maintenance",
}
FLAG_HELP = {
    "regression_warning": "Another official source says the contract or project behind this "
                          "passage was amended or cancelled. Check before relying on it.",
    "maintenance_only_suspect": "The passage talks about repairs or maintenance and never about "
                                "an upgrade. Routine upkeep may not count as climate action.",
}
POLARITY_LABEL = {"affirmative": "", "amendment": "Reports an amendment",
                  "termination": "Reports a cancellation"}
JURISDICTION_LABEL = {
    "district_municipality": "District municipality",
    "metropolitan_municipality": "City government",
    "public_utility_water": "Water utility",
    "public_utility_heating": "District heating",
    "national_government": "National government",
}

# quasar colour per value, same palette the react app used
KIND_TONE = {"objective": "blue", "target": "purple", "measure": "teal", "indicator": "amber",
             "background": "grey", "unclear": "grey"}
STATUS_TONE = {"announced": "grey", "planned": "amber", "in_preparation": "amber",
               "in_implementation": "blue", "completed": "green", "budget_evidence": "purple"}
REL_TONE = {"direct_implementation": "green", "supporting": "blue", "budget": "purple",
            "related_but_indirect": "amber", "probably_unrelated": "grey"}

STAGES = {
    "confirm": ("To confirm", "Check the promise against the strategy", "amber"),
    "search": ("To search", "Find official sources", "blue"),
    "review": ("To review", "Confirm or reject suggested matches", "purple"),
    "done": ("Done", "Nothing left to do", "green"),
    "rejected": ("Rejected", "Not a commitment", "grey"),
}
KIND_ORDER = ["objective", "target", "measure", "indicator", "background", "unclear"]
SEARCHABLE = {CandidateType.OBJECTIVE, CandidateType.MEASURE, CandidateType.TARGET}


def display_title(title: str | None) -> str:
    # markdown junk the llm leaves in titles, then stray punctuation at the ends
    text = re.sub(r"\s+", " ", re.sub(r"[*_#`>]+", "", title or "")).strip()
    return re.sub(r"^[.:–—\-\s]+|[.:–—\-\s]+$", "", text)


def huf(amount: float | None) -> str:
    return "" if amount is None else f"{round(amount):,} Ft".replace(",", " ")


_REPORT_CUES = re.compile(r"strateg|strategy|jelent|report|action.?plan|program", re.I)


def evidence_kind(url: str, title: str) -> str:
    # planning docs vs concrete project pages
    report = _REPORT_CUES.search(url or "") or _REPORT_CUES.search(title or "")
    return "Strategy / report" if report else "Project / update"


@dataclass
class Row:
    """one commitment across the whole pipeline: its source mentions, review, evidence"""

    id: int
    title: str
    kind: str
    group: list[PolicyCandidate]
    commitments: list[Commitment] = field(default_factory=list)
    trail: list = field(default_factory=list)  # TrailRow
    pending: list = field(default_factory=list)  # LinkView, unreviewed with evidence
    evidence: int = 0
    searchable: bool = False
    stage: str = "confirm"


def _stage(r: Row) -> str:
    if any(c.review_status == ReviewStatus.UNREVIEWED for c in r.group):
        return "confirm"
    if not r.commitments:
        return "rejected"
    if r.pending:
        return "review"
    if r.evidence > 0 or not r.searchable:
        return "done"
    return "search"


def build_rows(cands: list[PolicyCandidate], commitments: list[Commitment],
               links: list, trail: list) -> list[Row]:
    com_by_cand: dict[int, list[Commitment]] = {}
    for c in commitments:
        if c.candidate_id is not None:
            com_by_cand.setdefault(c.candidate_id, []).append(c)
    trail_by_id = {t.commitment.id: t for t in trail}
    pending: dict[int, list] = {}
    for lv in links:
        if lv.link.review_status == ReviewStatus.UNREVIEWED and lv.evidence:
            pending.setdefault(lv.link.commitment_id, []).append(lv)
    # same title + kind = one display row, every source mention kept in the group
    groups: dict[str, list[PolicyCandidate]] = {}
    for c in cands:
        key = display_title(c.normalized_title).lower() + c.suggested_type.value
        groups.setdefault(key, []).append(c)
    rows = []
    for group in groups.values():
        coms = [m for c in group for m in com_by_cand.get(c.id, [])]
        trails = [trail_by_id[m.id] for m in coms if m.id in trail_by_id]
        row = Row(id=group[0].id, title=group[0].normalized_title,
                  kind=group[0].suggested_type.value, group=group, commitments=coms,
                  trail=trails, pending=[lv for m in coms for lv in pending.get(m.id, [])],
                  evidence=sum(len(t.evidence) for t in trails),
                  searchable=group[0].suggested_type in SEARCHABLE)
        row.stage = _stage(row)
        rows.append(row)
    return sorted(rows, key=lambda r: (KIND_ORDER.index(r.kind), r.group[0].source_page))


def matches_filter(row: Row, stage: str, kind: str, q: str) -> bool:
    # "all" hides rejected, the stage pill shows them on purpose
    if (stage == "all" and row.stage == "rejected") or stage not in ("all", row.stage):
        return False
    if kind != "all" and row.kind != kind:
        return False
    q = q.strip().lower()
    return not q or q in row.title.lower() or any(
        q in (c.text or "").lower() or q in (c.code or "").lower() for c in row.group)


def shown(row: Row, picked: int | None = None) -> PolicyCandidate:
    """the source mention the panel shows: the one you picked, else the first open one"""
    by_id = {c.id: c for c in row.group}
    if picked in by_id:
        return by_id[picked]
    return next((c for c in row.group if c.review_status == ReviewStatus.UNREVIEWED), row.group[0])


def goal(c: PolicyCandidate | Commitment) -> str:
    number = f"{c.target_value:g}" if c.target_value is not None else None
    value = " ".join(x for x in (number, c.unit) if x)
    when = c.deadline_year or getattr(c, "timeframe", None)
    return " by ".join(str(x) for x in (value, when) if x) or "–"


def page_link(doc_url: str | None, page: int) -> tuple[str, str | None]:
    """label + href, the strategy pdf opened at the page"""
    if not doc_url:
        return f"Source · page {page}", None
    return f"Strategy · page {page}", f"{doc_url.split('#')[0]}#page={page}"
