import pytest

from paper_trail.domain.models import DocumentPage, PolicyCandidate, SourceDocument
from paper_trail.services.ingestion_service import IngestionService
from paper_trail.services.review_service import ReviewService


class ForgedExtractor:
    def extract(self, pages):
        return [PolicyCandidate(document_id=0, text="promise", normalized_title="promise",
                                source_page=page, source_excerpt=excerpt, excerpt_on_page=True)
                for page, excerpt in [(1, "real quote"), (1, "invented"), (99, "real quote"),
                                      (1, " ")]]


def test_ingestion_recomputes_receipts(policy, monkeypatch):
    monkeypatch.setattr("paper_trail.services.ingestion_service.read_pages",
                        lambda _: [DocumentPage(page_number=1, text="A real quote here")])
    _, count = IngestionService(policy, ForgedExtractor()).ingest(b"pdf", "title", "publisher")
    assert count == 1
    assert [c.source_excerpt for c in policy.candidates()] == ["real quote"]


@pytest.mark.parametrize("verified", [None, False])
def test_review_refuses_unverified_receipts(policy, evidence, verified):
    doc = policy.add_document(SourceDocument(title="title", publisher="publisher"))
    cid = policy.add_candidate(PolicyCandidate(document_id=doc, text="promise",
        normalized_title="promise", source_page=1, source_excerpt="quote",
        excerpt_on_page=verified))
    with pytest.raises(ValueError, match="verified source receipt"):
        ReviewService(policy, evidence).accept_candidate(cid)
    assert policy.commitments() == []


def test_budget_currency_is_part_of_receipt_identity(policy, evidence):
    from paper_trail.domain.enums import BudgetKind, CandidateType
    from paper_trail.domain.models import BudgetRecord, Commitment, EvidenceItem
    cid = policy.add_commitment(Commitment(kind=CandidateType.MEASURE, title="trees"))
    eid = evidence.add_evidence(EvidenceItem(commitment_id=cid, url="https://rev8.hu/a", title="a"))
    huf = evidence.add_budget(BudgetRecord(evidence_id=eid, kind=BudgetKind.ESTIMATED_COST,
                             amount_raw="100", currency="HUF", amount_huf=100))
    eur = evidence.add_budget(BudgetRecord(evidence_id=eid, kind=BudgetKind.ESTIMATED_COST,
                             amount_raw="100", currency="EUR", amount_native="100"))
    assert huf != eur
    assert len(evidence.budgets_for_evidence(eid)) == 2
