"""Step 3 — the paper trail: commitments plus their verified evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_state
from ..schemas import TrailRowView
from ...bootstrap import AppState

router = APIRouter(prefix="/api/trail", tags=["trail"])


@router.get("")
def trail(state: AppState = Depends(get_state)) -> list[TrailRowView]:
    return [TrailRowView.from_row(r) for r in state.metrics.trail()]
