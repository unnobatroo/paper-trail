"""Paper Trail — From policy text to implementation evidence.

Run:  uv run streamlit run app.py
API:  uv run uvicorn paper_trail.api.app:app --app-dir src

Golden path: ingest the strategy → review commitments → find evidence →
review links → read the paper trail.

This Streamlit UI is the dev/demo surface; the production frontend
consumes the same services through the REST API. Both share
`paper_trail.bootstrap.build_state` — one wiring path.
"""

from __future__ import annotations

import os

import streamlit as st

from paper_trail.bootstrap import AppState, build_state
from paper_trail.domain.enums import ReviewStatus
from paper_trail.infrastructure.settings import load
from paper_trail.presentation import (
    review_commitments,
    review_evidence,
    style,
    tracker,
)
from paper_trail.services.translation import get_translator

STRATEGY_PDF = "jozsefvaros_klimastrategia_2021.pdf"
STRATEGY_TITLE = "Józsefvárosi Klímastratégia"
STRATEGY_URL = (
    "https://jozsefvaros.hu/downloads/2022/03/"
    "2066_jozsefvarosi_klimastrategia.pdf?ver=20220321142957"
)


@st.cache_resource
def get_state() -> AppState:
    # on Streamlit Cloud, secrets.toml values arrive via st.secrets —
    # surface them as env vars so load() sees the same names everywhere
    try:
        for k, v in st.secrets.items():
            os.environ.setdefault(k, str(v))
    except Exception:
        pass
    return build_state(load())


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
    if not state.policy.documents():
        st.sidebar.info("We haven't read the strategy yet.")
        pdf = state.docs.read(STRATEGY_PDF)
        if pdf is not None:
            if st.sidebar.button("Read the strategy", type="primary",
                                 width="stretch"):
                with st.spinner("Reading the PDF…"):
                    _, n = state.ingestion.ingest(
                        pdf, STRATEGY_TITLE,
                        "Józsefvárosi Önkormányzat", STRATEGY_URL,
                    )
                st.sidebar.success(f"Found {n} possible commitments.")
                st.rerun()
        else:
            st.sidebar.error(
                f"We can't find the strategy PDF ({STRATEGY_PDF}) — "
                "check the document store.")

    page = st.session_state.get("page", 1)
    done, avail = _step_state(state)
    st.sidebar.markdown(":material/description: **Paper Trail**")
    st.sidebar.caption("Józsefváros · Climate Strategy")
    for n, label in enumerate(_STEPS, start=1):
        marker = "check_circle" if n in done else ("radio_button_checked" if n == page else "radio_button_unchecked")
        st.sidebar.button(
            f"{n}. {label}", icon=f":material/{marker}:",
            key=f"nav_{'active_' if n == page else ''}{n}", width="stretch",
            disabled=n not in avail,
            type="tertiary",
            on_click=_goto, args=(n,))

    st.sidebar.divider()
    if get_translator():
        st.sidebar.toggle("English translations", value=True, key="show_en")
        st.sidebar.caption("Machine translation · Hungarian sources are authoritative.")
    else:
        st.sidebar.toggle("English translations", value=False, disabled=True, key="show_en",
                          help="Machine translation is unavailable in this environment.")
    return page


def main() -> None:
    st.set_page_config(page_title="Paper Trail", page_icon=":material/description:", layout="wide")
    style.inject()
    state = get_state()
    page = sidebar(state)

    with st.container(key="pt_breadcrumb"):
        st.caption(f"JÓZSEFVÁROS CLIMATE STRATEGY  /  STEP {page} OF 3")

    if page == 1:
        review_commitments.render(state)
    elif page == 2:
        review_evidence.render(state)
    else:
        tracker.render(state)


if __name__ == "__main__":
    main()
