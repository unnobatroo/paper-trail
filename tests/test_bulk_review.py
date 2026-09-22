"""Bulk review actions + list filtering — the batch UX's state logic."""

from paper_trail.domain.enums import (
    CandidateType,
    RelationshipType,
    ReviewStatus,
)
from paper_trail.domain.models import (
    Commitment,
    EvidenceItem,
    EvidenceLink,
    PolicyCandidate,
    SourceDocument,
)
from paper_trail.presentation.filters import filter_candidates
from paper_trail.services.review_service import ReviewService


def _cand(document_id: int, title: str,
          kind: CandidateType = CandidateType.MEASURE,
          code: str | None = None) -> PolicyCandidate:
    return PolicyCandidate(
        document_id=document_id, suggested_type=kind,
        text=title + " text", normalized_title=title,
        source_page=1, source_excerpt=title + " text", code=code)


def _seed(policy, titles) -> list[int]:
    doc_id = policy.add_document(SourceDocument(title="S", publisher="P"))
    return [policy.add_candidate(_cand(doc_id, t)) for t in titles]


def test_confirm_candidates_bulk(policy, evidence):
    ids = _seed(policy, ["Utcafásítás", "Közösségi kertek", "Kerékpárutak"])
    review = ReviewService(policy, evidence)

    n = review.confirm_candidates(ids[:2])

    assert n == 2
    remaining = [c.id for c in review.queue()]
    assert remaining == [ids[2]]
    coms = policy.commitments()
    assert len(coms) == 2
    assert {c.title for c in coms} == {"Utcafásítás", "Közösségi kertek"}


def test_reject_candidates_bulk(policy, evidence):
    ids = _seed(policy, ["A", "B", "C"])
    review = ReviewService(policy, evidence)

    review.reject_candidates([ids[0], ids[2]])

    assert [c.id for c in review.queue()] == [ids[1]]
    rejected = policy.candidates(ReviewStatus.REJECTED)
    assert {c.id for c in rejected} == {ids[0], ids[2]}


def test_accept_links_bulk_keeps_chosen_relationship(policy, evidence):
    ids = _seed(policy, ["Utcafásítás"])
    review = ReviewService(policy, evidence)
    com_id = review.accept_candidate(ids[0])

    ev_ids = [
        evidence.add_evidence(EvidenceItem(
            commitment_id=com_id, url=f"https://rev8.hu/{i}",
            title=f"Page {i}"))
        for i in range(2)
    ]
    link_ids = [
        evidence.add_link(EvidenceLink(
            commitment_id=com_id, evidence_id=ev_ids[i],
            suggested_relationship=RelationshipType.INDIRECT))
        for i in range(2)
    ]

    review.accept_links(
        link_ids,
        {link_ids[1]: RelationshipType.DIRECT_IMPLEMENTATION},
    )

    links = {l.id: l for l in evidence.links()}
    assert all(l.review_status == ReviewStatus.ACCEPTED for l in links.values())
    # untouched link keeps its suggested relationship; the override wins
    assert links[link_ids[0]].relationship == RelationshipType.INDIRECT
    assert links[link_ids[1]].relationship == RelationshipType.DIRECT_IMPLEMENTATION


def test_filter_candidates_by_status_type_query(policy):
    ids = _seed(policy, ["Utcafásítás", "Közösségi kertek"])
    policy.set_candidate_status(ids[0], ReviewStatus.ACCEPTED)
    cands = policy.candidates()

    pending = filter_candidates(cands, status_label="Needs review")
    assert [c.id for c in pending] == [ids[1]]

    confirmed = filter_candidates(cands, status_label="Confirmed")
    assert [c.id for c in confirmed] == [ids[0]]

    assert len(filter_candidates(cands, status_label="All")) == 2
    assert [c.id for c in filter_candidates(cands, query="kertek",
                                            status_label="All")] == [ids[1]]
    assert filter_candidates(cands, type_label="Targets",
                             status_label="All") == []
