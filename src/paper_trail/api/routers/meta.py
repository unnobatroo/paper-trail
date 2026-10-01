"""Health and capability discovery for the frontend."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...bootstrap import AppState
from ...ml.lang import get_profile
from ...services.translation import get_translator
from ..deps import get_state

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@router.get("/api/meta")
def meta(state: AppState = Depends(get_state)) -> dict:
    s = state.settings
    return {
        "deployment": s.deployment,
        "storage": "supabase" if s.supabase_configured else "sqlite",
        "embed_model": s.embed_model,
        "reranker": s.reranker_model,
        "search_provider": s.search_provider,
        "llm_extraction": s.llm_configured,
        "translation": get_translator(
            get_profile(s.language)) is not None,
    }
