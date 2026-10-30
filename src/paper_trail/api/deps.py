"""one AppState + one job runner per process"""

from __future__ import annotations

import hmac
from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from ..bootstrap import AppState, build_state
from .jobs import JobRunner


@lru_cache
def get_state() -> AppState:
    return build_state()


def require_review_key(request: Request, state: AppState = Depends(get_state)) -> None:
    """write gate when PAPER_TRAIL_REVIEW_KEY is set. shared secret, not real auth"""
    key = state.settings.review_key
    given = request.headers.get("x-review-key", "")
    if key and not hmac.compare_digest(given.encode(), key.encode()):
        raise HTTPException(403, "this deployment requires a review key for changes")


def _handlers():
    """kind -> handler. state resolves per call so a cleared cache can't go stale"""

    def ingest(payload: dict, progress) -> dict:
        state = get_state()
        pdf = state.docs.read(payload["name"])
        if pdf is None:
            raise LookupError(f"{payload['name']} is not in the document store")
        doc_id, n = state.ingestion.ingest(
            pdf, payload["title"], payload["publisher"], payload.get("url", "")
        )
        result: dict = {"document_id": doc_id, "candidates": n}
        if n == 0:
            # zero candidates looks like a bug, so say why
            result["warnings"] = [
                "no commitments were extracted — the layout may not "
                "match the rule parser; try an LLM extractor "
                "(PAPER_TRAIL_LLM_*) or extend the language profile",
            ]
        return result

    def find_evidence(payload: dict, progress) -> dict:
        state = get_state()
        com = state.policy.commitment(payload["commitment_id"])
        if com is None:
            raise LookupError(f"unknown commitment {payload['commitment_id']}")
        warnings: list[str] = []
        links = state.evidence_svc.find_evidence(com, progress, warnings=warnings)
        return {"links": len(links), "warnings": warnings}

    return {"ingest": ingest, "find_evidence": find_evidence}


@lru_cache
def get_jobs():
    """postgres queue in prod, in-process for dev/tests"""
    settings = get_state().settings
    if settings.database_url:
        from ..repositories.postgres.jobs import PostgresJobRunner

        return PostgresJobRunner(settings.database_url)
    return JobRunner(_handlers())
