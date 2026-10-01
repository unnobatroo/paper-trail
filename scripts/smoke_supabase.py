"""Live Supabase smoke test — exercises every adapter end-to-end.

Writes clearly-marked SMOKE rows, verifies reads/writes/RPC/jobs/storage
round-trips against the real project, then deletes the rows it created.
Safe to re-run; touches nothing else.

Usage:  uv run python scripts/smoke_supabase.py
Needs SUPABASE_URL + SUPABASE_KEY (service_role) in .env or environment.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paper_trail.bootstrap import build_state
from paper_trail.domain.enums import (
    BudgetKind,
    CandidateType,
    RelationshipType,
    ReviewStatus,
    Status,
)
from paper_trail.domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    MatchFeatures,
    PolicyCandidate,
    SourceDocument,
)
from paper_trail.infrastructure.settings import load
from paper_trail.ml.embeddings import HashingProvider
from paper_trail.sources.fetch import FetchedPage

MARK = "SMOKE TEST — delete me"
SMOKE_OBJ = "smoke-test.txt"
MODEL = "hashing"

_checks: list[str] = []


def ok(name: str) -> None:
    _checks.append(name)
    print(f"  ok  {name}")


def main() -> int:
    settings = load()
    if not settings.supabase_configured:
        print("SUPABASE_URL / SUPABASE_KEY not set — nothing to verify.")
        return 1

    state = build_state(settings)
    db = state.policy._db  # same client every repo/store shares
    print(f"project: {settings.supabase_url}")

    # the marker URL rides on whatever host the deployment's registry
    # actually uses — no literals here, it follows the data
    registry = state.evidence.official_sources()
    host = urlsplit(registry[0].url).netloc if registry else "example.test"
    smoke_url = f"https://{host}/__smoke-test__/"

    created = {"doc": None, "cand": None, "com": None,
               "ev": None, "link": None, "job": None}
    try:
        # -- document store --------------------------------------------------
        names = state.docs.list()
        ok(f"Storage list ({len(names)} objects)")
        state.docs.write(SMOKE_OBJ, MARK.encode())
        try:
            assert state.docs.read(SMOKE_OBJ) == MARK.encode()
            ok("Storage write/read round-trip")
        finally:
            state.docs.delete(SMOKE_OBJ)
        assert state.docs.read(SMOKE_OBJ) is None
        ok("Storage delete")

        # -- policy repo -----------------------------------------------------
        created["doc"] = state.policy.add_document(
            SourceDocument(title=MARK, publisher="smoke", url="smoke:test"))
        assert created["doc"] == state.policy.add_document(
            SourceDocument(title=MARK, publisher="smoke", url="smoke:test"))
        ok("add_document dedupe")
        created["cand"] = state.policy.add_candidate(PolicyCandidate(
            document_id=created["doc"], suggested_type=CandidateType.MEASURE,
            text="smoke", normalized_title="smoke", source_page=1,
            source_excerpt="smoke"))
        assert created["cand"] == state.policy.add_candidate(PolicyCandidate(
            document_id=created["doc"], suggested_type=CandidateType.MEASURE,
            text="smoke", normalized_title="smoke", source_page=1,
            source_excerpt="smoke"))
        ok("add_candidate dedupe")
        created["com"] = state.policy.add_commitment(Commitment(
            candidate_id=created["cand"], kind=CandidateType.MEASURE,
            title=MARK))
        assert created["com"] == state.policy.add_commitment(Commitment(
            candidate_id=created["cand"], kind=CandidateType.MEASURE,
            title=MARK))
        ok("add_commitment dedupe (double-accept safe)")

        # -- evidence repo ---------------------------------------------------
        ev = EvidenceItem(commitment_id=created["com"], url=smoke_url,
                          title=MARK, snippet="smoke",
                          status_hint=Status.UNKNOWN)
        created["ev"] = state.evidence.add_evidence(ev)
        assert created["ev"] == state.evidence.add_evidence(ev)
        ok("add_evidence upsert")
        bid = state.evidence.add_budget(BudgetRecord(
            evidence_id=created["ev"], kind=BudgetKind.APPROVED_ALLOCATION,
            amount_huf=1000, amount_raw="1 ezer Ft", description=MARK))
        assert bid == state.evidence.add_budget(BudgetRecord(
            evidence_id=created["ev"], kind=BudgetKind.APPROVED_ALLOCATION,
            amount_huf=1000, amount_raw="1 ezer Ft", description=MARK))
        ok("add_budget dedupe")
        link = EvidenceLink(
            commitment_id=created["com"], evidence_id=created["ev"],
            features=MatchFeatures(semantic_similarity=0.9),
            suggested_relationship=RelationshipType.DIRECT_IMPLEMENTATION,
            score=0.9)
        created["link"] = state.evidence.add_link(link)
        assert created["link"] == state.evidence.add_link(link)
        ok("add_link upsert")
        state.evidence.decide_link(created["link"], ReviewStatus.ACCEPTED,
                                   RelationshipType.BUDGET)
        # re-proposing the link must not clobber the review decision
        state.evidence.add_link(link)
        kept = state.evidence.link(created["link"])
        assert kept.review_status == ReviewStatus.ACCEPTED
        assert kept.relationship == RelationshipType.BUDGET
        ok("re-run preserves review decisions")
        assert created["ev"] in state.evidence.evidence_many([created["ev"]])
        assert state.evidence.budgets_many([created["ev"]])[created["ev"]]
        ok("batch reads (evidence_many / budgets_many)")

        # -- page + vector index ---------------------------------------------
        page = FetchedPage(url=smoke_url, title=MARK, text="fák " * 100)
        state.evidence_svc._pages.put(page)
        assert state.evidence_svc._pages.get(smoke_url).title == MARK
        ok("PageStore round-trip")
        idx = state.evidence_svc._index
        assert not idx.has(page, MODEL, 2400)
        pairs = [("chunk a fák", HashingProvider().embed(["fák"])[0])]
        idx.put(page, MODEL, 2400, pairs)
        assert idx.has(page, MODEL, 2400)
        top = idx.match(pairs[0][1], "fák ültetés", MODEL, 2400, [page],
                        k=1)
        assert top and top[0][0].url == smoke_url
        ok("VectorIndex put + hybrid match RPC (dense+tsvector)")

        # -- durable jobs ----------------------------------------------------
        from paper_trail.api.jobs import SupabaseJobRunner
        def smoke_work(payload, progress):
            progress("half")
            return {"echo": payload.get("x")}

        runner = SupabaseJobRunner(
            settings.supabase_url, settings.supabase_key,
            {"smoke": smoke_work}, worker_id="smoke-test")
        try:
            job = runner.submit("smoke", {"x": 42})
            dupe = runner.submit("smoke", {"x": 42})
            assert dupe.id == job.id, "double-submit must attach"
            ok("job dedupe on submit")
            for _ in range(150):
                got = runner.get(job.id)
                if got and got.status in ("done", "failed"):
                    break
                time.sleep(0.2)
            assert got.status == "done" and got.result == {"echo": 42}, got
            created["job"] = job.id
            ok("job claim → run → durable result")
        finally:
            runner.shutdown()

        print(f"\n{len(_checks)} checks passed — cleaning up smoke rows")
        return 0

    finally:
        # remove only the marker rows this script created
        if created["link"]:
            db.table("links").delete().eq("id", created["link"]).execute()
        if created["ev"]:
            db.table("budgets").delete().eq(
                "evidence_id", created["ev"]).execute()
            db.table("evidence").delete().eq("id", created["ev"]).execute()
        if created["com"]:
            db.table("commitments").delete().eq(
                "id", created["com"]).execute()
        if created["cand"]:
            db.table("candidates").delete().eq(
                "id", created["cand"]).execute()
        if created["doc"]:
            db.table("documents").delete().eq("id", created["doc"]).execute()
        if created["job"]:
            db.table("jobs").delete().eq("id", created["job"]).execute()
        pid = db.table("pages").delete().eq("url", smoke_url).execute()
        _ = pid  # chunks cascade via FK
        print("smoke rows deleted")


if __name__ == "__main__":
    raise SystemExit(main())
