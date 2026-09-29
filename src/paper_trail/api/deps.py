"""Shared dependencies: one AppState and one job runner per process."""

from __future__ import annotations

from functools import lru_cache

from ..bootstrap import AppState, build_state
from .jobs import JobRunner


@lru_cache
def get_state() -> AppState:
    return build_state()


def _handlers():
    """kind → worker functions. `state` is resolved inside each handler —
    a fresh worker process or a cleared test cache must not keep handlers
    bound to a stale AppState."""

    def ingest(payload: dict, progress) -> dict:
        state = get_state()
        pdf = state.docs.read(payload["name"])
        if pdf is None:
            raise LookupError(
                f"{payload['name']} is not in the document store")
        doc_id, n = state.ingestion.ingest(
            pdf, payload["title"], payload["publisher"],
            payload.get("url", ""))
        return {"document_id": doc_id, "candidates": n}

    def find_evidence(payload: dict, progress) -> dict:
        state = get_state()
        com = state.policy.commitment(payload["commitment_id"])
        if com is None:
            raise LookupError(
                f"unknown commitment {payload['commitment_id']}")
        warnings: list[str] = []
        links = state.evidence_svc.find_evidence(
            com, progress, warnings=warnings)
        return {"links": len(links), "warnings": warnings}

    return {"ingest": ingest, "find_evidence": find_evidence}


@lru_cache
def get_jobs() -> JobRunner:
    """Durable Postgres-backed queue when Supabase is configured —
    otherwise the in-process runner (dev/test only)."""
    settings = get_state().settings
    if settings.supabase_configured:
        from .jobs import SupabaseJobRunner
        return SupabaseJobRunner(
            settings.supabase_url, settings.supabase_key, _handlers())
    return JobRunner(_handlers())
