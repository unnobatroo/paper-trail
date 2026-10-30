"""commitments + kicking off evidence search (minutes long, so it's a job)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.models import Commitment
from ..deps import get_jobs, get_state, require_review_key
from ..jobs import JobRunner
from ..schemas import JobOut, JurisdictionRequest

router = APIRouter(prefix="/api/commitments", tags=["commitments"])


@router.get("")
def commitments(state: AppState = Depends(get_state)) -> list[Commitment]:
    return state.policy.commitments()


@router.post("/{commitment_id}/find-evidence", status_code=202,
             dependencies=[Depends(require_review_key)])
def find_evidence(commitment_id: int,
                  state: AppState = Depends(get_state),
                  jobs: JobRunner = Depends(get_jobs)) -> JobOut:
    if state.policy.commitment(commitment_id) is None:
        raise HTTPException(404, f"unknown commitment {commitment_id}")

    job = jobs.submit("find_evidence", {"commitment_id": commitment_id})
    return JobOut(**job.__dict__)


@router.post("/{commitment_id}/jurisdiction", dependencies=[Depends(require_review_key)])
def set_jurisdiction(commitment_id: int, req: JurisdictionRequest,
                     state: AppState = Depends(get_state)) -> Commitment:
    """reviewer picks the asset owner, next search follows it"""
    try:
        state.review.set_jurisdiction(commitment_id, req.jurisdiction)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return state.policy.commitment(commitment_id)
