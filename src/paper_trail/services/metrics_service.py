"""Tracker rollups: what each accepted commitment has, and what's missing."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import RelationshipType, ReviewStatus, Status
from ..domain.models import BudgetRecord, Commitment, EvidenceItem
from ..repositories.store import EvidenceRepository, PolicyRepository


def _dedupe(budgets) -> list[BudgetRecord]:
    """The same figure can be quoted several times across a long report —
    keep each (wording, kind, source) once."""
    seen, out = set(), []
    for b in budgets:
        key = (b.amount_raw, b.kind, b.source_url)
        if key not in seen:
            seen.add(key)
            out.append(b)
    return out

# lifecycle stages only — BUDGET / BACKGROUND evidence never promotes a
# commitment's status
_STATUS_ORDER = [
    Status.UNKNOWN,
    Status.ANNOUNCED,
    Status.PLANNED,
    Status.IN_PREPARATION,
    Status.IN_IMPLEMENTATION,
    Status.COMPLETED,
]


@dataclass
class TrailRow:
    """One commitment plus everything verified about it."""

    commitment: Commitment
    evidence: list[EvidenceItem] = field(default_factory=list)
    relationships: list[RelationshipType] = field(default_factory=list)
    budgets: list[BudgetRecord] = field(default_factory=list)
    status: Status = Status.UNKNOWN
    status_excerpt: str | None = None
    gaps: list[str] = field(default_factory=list)


class MetricsService:
    def __init__(self, policy: PolicyRepository, evidence: EvidenceRepository):
        self._policy = policy
        self._evidence = evidence

    def trail(self) -> list[TrailRow]:
        rows = []
        for com in self._policy.commitments():
            accepted = [
                l for l in self._evidence.links_for(com.id)
                if l.review_status == ReviewStatus.ACCEPTED
            ]
            items = [
                self._evidence.evidence(l.evidence_id)
                for l in accepted
            ]
            items = [e for e in items if e]
            budgets = _dedupe(
                b for e in items
                for b in self._evidence.budgets_for_evidence(e.id)
            )
            # only evidence the reviewer called "direct implementation" can
            # mark a commitment as progressing or done — supporting/budget
            # pages never promote status on their own
            direct = [
                e for e, l in zip(items, accepted)
                if (l.relationship or l.suggested_relationship)
                == RelationshipType.DIRECT_IMPLEMENTATION
            ]
            status, excerpt = self._best_status(direct)
            rows.append(TrailRow(
                commitment=com,
                evidence=items,
                relationships=[l.relationship or l.suggested_relationship for l in accepted],
                budgets=budgets,
                status=status,
                status_excerpt=excerpt,
                gaps=self._gaps(com, items, budgets, direct),
            ))
        return rows

    def _gaps(self, com: Commitment, items: list[EvidenceItem],
            budgets: list[BudgetRecord],
            direct: list[EvidenceItem]) -> list[str]:
        gaps = []
        if not direct:
            gaps.append("No implementation evidence found yet.")
        elif all(e.status_hint != Status.COMPLETED for e in direct):
            gaps.append("No completion evidence found.")
        if com.target_value is None:
            gaps.append("No measurable target was stated.")
        if not budgets:
            gaps.append("No confirmed budget found.")
        return gaps

    @staticmethod
    def _best_status(items: list[EvidenceItem]) -> tuple[Status, str | None]:
        best, excerpt = Status.UNKNOWN, None
        for e in items:
            if e.status_hint not in _STATUS_ORDER:
                continue
            if _STATUS_ORDER.index(e.status_hint) > _STATUS_ORDER.index(best):
                best, excerpt = e.status_hint, e.status_excerpt
        return best, excerpt
