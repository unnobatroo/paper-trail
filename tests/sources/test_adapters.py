"""offline contracts for local provider adapters and source boundaries"""
from types import SimpleNamespace

import pytest

from paper_trail.ml.extraction import source_excerpt
from paper_trail.ml.rerank import Reranker
from paper_trail.repositories.index import reciprocal_rank_fusion
from paper_trail.sources.chunking import structure_chunks
from paper_trail.sources.parsers import FallbackDocumentParser, ParsedDocument
from paper_trail.sources.web_search import SearxngSearchProvider, allowed


def test_receipt_restores_source_bytes():
    raw = "A  fák\nültetése."
    receipt = source_excerpt(raw, "A fák ültetése.")
    assert receipt == raw
    assert source_excerpt(raw, "") is None
    assert "A fák ültetése." not in raw


def test_table_rows_and_heading_boundaries():
    row = "| " + "x" * 1500 + " |\n"
    text = "# First\n" + row * 3 + "# Second\nDone"
    chunks = structure_chunks(text)
    assert all(len(c) <= 2400 for c in chunks)
    assert all(c.count("x") % 1500 == 0 for c in chunks)
    assert not any("# First" in c and "# Second" in c for c in chunks)
    assert all(row.strip() in c for c in chunks if "x" in c)


def test_oversize_row_quarantined_not_split():
    warnings = []
    chunks = structure_chunks("before\n|" + "x" * 2500 + "|\nafter", warn=warnings.append)
    assert warnings and all("x" not in c for c in chunks)
    assert "before" in "".join(chunks) and "after" in "".join(chunks)


def test_rrf_is_rank_based_and_stable():
    scores = reciprocal_rank_fusion([[1, 2], [2, 1]])
    assert scores[1] == scores[2] == 1 / 61 + 1 / 62
    assert reciprocal_rank_fusion([[1, 1]])[1] == 1 / 61


class _RerankServer:
    """stands in for the openai sdk client, records what /rerank got"""

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def post(self, path, cast_to, body):
        assert path == "/rerank" and cast_to is object
        self.calls.append(body)
        return self.reply(body)


def test_rerank_maps_sorted_indices_and_bounds_batches():
    server = _RerankServer(lambda body: {"results": [
        {"index": i, "relevance_score": i + 0.5} for i in reversed(range(len(body["documents"])))]})
    assert Reranker(server, batch_size=2).score("q", ["a", "b", "c"]) == [0.5, 1.5, 0.5]
    assert [len(c["documents"]) for c in server.calls] == [2, 1]


def test_rerank_reads_sglang_bare_lists():
    server = _RerankServer(lambda body: [{"index": 1, "score": 0.2}, {"index": 0, "score": 0.9}])
    assert Reranker(server, model="paper-trail/bge").score("q", ["a", "b"]) == [0.9, 0.2]
    assert server.calls[0]["model"] == "paper-trail/bge"


def test_rerank_rejects_duplicate_index():
    server = _RerankServer(lambda body: {"results": [
        {"index": 0, "relevance_score": 1}, {"index": 0, "relevance_score": 1}]})
    with pytest.raises(ValueError, match="indices"):
        Reranker(server).score("q", ["a", "b"])


def test_searxng_enforces_allowlist_and_domain_scope(monkeypatch):
    calls = []
    def get(url, params, timeout):
        calls.append(params["q"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": [
            {"url": "https://rev8.hu/a", "title": "a"}, {"url": "https://evil.test/a"}]})
    monkeypatch.setattr("requests.get", get)
    provider = SearxngSearchProvider("http://search", ["rev8.hu"])
    # the caller's scope is one request; a site token smuggled in via commitment text is dropped
    hits = provider.search("site:rev8.hu trees site:evil.test")
    assert calls == ["site:rev8.hu trees"]
    assert len(hits) == 1 and hits[0].url == "https://rev8.hu/a"
    # unscoped queries fall back to the configured domains
    assert provider.search("trees")[0].url == "https://rev8.hu/a"
    assert calls[-1] == "site:rev8.hu trees"
    assert not allowed("file://rev8.hu/a", ["rev8.hu"])


def test_parser_fallback_exposes_failure():
    class Broken:
        def parse(self, content):
            raise RuntimeError("offline")
    class Stub:
        def parse(self, content):
            return ParsedDocument([], "")
    doc = FallbackDocumentParser(Broken(), Stub()).parse(b"pdf")
    assert doc.provenance["fallback_warning"] == "RuntimeError"


def test_sitemap_registers_only_allowlisted_pdf_links(monkeypatch):
    from paper_trail.sources.sitemaps import SitemapCrawler
    xml = (b'<urlset><url><loc>https://rev8.hu/strategy.pdf</loc></url>'
           b'<url><loc>https://evil.test/x.pdf</loc></url></urlset>')
    response = SimpleNamespace(raise_for_status=lambda: None, iter_content=lambda _: [xml])
    monkeypatch.setattr("paper_trail.sources.sitemaps.safe_get", lambda *a: response)
    rows = SitemapCrawler().discover(["rev8.hu"])
    assert [row.url for row in rows] == ["https://rev8.hu/strategy.pdf"]


def test_evidence_entities_see_only_matched_passage(policy, evidence, tmp_path):
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import Commitment
    from paper_trail.ml.embeddings import HashingProvider
    from paper_trail.ml.ner import Found
    from paper_trail.services.evidence_service import EvidenceService
    from paper_trail.sources.fetch import FetchedPage
    url = "https://rev8.hu/report"
    page = FetchedPage(url, "Report", "Outside entity 1999.\nMatched trees 2024.")
    seen = []

    class SpyNer:
        def find(self, text):
            seen.append(text)
            return Found()
    svc = EvidenceService(evidence, SimpleNamespace(search=lambda *a, **kw: []),
                          HashingProvider(), ner=SpyNer())
    svc._collect_urls = lambda *a: [url]
    svc._fetch_page = lambda *a: page
    svc._rank = lambda *a: [(page, "Matched trees 2024.", 0.8)]
    commitment = Commitment(kind=CandidateType.MEASURE, title="Trees")
    commitment.id = policy.add_commitment(commitment)
    svc.find_evidence(commitment)
    # the commitment title gets looked at for matching, the page only through its passage
    assert "Matched trees 2024." in seen and not any("Outside" in t for t in seen)


def test_eur_receipts_preserve_cents_without_huf_conversion():
    from paper_trail.ml.entities import extract_money
    from tests.profiles import HU
    rows = extract_money("A támogatás költségvetési kerete 10,50 EUR. A keret 10000 Ft.", HU)
    assert [(r.currency, r.amount_native, r.amount_huf) for r in rows] == [
        ("EUR", "10.50", None), ("HUF", "10000", 10000)]
    assert extract_money("A költségvetés 20 €.", HU)[0].currency == "EUR"
