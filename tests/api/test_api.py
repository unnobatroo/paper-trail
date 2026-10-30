"""api smoke tests, offline: sqlite, hashing embeddings, fixture search, stub fetcher"""

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
def state(tmp_path, monkeypatch):
    """AppState on a throwaway sqlite db, same object the api serves (get_state is cached)"""
    # empty strings defeat .env loading (setdefault) and mark the
    # services unconfigured → fully offline
    # empty strings beat whatever a local .env says, tests never call a real model
    for var in ("HF_TOKEN", "PAPER_TRAIL_LLM_BASE_URL", "PAPER_TRAIL_LLM_MODEL",
                "PAPER_TRAIL_EMBED_BASE_URL", "PAPER_TRAIL_DATABASE_URL"):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("PAPER_TRAIL_DB", str(tmp_path / "t.db"))
    # the profile lives in the db now, load the fixture before the app boots
    from paper_trail.repositories.sqlite.store import PolicyRepository
    from tests.profiles import HU
    PolicyRepository(tmp_path / "t.db").put_language_profile("hu", HU.to_dict())
    monkeypatch.setenv("PAPER_TRAIL_EMBED_MODEL", "hashing")
    monkeypatch.setenv("PAPER_TRAIL_RERANKER", "none")
    monkeypatch.setenv("PAPER_TRAIL_SEARCH", "fixture")
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
    assert meta["storage"] == "sqlite"
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
