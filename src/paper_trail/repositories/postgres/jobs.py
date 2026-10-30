"""durable job queue: the api enqueues, workers lease and run"""

import json
import logging
import os
import socket
import threading
import uuid
from datetime import timedelta

from ...domain.jobs import Job, dedupe_key
from .store import connect

log = logging.getLogger(__name__)


class PostgresJobRunner:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @staticmethod
    def _job(row):
        return Job(
            id=row["id"],
            kind=row["kind"],
            payload=row["payload"],
            status=row["status"],
            progress=row["progress"],
            result=row["result"],
            error=row["error"],
            created_at=row["created_at"].isoformat(),
        )

    def submit(self, kind, payload=None):
        payload = payload or {}
        key = dedupe_key(kind, payload)
        with connect(self.database_url) as conn:
            # lock per key so submitters don't race, unrelated jobs untouched
            conn.execute("""SELECT pg_advisory_xact_lock(hashtextextended(%s,0))""", (key,))
            row = conn.execute(
                """SELECT * FROM jobs WHERE dedupe_key=%s AND status IN ('queued','running')""",
                (key,),
            ).fetchone()
            if not row:
                row = conn.execute(
                    (
                        """INSERT INTO jobs(id,kind,payload,dedupe_key) VALUES(%s,%s,%s::jsonb,%s)
                        RETURNING *"""
                    ),
                    (uuid.uuid4().hex, kind, json.dumps(payload), key),
                ).fetchone()
        return self._job(row)

    def get(self, job_id):
        with connect(self.database_url) as conn:
            row = conn.execute("""SELECT * FROM jobs WHERE id=%s""", (job_id,)).fetchone()
        return self._job(row) if row else None

    def active(self, kind):
        with connect(self.database_url) as conn:
            rows = conn.execute(
                (
                    """SELECT * FROM jobs WHERE kind=%s AND status IN ('queued','running') ORDER BY
                    created_at LIMIT 200"""
                ),
                (kind,),
            ).fetchall()
        return [self._job(r) for r in rows]

    def shutdown(self):
        pass


class PostgresWorker:
    HEARTBEAT_SECONDS = 15
    LEASE_SECONDS = 120
    MAX_ATTEMPTS = 5

    def __init__(self, database_url, handlers):
        self.database_url = database_url
        self.handlers = handlers
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.stop = threading.Event()

    def recover(self):
        with connect(self.database_url) as conn:
            conn.execute(
                (
                    """UPDATE jobs SET status=CASE WHEN attempts >= %s THEN 'failed' ELSE 'queued'
                    END, error='worker lease expired',
                    available_at=now()+make_interval(secs=>least(300,power(2,attempts)::integer)),
                    worker_id=NULL,lease_token=NULL,claimed_by=NULL,updated_at=now() WHERE
                    status='running' AND coalesce(heartbeat_at,locked_at,updated_at) <
                    now()-make_interval(secs=>%s)"""
                ),
                (self.MAX_ATTEMPTS, self.LEASE_SECONDS),
            )

    def claim(self):
        with connect(self.database_url) as conn:
            return conn.execute(
                """WITH next AS (
                    SELECT id FROM jobs WHERE status='queued' AND available_at<=now()
                    ORDER BY available_at,created_at,id FOR UPDATE SKIP LOCKED LIMIT 1
                ) UPDATE jobs j SET status='running',worker_id=%s,claimed_by=%s,lease_token=%s,
                    locked_at=now(),heartbeat_at=now(),updated_at=now(),attempts=attempts+1
                FROM next WHERE j.id=next.id RETURNING j.*""",
                (self.worker_id, self.worker_id, uuid.uuid4().hex),
            ).fetchone()

    def _owned(self, row, sql, params=()):
        with connect(self.database_url) as conn:
            return conn.execute(
                sql + " WHERE id=%s AND status='running' AND worker_id=%s AND lease_token=%s",
                (*params, row["id"], self.worker_id, row["lease_token"]),
            ).rowcount

    def run_once(self):
        self.recover()
        row = self.claim()
        if not row:
            return False
        done = threading.Event()

        def heartbeat():
            while not done.wait(self.HEARTBEAT_SECONDS):
                try:
                    if not self._owned(
                        row, """UPDATE jobs SET heartbeat_at=now(),updated_at=now()"""
                    ):
                        return
                except Exception:
                    log.exception("job heartbeat failed", extra={"job_id": row["id"]})

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()

        def progress(message):
            if not self._owned(
                row,
                """UPDATE jobs SET progress=%s,heartbeat_at=now(),updated_at=now()""",
                (message,),
            ):
                raise RuntimeError("job lease lost")

        try:
            result = self.handlers[row["kind"]](row["payload"], progress)
            self._owned(
                row,
                """UPDATE jobs SET status='done',result=%s::jsonb,error=NULL,updated_at=now()""",
                (json.dumps(result),),
            )
        except Exception as exc:
            import httpx
            import requests

            retryable = isinstance(
                exc,
                (
                    TimeoutError,
                    ConnectionError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    requests.Timeout,
                    requests.ConnectionError,
                ),
            )
            status = "queued" if retryable and row["attempts"] < self.MAX_ATTEMPTS else "failed"
            self._owned(
                row,
                (
                    """UPDATE jobs SET status=%s,error=%s,updated_at=now(),
                    available_at=now()+%s,worker_id=NULL,lease_token=NULL,claimed_by=NULL"""
                ),
                (
                    status,
                    f"{type(exc).__name__}: {exc}",
                    timedelta(seconds=min(300, 2 ** row["attempts"])),
                ),
            )
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
