"""Job polling — GET /api/jobs/{id} while a long task runs, and
GET /api/jobs?kind= for what's in flight, so a reload or another tab can
pick running work back up."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_jobs
from ..jobs import JobRunner
from ..schemas import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def active_jobs(kind: str, jobs: JobRunner = Depends(get_jobs)) -> list[JobOut]:
    return [JobOut(**j.__dict__) for j in jobs.active(kind)]


@router.get("/{job_id}")
def job(job_id: str, jobs: JobRunner = Depends(get_jobs)) -> JobOut:
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, f"unknown job {job_id}")
    return JobOut(**j.__dict__)
