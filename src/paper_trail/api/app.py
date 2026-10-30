"""rest api, run with `make dev-api`

services come from `bootstrap.build_state`, slow work runs as jobs (poll /api/jobs/{id}),
docs at /docs
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
    # build the runner at boot so jobs orphaned by a restart get claimed (cheap, embedder is lazy)
    jobs = get_jobs() if load().supabase_configured else None
    yield
    if jobs is not None:
        jobs.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Paper Trail",
        version="0.2.0",
        description="From policy text to implementation evidence — "
                    "Józsefváros climate commitments under human review.",
        lifespan=_lifespan,
    )
    # load() only, building AppState here would pull the embedder at import time
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
