"""End-to-end pipeline, fully offline: fixture search + cached fetches +
hashing embedder. Exercises ingest → review → evidence → trail."""

import hashlib
import json

from paper_trail.domain.enums import (
    CandidateType,
    RelationshipType,
    ReviewStatus,
    Status,
)
from paper_trail.domain.models import DocumentPage, PolicyCandidate, SourceDocument
from paper_trail.ml.embeddings import HashingProvider
from paper_trail.ml.extraction import Extractor
from paper_trail.repositories.store import EvidenceRepository, PolicyRepository
from paper_trail.services.evidence_service import EvidenceService
from paper_trail.services.metrics_service import MetricsService
from paper_trail.services.review_service import ReviewService
from paper_trail.sources.web_search import FixtureSearch

EVIDENCE_URL = "https://rev8.hu/utcafasitas/"
EVIDENCE_TEXT = (
    "Utcafásítás Józsefvárosban. A RÉV8 Zrt. 2024-ben mintegy 100 fa "
    "ültetését tervezi a Bérkocsis utcában és környékén. A programra "
    "2 000 000 Ft költségkeret áll rendelkezésre. A munkák elkészültek."
)


class _FakeExtractor(Extractor):
    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        return [PolicyCandidate(
            document_id=0, suggested_type=CandidateType.MEASURE,
            text="Utcai fák ültetése", normalized_title="Utcafásítás",
            source_page=1, source_excerpt=pages[0].text,
            code="A1.1.1", responsible_org="RÉV8 Zrt.",
        )]


def _seed_fetch_cache(cache_dir, url, text):
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    (cache_dir / f"{key}.txt").write_text(text, encoding="utf-8")
    (cache_dir / f"{key}.json").write_text(
        json.dumps({"title": "Utcafásítás", "date": None}), encoding="utf-8"
    )


def _fixture_search(tmp_path):
    f = tmp_path / "search_results.jsonl"
    f.write_text(json.dumps({
        "query_substring": "utcafásítás",
        "url": EVIDENCE_URL, "title": "Utcafásítás", "snippet": "...",
    }))
    return FixtureSearch(f)


def test_full_pipeline(policy: PolicyRepository, evidence: EvidenceRepository,
                       tmp_path):
    # 1. ingest — a document lands, candidates carry page + excerpt
    doc_id = policy.add_document(SourceDocument(title="t", publisher="p"))
    cand = _FakeExtractor().extract([DocumentPage(page_number=1, text="x")])[0]
    cand.document_id = doc_id
    cand_id = policy.add_candidate(cand)

    review = ReviewService(policy, evidence)
    assert len(review.queue()) == 1

    # 2. human accepts the candidate → searchable commitment
    com_id = review.accept_candidate(cand_id)
    assert review.queue() == []
    com = policy.commitment(com_id)
    assert com.code == "A1.1.1"

    # rejected candidates never become commitments
    cand2 = policy.add_candidate(PolicyCandidate(
        document_id=doc_id, text="noise", normalized_title="noise",
        source_page=2, source_excerpt="noise"))
    review.reject_candidate(cand2)
    assert len(policy.commitments()) == 1

    # 3. evidence discovery — bounded, allowlisted, offline fixtures
    cache = tmp_path / "fetched"
    cache.mkdir()
    _seed_fetch_cache(cache, EVIDENCE_URL, EVIDENCE_TEXT)
    svc = EvidenceService(evidence, _fixture_search(tmp_path),
                          HashingProvider(), cache_dir=cache,
                          fetcher=lambda url: None)
    links = svc.find_evidence(com)
    assert links  # proposed at least one link
    assert all(evidence.evidence(l.evidence_id).url == EVIDENCE_URL
               for l in links)
    ev = evidence.evidence(links[0].evidence_id)
    assert ev.status_hint in (Status.COMPLETED, Status.PLANNED)
    assert evidence.budgets_for_evidence(ev.id)  # money parsed from source

    # 4. human reviews the link → tracker
    link = links[0]
    review.accept_link(link.id, RelationshipType.DIRECT_IMPLEMENTATION)
    assert evidence.link(link.id).review_status == ReviewStatus.ACCEPTED

    trail = MetricsService(policy, evidence).trail()
    assert len(trail) == 1
    row = trail[0]
    assert row.evidence and row.budgets
    assert row.status != Status.UNKNOWN
    assert "We haven't found evidence that this has happened yet." not in row.gaps


def test_gaps_when_nothing_found(policy: PolicyRepository,
                                 evidence: EvidenceRepository):
    from paper_trail.domain.models import Commitment
    policy.add_commitment(Commitment(
        kind=CandidateType.MEASURE, title="Üres intézkedés"))
    rows = MetricsService(policy, evidence).trail()
    assert rows[0].gaps == [
        "No implementation evidence found yet.",
        "No measurable target was stated.",
        "No confirmed budget found.",
    ]
