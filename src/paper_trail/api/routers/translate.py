"""machine translation for the ui, always labelled, never the source of truth"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...services.translation import get_translator
from ..deps import get_state
from ..schemas import TranslateRequest

router = APIRouter(prefix="/api/translate", tags=["translate"])


@router.post("")
def translate(req: TranslateRequest,
              state: AppState = Depends(get_state)) -> dict:
    translator = get_translator(state.profile, state.settings.hf_token,
                                model=state.settings.mt_model,
                                enabled=state.settings.environment != "production")
    if translator is None:
        raise HTTPException(
            503, "machine translation is unavailable (HF_TOKEN unset)")
    return {
        "translations": [translator.translate(t) for t in req.texts],
        "disclaimer": translator.disclaimer,
    }
