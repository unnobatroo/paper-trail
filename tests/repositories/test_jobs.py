"""postgres job queue: dedupe, one claim per job, leases, retries"""

from concurrent.futures import ThreadPoolExecutor

import psycopg

from paper_trail.repositories.postgres.jobs import PostgresJobRunner, PostgresWorker


def _sql(dsn, sql, *params):
    with psycopg.connect(dsn) as conn:
        conn.execute(sql, params)


def test_racing_submits_share_one_waiting_job(dsn):
    queue = PostgresJobRunner(dsn)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: queue.submit("echo", {"x": 42}), range(8)))
    assert len({j.id for j in jobs}) == 1
    assert [j.id for j in queue.active("echo")] == [jobs[0].id]
    assert queue.get(jobs[0].id).payload == {"x": 42} and queue.get("nope") is None


def test_only_one_worker_claims_and_runs_with_progress(dsn):
    queue = PostgresJobRunner(dsn)
    job = queue.submit("echo", {"x": 42})

    def echo(payload, progress):
        progress("halfway")
        return payload["x"]

    w1, w2 = (PostgresWorker(dsn, {"echo": echo}) for _ in range(2))
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda w: w.claim(), [w1, w2]))
    assert sum(c is not None for c in claims) == 1
    # put it back and let run_once do the whole thing
    _sql(dsn, "UPDATE jobs SET status='queued', worker_id=NULL WHERE id=%s", job.id)
    assert w1.run_once() and not w1.run_once()
    done = queue.get(job.id)
    assert (done.status, done.result, done.progress, done.error) == ("done", 42, "halfway", None)


def test_stale_lease_goes_back_to_the_queue_and_fences_the_old_owner(dsn):
    queue = PostgresJobRunner(dsn)
    job = queue.submit("echo", {"x": 1})
    owner = PostgresWorker(dsn, {})
    row = owner.claim()
    _sql(dsn, "UPDATE jobs SET heartbeat_at=now()-interval '10 minutes' WHERE id=%s", job.id)
    PostgresWorker(dsn, {}).recover()
    back = queue.get(job.id)
    assert (back.status, back.error) == ("queued", "worker lease expired")
    assert owner._owned(row, "UPDATE jobs SET status='done'") == 0


def test_network_errors_retry_everything_else_fails(dsn):
    queue = PostgresJobRunner(dsn)

    def timeout(payload, progress):
        raise TimeoutError("temporary network timeout")

    def broken(payload, progress):
        raise ValueError("bad payload")

    retry, fail = queue.submit("timeout"), queue.submit("broken")
    PostgresWorker(dsn, {"timeout": timeout, "broken": broken}).run_once()
    PostgresWorker(dsn, {"timeout": timeout, "broken": broken}).run_once()
    assert queue.get(retry.id).status == "queued"
    assert queue.get(retry.id).error == "TimeoutError: temporary network timeout"
    assert (queue.get(fail.id).status, queue.get(fail.id).error) == (
        "failed", "ValueError: bad payload")


def test_progress_after_losing_the_lease_aborts_the_job(dsn):
    queue = PostgresJobRunner(dsn)
    job = queue.submit("slow")

    def slow(payload, progress):
        _sql(dsn, "UPDATE jobs SET lease_token='stolen' WHERE id=%s", job.id)
        progress("still here?")

    PostgresWorker(dsn, {"slow": slow}).run_once()
    # the job isn't ours anymore, so the worker can't touch it either way
    assert queue.get(job.id).status == "running"
