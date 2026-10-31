"""opt-in integration check against an empty disposable PostgreSQL/pgvector database"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from urllib.parse import urlsplit

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from sqlalchemy.exc import DBAPIError

from paper_trail.domain.enums import BudgetKind, CandidateType, ReviewStatus
from paper_trail.domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    PolicyCandidate,
    SourceDocument,
)
from paper_trail.jobs.postgres import PostgresJobRunner, PostgresWorker
from paper_trail.repositories.db import connect
from paper_trail.repositories.index import PostgresPageStore, PostgresVectorIndex
from paper_trail.repositories.store import EvidenceRepository, PolicyRepository
from paper_trail.sources.fetch import FetchedPage


@contextmanager
def refused(what):
    # store errors come wrapped by sqlalchemy, the db one sits in .orig
    try:
        yield
    except DBAPIError as e:
        if not isinstance(e.orig, psycopg.errors.InsufficientPrivilege):
            raise
    else:
        raise AssertionError(what)


def main():
    url = os.environ["TEST_DATABASE_URL"]
    with connect(url) as conn:
        if conn.execute("SELECT to_regclass('public.documents') present").fetchone()["present"]:
            raise RuntimeError("integration checks require an empty disposable database")
        conn.execute("""DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
                CREATE ROLE paper_trail_api LOGIN;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_worker') THEN
                CREATE ROLE paper_trail_worker LOGIN;
            END IF;
        END $$""")
        # same throwaway password as the owner url, so the role urls below just swap the user
        password = urlsplit(url).password or ""
        for role in ("paper_trail_api", "paper_trail_worker"):
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)))
    subprocess.run(
        ["alembic", "-c", "db/alembic.ini", "upgrade", "head"],
        check=True,
        env={**os.environ, "DATABASE_URL": url},
    )
    api = make_conninfo(url, user="paper_trail_api")
    worker_url = make_conninfo(url, user="paper_trail_worker")
    policy, evidence = PolicyRepository(api), EvidenceRepository(api)
    ingest = PolicyRepository(worker_url)
    doc = SourceDocument(title="integration", publisher="municipality")
    assert (doc_id := ingest.add_document(doc)) == ingest.add_document(doc)
    candidate = PolicyCandidate(
        document_id=doc_id,
        text="verified receipt",
        normalized_title="verified receipt",
        source_page=1,
        source_excerpt="verified receipt",
        excerpt_on_page=True,
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: ingest.add_candidate(candidate), range(8)))
    assert len(set(ids)) == 1
    cid = ids[0]
    with refused("worker accepted a candidate"):
        ingest.set_candidate_status(cid, ReviewStatus.ACCEPTED)
    commitment = Commitment(candidate_id=cid, kind=CandidateType.MEASURE, title="verified receipt")
    with refused("worker created a commitment"):
        ingest.add_commitment(commitment)
    policy.set_candidate_status(cid, ReviewStatus.ACCEPTED)
    com_id = policy.add_commitment(commitment)
    assert com_id == policy.add_commitment(commitment)
    worker_evidence = EvidenceRepository(worker_url)
    ev = EvidenceItem(
        commitment_id=com_id,
        url="https://jozsefvaros.hu/test",
        title="test",
        published_on=date(2026, 1, 1),
        snippet="receipt",
    )
    ev_id = worker_evidence.add_evidence(ev)
    assert worker_evidence.evidence(ev_id).published_on == date(2026, 1, 1)
    link = EvidenceLink(commitment_id=com_id, evidence_id=ev_id)
    link_id = worker_evidence.add_link(link)
    b = BudgetRecord(evidence_id=ev_id, kind=BudgetKind.ESTIMATED_COST, amount_raw="100 Ft")
    assert worker_evidence.add_budget(b) == worker_evidence.add_budget(b)
    with refused("worker accepted an evidence link"):
        worker_evidence.decide_link(link_id, ReviewStatus.ACCEPTED)
    evidence.decide_link(link_id, ReviewStatus.ACCEPTED)
    assert worker_evidence.add_link(link) == link_id
    worker_evidence.add_evidence(ev.model_copy(update={"snippet": "changed"}))
    assert evidence.evidence(ev_id).snippet == "receipt"
    with connect(worker_url) as conn:
        try:
            conn.execute("UPDATE evidence SET snippet=%s WHERE id=%s", ("tampered", ev_id))
        except psycopg.errors.RaiseException:
            conn.rollback()
        else:
            raise AssertionError("worker rewrote reviewed evidence")
    # 010: artifacts, polarity, gazetteer, jurisdiction stay on the right side of the wall
    from paper_trail.domain.enums import ArtifactStatus, EvidencePolarity, Jurisdiction
    from paper_trail.ml.accountability import PassageAuditor
    worker_evidence.link_artifact("EKR001234562021", ev_id, EvidencePolarity.AFFIRMATIVE)
    cancel_id = worker_evidence.add_evidence(EvidenceItem(
        commitment_id=com_id, url="https://jozsefvaros.hu/felmondas", title="felmondás",
        snippet="felmondta", polarity=EvidencePolarity.TERMINATION,
        flags=["maintenance_only_suspect"],
        procurement_ids=["EKR001234562021"], parcels=["36542/1"]))
    art = worker_evidence.link_artifact("EKR001234562021", cancel_id,
                                        EvidencePolarity.TERMINATION)
    assert art.status == ArtifactStatus.TERMINATED and art.status_evidence_id == cancel_id
    # escalation only: a later affirmative passage can't revive a cancelled contract
    assert worker_evidence.link_artifact(
        "EKR001234562021", ev_id, EvidencePolarity.AFFIRMATIVE).status == ArtifactStatus.TERMINATED
    stored = worker_evidence.evidence(cancel_id)
    assert stored.polarity == EvidencePolarity.TERMINATION and stored.parcels == ["36542/1"]
    reviewed = evidence.evidence(ev_id)
    arts = evidence.artifacts_many([ev_id])[ev_id]
    assert "regression_warning" in PassageAuditor.effective_flags(reviewed, arts)
    worker_evidence.record_parcel("36542/1", "Kálvária tér", "https://jozsefvaros.hu/a")
    assert worker_evidence.resolve_parcel("36542/1") == "Kálvária tér"
    with connect(worker_url) as conn:
        try:
            conn.execute("UPDATE places SET confirmed=true")
        except psycopg.errors.InsufficientPrivilege:
            conn.rollback()
        else:
            raise AssertionError("worker confirmed a gazetteer entry")
    with connect(worker_url) as conn:
        try:
            # notes are owner-written suggestions, the worker can't plant one
            conn.execute("INSERT INTO notes(subject_kind, subject_id, title_en, summary_en,"
                         " suggestion, author) VALUES ('link', %s, 't', 's', 'accept', 'w')",
                         (link_id,))
        except psycopg.errors.InsufficientPrivilege:
            conn.rollback()
        else:
            raise AssertionError("worker wrote a note")
    with refused("worker changed a commitment's jurisdiction"):
        PolicyRepository(worker_url).set_commitment_jurisdiction(
            com_id, Jurisdiction.PUBLIC_UTILITY_WATER)
    policy.set_commitment_jurisdiction(com_id, Jurisdiction.PUBLIC_UTILITY_WATER)
    assert policy.commitment(com_id).asset_owner_jurisdiction == Jurisdiction.PUBLIC_UTILITY_WATER
    page = FetchedPage(url=ev.url, title="test", text="climate trees budget")
    pages, index = PostgresPageStore(worker_url), PostgresVectorIndex(worker_url)
    pages.put(page)
    index.put(page, "test", 2400, [("trees climate", [1.0, 0.0]), ("budget", [0.0, 1.0])])
    index.put(page, "test", 2400, [("trees climate", [1.0, 0.0]), ("budget", [0.0, 1.0])])
    assert index.has(page, "test", 2400)
    assert len(index.get(page, "test", 2400)) == 2
    assert index.match([1.0, 0.0], "trees", "test", 2400, [page], 2)[0][1] == "trees climate"
    queue = PostgresJobRunner(api)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: queue.submit("echo", {"x": 42}), range(8)))
    assert len({j.id for j in jobs}) == 1
    w1, w2 = [PostgresWorker(worker_url, {"echo": lambda p, progress: p["x"]}) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda w: w.claim(), [w1, w2]))
    assert sum(r is not None for r in claims) == 1
    row = next(r for r in claims if r)
    owner = w1 if row["worker_id"] == w1.worker_id else w2
    with connect(url) as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at=now()-interval '10 minutes' WHERE id=%s", (row["id"],)
        )
    w1.recover()
    assert queue.get(row["id"]).status == "queued"
    assert owner._owned(row, "UPDATE jobs SET status='done'") == 0
    with connect(url) as conn:
        conn.execute("UPDATE jobs SET available_at=now() WHERE id=%s", (row["id"],))
    assert w1.run_once()
    assert queue.get(row["id"]).result == 42

    def timeout(payload, progress):
        raise TimeoutError("temporary network timeout")

    retry = queue.submit("timeout")
    PostgresWorker(worker_url, {"timeout": timeout}).run_once()
    assert queue.get(retry.id).status == "queued"
    with connect(url) as conn:
        plan = conn.execute("SET enable_seqscan=off")
        plan = conn.execute(
            "EXPLAIN SELECT id FROM chunks ORDER BY embedding <=> %s::vector LIMIT 1",
            ("[" + ",".join(["1"] + ["0"] * 1023) + "]",),
        ).fetchall()
        assert any("chunks_embedding_hnsw" in str(r) for r in plan)
    # reset with artifacts hanging off unreviewed passages, the reviewed link stays
    from paper_trail.maintenance import reset
    assert reset(url, cache=True, everything=False, yes=False)["evidence"] >= 1
    reset(url, cache=True, everything=False, yes=True)
    assert evidence.link(link_id).review_status == ReviewStatus.ACCEPTED
    assert evidence.evidence(ev_id) is not None and evidence.evidence(cancel_id) is None
    print(
        "PostgreSQL integration passed: migrations, worker permissions, repositories, index, "
        "concurrent dedupe/claims, stale recovery, fencing, timeout retry and reset"
    )


if __name__ == "__main__":
    main()
