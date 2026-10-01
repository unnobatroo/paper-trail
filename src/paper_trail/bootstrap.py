"""Shared application wiring — one `build_state` for every front door.

The FastAPI service (api/), scripts and tests all construct the same
AppState from Settings:

* repositories      — Supabase/Postgres when configured, SQLite otherwise
* page/vector cache — Postgres `pages`/`chunks` + pgvector when
                      configured, the `data/processed/fetched/` file
                      layout otherwise
* document store    — Supabase Storage bucket, else `data/source_documents/`
* ml providers      — embedder / reranker / extractor per env config

Nothing here may hold a live sqlite3 connection: the SQLite repos hold a
path and open per-operation connections, the Supabase pieces hold a
stateless HTTP client — safe to share across the FastAPI process and its
job-runner threads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .infrastructure.settings import Settings, load
from .ml.embeddings import get_provider
from .ml.extraction import get_extractor
from .ml.lang import get_profile
from .ml.rerank import get_reranker
from .repositories.cache import FilePageStore, FileVectorIndex
from .repositories.store import EvidenceRepository, PolicyRepository
from .repositories.supabase_store import (
    SupabaseEvidenceRepository,
    SupabasePolicyRepository,
)
from .services.evidence_service import EvidenceService
from .services.ingestion_service import IngestionService
from .services.metrics_service import MetricsService
from .services.review_service import ReviewService
from .sources.document_store import DocumentStore, LocalDocumentStore
from .sources.web_search import get_search_provider


@dataclass
class AppState:
    settings: Settings
    policy: PolicyRepository | SupabasePolicyRepository
    evidence: EvidenceRepository | SupabaseEvidenceRepository
    review: ReviewService
    ingestion: IngestionService
    evidence_svc: EvidenceService
    metrics: MetricsService
    docs: DocumentStore


def _baseline_year(settings: Settings, policy) -> int | None:
    """The year the tracked strategy was adopted: PAPER_TRAIL_BASELINE_YEAR
    wins, else the earliest /YYYY/MM/ segment in a document URL (uploads sit
    under dated folders on the official site)."""
    if settings.baseline_year:
        return settings.baseline_year
    years = [
        int(m.group(1))
        for d in policy.documents()
        if (m := re.search(r"/(20\d{2})/\d{2}/", d.url or ""))
    ]
    return min(years) if years else None


def build_state(settings: Settings | None = None) -> AppState:
    settings = settings or load()
    profile = get_profile(settings.language)
    if settings.supabase_configured:
        from .repositories.supabase_index import (
            SupabasePageStore,
            SupabaseVectorIndex,
        )
        from .sources.document_store import StorageDocumentStore

        url, key = settings.supabase_url, settings.supabase_key
        policy = SupabasePolicyRepository(url, key)
        evidence = SupabaseEvidenceRepository(url, key)
        page_store = SupabasePageStore(url, key)
        vector_index = SupabaseVectorIndex(
            url, key, ts_config=profile.ts_config)
        docs: DocumentStore = StorageDocumentStore(
            url, key, bucket=settings.storage_bucket)
    else:
        policy = PolicyRepository(settings.db_path)
        evidence = EvidenceRepository(settings.db_path)
        cache_dir = Path(settings.db_path).parent / "fetched"
        page_store = FilePageStore(cache_dir)
        vector_index = FileVectorIndex(
            cache_dir, stemmer_language=profile.stemmer)
        docs = LocalDocumentStore(settings.seed_dir)

    embedder = get_provider(settings.embed_model,
                            cache_dir=str(settings.model_cache))
    extractor = get_extractor(
        settings.llm_base_url, settings.llm_api_key, settings.llm_model,
        profile)
    search = get_search_provider(settings.search_provider,
                                 settings.fixture_dir)
    return AppState(
        settings=settings,
        policy=policy,
        evidence=evidence,
        review=ReviewService(policy, evidence),
        ingestion=IngestionService(policy, extractor),
        evidence_svc=EvidenceService(
            evidence, search, embedder,
            page_store=page_store,
            vector_index=vector_index,
            reranker=get_reranker(settings.reranker_model,
                                  cache_dir=str(settings.model_cache)),
            candidates=settings.rerank_candidates,
            max_doc_chars=settings.max_doc_chars,
            baseline_year=_baseline_year(settings, policy),
            profile=profile,
            allowed_domains=settings.allowed_domains,
        ),
        metrics=MetricsService(policy, evidence),
        docs=docs,
    )
