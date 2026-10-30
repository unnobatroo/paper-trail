"""the trail: commitments + accepted evidence + gaps"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...bootstrap import AppState
from ..deps import get_state
from ..schemas import TrailRowView

router = APIRouter(prefix="/api/trail", tags=["trail"])


@router.get("")
def trail(state: AppState = Depends(get_state)) -> list[TrailRowView]:
    return [TrailRowView.from_row(r) for r in state.metrics.trail()]
