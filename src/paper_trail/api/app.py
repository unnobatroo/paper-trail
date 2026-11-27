"""rest api, served next to the ui by `make dev`. docs at /docs, slow stuff runs as jobs"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..settings import load
from .routers import (
    candidates,
    commitments,
    documents,
    jobs,
    links,
    meta,
    trail,
    translate,
    workspace,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from .deps import get_jobs
    # build the runner at boot so jobs a restart orphaned get picked up
    jobs = get_jobs()
    yield
    jobs.shutdown()


def _redirect_to(stage: str):
    # a factory, not a default argument: fastapi would expose that as a query parameter
    def redirect() -> RedirectResponse:
        return RedirectResponse(f"/?stage={stage}")
    return redirect


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

    @app.middleware("http")
    async def cache_reads(request, call_next):
        """let a cdn cache successful GET /api responses, when the deployment is read-only"""
        response = await call_next(request)
        if (settings.api_cache_seconds and request.method == "GET"
                and request.url.path.startswith("/api/") and response.status_code == 200):
            ttl = settings.api_cache_seconds
            response.headers["cache-control"] = (
                f"public, s-maxage={ttl}, stale-while-revalidate={ttl * 10}")
        return response

    # X-Request-ID in and out, added last so it wraps the log middleware
    app.add_middleware(CorrelationIdMiddleware)
    # load() only, building AppState here would drag the embedder in at import
    settings = load()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (meta.router, documents.router, candidates.router,
              commitments.router, links.router, trail.router,
              jobs.router, translate.router, workspace.router):
        app.include_router(r)
    # The old app's bookmarks still land in the right stage.
    for old_path, stage in (("commitments", "confirm"), ("evidence", "review"), ("trail", "done")):
        app.add_api_route(f"/{old_path}", _redirect_to(stage), include_in_schema=False)
    # The review app is a single page, so a plain static mount covers it. Mounted last, so
    # the API routes win.
    if (settings.frontend_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
