"""wires one AppState from settings, used by the api, scripts and tests

postgres if PAPER_TRAIL_DATABASE_URL is set, else sqlite + file caches.
never keep a sqlite connection here, jobs run on other threads
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .infrastructure.settings import Settings, load
from .ml.embeddings import get_provider
from .ml.extraction import get_extractor
from .ml.lang import LanguageProfile
from .ml.rerank import get_reranker
from .repositories.ports import EvidenceStore, PolicyStore
from .repositories.sqlite.files import FilePageStore, FileVectorIndex
from .repositories.store import EvidenceRepository, PolicyRepository
from .services.evidence_service import EvidenceService
from .services.ingestion_service import IngestionService
from .services.metrics_service import MetricsService
from .services.review_service import ReviewService
from .sources.document_store import DocumentStore, LocalDocumentStore
from .sources.web_search import get_search_provider

log = logging.getLogger(__name__)


@dataclass
class AppState:
    settings: Settings
    policy: PolicyStore
    evidence: EvidenceStore
    review: ReviewService
    ingestion: IngestionService
    evidence_svc: EvidenceService
    metrics: MetricsService
    docs: DocumentStore
    profile: LanguageProfile


def _baseline_year(settings: Settings, policy) -> int | None:
    """strategy year: PAPER_TRAIL_BASELINE_YEAR, else the earliest /YYYY/MM/ in a doc url"""
    if settings.baseline_year:
        return settings.baseline_year
    years = [
        int(m.group(1))
        for d in policy.documents()
        if (m := re.search(r"/(20\d{2})/\d{2}/", d.url or ""))
    ]
    return min(years) if years else None


def load_profile(policy: PolicyStore, code: str) -> LanguageProfile:
    """the language profile lives in the db, an empty one just means the rules find nothing"""
    data = policy.language_profile(code)
    if data is None:
        log.warning("no language profile %r in the db, rules will find nothing. "
                    "import one: python -m paper_trail.maintenance profile import FILE", code)
        return LanguageProfile.empty(code)
    return LanguageProfile.from_dict(data)


def build_state(settings: Settings | None = None) -> AppState:
    settings = settings or load()
    if settings.model_ca_bundle:
        # .env values don't reach os.environ on their own, ModelClient reads it there
        os.environ.setdefault("PAPER_TRAIL_MODEL_CA_BUNDLE", str(settings.model_ca_bundle))
    analyzer = None
    if settings.nlp == "huspacy":
        from .ml.nlp import HuSpacyAnalyzer
        analyzer = HuSpacyAnalyzer()
    # one store for both, the url picks postgres or the sqlite file
    policy = PolicyRepository(settings.database_url or settings.db_path)
    evidence = EvidenceRepository(settings.database_url or settings.db_path)
    profile = load_profile(policy, settings.language)
    docs: DocumentStore = LocalDocumentStore(settings.document_dir or settings.seed_dir)
    if settings.database_url:
        from .repositories.postgres.index import PostgresPageStore, PostgresVectorIndex
        page_store = PostgresPageStore(settings.database_url)
        vector_index = PostgresVectorIndex(settings.database_url, ts_config=profile.ts_config,
                                           analyzer=analyzer)
    else:
        cache_dir = Path(settings.db_path).parent / "fetched"
        page_store = FilePageStore(cache_dir)
        vector_index = FileVectorIndex(cache_dir, stemmer_language=profile.stemmer,
                                       analyzer=analyzer)

    from .sources.parsers import (
        DoclingDocumentParser,
        FallbackDocumentParser,
        PypdfDocumentParser,
    )
    parser = PypdfDocumentParser()
    if settings.parser == "docling":
        artifact_dir = (settings.document_dir or settings.seed_dir) / "parsed"
        parser = FallbackDocumentParser(
            DoclingDocumentParser(device=settings.parser_device, artifact_dir=artifact_dir),
            parser)
    crawler = None
    if settings.enable_sitemaps:
        from .sources.sitemaps import SitemapCrawler
        crawler = SitemapCrawler()

    embedder = get_provider(settings.embed_model, settings.embed_base_url,
                            settings.embed_api_key, str(settings.model_cache))
    extractor = get_extractor(settings.llm_base_url, settings.llm_api_key, settings.llm_model,
                              profile, settings.llm_window_pages, settings.llm_concurrency)
    if settings.search_provider == "searxng":
        from .sources.web_search import SearxngSearchProvider
        search = SearxngSearchProvider(settings.searxng_url, settings.allowed_domains)
    else:
        search = get_search_provider(settings.search_provider, settings.fixture_dir)
    reranker = get_reranker(settings.reranker_model, settings.rerank_base_url,
                            settings.rerank_api_key, settings.rerank_model, settings.rerank_batch)
    return AppState(
        settings=settings,
        policy=policy,
        evidence=evidence,
        review=ReviewService(policy, evidence, profile),
        ingestion=IngestionService(policy, extractor, parser=parser),
        evidence_svc=EvidenceService(
            evidence, search, embedder,
            page_store=page_store,
            vector_index=vector_index,
            reranker=reranker,
            analyzer=analyzer, crawler=crawler,
            max_fetch_workers=settings.max_fetch_workers, parser=parser,
            candidates=settings.rerank_candidates,
            max_doc_chars=settings.max_doc_chars,
            baseline_year=_baseline_year(settings, policy),
            profile=profile,
            allowed_domains=settings.allowed_domains,
        ),
        metrics=MetricsService(policy, evidence, profile),
        docs=docs,
        profile=profile,
    )
