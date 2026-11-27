"""The review workspace's rows: what needs doing for each commitment, and in which stage.

Pure functions with no web framework in them, so the API and the tests share one set of rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain.enums import CandidateType, ReviewStatus
from ..domain.models import Commitment, PolicyCandidate

STAGES = ("confirm", "search", "review", "done", "rejected")
KIND_ORDER = ["objective", "target", "measure", "indicator", "background", "unclear"]
SEARCHABLE = {CandidateType.OBJECTIVE, CandidateType.MEASURE, CandidateType.TARGET}


def display_title(title: str | None) -> str:
    """Return a title without the Markdown characters and edge punctuation the model leaves in."""
    text = re.sub(r"\s+", " ", re.sub(r"[*_#`>]+", "", title or "")).strip()
    return re.sub(r"^[.:–—\-\s]+|[.:–—\-\s]+$", "", text)


@dataclass
class Row:
    """One commitment across the pipeline: its source mentions, review and evidence."""

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
    """Group candidates, commitments, links and trail rows into one Row per commitment.

    Candidates with the same title and kind share a row, and each row keeps every source mention.
    """
    com_by_cand: dict[int, list[Commitment]] = {}
    for c in commitments:
        if c.candidate_id is not None:
            com_by_cand.setdefault(c.candidate_id, []).append(c)
    trail_by_id = {t.commitment.id: t for t in trail}
    pending: dict[int, list] = {}
    for lv in links:
        if lv.link.review_status == ReviewStatus.UNREVIEWED and lv.evidence:
            pending.setdefault(lv.link.commitment_id, []).append(lv)
    # Same title and kind make one display row, keeping every source mention in it.
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


def stage_counts(rows: list[Row]) -> dict[str, int]:
    """Return how many rows sit in each stage."""
    return {s: sum(r.stage == s for r in rows) for s in STAGES}


def matches_filter(row: Row, stage: str, kind: str, q: str) -> bool:
    """Tell whether a row passes the stage, type and search filters. "all" hides rejected rows."""
    if (stage == "all" and row.stage == "rejected") or stage not in ("all", row.stage):
        return False
    if kind != "all" and row.kind != kind:
        return False
    q = q.strip().lower()
    return not q or q in row.title.lower() or any(
        q in (c.text or "").lower() or q in (c.code or "").lower() for c in row.group)
