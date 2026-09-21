"""Screen 2 — Check the possible matches."""

from __future__ import annotations

import streamlit as st

from ..domain.enums import CandidateType, RelationshipType, ReviewStatus
from .formatting import (
    BUDGET_LABEL,
    REL_LABEL,
    STATUS_SENTENCE,
    evidence_kind,
    huf,
)

_EVIDENCE_KINDS = (CandidateType.OBJECTIVE, CandidateType.MEASURE,
                   CandidateType.TARGET)


def render(state) -> None:
    st.header("Find evidence")
    commitments = [
        c for c in state.policy.commitments() if c.kind in _EVIDENCE_KINDS
    ]
    if not commitments:
        st.info("Nothing to check yet — confirm some commitments first.")
        return

    found_msg = st.session_state.pop("_found_msg", None)
    if found_msg is not None:
        st.success(
            "Search done — "
            + (f"{found_msg} possible matches." if found_msg
               else "nothing useful on the official sites.")
        )
    for w in st.session_state.pop("_found_warn", []):
        st.warning(w)

    st.write(
        "For each confirmed commitment we search the district's official "
        "sources — `jozsefvaros.hu`, `rev8.hu`, `budapest.hu` and the "
        "official reports — and list the pages that look related. "
        "Nothing counts until you confirm it."
    )

    for com in commitments:
        links = state.evidence.links_for(com.id)
        pending = [l for l in links if l.review_status == ReviewStatus.UNREVIEWED]
        decided = [l for l in links if l.review_status != ReviewStatus.UNREVIEWED]

        with st.container(border=True):
            head = f"**{com.title}**"
            if com.code:
                head += f"  ·  `{com.code}`"
            st.markdown(head)
            st.caption(f"from the strategy, page {com.source_page}")

            if not links:
                if st.button("Find evidence", key=f"find_{com.id}"):
                    with st.status("Searching official sources…",
                                   expanded=True) as status:
                        if _models_cold(state):
                            status.write(
                                "Paper Trail is downloading its language "
                                "models — this only happens the first time.")
                        try:
                            found = state.evidence_svc.find_evidence(
                                com, progress=status.write)
                        except Exception as exc:
                            status.update(
                                label="The search didn't finish.",
                                state="error")
                            st.error(
                                "We couldn't load the evidence model or "
                                "finish the search. The details: "
                                f"{type(exc).__name__}.")
                            continue
                        status.update(
                            label=f"Search done — {len(found)} possible matches.",
                            state="complete", expanded=False)
                    st.session_state["_found_msg"] = len(found)
                    st.session_state["_found_warn"] = list(
                        state.evidence_svc.warnings)
                    st.rerun()
                continue

            st.caption(
                f"{len(pending)} to check"
                + (f" · {len(decided)} already checked" if decided else "")
            )
            for link in pending:
                _render_link(state, com, link)


def _render_link(state, com, link) -> None:
    ev = state.evidence.evidence(link.evidence_id)
    if ev is None:
        return
    budgets = state.evidence.budgets_for_evidence(ev.id)

    st.divider()
    st.markdown(f"**[{ev.title}]({ev.url})**")
    st.caption(
        f"{ev.publisher} · {evidence_kind(ev.url, ev.title)} · {ev.url}"
        + (f" · published {ev.published_on}" if ev.published_on else "")
    )
    if link.reasons:
        st.caption("Why it might be related: " + "; ".join(link.reasons))
    st.caption(
        STATUS_SENTENCE[ev.status_hint]
        + (f" — “{ev.status_excerpt}”" if ev.status_excerpt else "")
    )
    if budgets:
        st.caption("Money mentioned:")
        for b in budgets:
            st.caption(
                f"· {huf(b.amount_huf)} ({BUDGET_LABEL[b.kind]})"
                f" — “{b.description}”"
            )
    with st.expander("What the page says"):
        st.caption(ev.snippet[:1500])

    rel = st.selectbox(
        "What does it prove",
        list(RelationshipType),
        index=list(RelationshipType).index(link.suggested_relationship),
        format_func=lambda r: REL_LABEL[r],
        key=f"rel_{link.id}",
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm match", key=f"lacc_{link.id}", type="primary"):
        state.review.accept_link(link.id, rel)
        st.rerun()
    if c2.button("Reject", key=f"lrej_{link.id}"):
        state.review.reject_link(link.id)
        st.rerun()


def _models_cold(state) -> bool:
    """True when no model files are cached yet — the first search downloads
    ~2 GB, so the UI should say so instead of looking frozen."""
    cache = state.settings.model_cache
    return not cache.exists() or not any(cache.iterdir())
