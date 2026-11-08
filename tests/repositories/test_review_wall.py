"""the db keeps the worker off reviewed rows, whatever the python does"""

from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from paper_trail.domain.enums import BudgetKind, CandidateType, ReviewStatus
from paper_trail.domain.models import BudgetRecord, Commitment, EvidenceItem, EvidenceLink
from paper_trail.repositories.store import EvidenceRepository


def _evidence(policy, evidence, url: str, status: ReviewStatus | None) -> int:
    c = policy.add_commitment(Commitment(kind=CandidateType.MEASURE, title="plant trees"))
    ev_id = evidence.add_evidence(EvidenceItem(commitment_id=c, url=url, title="t", snippet="s"))
    link_id = evidence.add_link(EvidenceLink(commitment_id=c, evidence_id=ev_id, score=0.5))
    if status:
        evidence.decide_link(link_id, status)
    return ev_id


def _worker_adds_budget(dsn: str, ev_id: int) -> None:
    # owner logs in, then drops to the worker role, same grants and triggers as prod
    with psycopg.connect(dsn) as conn:
        conn.execute("SET ROLE paper_trail_worker")
        conn.execute("INSERT INTO budgets(evidence_id, kind, amount_raw)"
                     " VALUES (%s, 'actual_expenditure', '2,5 millió Ft')", (ev_id,))


@pytest.mark.parametrize("status", [ReviewStatus.ACCEPTED, ReviewStatus.REJECTED])
def test_worker_cannot_add_money_to_reviewed_evidence(dsn, policy, evidence, status):
    ev_id = _evidence(policy, evidence, "https://jozsefvaros.hu/zarszamadas", status)
    with pytest.raises(psycopg.DatabaseError, match="reviewed evidence") as exc:
        _worker_adds_budget(dsn, ev_id)
    assert exc.value.sqlstate == "PTR01"
    assert evidence.budgets_for_evidence(ev_id) == []


def test_worker_can_add_money_to_unreviewed_evidence(dsn, policy, evidence):
    ev_id = _evidence(policy, evidence, "https://jozsefvaros.hu/koltsegvetes", None)
    _worker_adds_budget(dsn, ev_id)
    [b] = evidence.budgets_for_evidence(ev_id)
    assert b.amount_raw == "2,5 millió Ft"


def test_store_skips_money_when_a_reviewer_got_there_first(dsn, policy, evidence):
    # the race: worker checked "not reviewed", then a reviewer clicked before the money landed
    ev_id = _evidence(policy, evidence, "https://jozsefvaros.hu/rendelet", ReviewStatus.ACCEPTED)
    # conftest gives both app roles the password test-only
    as_worker = urlunsplit(urlsplit(dsn)._replace(
        netloc=f"paper_trail_worker:test-only@{urlsplit(dsn).hostname}:{urlsplit(dsn).port}"))
    worker = EvidenceRepository(as_worker)
    assert worker.add_budget(BudgetRecord(
        evidence_id=ev_id, kind=BudgetKind.ACTUAL_EXPENDITURE, amount_raw="1 millió Ft")) is None
    assert evidence.budgets_for_evidence(ev_id) == []
