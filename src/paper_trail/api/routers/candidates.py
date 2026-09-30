"""Step 1 — review extraction candidates: accept becomes a commitment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.enums import ReviewStatus
from ...domain.models import PolicyCandidate
from ..deps import get_state, require_key
from ..schemas import AcceptCandidateRequest, BulkCandidatesRequest

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("")
def candidates(status: ReviewStatus | None = None,
               state: AppState = Depends(get_state)
               ) -> list[PolicyCandidate]:
    return state.policy.candidates(status)


@router.post("/{candidate_id}/accept")
def accept(candidate_id: int, req: AcceptCandidateRequest | None = None,
           state: AppState = Depends(get_state),
           _: None = Depends(require_key)) -> dict:
    req = req or AcceptCandidateRequest()
    try:
        cid = state.review.accept_candidate(
            candidate_id, kind=req.kind, title=req.title,
            parent_id=req.parent_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"commitment_id": cid}


@router.post("/{candidate_id}/reject")
def reject(candidate_id: int,
           state: AppState = Depends(get_state),
           _: None = Depends(require_key)) -> dict:
    if state.policy.candidate(candidate_id) is None:
        raise HTTPException(404, f"unknown candidate {candidate_id}")
    state.review.reject_candidate(candidate_id)
    return {"ok": True}


@router.post("/bulk")
def bulk(req: BulkCandidatesRequest,
         state: AppState = Depends(get_state),
         _: None = Depends(require_key)) -> dict:
    accepted = state.review.confirm_candidates(req.accept)
    rejected = state.review.reject_candidates(req.reject)
    if req.reject_rest:
        rejected += state.review.reject_all_pending()
    return {"accepted": accepted, "rejected": rejected}
