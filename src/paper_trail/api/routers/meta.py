"""health checks + what this deployment runs"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...bootstrap import AppState
from ...services.translation import get_translator
from ..deps import get_state
from ..schemas import MetaOut

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@router.get("/readyz")
def readyz(state: AppState = Depends(get_state)) -> dict:
    try:
        if state.settings.database_url:
            import psycopg
            with psycopg.connect(state.settings.database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM jobs LIMIT 1")
                    cur.execute("INSERT INTO readiness_probe(id,checked_at) VALUES(1,now()) "
                                "ON CONFLICT(id) DO UPDATE SET checked_at=excluded.checked_at")
                conn.rollback()
        else:
            import sqlite3
            with sqlite3.connect(state.settings.db_path) as conn:
                conn.execute("CREATE TEMP TABLE paper_trail_probe (value integer)")
                conn.execute("INSERT INTO paper_trail_probe VALUES (1)")
                conn.rollback()
    except Exception as exc:
        raise HTTPException(503, "storage readiness check failed") from exc
    return {"ok": True}


@router.get("/api/meta")
def meta(state: AppState = Depends(get_state)) -> MetaOut:
    s = state.settings
    return MetaOut(**{
        "deployment": s.deployment,
        "storage": "postgres" if s.database_url else "sqlite",
        "embed_model": s.embed_model,
        "reranker": s.reranker_model,
        "search_provider": s.search_provider,
        "llm_extraction": s.llm_configured,
        "review_required": bool(s.review_key),
        "translation": get_translator(
            state.profile, s.hf_token, enabled=s.environment != "production") is not None,
        "language_profile_loaded": bool(state.profile.status_rules),
        "language_name": state.profile.name if state.profile.status_rules else "",
        "glossary": [{"term": t, "meaning": m} for t, m in state.profile.glossary.items()],
    })
