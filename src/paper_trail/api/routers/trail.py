"""the trail: commitments + accepted evidence + gaps"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...bootstrap import AppState
from ...services.metrics_service import TrailRow
from ..deps import get_state

router = APIRouter(prefix="/api/trail", tags=["trail"])


@router.get("")
def trail(state: AppState = Depends(get_state)) -> list[TrailRow]:
    return state.metrics.trail()
