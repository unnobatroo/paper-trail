"""documents + starting an ingest (slow with an llm, so it's a job)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Response

from ...bootstrap import AppState
from ...domain.models import SourceDocument
from ...jobs.local import JobRunner
from ...sources import pdf_page
from ..deps import get_jobs, get_state, require_review_key
from ..schemas import IngestRequest, JobOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def documents(state: AppState = Depends(get_state)) -> list[SourceDocument]:
    return state.policy.documents()


@router.get("/{document_id}/pages/{page}/image", response_class=Response)
def page_image(document_id: int, page: int = Path(ge=1),
               state: AppState = Depends(get_state)) -> Response:
    """one page of the strategy's own pdf, drawn as a small image"""
    doc = state.policy.document(document_id)
    if doc is None or not doc.url:
        raise HTTPException(404, "this strategy has no web address to read the page from")
    try:
        image = pdf_page.page_image(doc.url, page)
    except pdf_page.PageMissing as exc:
        raise HTTPException(404, str(exc)) from exc
    except pdf_page.PdfUnavailable as exc:
        raise HTTPException(502, f"could not read the source page: {exc}") from exc
    # the same page of the same file never changes, so browsers and the cdn may keep it
    return Response(image, media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=86400"})


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
