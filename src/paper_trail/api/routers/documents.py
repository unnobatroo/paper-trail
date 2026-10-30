"""documents + starting an ingest (slow with an llm, so it's a job)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.models import SourceDocument
from ..deps import get_jobs, get_state, require_review_key
from ..jobs import JobRunner
from ..schemas import IngestRequest, JobOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def documents(state: AppState = Depends(get_state)) -> list[SourceDocument]:
    return state.policy.documents()


@router.get("/available")
def available(state: AppState = Depends(get_state)) -> list[str]:
    """files you can ingest"""
    return state.docs.list()


@router.post("/ingest", status_code=202,
             dependencies=[Depends(require_review_key)])
def ingest(req: IngestRequest,
           state: AppState = Depends(get_state),
           jobs: JobRunner = Depends(get_jobs)) -> JobOut:
    # fail fast on a missing file, the job re-reads it by name so the payload stays plain
    if state.docs.read(req.name) is None:
        raise HTTPException(
            404, f"{req.name} is not in the document store")

    job = jobs.submit("ingest", {
        "name": req.name, "title": req.title,
        "publisher": req.publisher, "url": req.url,
    })
    return JobOut(**job.__dict__)
