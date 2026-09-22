"""Paper Trail — From policy text to implementation evidence.

Run:  uv run streamlit run app.py

Golden path: ingest the strategy → review commitments → find evidence →
review links → read the paper trail.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from paper_trail.infrastructure.settings import Settings, load
from paper_trail.ml.embeddings import get_provider
from paper_trail.ml.rerank import get_reranker
from paper_trail.ml.extraction import get_extractor
from paper_trail.presentation import review_commitments, review_evidence, tracker
from paper_trail.repositories.store import EvidenceRepository, PolicyRepository
from paper_trail.services.evidence_service import EvidenceService
from paper_trail.services.ingestion_service import IngestionService
from paper_trail.services.metrics_service import MetricsService
from paper_trail.services.review_service import ReviewService
from paper_trail.services.translation import MT_DISCLAIMER, get_translator
from paper_trail.sources.web_search import get_search_provider

STRATEGY_PDF = "jozsefvaros_klimastrategia_2021.pdf"
STRATEGY_TITLE = "Józsefvárosi Klímastratégia"
STRATEGY_URL = (
    "https://jozsefvaros.hu/downloads/2022/03/"
    "2066_jozsefvarosi_klimastrategia.pdf?ver=20220321142957"
)


@dataclass
class AppState:
    settings: Settings
    policy: PolicyRepository
    evidence: EvidenceRepository
    review: ReviewService
    ingestion: IngestionService
    evidence_svc: EvidenceService
    metrics: MetricsService


@st.cache_resource
def get_state() -> AppState:
    # on Streamlit Cloud, secrets.toml values arrive via st.secrets —
    # surface them as env vars so load() sees the same names everywhere
    try:
        for k, v in st.secrets.items():
            os.environ.setdefault(k, str(v))
    except Exception:
        pass

    settings = load()
    # no sqlite3 connection may live inside this cached state — the SQLite
    # repos hold the path and open per-operation connections; the Supabase
    # repos hold a stateless HTTP client
    if settings.supabase_configured:
        from paper_trail.repositories.supabase_store import (
            SupabaseEvidenceRepository,
            SupabasePolicyRepository,
        )
        policy = SupabasePolicyRepository(
            settings.supabase_url, settings.supabase_key)
        evidence = SupabaseEvidenceRepository(
            settings.supabase_url, settings.supabase_key)
    else:
        policy = PolicyRepository(settings.db_path)
        evidence = EvidenceRepository(settings.db_path)
    embedder = get_provider(settings.embed_model,
                            cache_dir=str(settings.model_cache))
    extractor = get_extractor(
        settings.llm_base_url, settings.llm_api_key, settings.llm_model
    )
    search = get_search_provider(settings.search_provider, settings.fixture_dir)
    return AppState(
        settings=settings,
        policy=policy,
        evidence=evidence,
        review=ReviewService(policy, evidence),
        ingestion=IngestionService(policy, extractor),
        evidence_svc=EvidenceService(
            evidence, search, embedder,
            cache_dir=Path(settings.db_path).parent / "fetched",
            reranker=get_reranker(settings.reranker_model,
                                  cache_dir=str(settings.model_cache)),
            candidates=settings.rerank_candidates,
            max_doc_chars=settings.max_doc_chars,
        ),
        metrics=MetricsService(policy, evidence),
    )


def sidebar(state: AppState) -> str:
    st.sidebar.title("Paper Trail")
    st.sidebar.caption("From policy text to implementation evidence.")

    pdf_path = Path(state.settings.seed_dir) / STRATEGY_PDF
    if not state.policy.documents():
        st.sidebar.warning("We haven't read the strategy yet.")
        if pdf_path.exists():
            if st.sidebar.button("Read the strategy", type="primary"):
                with st.spinner("Reading the PDF…"):
                    _, n = state.ingestion.ingest(
                        pdf_path, STRATEGY_TITLE,
                        "Józsefvárosi Önkormányzat", STRATEGY_URL,
                    )
                st.sidebar.success(f"Found {n} possible commitments.")
                st.rerun()
        else:
            st.sidebar.error(
                f"We can't find the strategy PDF at {pdf_path}."
            )

    st.sidebar.divider()
    page = st.sidebar.radio(
        "Steps",
        ["1. Check commitments", "2. Find evidence", "3. Paper trail"],
    )

    if get_translator():
        st.sidebar.toggle("English translations", value=True, key="show_en")
        st.sidebar.caption(MT_DISCLAIMER)
    else:
        st.session_state["show_en"] = False
        st.sidebar.caption(
            "English translations need an HF_TOKEN for machine translation.")
    return page


def main() -> None:
    st.set_page_config(page_title="Paper Trail", layout="wide")
    state = get_state()
    page = sidebar(state)

    st.title("Paper Trail")
    st.caption(
        "From policy text to implementation evidence. We read the "
        "Józsefváros Climate Strategy and check official sources for what "
        "actually happened."
    )

    if page.startswith("1"):
        review_commitments.render(state)
    elif page.startswith("2"):
        review_evidence.render(state)
    else:
        tracker.render(state)


if __name__ == "__main__":
    main()
