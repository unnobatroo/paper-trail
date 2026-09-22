"""Screen 2 — Check the possible matches.

Same interaction language as the commitment review: checkbox rows,
batch confirm/reject, details behind an expander. Confirming a link keeps
the suggested relationship unless the reviewer changed it in details.
"""

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
from .style import badge, selected
from .translate import english, render_en

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
    rev_msg = st.session_state.pop("_rev_msg", None)
    if rev_msg:
        st.success(rev_msg)

    st.caption(
        "The status under each match describes what that specific source "
        "passage says about this commitment — the same long report can "
        "honestly say different things for different commitments."
    )

    pending_ids = [
        l.id for com in commitments
        for l in state.evidence.links_for(com.id)
        if l.review_status == ReviewStatus.UNREVIEWED
    ]
    if pending_ids:
        t1, t2 = st.columns([1.5, 8.5])
        t1.button("Select all", key="lsel_all",
                  on_click=_select, args=(pending_ids, True))
        t2.button("Clear selection", key="lsel_none",
                  on_click=_select, args=(pending_ids, False))

    for com in commitments:
        links = state.evidence.links_for(com.id)
        pending = [l for l in links if l.review_status == ReviewStatus.UNREVIEWED]

        with st.container(border=True, key=f"com-{com.id}"):
            st.markdown(f"**{com.title}**"
                        + (f"  ·  `{com.code}`" if com.code else ""))
            render_en(com.title)
            st.caption(
                f"from the strategy, page {com.source_page} · "
                f"{len(pending)} to check"
                + (f" · {len(links) - len(pending)} checked"
                   if links and not pending else "")
            )

            if not links:
                if st.button("Find evidence", key=f"find_{com.id}",
                             type="primary"):
                    _search(state, com)
                continue

            for link in pending:
                _link_row(state, com, link)

    _batch_bar(state, pending_ids)


def _search(state, com) -> None:
    with st.status("Searching official sources…", expanded=True) as status:
        if _models_cold(state):
            status.write(
                "Paper Trail is downloading its language "
                "models — this only happens the first time.")
        try:
            found = state.evidence_svc.find_evidence(
                com, progress=status.write)
        except Exception as exc:
            status.update(label="The search didn't finish.", state="error")
            st.error(
                "We couldn't load the evidence model or "
                f"finish the search. The details: {type(exc).__name__}.")
            return
        status.update(label=f"Search done — {len(found)} possible matches.",
                      state="complete", expanded=False)
    st.session_state["_found_msg"] = len(found)
    st.session_state["_found_warn"] = list(state.evidence_svc.warnings)
    st.rerun()


def _link_row(state, com, link) -> None:
    ev = state.evidence.evidence(link.evidence_id)
    if ev is None:
        return
    budgets = state.evidence.budgets_for_evidence(ev.id)
    key = f"lrow-{link.id}"
    if st.session_state.get(f"lsel_{link.id}"):
        selected(key)

    with st.container(border=True, key=key):
        c_sel, c_body = st.columns([0.8, 19.2])
        c_sel.checkbox(
            "select", key=f"lsel_{link.id}", label_visibility="collapsed")
        with c_body:
            st.markdown(f"**[{ev.title}]({ev.url})**")
            render_en(ev.title)
            st.markdown(
                " &nbsp;·&nbsp; ".join([
                    badge(evidence_kind(ev.url, ev.title).upper()),
                    ev.publisher or "official source",
                    ev.url.split("/")[2] if "//" in ev.url else ev.url,
                ] + ([f"published {ev.published_on}"]
                     if ev.published_on else [])),
                unsafe_allow_html=True)
            st.caption(
                STATUS_SENTENCE[ev.status_hint]
                + (f" — “{ev.status_excerpt}”" if ev.status_excerpt else ""))
            if link.reasons:
                st.caption("Why it might be related: "
                           + "; ".join(link.reasons))
            if budgets:
                st.caption("Money mentioned: " + " · ".join(
                    f"{huf(b.amount_huf)} ({BUDGET_LABEL[b.kind]})"
                    for b in budgets[:4]))

            a1, a2, _ = st.columns([1.6, 1.6, 8])
            if a1.button("Confirm match", key=f"lacc_{link.id}",
                         type="primary"):
                state.review.accept_link(
                    link.id, st.session_state.get(
                        f"rel_{link.id}", link.suggested_relationship))
                st.session_state[f"lsel_{link.id}"] = False
                st.rerun()
            with a2.container(key=f"danger-l{link.id}"):
                if st.button("Reject", key=f"lrej_{link.id}"):
                    state.review.reject_link(link.id)
                    st.session_state[f"lsel_{link.id}"] = False
                    st.rerun()

            with st.expander("What the page says"):
                st.caption(ev.snippet[:1500])
                en = english(ev.snippet[:1500])
                if en:
                    st.caption(f"EN · *{en}*")
                st.selectbox(
                    "What does it prove",
                    list(RelationshipType),
                    index=list(RelationshipType).index(
                        link.suggested_relationship),
                    format_func=lambda r: REL_LABEL[r],
                    key=f"rel_{link.id}",
                )


def _select(ids: list[int], on: bool) -> None:
    for i in ids:
        st.session_state[f"lsel_{i}"] = on


def _apply(state, ids: list[int], action: str) -> None:
    if action == "confirm":
        rel = {i: st.session_state[f"rel_{i}"] for i in ids
               if f"rel_{i}" in st.session_state}
        state.review.accept_links(ids, rel)
        st.session_state["_rev_msg"] = f"{len(ids)} match(es) confirmed."
    else:
        state.review.reject_links(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} match(es) rejected."
    for i in ids:
        st.session_state[f"lsel_{i}"] = False


def _batch_bar(state, ids: list[int]) -> None:
    sel = [i for i in ids if st.session_state.get(f"lsel_{i}")]
    with st.container(key="batchbar"):
        c1, c2, c3, c4 = st.columns([2.5, 2, 2, 1.5])
        c1.markdown(f"**{len(sel)} selected**" if sel else "Nothing selected")
        c2.button("Confirm matches", type="primary",
                  width="stretch", disabled=not sel,
                  on_click=_apply, args=(state, sel, "confirm"))
        with c3.container(key="danger-batch"):
            st.button("Reject selected", width="stretch",
                      disabled=not sel,
                      on_click=_apply, args=(state, sel, "reject"))
        c4.button("Clear", width="stretch", disabled=not sel,
                  on_click=_select, args=(sel, False))


def _models_cold(state) -> bool:
    """True when local model files aren't cached yet — the first search
    downloads ~2 GB, so the UI should say so instead of looking frozen.
    Hosted inference (Jina) downloads nothing."""
    s = state.settings
    if s.embed_model.startswith("jina") or s.reranker_model.startswith("jina"):
        return False
    cache = s.model_cache
    return not cache.exists() or not any(cache.iterdir())
