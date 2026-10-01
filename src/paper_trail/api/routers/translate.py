"""Source-language→English machine translation — always labelled, never
authoritative."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...ml.lang import get_profile
from ...services.translation import get_translator
from ..deps import get_state
from ..schemas import TranslateRequest

router = APIRouter(prefix="/api/translate", tags=["translate"])


@router.post("")
def translate(req: TranslateRequest,
              state: AppState = Depends(get_state)) -> dict:
    translator = get_translator(get_profile(state.settings.language),
                                model=state.settings.mt_model)
    if translator is None:
        raise HTTPException(
            503, "machine translation is unavailable (HF_TOKEN unset)")
    return {
        "translations": [translator.translate(t) for t in req.texts],
        "disclaimer": translator.disclaimer,
    }
