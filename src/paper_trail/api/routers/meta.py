"""health checks + what this deployment runs"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ..deps import get_state
from ..schemas import MetaOut

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@router.get("/readyz")
def readyz(state: AppState = Depends(get_state)) -> dict:
    try:
        import psycopg
        with psycopg.connect(state.settings.database_url) as conn:
            # a real write, rolled back: proves the role can still write, not just read
            conn.execute("SELECT 1 FROM jobs LIMIT 1")
            conn.execute("INSERT INTO readiness_probe(id,checked_at) VALUES(1,now()) "
                         "ON CONFLICT(id) DO UPDATE SET checked_at=excluded.checked_at")
            conn.rollback()
    except Exception as exc:
        raise HTTPException(503, "storage readiness check failed") from exc
    return {"ok": True}


@router.get("/api/meta")
def meta(state: AppState = Depends(get_state)) -> MetaOut:
    s = state.settings
    return MetaOut(**{
        "deployment": s.deployment,
        "storage": "postgres",
        "embed_model": s.embed_model,
        "reranker": s.reranker_model,
        "search_provider": s.search_provider,
        "llm_extraction": s.llm_configured,
        "review_required": bool(s.review_key),
        "translation": s.translation,
        "language_profile_loaded": bool(state.profile.status_rules),
        "language_name": state.profile.name if state.profile.status_rules else "",
        "glossary": [{"term": t, "meaning": m} for t, m in state.profile.glossary.items()],
    })
