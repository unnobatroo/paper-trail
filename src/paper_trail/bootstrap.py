"""Shared application wiring — one `build_state` for every front door.

The Streamlit app (app.py) and the FastAPI service (api/) both construct
the same AppState from Settings:

* repositories      — Supabase/Postgres when configured, SQLite otherwise
* page/vector cache — Postgres `pages`/`chunks` + pgvector when
                      configured, the `data/processed/fetched/` file
                      layout otherwise
* document store    — Supabase Storage bucket, else `data/source_documents/`
* ml providers      — embedder / reranker / extractor per env config

Nothing here may hold a live sqlite3 connection: the SQLite repos hold a
path and open per-operation connections, the Supabase pieces hold a
stateless HTTP client — safe inside Streamlit's cached state and inside
a long-lived FastAPI process alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .infrastructure.settings import Settings, load
from .ml.embeddings import get_provider
from .ml.extraction import get_extractor
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


def build_state(settings: Settings | None = None) -> AppState:
    settings = settings or load()
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
        vector_index = SupabaseVectorIndex(url, key)
        docs: DocumentStore = StorageDocumentStore(
            url, key, bucket=settings.storage_bucket)
    else:
        policy = PolicyRepository(settings.db_path)
        evidence = EvidenceRepository(settings.db_path)
        cache_dir = Path(settings.db_path).parent / "fetched"
        page_store = FilePageStore(cache_dir)
        vector_index = FileVectorIndex(cache_dir)
        docs = LocalDocumentStore(settings.seed_dir)

    embedder = get_provider(settings.embed_model,
                            cache_dir=str(settings.model_cache))
    extractor = get_extractor(
        settings.llm_base_url, settings.llm_api_key, settings.llm_model)
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
        ),
        metrics=MetricsService(policy, evidence),
        docs=docs,
    )
