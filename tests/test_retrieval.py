"""Retrieval pipeline guarantees, fully offline:

- documents are chunked in full — no silent 60 KB-style truncation
- the emergency bound truncates AND warns, never silently
- embeddings are cached by content hash (no re-embedding on repeat runs)
- the reranker only ever sees the bounded candidate set
- links are proposed UNREVIEWED — nothing auto-accepts
- provenance (url/title) survives the pipeline
"""

import hashlib
import json

from paper_trail.domain.enums import CandidateType, ReviewStatus
from paper_trail.domain.models import Commitment
from paper_trail.ml.embeddings import HashingProvider
from paper_trail.ml.rerank import Reranker
from paper_trail.repositories.store import EvidenceRepository
from paper_trail.services.evidence_service import EvidenceService, _CHUNK
from paper_trail.sources.fetch import FetchedPage
from paper_trail.sources.web_search import SearchHit

URL = "https://rev8.hu/utcafasitas/"


class _CountingEmbedder(HashingProvider):
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return super().embed(texts)


class _RecordingReranker(Reranker):
    name = "stub"

    def __init__(self):
        self.seen = []

    def score(self, query, passages):
        self.seen.append(len(passages))
        # reverse order — rerank effect must be observable
        return list(range(len(passages)))


class _Search:
    def search(self, query, max_results=5):
        return [SearchHit(url=URL, title="t", snippet="s")]


def _svc(tmp_path, repo: EvidenceRepository, policy, text: str,
         embedder=None, **kw) -> tuple[EvidenceService, Commitment]:
    cache = tmp_path / "fetched"
    cache.mkdir(exist_ok=True)
    key = hashlib.sha256(URL.encode()).hexdigest()[:16]
    (cache / f"{key}.txt").write_text(text, encoding="utf-8")
    (cache / f"{key}.json").write_text(
        json.dumps({"title": "Utcafásítás", "date": None}))
    svc = EvidenceService(repo, _Search(),
                          embedder or _CountingEmbedder(),
                          cache_dir=cache, fetcher=lambda u: None, **kw)
    cid = policy.add_commitment(
        Commitment(kind=CandidateType.MEASURE, title="Utcafásítás"))
    return svc, policy.commitment(cid)


def test_full_document_is_chunked(policy, evidence, tmp_path):
    text = "x " * 40_000  # ~80 KB — beyond the old 60 KB boundary
    svc, _ = _svc(tmp_path, evidence, policy, text)
    chunks = svc._doc_chunks(FetchedPage(url=URL, title="t", text=text))
    assert len(chunks) == len(text) // _CHUNK + (
        1 if len(text) % _CHUNK else 0)
    assert not svc.warnings  # nothing truncated, nothing warned


def test_emergency_bound_truncates_and_warns(policy, evidence, tmp_path):
    svc, _ = _svc(tmp_path, evidence, policy, "x " * 40_000,
                  max_doc_chars=1_000)
    page = FetchedPage(url=URL, title="t", text="x " * 40_000)
    svc._doc_vectors(page)
    assert svc.warnings and "safety limit" in svc.warnings[0]
    # second call (cached) still warns — the user must always know
    svc.warnings = []
    svc._doc_vectors(page)
    assert svc.warnings


def test_embeddings_cached_by_content(policy, evidence, tmp_path):
    emb = _CountingEmbedder()
    svc, com = _svc(tmp_path, evidence, policy,
                    "fák ültetése a kerületben " * 200, embedder=emb)
    svc.find_evidence(com)
    first = emb.calls
    assert first > 1  # query + chunks
    svc.find_evidence(com)  # cached chunks — only the query re-embeds
    assert emb.calls == first + 1


def test_reranker_sees_bounded_candidates(policy, evidence, tmp_path):
    reranker = _RecordingReranker()
    svc, com = _svc(tmp_path, evidence, policy,
                    "fák és zöldfelületek " * 400,
                    reranker=reranker, candidates=20)
    svc.find_evidence(com)
    assert reranker.seen and max(reranker.seen) <= 20


def test_links_unreviewed_and_provenance(policy, evidence, tmp_path):
    svc, com = _svc(
        tmp_path, evidence, policy,
        "A RÉV8 Zrt. 2024-ben 100 fa ültetését tervezi. "
        "A munkák elkészültek. " * 5)
    links = svc.find_evidence(com)
    assert links
    assert all(l.review_status == ReviewStatus.UNREVIEWED for l in links)
    ev = evidence.evidence(links[0].evidence_id)
    assert ev.url == URL and ev.title == "Utcafásítás"
    assert ev.snippet  # the winning chunk, verbatim
