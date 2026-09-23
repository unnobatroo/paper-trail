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

from paper_trail.domain.enums import ReviewStatus
from paper_trail.infrastructure.settings import Settings, load
from paper_trail.ml.embeddings import get_provider
from paper_trail.ml.extraction import get_extractor
from paper_trail.ml.rerank import get_reranker
from paper_trail.presentation import (
    review_commitments,
    review_evidence,
    style,
    tracker,
)
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


_STEPS = ["Check commitments", "Find evidence", "Paper trail"]


def _step_state(state: AppState) -> tuple[set[int], set[int]]:
    """(done, available) step numbers — drives the sidebar markers."""
    cands = state.policy.candidates()
    coms = state.policy.commitments()
    links = state.evidence.links()
    pending_links = [l for l in links
                     if l.review_status == ReviewStatus.UNREVIEWED]
    done, avail = set(), set()
    avail.add(1)
    if cands and all(c.review_status != ReviewStatus.UNREVIEWED
                     for c in cands):
        done.add(1)
    if coms:
        avail.update({2, 3})
        if links and not pending_links:
            done.add(2)
    return done, avail


def _goto(page: int) -> None:
    st.session_state["page"] = page
    # inspectors/dialogs belong to the screen that opened them
    for k in ("detail_id", "link_detail_id", "trail_sel"):
        st.session_state.pop(k, None)


def sidebar(state: AppState) -> int:
    pdf_path = Path(state.settings.seed_dir) / STRATEGY_PDF
    if not state.policy.documents():
        st.sidebar.info("We haven't read the strategy yet.")
        if pdf_path.exists():
            if st.sidebar.button("Read the strategy", type="primary",
                                 width="stretch"):
                with st.spinner("Reading the PDF…"):
                    _, n = state.ingestion.ingest(
                        pdf_path, STRATEGY_TITLE,
                        "Józsefvárosi Önkormányzat", STRATEGY_URL,
                    )
                st.sidebar.success(f"Found {n} possible commitments.")
                st.rerun()
        else:
            st.sidebar.error(
                f"We can't find the strategy PDF at {pdf_path}.")

    page = st.session_state.get("page", 1)
    done, avail = _step_state(state)
    for n, label in enumerate(_STEPS, start=1):
        marker = "✓" if n in done else ("●" if n == page else "○")
        st.sidebar.button(
            f"{marker}  {n}. {label}",
            key=f"nav_{n}", width="stretch",
            disabled=n not in avail,
            type="primary" if n == page else "tertiary",
            on_click=_goto, args=(n,))

    st.sidebar.divider()
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
    style.inject()
    state = get_state()
    page = sidebar(state)

    st.title("Paper Trail")
    st.caption(
        "From policy text to implementation evidence. We read the "
        "Józsefváros Climate Strategy and check official sources for what "
        "actually happened."
    )

    if page == 1:
        review_commitments.render(state)
    elif page == 2:
        review_evidence.render(state)
    else:
        tracker.render(state)


if __name__ == "__main__":
    main()
