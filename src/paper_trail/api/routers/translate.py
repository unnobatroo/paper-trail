"""machine translation for the ui, always labelled, never the source of truth"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...services.translation import Translator
from ..deps import get_state
from ..schemas import TranslateRequest

router = APIRouter(prefix="/api/translate", tags=["translate"])


@router.post("")
def translate(req: TranslateRequest,
              state: AppState = Depends(get_state)) -> dict:
    s = state.settings
    if not s.translation:
        raise HTTPException(503, "machine translation is unavailable (HF_TOKEN unset)")
    translator = Translator(state.profile, s.hf_token, s.mt_model)
    return {
        "translations": [translator.translate(t) for t in req.texts],
        "disclaimer": translator.disclaimer,
    }
