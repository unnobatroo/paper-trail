"""SupabaseJobRunner against an in-memory stand-in for PostgREST."""

from __future__ import annotations

import time
from types import SimpleNamespace

from paper_trail.api.jobs import SupabaseJobRunner


class _Query:
    def __init__(self, rows: list[dict], op: str, values=None):
        self.rows, self.op, self.values = rows, op, values
        self.filters: list = []
        self.n: int | None = None

    def eq(self, k, v):
        self.filters.append(lambda r: r.get(k) == v)
        return self

    def in_(self, k, vs):
        self.filters.append(lambda r: r.get(k) in vs)
        return self

    def lt(self, k, v):
        self.filters.append(lambda r: r.get(k, "") < v)
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self.n = n
        return self

    def execute(self):
        if self.op == "insert":
            self.rows.append({"status": "queued", "progress": "",
                              "result": None, "error": None,
                              "created_at": "t", "claimed_by": None,
                              **self.values})
            return SimpleNamespace(data=[self.values])
        hit = [r for r in self.rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in hit:
                r.update(self.values)
        return SimpleNamespace(data=[dict(r) for r in hit[: self.n]])


class _Table:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_a):
        return _Query(self.rows, "select")

    def update(self, values):
        return _Query(self.rows, "update", values)

    def insert(self, values):
        return _Query(self.rows, "insert", values)


class _DB:
    def __init__(self):
        self.rows: list[dict] = []

    def table(self, _name):
        return _Table(self.rows)


class _Runner(SupabaseJobRunner):
    POLL_SECONDS = 3600  # tests drive _poll_once by hand

    @staticmethod
    def _client(url, key):
        return _DB()


def _wait(pred, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_job_runs_to_done():
    r = _Runner("u", "k", {"echo": lambda p, progress: p["x"]})
    job = r.submit("echo", {"x": 42})
    assert _wait(lambda: r.get(job.id).status == "done")
    assert r.get(job.id).result == 42
    r.shutdown()


def test_late_finish_cannot_resurrect_a_swept_job():
    holder = {}

    def slow(_payload, _progress):
        # the sweeper declares this worker dead mid-run...
        row = holder["r"]._db.rows[0]
        row["status"] = "failed"
        row["error"] = "worker lost mid-run"
        return "finished anyway"

    r = _Runner("u", "k", {"slow": slow})
    holder["r"] = r
    job = r.submit("slow", {})
    assert _wait(lambda: r._busy == 0)
    # ...so its late "done" must not overwrite the failure
    assert r.get(job.id).status == "failed"
    assert r.get(job.id).result is None
    r.shutdown()


def test_poller_does_not_claim_when_pool_is_full():
    r = _Runner("u", "k", {"noop": lambda p, progress: None},
                max_workers=1)
    r._db.rows.append({"id": "orphan", "kind": "noop", "payload": {},
                       "status": "queued", "updated_at": "z",
                       "claimed_by": None})
    r._busy = 1  # pretend the only worker is busy
    r._poll_once()
    assert r._db.rows[0]["status"] == "queued"
    r._busy = 0
    r._poll_once()
    assert _wait(lambda: r._db.rows[0]["status"] == "done")
    r.shutdown()
