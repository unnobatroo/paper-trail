"""Job polling — GET /api/jobs/{id} while a long task runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_jobs
from ..jobs import JobRunner
from ..schemas import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job(job_id: str, jobs: JobRunner = Depends(get_jobs)) -> JobOut:
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, f"unknown job {job_id}")
    return JobOut(**j.__dict__)
