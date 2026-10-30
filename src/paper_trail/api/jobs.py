"""in-process job runner for dev/tests. prod uses repositories/postgres/jobs.py"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from ..domain.jobs import IN_FLIGHT, Handler, Job


class JobRunner:
    """thread pool runner, state dies with the process"""

    _KEEP = 500  # evict finished jobs past this

    def __init__(self, handlers: dict[str, Handler], max_workers: int = 4):
        self._jobs: dict[str, Job] = {}
        self._handlers = handlers
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, kind: str, payload: dict | None = None) -> Job:
        payload = payload or {}
        for job in self._jobs.values():
            if (job.kind == kind and job.payload == payload
                    and job.status in IN_FLIGHT):
                return job
        if len(self._jobs) >= self._KEEP:
            self._jobs = {i: j for i, j in self._jobs.items()
                          if j.status in IN_FLIGHT}
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
        return [j for j in self._jobs.values() if j.kind == kind and j.status in IN_FLIGHT]

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)
