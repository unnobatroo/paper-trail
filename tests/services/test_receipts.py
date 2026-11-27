from types import SimpleNamespace

import pytest

from paper_trail.domain.enums import ReviewStatus
from paper_trail.domain.models import DocumentPage, PolicyCandidate, SourceDocument
from paper_trail.services.ingestion_service import IngestionService
from paper_trail.services.review_service import ReviewService


class ForgedExtractor:
    name = "llm:forged"

    def extract_windows(self, pages):
        yield pages, [
            PolicyCandidate(document_id=0, text="promise", normalized_title="promise",
                            source_page=page, source_excerpt=excerpt, excerpt_on_page=True)
            for page, excerpt in [(1, "real quote"), (1, "invented"), (99, "real quote"),
                                  (1, " ")]]


def test_ingestion_recomputes_receipts(policy):
    page = DocumentPage(page_number=1, text="A real quote here")
    parser = SimpleNamespace(pages=lambda _: [page])
    _, count = IngestionService(policy, ForgedExtractor(), parser=parser).ingest(
        b"pdf", "title", "publisher")
    assert count == 1
    assert [c.source_excerpt for c in policy.candidates()] == ["real quote"]


class WordingExtractor:
    """same receipts every run, the model's own wording drifts. each run is another
    model, so its checkpoints don't skip the page"""

    def __init__(self, run: int):
        self.run, self.name = run, f"llm:run{run}"

    def extract_windows(self, pages):
        yield pages, [
            PolicyCandidate(document_id=0, text=f"{what} (run {self.run})",
                            normalized_title=what, source_page=1, source_excerpt=quote)
            for what, quote in [("trees", "Plant 200 trees"), ("shrubs", "Plant 500 shrubs")]]


def test_reingest_dedupes_on_the_receipt_not_the_wording(policy):
    page = DocumentPage(page_number=1, text="Plant 200 trees. Plant 500 shrubs.")
    parser = SimpleNamespace(pages=lambda _: [page])
    def ingest(run):
        return IngestionService(policy, WordingExtractor(run), parser=parser).ingest(
            b"pdf", "t", "p")

    ingest(1)
    trees = next(c for c in policy.candidates() if c.normalized_title == "trees")
    ReviewService(policy, None).reject_candidate(trees.id)

    assert ingest(2)[1] == 2  # the page really was extracted again
    # two receipts on the page = two candidates, still the run-1 rows; the rejection stands
    rows = sorted(policy.candidates(), key=lambda c: c.id)
    assert [(c.text, c.review_status) for c in rows] == [
        ("trees (run 1)", ReviewStatus.REJECTED), ("shrubs (run 1)", ReviewStatus.UNREVIEWED)]
    # pdf text splits words ("tr ees"): whitespace isn't part of the receipt's identity
    split = PolicyCandidate(document_id=rows[0].document_id, text="other", normalized_title="x",
                            source_page=1, source_excerpt="Plant 200 tr ees")
    assert policy.add_candidate(split) == trees.id


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
