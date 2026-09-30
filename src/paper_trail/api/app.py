"""Paper Trail REST API — the production surface.

Run locally:

    uv run uvicorn paper_trail.api.app:app --app-dir src --reload

Same services as the Streamlit UI via `bootstrap.build_state`; evidence
discovery and ingestion run as background jobs — poll GET /api/jobs/{id}.
OpenAPI docs at /docs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..infrastructure.settings import load
from .routers import (
    candidates,
    commitments,
    documents,
    jobs,
    links,
    meta,
    trail,
    translate,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from .deps import get_jobs
    # Build the durable runner at boot so queued jobs orphaned by a
    # restart get claimed — otherwise they wait for the first request.
    # Cheap now that the embedder lazy-loads.
    if load().supabase_configured:
        get_jobs()
    yield
    if get_jobs.cache_info().currsize:  # only if a runner was ever built
        get_jobs().shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Paper Trail",
        version="0.2.0",
        description="From policy text to implementation evidence — "
                    "Józsefváros climate commitments under human review.",
        lifespan=_lifespan,
    )
    # load() alone for origins — building AppState here would load the
    # embedder (~GB model) at import time instead of on first request
    app.add_middleware(
        CORSMiddleware,
        allow_origins=load().api_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (meta.router, documents.router, candidates.router,
              commitments.router, links.router, trail.router,
              jobs.router, translate.router):
        app.include_router(r)
    return app


app = create_app()
