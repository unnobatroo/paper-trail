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
    """a synced document ingests end to end, offline"""
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
    assert job["result"]["candidates"] > 0


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
