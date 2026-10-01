"""HU→EN machine translation — always labelled, never authoritative."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...services.translation import MT_DISCLAIMER, get_translator
from ..schemas import TranslateRequest

router = APIRouter(prefix="/api/translate", tags=["translate"])


@router.post("")
def translate(req: TranslateRequest) -> dict:
    translator = get_translator()
    if translator is None:
        raise HTTPException(
            503, "machine translation is unavailable (HF_TOKEN unset)")
    return {
        "translations": [translator.translate(t) for t in req.texts],
        "disclaimer": MT_DISCLAIMER,
    }
