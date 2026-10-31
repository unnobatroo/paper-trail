"""durable job queue: the api enqueues, workers lease and run"""

import json
import logging
import os
import socket
import threading
import uuid
from datetime import timedelta

import httpx
import requests
from sqlalchemy import text

from ..repositories.store import Repo
from . import Job, dedupe_key

log = logging.getLogger(__name__)

# network hiccups get another go, anything else is a real failure
_RETRYABLE = (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError,
              requests.Timeout, requests.ConnectionError)


def _job(row) -> Job:
    return Job(id=row["id"], kind=row["kind"], payload=row["payload"], status=row["status"],
               progress=row["progress"], result=row["result"], error=row["error"],
               created_at=row["created_at"].isoformat())


class PostgresJobRunner(Repo):
    def submit(self, kind, payload=None):
        payload = payload or {}
        key = dedupe_key(kind, payload)
        with self._engine.begin() as conn:
            # lock per key so submitters don't race, unrelated jobs untouched
            self._lock(conn, key)
            row = conn.execute(text("SELECT * FROM jobs WHERE dedupe_key=:key"
                                    " AND status IN ('queued','running')"),
                               {"key": key}).mappings().first()
            row = row or conn.execute(text(
                "INSERT INTO jobs(id, kind, payload, dedupe_key)"
                " VALUES (:id, :kind, CAST(:payload AS jsonb), :key) RETURNING *"),
                {"id": uuid.uuid4().hex, "kind": kind, "payload": json.dumps(payload),
                 "key": key}).mappings().first()
        return _job(row)

    def get(self, job_id):
        row = self._one("SELECT * FROM jobs WHERE id=:id", id=job_id)
        return _job(row) if row else None

    def active(self, kind):
        return [_job(r) for r in self._all(
            "SELECT * FROM jobs WHERE kind=:kind AND status IN ('queued','running')"
            " ORDER BY created_at LIMIT 200", kind=kind)]

    def shutdown(self):
        pass


class PostgresWorker(Repo):
    HEARTBEAT_SECONDS = 15
    LEASE_SECONDS = 120
    MAX_ATTEMPTS = 5

    def __init__(self, database_url, handlers):
        super().__init__(database_url)
        self.handlers = handlers
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.stop = threading.Event()

    def recover(self):
        self._exec(
            "UPDATE jobs SET status=CASE WHEN attempts >= :max THEN 'failed' ELSE 'queued' END,"
            " error='worker lease expired',"
            " available_at=now() + make_interval(secs => least(300, power(2, attempts)::integer)),"
            " worker_id=NULL, lease_token=NULL, claimed_by=NULL, updated_at=now()"
            " WHERE status='running' AND coalesce(heartbeat_at, locked_at, updated_at)"
            " < now() - make_interval(secs => :lease)",
            max=self.MAX_ATTEMPTS, lease=self.LEASE_SECONDS)

    def claim(self):
        return self._one(
            "WITH next AS (SELECT id FROM jobs WHERE status='queued' AND available_at<=now()"
            " ORDER BY available_at, created_at, id FOR UPDATE SKIP LOCKED LIMIT 1)"
            " UPDATE jobs j SET status='running', worker_id=:me, claimed_by=:me,"
            " lease_token=:token, locked_at=now(), heartbeat_at=now(), updated_at=now(),"
            " attempts=attempts+1 FROM next WHERE j.id=next.id RETURNING j.*",
            me=self.worker_id, token=uuid.uuid4().hex)

    def _owned(self, row, sql, **params):
        """touch the job only while we hold its lease, 0 rows = someone else has it now"""
        return self._exec(
            sql + " WHERE id=:id AND status='running' AND worker_id=:me AND lease_token=:token",
            **params, id=row["id"], me=self.worker_id, token=row["lease_token"])

    def run_once(self):
        self.recover()
        row = self.claim()
        if not row:
            return False
        done = threading.Event()

        def heartbeat():
            while not done.wait(self.HEARTBEAT_SECONDS):
                try:
                    if not self._owned(row, "UPDATE jobs SET heartbeat_at=now(), updated_at=now()"):
                        return
                except Exception:
                    log.exception("job heartbeat failed", extra={"job_id": row["id"]})

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()

        def progress(message):
            if not self._owned(row, "UPDATE jobs SET progress=:msg, heartbeat_at=now(),"
                                    " updated_at=now()", msg=message):
                raise RuntimeError("job lease lost")

        try:
            result = self.handlers[row["kind"]](row["payload"], progress)
            self._owned(row, "UPDATE jobs SET status='done', result=CAST(:result AS jsonb),"
                             " error=NULL, updated_at=now()", result=json.dumps(result))
        except Exception as exc:
            retry = isinstance(exc, _RETRYABLE) and row["attempts"] < self.MAX_ATTEMPTS
            self._owned(row, "UPDATE jobs SET status=:status, error=:error, updated_at=now(),"
                             " available_at=now() + :delay,"
                             " worker_id=NULL, lease_token=NULL, claimed_by=NULL",
                        status="queued" if retry else "failed",
                        error=f"{type(exc).__name__}: {exc}",
                        delay=timedelta(seconds=min(300, 2 ** row["attempts"])))
            log.exception("job execution failed", extra={"job_id": row["id"]})
        finally:
            done.set()
            thread.join(timeout=2)
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                if not self.run_once():
                    self.stop.wait(2)
            except Exception:
                log.exception("worker poll failed")
                self.stop.wait(2)
