"""confirm queue: accept turns a candidate into a commitment"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.enums import ReviewStatus
from ...sources import pdf_page
from ..deps import get_state, require_review_key
from ..schemas import (
    AcceptCandidateRequest,
    BulkCandidatesRequest,
    CandidateView,
    HighlightBox,
    PageHighlight,
)

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("")
def candidates(status: ReviewStatus | None = None,
               state: AppState = Depends(get_state)
               ) -> list[CandidateView]:
    rows = state.policy.candidates(status)
    notes = state.policy.notes("candidate", [c.id for c in rows])
    return [CandidateView(**c.model_dump(), note=notes.get(c.id)) for c in rows]


@router.get("/{candidate_id}/highlight")
def highlight(candidate_id: int, state: AppState = Depends(get_state)) -> PageHighlight:
    """the quote's rectangles on its source page, read from the strategy's own pdf"""
    cand = state.policy.candidate(candidate_id)
    if cand is None:
        raise HTTPException(404, f"no candidate {candidate_id}")
    doc = state.policy.document(cand.document_id)
    if doc is None or not doc.url:
        raise HTTPException(404, "this strategy has no web address to read the page from")
    try:
        view = pdf_page.highlight(doc.url, cand.source_page, cand.source_excerpt)
    except pdf_page.PageMissing as exc:
        raise HTTPException(404, str(exc)) from exc
    except pdf_page.PdfUnavailable as exc:
        raise HTTPException(502, f"could not read the source page: {exc}") from exc
    return PageHighlight(
        page=cand.source_page,
        found=view.found,
        boxes=[HighlightBox(x=b.x, y=b.y, w=b.w, h=b.h) for b in view.boxes],
        image_url=f"/api/documents/{doc.id}/pages/{cand.source_page}/image",
    )


@router.post("/{candidate_id}/accept",
             dependencies=[Depends(require_review_key)])
def accept(candidate_id: int, req: AcceptCandidateRequest | None = None,
           state: AppState = Depends(get_state)) -> dict:
    req = req or AcceptCandidateRequest()
    try:
        cid = state.review.accept_candidate(
            candidate_id, kind=req.kind, title=req.title,
            parent_id=req.parent_id)
    except ValueError as exc:
        raise HTTPException(
            404 if state.policy.candidate(candidate_id) is None else 422, str(exc)) from exc
    return {"commitment_id": cid}


@router.post("/{candidate_id}/reject",
             dependencies=[Depends(require_review_key)])
def reject(candidate_id: int,
           state: AppState = Depends(get_state)) -> dict:
    if state.policy.candidate(candidate_id) is None:
        raise HTTPException(404, f"unknown candidate {candidate_id}")
    state.review.reject_candidate(candidate_id)
    return {"ok": True}


@router.post("/bulk", dependencies=[Depends(require_review_key)])
def bulk(req: BulkCandidatesRequest,
         state: AppState = Depends(get_state)) -> dict:
    try:
        accepted = state.review.confirm_candidates(req.accept)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rejected = state.review.reject_candidates(req.reject)
    if req.reject_rest:
        rejected += state.review.reject_all_pending()
    return {"accepted": accepted, "rejected": rejected}
