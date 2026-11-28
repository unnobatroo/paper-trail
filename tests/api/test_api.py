"""api smoke tests, offline: throwaway postgres, hashing embeddings, fixture search, stub fetcher"""

import json
import time

import pytest
from fastapi.testclient import TestClient

from paper_trail.sources.fetch import FetchedPage

EVIDENCE_URL = "https://rev8.hu/utcafasitas/"
EVIDENCE_TEXT = (
        "Utcafásítás Józsefvárosban. A RÉV8 Zrt. 2024-ben mintegy 100 fa "
        "ültetését tervezi. A programra 2 000 000 Ft költségkeret áll "
        "rendelkezésre. A munkák elkészültek. " * 5
)


@pytest.fixture
def state(dsn, monkeypatch):
    """AppState on a throwaway database, same object the api serves (get_state is cached)"""
    # empty strings defeat .env loading (setdefault) and mark the
    # services unconfigured → fully offline
    # empty strings beat whatever a local .env says, tests never call a real model
    for var in ("HF_TOKEN", "LLM_BASE_URL", "LLM_MODEL",
                "EMBED_BASE_URL"):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("DATABASE_URL", dsn)
    # the profile lives in the db now, load the fixture before the app boots
    from paper_trail.repositories.store import PolicyRepository
    from tests.profiles import HU
    PolicyRepository(dsn).put_language_profile("hu", HU.to_dict())
    monkeypatch.setenv("EMBED_MODEL", "hashing")
    monkeypatch.setenv("RERANKER", "none")
    monkeypatch.setenv("NER", "none")
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")
    from paper_trail.api.deps import get_state
    get_state.cache_clear()
    s = get_state()
    # never touch the network from tests
    s.evidence_svc._fetch = lambda url, domains=None: None
    yield s
    get_state.cache_clear()


@pytest.fixture
def client(state):
    from paper_trail.api.app import app
    return TestClient(app)


def test_health_and_meta(client):
    assert client.get("/healthz").json() == {"ok": True}
    meta = client.get("/api/meta").json()
    assert meta["storage"] == "postgres"
    assert meta["embed_model"] == "hashing"


def test_candidate_review_flow(client, state):
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import (
        PolicyCandidate,
        SourceDocument,
    )
    doc_id = state.policy.add_document(
        SourceDocument(title="t", publisher="p"))
    cand_id = state.policy.add_candidate(PolicyCandidate(
        document_id=doc_id, suggested_type=CandidateType.MEASURE,
        text="Utcai fák ültetése", normalized_title="Utcafásítás",
        source_page=1, source_excerpt="…fák ültetése…", excerpt_on_page=True))

    assert len(client.get("/api/candidates?status=unreviewed").json()) == 1
    r = client.post(f"/api/candidates/{cand_id}/accept", json={})
    assert r.status_code == 200
    coms = client.get("/api/commitments").json()
    assert len(coms) == 1 and coms[0]["title"] == "Utcafásítás"
    # the trail shows the commitment with its gaps, pre-evidence
    trail = client.get("/api/trail").json()
    assert trail[0]["gaps"]


def test_find_evidence_job_and_link_review(client, state):
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import Commitment, OfficialSource
    # sources are data, register the url in the db
    # migration 005 seeds it in Postgres
    state.evidence.upsert_official_source(OfficialSource(url=EVIDENCE_URL))
    # page's already in the file store, no fetch
    state.evidence_svc._pages.put(FetchedPage(
        url=EVIDENCE_URL, title="Utcafásítás", text=EVIDENCE_TEXT))
    cid = state.policy.add_commitment(Commitment(
        kind=CandidateType.MEASURE, title="Utcafásítás"))

    r = client.post(f"/api/commitments/{cid}/find-evidence")
    assert r.status_code == 202
    job_id = r.json()["id"]
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert job["status"] == "done", job
    assert job["result"]["links"] >= 1

    views = client.get("/api/links").json()
    assert views and views[0]["evidence"]["url"] == EVIDENCE_URL
    link_id = views[0]["link"]["id"]
    r = client.post(f"/api/links/{link_id}/decide",
                    json={"decision": "accept",
                          "relationship": "direct_implementation"})
    assert r.json() == {"ok": True}
    row = client.get("/api/trail").json()[0]
    assert row["evidence"] and row["status"] != "unknown"


def test_ingest_job_from_document_store(client, state, strategy_pdf):
    """a synced document ingests end to end, offline: no llm, so no candidates, and the job
    says why instead of looking like a silent bug"""
    r = client.post("/api/documents/ingest", json={
        "name": strategy_pdf.name, "title": "t", "publisher": "p"})
    assert r.status_code == 202
    job_id = r.json()["id"]
    for _ in range(600):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "done", job
    assert job["result"]["candidates"] == 0 and job["result"]["warnings"]


def test_review_key_gates_mutations(client, state):
    """with a review key POSTs need the header, GETs stay open. empty key = open review"""
    state.settings.review_key = "k"
    assert client.post("/api/candidates/1/reject").status_code == 403
    assert client.post(
        "/api/candidates/1/reject", headers={"x-review-key": "wrong"}
    ).status_code == 403
    # right key passes the gate, 404 because candidate 1 doesn't exist
    assert client.post(
        "/api/candidates/1/reject", headers={"x-review-key": "k"}
    ).status_code == 404
    assert client.get("/api/candidates").status_code == 200
    assert client.get("/api/meta").json()["review_required"] is True
    state.settings.review_key = ""


def test_unknown_ids_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.post("/api/candidates/999/reject").status_code == 404
    assert client.post(
        "/api/commitments/999/find-evidence").status_code == 404


def test_active_jobs_endpoint_lists_in_flight_work(client):
    res = client.get("/api/jobs", params={"kind": "find_evidence"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_request_id_round_trips(client):
    # asgi-correlation-id: we echo a caller's id, or mint one
    echoed = client.get("/healthz", headers={"X-Request-ID": "a" * 32})
    assert echoed.headers["X-Request-ID"] == "a" * 32
    assert len(client.get("/healthz").headers["X-Request-ID"]) == 32


def test_notes_ride_along_but_never_decide(client, state, tmp_path):
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import PolicyCandidate, SourceDocument
    from paper_trail.maintenance import main
    doc_id = state.policy.add_document(SourceDocument(title="t", publisher="p"))
    cand_id = state.policy.add_candidate(PolicyCandidate(
        document_id=doc_id, suggested_type=CandidateType.MEASURE,
        text="Utcai fák ültetése", normalized_title="Utcafásítás",
        source_page=1, source_excerpt="…fák ültetése…", excerpt_on_page=True))
    f = tmp_path / "notes.jsonl"
    f.write_text(json.dumps({"subject_kind": "candidate", "subject_id": cand_id,
                             "title_en": "Street trees", "summary_en": "plant trees on streets",
                             "suggestion": "accept", "reason_en": "a concrete measure",
                             "author": "claude"}) + "\n")
    assert main(["notes", "import", str(f)]) == 0
    assert main(["notes", "import", str(f)]) == 0  # re-import updates, no dupes

    cand = client.get("/api/candidates").json()[0]
    assert cand["note"]["title_en"] == "Street trees"
    assert cand["note"]["suggestion"] == "accept"
    # a suggestion is just text, the candidate is still waiting for a person
    assert cand["review_status"] == "unreviewed"


def test_meta_glossary_comes_from_the_profile(client):
    glossary = client.get("/api/meta").json()["glossary"]
    assert {"term": "M", "meaning": "mitigation: cutting greenhouse gas emissions"} in glossary


def test_workspace_lists_rows_with_stage_counts_and_filters(client, state):
    from paper_trail.domain.enums import CandidateType, ReviewStatus
    from paper_trail.domain.models import PolicyCandidate, SourceDocument

    doc = state.policy.add_document(SourceDocument(title="S", publisher="P", url="https://x/s.pdf"))
    for title, status in (("Fák ültetése", ReviewStatus.UNREVIEWED),
                          ("Napelemek", ReviewStatus.REJECTED)):
        cid = state.policy.add_candidate(PolicyCandidate(
            document_id=doc, suggested_type=CandidateType.MEASURE, text=title,
            normalized_title=title, source_page=3, source_excerpt=title))
        state.policy.set_candidate_status(cid, status)

    body = client.get("/api/workspace").json()
    assert [r["title"] for r in body["rows"]] == ["Fák ültetése"]
    assert body["rows"][0]["stage"] == "confirm"
    assert body["stage_counts"]["rejected"] == 1
    assert body["documents"] == {str(doc): "https://x/s.pdf"}

    rejected = client.get("/api/workspace", params={"stage": "rejected"}).json()
    assert [r["title"] for r in rejected["rows"]] == ["Napelemek"]
    assert client.get("/api/workspace", params={"q": "nincs"}).json()["rows"] == []


def test_serves_the_built_frontend_and_keeps_api_errors(state, monkeypatch, tmp_path):
    from paper_trail.api.app import create_app

    (tmp_path / "index.html").write_text("<!doctype html><title>Paper Trail</title>")
    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path))
    client = TestClient(create_app())
    assert "<title>Paper Trail</title>" in client.get("/").text
    assert client.get("/api/meta").json()["storage"] == "postgres"
    # A mistyped API path is a 404, never the app's HTML.
    missing = client.get("/api/nope")
    assert missing.status_code == 404 and "<html" not in missing.text.lower()
    # The old app's bookmarks still land in the right stage.
    old = client.get("/commitments", follow_redirects=False)
    assert old.headers["location"] == "/?stage=confirm"


def test_without_a_frontend_build_the_api_still_runs(state, monkeypatch, tmp_path):
    from paper_trail.api.app import create_app

    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path / "missing"))
    client = TestClient(create_app())
    assert client.get("/").status_code == 404
    assert client.get("/healthz").json() == {"ok": True}


def test_api_responses_are_cacheable_only_when_the_deployment_asks(state, monkeypatch):
    from paper_trail.api.app import create_app

    default = TestClient(create_app())
    assert "cache-control" not in default.get("/api/meta").headers
    monkeypatch.setenv("API_CACHE_SECONDS", "120")
    cached = TestClient(create_app())
    assert "s-maxage=120" in cached.get("/api/meta").headers["cache-control"]
    # a write is never cached, and neither are non-API paths
    assert "cache-control" not in cached.get("/healthz").headers
    assert "cache-control" not in cached.get("/api/nope").headers  # errors aren't cached
    assert "cache-control" not in cached.post("/api/meta").headers  # nor are non-GETs



# --- the strategy's own page, drawn, with the quote marked -------------------------------------

def _strategy_with_a_quote(state, url="https://city.example/plan.pdf", page=1,
                           excerpt="plant 500 new trees"):
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import PolicyCandidate, SourceDocument
    doc_id = state.policy.add_document(SourceDocument(title="t", publisher="p", url=url))
    cand_id = state.policy.add_candidate(PolicyCandidate(
        document_id=doc_id, suggested_type=CandidateType.TARGET, text="500 trees",
        normalized_title="Trees", source_page=page, source_excerpt=excerpt,
        excerpt_on_page=True))
    return doc_id, cand_id


@pytest.fixture
def city_pdf(monkeypatch):
    from paper_trail.sources import pdf_page
    from tests.sources.pdfs import make_pdf
    pdf = make_pdf(["The city will plant 500 new trees by 2030", "and cut emissions."])
    monkeypatch.setattr(pdf_page, "download", lambda url: pdf)
    _forget_pages()


def _forget_pages():
    # pages and highlights are cached per address, and every test uses the same one
    from paper_trail.sources import pdf_page
    pdf_page.highlight.cache_clear()
    pdf_page.page_image.cache_clear()


def test_a_candidates_quote_is_marked_on_its_page(client, state, city_pdf):
    doc_id, cand_id = _strategy_with_a_quote(state)
    body = client.get(f"/api/candidates/{cand_id}/highlight").json()
    assert body["found"] and body["page"] == 1 and len(body["boxes"]) == 1
    assert body["image_url"] == f"/api/documents/{doc_id}/pages/1/image"


def test_a_quote_the_page_does_not_contain_is_reported_not_guessed(client, state, city_pdf):
    _, cand_id = _strategy_with_a_quote(state, excerpt="build a bridge over the river")
    body = client.get(f"/api/candidates/{cand_id}/highlight").json()
    assert body["found"] is False and body["boxes"] == []


def test_the_page_image_is_a_cacheable_webp(client, state, city_pdf):
    doc_id, _ = _strategy_with_a_quote(state)
    r = client.get(f"/api/documents/{doc_id}/pages/1/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert "max-age" in r.headers["cache-control"]
    assert client.get(f"/api/documents/{doc_id}/pages/9/image").status_code == 404
    assert client.get(f"/api/documents/{doc_id}/pages/0/image").status_code == 422


def test_a_strategy_without_an_address_has_no_page_to_show(client, state, city_pdf):
    doc_id, cand_id = _strategy_with_a_quote(state, url="")
    assert client.get(f"/api/candidates/{cand_id}/highlight").status_code == 404
    assert client.get(f"/api/documents/{doc_id}/pages/1/image").status_code == 404
    assert client.get("/api/candidates/99999/highlight").status_code == 404


def test_a_source_that_cannot_be_read_is_a_bad_gateway(client, state, monkeypatch):
    from paper_trail.sources import pdf_page

    def refuse(url):
        raise pdf_page.PdfUnavailable("source resolves to a private address")
    monkeypatch.setattr(pdf_page, "download", refuse)
    _forget_pages()
    _, cand_id = _strategy_with_a_quote(state)
    r = client.get(f"/api/candidates/{cand_id}/highlight")
    assert r.status_code == 502 and "private address" in r.json()["detail"]
