"""Step 2 — commitments and evidence discovery.

`find_evidence` is a minutes-long pipeline (search → fetch → embed →
rerank), so it runs as a background job; poll GET /api/jobs/{id}.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.models import Commitment
from ..deps import get_jobs, get_state
from ..jobs import JobRunner
from ..schemas import JobOut

router = APIRouter(prefix="/api/commitments", tags=["commitments"])


@router.get("")
def commitments(state: AppState = Depends(get_state)) -> list[Commitment]:
    return state.policy.commitments()


@router.post("/{commitment_id}/find-evidence", status_code=202)
def find_evidence(commitment_id: int,
                  state: AppState = Depends(get_state),
                  jobs: JobRunner = Depends(get_jobs)) -> JobOut:
    if state.policy.commitment(commitment_id) is None:
        raise HTTPException(404, f"unknown commitment {commitment_id}")

    job = jobs.submit("find_evidence", {"commitment_id": commitment_id})
    return JobOut(**job.__dict__)
