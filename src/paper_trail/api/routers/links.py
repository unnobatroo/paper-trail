"""Step 2 (cont.) — review proposed commitment↔evidence links."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.enums import ReviewStatus
from ..deps import get_state
from ..schemas import BulkLinksRequest, LinkDecisionRequest, LinkView

router = APIRouter(prefix="/api/links", tags=["links"])


def _views(state: AppState, links: list) -> list[LinkView]:
    """Batch the evidence + budget lookups — a per-link `.evidence()`
    call turns a 500-link list into 1000 round-trips."""
    ids = sorted({l.evidence_id for l in links})
    ev_map = state.evidence.evidence_many(ids)
    budget_map = state.evidence.budgets_many(ids)
    return [
        LinkView(link=l,
                 evidence=(ev := ev_map.get(l.evidence_id)),
                 budgets=(budget_map.get(l.evidence_id, [])
                          if ev else []))
        for l in links
    ]


@router.get("")
def links(status: ReviewStatus | None = None,
          commitment_id: int | None = None,
          state: AppState = Depends(get_state)) -> list[LinkView]:
    rows = (state.evidence.links_for(commitment_id)
            if commitment_id is not None
            else state.evidence.links(status))
    if commitment_id is not None and status is not None:
        rows = [l for l in rows if l.review_status == status]
    return _views(state, rows)


@router.post("/{link_id}/decide")
def decide(link_id: int, req: LinkDecisionRequest,
           state: AppState = Depends(get_state)) -> dict:
    if state.evidence.link(link_id) is None:
        raise HTTPException(404, f"unknown link {link_id}")
    if req.decision == "accept":
        state.review.accept_link(link_id, req.relationship)
    else:
        state.review.reject_link(link_id)
    return {"ok": True}


@router.post("/bulk")
def bulk(req: BulkLinksRequest,
         state: AppState = Depends(get_state)) -> dict:
    return {
        "accepted": state.review.accept_links(req.accept, req.relationships),
        "rejected": state.review.reject_links(req.reject),
    }
