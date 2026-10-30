"""review the suggested commitment <-> evidence links"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...domain.enums import ReviewStatus
from ...services.metrics_service import with_effective_flags
from ..deps import get_state, require_review_key
from ..schemas import BulkLinksRequest, LinkDecisionRequest, LinkView

router = APIRouter(prefix="/api/links", tags=["links"])


def _views(state: AppState, links: list,
           lite: bool = False) -> list[LinkView]:
    """batch lookups, per-link calls turn 500 links into 1000 round trips"""
    ids = sorted({l.evidence_id for l in links})
    ev_map = state.evidence.evidence_many(ids)
    with_effective_flags(state.evidence, ev_map)
    if lite:
        for ev in ev_map.values():
            ev.snippet = ""
            ev.status_excerpt = None
            ev.organisations = []
            ev.locations = []
            ev.dates_mentioned = []
    budget_map = {} if lite else state.evidence.budgets_many(ids)
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
          lite: bool = False,
          state: AppState = Depends(get_state)) -> list[LinkView]:
    rows = (state.evidence.links_for(commitment_id)
            if commitment_id is not None
            else state.evidence.links(status))
    if commitment_id is not None and status is not None:
        rows = [l for l in rows if l.review_status == status]
    return _views(state, rows, lite)


@router.get("/{link_id}")
def link(link_id: int,
         state: AppState = Depends(get_state)) -> LinkView:
    row = state.evidence.link(link_id)
    if row is None:
        raise HTTPException(404, f"unknown link {link_id}")
    return _views(state, [row])[0]


@router.post("/{link_id}/decide",
             dependencies=[Depends(require_review_key)])
def decide(link_id: int, req: LinkDecisionRequest,
           state: AppState = Depends(get_state)) -> dict:
    if state.evidence.link(link_id) is None:
        raise HTTPException(404, f"unknown link {link_id}")
    if req.decision == "accept":
        state.review.accept_link(link_id, req.relationship)
    else:
        state.review.reject_link(link_id)
    return {"ok": True}


@router.post("/bulk", dependencies=[Depends(require_review_key)])
def bulk(req: BulkLinksRequest,
         state: AppState = Depends(get_state)) -> dict:
    return {
        "accepted": state.review.accept_links(req.accept, req.relationships),
        "rejected": state.review.reject_links(req.reject),
    }
