"""retrieval guarantees, offline

- whole docs get chunked, no silent 60kb truncation
- the panic bound truncates AND warns
- embeddings cached by content hash, no re-embedding on repeat runs
"""

from datetime import date

from paper_trail.domain.enums import CandidateType, ReviewStatus, Status
from paper_trail.domain.models import Commitment, OfficialSource
from paper_trail.ml.embeddings import HashingProvider
from paper_trail.repositories.postgres.index import PostgresPageStore
from paper_trail.repositories.store import EvidenceRepository
from paper_trail.services.evidence_service import (
    _CHUNK,
    _CHUNK_STRIDE,
    EvidenceService,
    _Run,
)
from paper_trail.sources.fetch import FetchedPage
from paper_trail.sources.web_search import SearchHit
from tests.profiles import HU

URL = "https://rev8.hu/utcafasitas/"


class _CountingEmbedder(HashingProvider):
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return super().embed(texts)


class _RecordingReranker:
    name = "stub"

    def __init__(self):
        self.seen = []

    def score(self, query, passages):
        self.seen.append(len(passages))
        # reverse order, the rerank has to visibly do something
        return list(range(len(passages)))


class _Search:
    def search(self, query, max_results=5):
        return [SearchHit(url=URL, title="t", snippet="s")]


def _svc(tmp_path, repo: EvidenceRepository, policy, text: str,
         embedder=None, page_date=None, **kw
         ) -> tuple[EvidenceService, Commitment]:
    # the page is already fetched: sits in the page store, the fetcher never runs
    PostgresPageStore(repo.dsn).put(FetchedPage(
        URL, "Utcafásítás", text, date.fromisoformat(page_date) if page_date else None))
    svc = EvidenceService(repo, _Search(),
                          embedder or _CountingEmbedder(), fetcher=lambda u, d=None: None,
                          profile=HU, allowed_domains=("rev8.hu",), **kw)
    cid = policy.add_commitment(
        Commitment(kind=CandidateType.MEASURE, title="Utcafásítás"))
    return svc, policy.commitment(cid)


def test_source_catalogue_comes_from_db(policy, evidence, tmp_path):
    """the source registry is data: rows from the repo drive url collection + the title fallback"""
    evidence.upsert_official_source(OfficialSource(
        url="https://jozsefvaros.hu/registry-doc.pdf?ver=1",
        title="Registry title", publisher="Józsefvárosi Önkormányzat"))
    evidence.upsert_official_source(OfficialSource(
        url="https://jozsefvaros.hu/registry-doc.pdf?ver=1",
        title="Renamed", publisher="Józsefvárosi Önkormányzat"))
    sources = evidence.official_sources()
    assert len(sources) == 1  # upsert on url, not a second row
    assert sources[0].title == "Renamed"

    svc, com = _svc(tmp_path, evidence, policy, "fák " * 200)
    registry = svc._repo.official_sources()
    urls = svc._collect_urls(com, registry, svc._allowed(registry))
    assert "https://jozsefvaros.hu/registry-doc.pdf?ver=1" in urls
    # a registry url with a port still allowlists its host
    assert svc._allowed([OfficialSource(url="https://Data.Example.hu:8443/x.pdf")]) >= {
        "data.example.hu"}
    assert svc._better_title(
        "https://jozsefvaros.hu/registry-doc.pdf?ver=1",
        "registry-doc.pdf", svc._repo.official_sources()) == "Renamed"


def test_full_document_is_chunked(policy, evidence, tmp_path):
    text = "x " * 40_000  # ~80kb, past the old 60kb cutoff
    svc, _ = _svc(tmp_path, evidence, policy, text)
    page = FetchedPage(url=URL, title="t", text=text)
    run = _Run()
    svc._index_page(page, run)
    chunks = [c for c, _ in svc._index.get(page, svc._embed.model_name, _CHUNK)]
    assert len(chunks) == len(text) // _CHUNK_STRIDE + (
        1 if len(text) % _CHUNK_STRIDE else 0)
    # overlapping windows: each chunk still max _CHUNK, consecutive
    # chunks share a boundary region
    assert all(len(c) <= _CHUNK for c in chunks)
    assert chunks[0].endswith(chunks[1][: _CHUNK - _CHUNK_STRIDE])
    assert not run.warnings  # nothing truncated, nothing warned


def test_emergency_bound_truncates_and_warns(policy, evidence, tmp_path):
    svc, _ = _svc(tmp_path, evidence, policy, "x " * 40_000,
                  max_doc_chars=1_000)
    page = FetchedPage(url=URL, title="t", text="x " * 40_000)
    first, cached = _Run(), _Run()
    svc._index_page(page, first)
    assert first.warnings and "safety limit" in first.warnings[0]
    # cached call still warns, the user always has to know
    svc._index_page(page, cached)
    assert cached.warnings


def test_embeddings_cached_by_content(policy, evidence, tmp_path):
    emb = _CountingEmbedder()
    svc, com = _svc(tmp_path, evidence, policy,
                    "fák ültetése a kerületben " * 200, embedder=emb)
    svc.find_evidence(com)
    first = emb.calls
    assert first > 1  # query + chunks
    svc.find_evidence(com)  # chunks cached, only the query re-embeds
    assert emb.calls == first + 1


def test_reranker_sees_bounded_candidates(policy, evidence, tmp_path):
    reranker = _RecordingReranker()
    svc, com = _svc(tmp_path, evidence, policy,
                    "fák és zöldfelületek " * 400,
                    reranker=reranker, candidates=20)
    svc.find_evidence(com)
    assert reranker.seen and max(reranker.seen) <= 20


class _DownReranker:
    name = "down"

    def score(self, query, passages):
        raise ConnectionError("429 from the hosted reranker")


def test_reranker_outage_falls_back_to_retrieval_order(policy, evidence, tmp_path):
    svc, com = _svc(tmp_path, evidence, policy, "fák és zöldfelületek " * 400,
                    reranker=_DownReranker(), candidates=20)
    warnings: list[str] = []
    assert svc.find_evidence(com, warnings=warnings)  # still produces links
    assert any("Reranker failed" in w for w in warnings)


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


def test_pre_strategy_evidence_forced_background(policy, evidence, tmp_path):
    """published before the strategy year: 'completed' talk is about older work, so the
    hint is forced to BACKGROUND and the reasons say why
    """
    svc, com = _svc(
        tmp_path, evidence, policy,
        "A munkálatok elkészültek. " * 50,
        page_date="2019-05-01", baseline_year=2022)
    links = svc.find_evidence(com)
    assert links
    ev = evidence.evidence(links[0].evidence_id)
    assert ev.status_hint == Status.BACKGROUND
    assert ev.status_excerpt is None
    assert any("predates the strategy" in r for r in links[0].reasons)


def test_post_strategy_evidence_keeps_hint(policy, evidence, tmp_path):
    svc, com = _svc(
        tmp_path, evidence, policy,
        "A munkálatok elkészültek. " * 50,
        page_date="2024-05-01", baseline_year=2022)
    links = svc.find_evidence(com)
    assert links
    ev = evidence.evidence(links[0].evidence_id)
    assert ev.status_hint == Status.COMPLETED


def test_no_baseline_keeps_hint(policy, evidence, tmp_path):
    """no baseline year, guard stays off"""
    svc, com = _svc(
        tmp_path, evidence, policy,
        "A munkálatok elkészültek. " * 50,
        page_date="2019-05-01")
    links = svc.find_evidence(com)
    assert links
    ev = evidence.evidence(links[0].evidence_id)
    assert ev.status_hint == Status.COMPLETED
