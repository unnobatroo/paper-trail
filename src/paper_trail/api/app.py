"""rest api. `make dev-api`, docs at /docs, slow stuff runs as jobs"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
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
    # build the runner at boot so jobs a restart orphaned get picked up
    jobs = get_jobs()
    yield
    jobs.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Paper Trail",
        version="0.2.0",
        description="From policy text to implementation evidence — "
                    "climate commitments under human review.",
        lifespan=_lifespan,
    )

    @app.middleware("http")
    async def request_log(request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        logging.getLogger("uvicorn.error").info(json.dumps({
            "event": "http_request", "request_id": correlation_id.get(),
            "method": request.method, "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }))
        return response

    # X-Request-ID in and out, added last so it wraps the log middleware
    app.add_middleware(CorrelationIdMiddleware)
    # load() only, building AppState here would drag the embedder in at import
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
