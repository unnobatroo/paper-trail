"""Background jobs — evidence discovery and ingest take minutes, so they
run off the request thread and the client polls GET /api/jobs/{id}.

A job is data (kind + JSON payload), not a closure — that's what makes
it portable across workers. `handlers[kind](payload, progress)` does the
work; the handler registry lives in deps.py.

Two backends, same interface:

* JobRunner          in-process thread pool — dev/test only. Job state
                     dies with the process and is invisible to other
                     workers.
* SupabaseJobRunner  jobs as rows in the `jobs` table — every API worker
                     sees the same queue. Claiming is a conditional
                     UPDATE (queued → running), which PostgREST executes
                     as one atomic statement, so a job can't run twice.
                     A run whose worker dies is marked failed by the
                     stale-claim sweeper — never silently re-run.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

Handler = Callable[[dict, Callable[[str], None]], Any]

_IN_FLIGHT = ("queued", "running")


@dataclass
class Job:
    id: str
    kind: str
    payload: dict = field(default_factory=dict)
    status: str = "queued"  # queued | running | done | failed
    progress: str = ""
    result: Any = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat())


def _dedupe_key(kind: str, payload: dict) -> str:
    """Stable identity for 'the same work' — a double-submit attaches to
    the in-flight job instead of duplicating it."""
    raw = json.dumps(payload or {}, sort_keys=True)
    return f"{kind}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class JobRunner:
    """In-process runner — SQLite/dev mode only, not for deployment."""

    _KEEP = 500  # bound the dict — finished jobs are evicted past this

    def __init__(self, handlers: dict[str, Handler], max_workers: int = 4):
        self._jobs: dict[str, Job] = {}
        self._handlers = handlers
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, kind: str, payload: dict | None = None) -> Job:
        payload = payload or {}
        for job in self._jobs.values():
            if (job.kind == kind and job.payload == payload
                    and job.status in _IN_FLIGHT):
                return job
        if len(self._jobs) >= self._KEEP:
            self._jobs = {i: j for i, j in self._jobs.items()
                          if j.status in _IN_FLIGHT}
            if len(self._jobs) >= self._KEEP:
                raise RuntimeError(
                    f"more than {self._KEEP} jobs in flight")
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, payload=payload)
        self._jobs[job.id] = job
        self._pool.submit(self._run, job)
        return job

    def _run(self, job: Job) -> None:
        job.status = "running"
        try:
            job.result = self._handlers[job.kind](
                job.payload, lambda msg: setattr(job, "progress", msg))
            job.status = "done"
        except Exception as exc:
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "failed"

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def active(self, kind: str) -> list[Job]:
        return [j for j in self._jobs.values() if j.kind == kind and j.status in _IN_FLIGHT]

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)


class SupabaseJobRunner:
    """Durable queue on the `jobs` table (migration 003_jobs.sql).

    submit() inserts a queued row — a unique index on the dedupe key of
    in-flight jobs makes double-submit return the existing job. The
    claiming worker (this instance immediately, or any instance's poller
    for orphaned rows) runs it on the local pool and writes progress,
    result and status back to the row.
    """

    POLL_SECONDS = 2.0
    STALE_AFTER = timedelta(minutes=20)  # no heartbeat → worker died
    HEARTBEAT_SECONDS = 60.0  # lease renewal while a handler runs

    def __init__(self, url: str, key: str, handlers: dict[str, Handler],
                 *, max_workers: int = 4, worker_id: str | None = None):
        self._db = self._client(url, key)
        self._handlers = handlers
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._max_workers = max_workers
        self._busy = 0  # claims submitted to the pool and not yet finished
        self._busy_lock = threading.Lock()
        self._worker = worker_id or (
            f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:4]}")
        self._stop = threading.Event()
        self._poller = threading.Thread(
            target=self._poll_loop, name="paper-trail-jobs", daemon=True)
        self._poller.start()

    # -- API-facing ---------------------------------------------------------

    def submit(self, kind: str, payload: dict | None = None) -> Job:
        payload = payload or {}
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, payload=payload)
        try:
            self._db.table("jobs").insert({
                "id": job.id, "kind": kind, "payload": payload,
                "dedupe_key": _dedupe_key(kind, payload),
            }).execute()
        except Exception:
            # jobs_inflight_uq — identical work is already queued/running;
            # return that job instead of duplicating it
            rows = (self._db.table("jobs").select("*")
                    .eq("dedupe_key", _dedupe_key(kind, payload))
                    .in_("status", _IN_FLIGHT).limit(1).execute()).data
            if rows:
                return self._to_job(rows[0])
            raise
        # try to run it ourselves right away if there's room; otherwise it
        # waits queued and a poller (here or on another worker) claims it
        self._spawn(job.id)
        return job

    def active(self, kind: str) -> list[Job]:
        rows = (self._db.table("jobs").select("*").eq("kind", kind)
                .in_("status", _IN_FLIGHT).order("created_at").limit(200)
                .execute()).data
        return [self._to_job(r) for r in rows]

    def get(self, job_id: str) -> Job | None:
        res = (self._db.table("jobs").select("*")
               .eq("id", job_id).execute())
        return self._to_job(res.data[0]) if res.data else None

    def shutdown(self) -> None:
        self._stop.set()
        self._pool.shutdown(wait=False)

    # -- worker side --------------------------------------------------------

    @staticmethod
    def _client(url: str, key: str):
        from ..infrastructure.supabase_client import create

        return create(url, key)

    def _spawn(self, job_id: str) -> bool:
        """Reserve a pool slot and claim, or leave the job queued. Check and
        reserve happen under one lock, so neither concurrent submits nor
        the poller can overfill the pool."""
        with self._busy_lock:
            if self._busy >= self._max_workers:
                return False
            self._busy += 1
        self._pool.submit(self._claim_and_run, job_id)
        return True

    def _has_capacity(self) -> bool:
        with self._busy_lock:
            return self._busy < self._max_workers

    def _claim_and_run(self, job_id: str) -> None:
        """Conditional UPDATE = atomic compare-and-swap: the row goes
        queued → running only if nobody else claimed it first."""
        try:
            claimed = (self._db.table("jobs").update({
                "status": "running", "claimed_by": self._worker,
                "updated_at": _now(),
            }).eq("id", job_id).eq("status", "queued").execute())
            if claimed.data:
                self._run_claimed(claimed.data[0])
        finally:
            with self._busy_lock:
                self._busy -= 1

    def _owned(self, job_id: str):
        """Update builder scoped to a row this worker still owns. If the
        sweeper failed the job (or anyone else touched it) the write
        matches nothing, so a late finish can't resurrect it as done."""
        def update(values: dict):
            return (self._db.table("jobs").update(values).eq("id", job_id)
                    .eq("status", "running").eq("claimed_by", self._worker))
        return update

    def _run_claimed(self, row: dict) -> None:
        owned = self._owned(row["id"])

        def progress(msg: str) -> None:
            owned({"progress": msg, "updated_at": _now()}).execute()

        # heartbeat: a healthy handler that never reports progress (ingest)
        # must not look dead to the stale sweep
        done = threading.Event()

        def heartbeat() -> None:
            while not done.wait(self.HEARTBEAT_SECONDS):
                try:
                    owned({"updated_at": _now()}).execute()
                except Exception:
                    pass  # a missed beat is fine; STALE_AFTER spans many
        threading.Thread(target=heartbeat, daemon=True).start()

        try:
            result = self._handlers[row["kind"]](row["payload"], progress)
            owned({"status": "done", "result": result,
                   "updated_at": _now()}).execute()
        except Exception as exc:
            owned({"status": "failed",
                   "error": f"{type(exc).__name__}: {exc}",
                   "updated_at": _now()}).execute()
        finally:
            done.set()

    def _poll_loop(self) -> None:
        """Pick up queued rows nobody claimed (e.g. the submitting worker
        died between insert and claim) and fail stale claims."""
        while not self._stop.wait(self.POLL_SECONDS):
            try:
                self._poll_once()
            except Exception:
                pass  # transient DB errors mustn't kill the poller

    def _poll_once(self) -> None:
        self._sweep_stale()
        # a full pool would just queue claim attempts behind the running
        # jobs, so only look for work when there's room
        if not self._has_capacity():
            return
        rows = (self._db.table("jobs").select("id")
                .eq("status", "queued").order("created_at")
                .limit(1).execute()).data
        if rows:
            self._spawn(rows[0]["id"])

    def _sweep_stale(self) -> None:
        cutoff = (datetime.now(UTC) - self.STALE_AFTER).isoformat()
        self._db.table("jobs").update({
            "status": "failed",
            "error": "worker lost mid-run — resubmit to retry",
            "updated_at": _now(),
        }).eq("status", "running").lt("updated_at", cutoff).execute()

    @staticmethod
    def _to_job(row: dict) -> Job:
        return Job(
            id=row["id"], kind=row["kind"], payload=row["payload"] or {},
            status=row["status"], progress=row["progress"] or "",
            result=row["result"], error=row["error"],
            created_at=row["created_at"])


def _now() -> str:
    return datetime.now(UTC).isoformat()
