"""Documents: what has been ingested, and starting a new ingest.

Ingestion parses a whole PDF and can take a while with an LLM extractor,
so it runs as a background job — the client polls GET /api/jobs/{id}.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.models import SourceDocument
from ..deps import get_jobs, get_state
from ..jobs import JobRunner
from ..schemas import IngestRequest, JobOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def documents(state: AppState = Depends(get_state)) -> list[SourceDocument]:
    return state.policy.documents()


@router.post("/ingest", status_code=202)
def ingest(req: IngestRequest,
           state: AppState = Depends(get_state),
           jobs: JobRunner = Depends(get_jobs)) -> JobOut:
    # fail fast if the PDF isn't in the store — the job itself re-reads
    # it by name so the payload stays portable data
    if state.docs.read(req.name) is None:
        raise HTTPException(
            404, f"{req.name} is not in the document store")

    job = jobs.submit("ingest", {
        "name": req.name, "title": req.title,
        "publisher": req.publisher, "url": req.url,
    })
    return JobOut(**job.__dict__)
