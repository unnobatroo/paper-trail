"""trail rollups: what each commitment has, what's missing"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..domain.enums import BudgetKind, EvidenceFlag, RelationshipType, ReviewStatus, Status
from ..domain.models import BudgetRecord, Commitment, EvidenceItem
from ..ml.accountability import FinancialAuditor, PassageAuditor
from ..ml.lang import LanguageProfile
from ..repositories.ports import EvidenceStore, PolicyStore


def with_effective_flags(store: EvidenceStore, ev_map: dict[int, EvidenceItem]) -> None:
    """regression warnings come from artifacts other passages changed, add on read"""
    artifacts = store.artifacts_many(sorted(ev_map))
    for ev_id, ev in ev_map.items():
        ev.flags = PassageAuditor.effective_flags(ev, artifacts.get(ev_id, []))


def _dedupe(budgets) -> list[BudgetRecord]:
    """same figure gets quoted all over a report, keep one per (wording, kind, source)"""
    seen, out = set(), []
    for b in budgets:
        key = (b.amount_raw, b.currency, b.kind, b.source_url)
        if key not in seen:
            seen.add(key)
            out.append(b)
    return out


# lifecycle only, budget/background evidence never bumps status
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
    """a commitment + everything verified about it"""

    commitment: Commitment
    evidence: list[EvidenceItem] = field(default_factory=list)
    relationships: list[RelationshipType] = field(default_factory=list)
    budgets: list[BudgetRecord] = field(default_factory=list)
    status: Status = Status.UNKNOWN
    status_excerpt: str | None = None
    gaps: list[str] = field(default_factory=list)
    # money accepted evidence proves, one entry per state, never a sum
    financial_states: list[BudgetKind] = field(default_factory=list)
    financially_executed: bool = False
    findings: list[str] = field(default_factory=list)


class MetricsService:
    def __init__(self, policy: PolicyStore, evidence: EvidenceStore,
                 profile: LanguageProfile | None = None):
        self._policy = policy
        self._evidence = evidence
        self._money = FinancialAuditor(profile or LanguageProfile.empty())

    def trail(self) -> list[TrailRow]:
        # batch reads, per-link lookups = hundreds of queries per trail view
        links = self._evidence.links()
        ev_ids = sorted({l.evidence_id for l in links})
        ev_map = self._evidence.evidence_many(ev_ids)
        with_effective_flags(self._evidence, ev_map)
        budget_map = self._evidence.budgets_many(ev_ids)

        by_commit: dict[int, list] = defaultdict(list)
        for link in links:
            by_commit[link.commitment_id].append(link)

        rows = []
        for com in self._policy.commitments():
            accepted = [
                l for l in by_commit.get(com.id, [])
                if l.review_status == ReviewStatus.ACCEPTED
            ]
            # pair by id, zip() quietly misaligns on a missing row
            pairs = [(l, e) for l in accepted
                     if (e := ev_map.get(l.evidence_id)) is not None]
            items = [e for _, e in pairs]
            budgets = _dedupe(
                b for e in items for b in budget_map.get(e.id, []))
            # only reviewer-confirmed direct implementation moves status
            direct = [
                e for l, e in pairs
                if (l.relationship or l.suggested_relationship)
                   == RelationshipType.DIRECT_IMPLEMENTATION
            ]
            # a later amendment/cancellation means the old "done" doesn't get to stand
            regressed = [e for e in direct if EvidenceFlag.REGRESSION_WARNING in e.flags]
            status, excerpt = self._best_status(
                [e for e in direct if e not in regressed])
            money = self._money.summarize(budgets, items)
            findings = list(money.findings)
            if regressed:
                findings.append(
                    "A contract or project behind the implementation evidence was later "
                    "amended or cancelled: " + ", ".join(e.title for e in regressed) + ".")
            rows.append(TrailRow(
                commitment=com,
                evidence=items,
                relationships=[l.relationship or l.suggested_relationship for l in accepted],
                budgets=budgets,
                status=status,
                status_excerpt=excerpt,
                gaps=self._gaps(com, items, budgets, direct),
                financial_states=money.states,
                financially_executed=money.executed,
                findings=findings,
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
