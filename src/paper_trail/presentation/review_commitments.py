"""Screen 1 — Check what we found in the strategy.

Compact review rows with checkbox selection: batch confirm/reject is the
primary path, editing stays behind an Edit action per item. Selection is
a UI concern only — it never changes review status by itself.
"""

from __future__ import annotations

import streamlit as st

from ..domain.enums import CandidateType, ReviewStatus
from .filters import (
    STATUS_ALL,
    STATUS_CONFIRMED,
    STATUS_PENDING,
    STATUS_REJECTED,
    filter_candidates,
)
from .formatting import KIND_LABEL
from .style import badge, quiet, selected
from .translate import render_en

_PAGE = 15
_TYPE_OPTS = ["All", "Objectives", "Measures", "Targets"]
_STATUS_OPTS = [STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED, STATUS_ALL]


def render(state) -> None:
    st.header("Check what we found")

    cands = state.policy.candidates()
    if not cands:
        st.info("Nothing to check yet — read the strategy from the sidebar.")
        return

    msg = st.session_state.pop("_rev_msg", None)
    if msg:
        st.success(msg)

    done = [c for c in cands if c.review_status != ReviewStatus.UNREVIEWED]
    st.caption(
        f"{len(cands)} possible commitments · {len(done)} reviewed · "
        f"{len(cands) - len(done)} left"
    )

    with st.container(key="filters"):
        q = st.text_input(
            "Search", placeholder="Search commitments…",
            label_visibility="collapsed")
        f1, f2 = st.columns([1.6, 1.4])
        type_label = f1.segmented_control(
            "Type", _TYPE_OPTS, default="All",
            label_visibility="collapsed") or "All"
        status_label = f2.pills(
            "Show", _STATUS_OPTS, default=STATUS_PENDING,
            label_visibility="collapsed") or STATUS_PENDING

    visible = filter_candidates(cands, q or "", type_label, status_label)

    if not visible:
        st.caption("Nothing matches these filters.")

    vis_ids = [c.id for c in visible]
    t1, t2 = st.columns([1.5, 8.5])
    t1.button(
        "Select all visible", key="sel_all",
        on_click=_select, args=(vis_ids, True))
    t2.button("Clear selection", key="sel_none",
              on_click=_select, args=(vis_ids, False))

    limit = st.session_state.get("show_n", _PAGE)
    for cand in visible[:limit]:
        _row(state, cand)
    if len(visible) > limit:
        st.button(f"Show more ({len(visible) - limit} left)",
                  key="show_more", on_click=_more)

    _batch_bar(state, vis_ids)


def _select(ids: list[int], on: bool) -> None:
    for i in ids:
        st.session_state[f"sel_{i}"] = on


def _more() -> None:
    st.session_state["show_n"] = st.session_state.get("show_n", _PAGE) + _PAGE


def _batch_bar(state, ids: list[int]) -> None:
    # checkbox widget state is the single source of truth for selection —
    # no parallel set to keep in sync
    sel = [i for i in ids if st.session_state.get(f"sel_{i}")]
    with st.container(key="batchbar"):
        c1, c2, c3, c4 = st.columns([2.5, 2, 2, 1.5])
        c1.markdown(f"**{len(sel)} selected**" if sel else "Nothing selected")
        c2.button("Confirm selected", type="primary", width="stretch",
                  disabled=not sel,
                  on_click=_apply, args=(state, sel, "confirm"))
        with c3.container(key="danger-batch"):
            st.button("Reject selected", width="stretch",
                      disabled=not sel,
                      on_click=_apply, args=(state, sel, "reject"))
        c4.button("Clear", width="stretch", disabled=not sel,
                  on_click=_select, args=(sel, False))


def _apply(state, ids: list[int], action: str) -> None:
    if action == "confirm":
        state.review.confirm_candidates(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} confirmed."
    else:
        state.review.reject_candidates(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} rejected."
    for i in ids:
        # uncheck the widget itself — popping the key desyncs rows that
        # re-render under a different status filter
        st.session_state[f"sel_{i}"] = False


def _status_badge(cand) -> str:
    if cand.review_status == ReviewStatus.ACCEPTED:
        return badge("Confirmed", "ok")
    if cand.review_status == ReviewStatus.REJECTED:
        return badge("Rejected", "quiet")
    if cand.excerpt_on_page is False:
        return badge("Unclear", "warn")
    return badge("Needs review", "warn")


def _row(state, cand) -> None:
    key = f"row-{cand.id}"
    if st.session_state.get(f"sel_{cand.id}"):
        selected(key)
    if cand.review_status == ReviewStatus.REJECTED:
        quiet(key)

    with st.container(border=True, key=key):
        c_sel, c_body = st.columns([0.8, 19.2])
        c_sel.checkbox(
            "select", key=f"sel_{cand.id}", label_visibility="collapsed")
        with c_body:
            st.markdown(f"**{cand.normalized_title}**")
            render_en(cand.normalized_title)
            meta = [
                badge(KIND_LABEL[cand.suggested_type].upper()),
                _status_badge(cand),
                f"p.{cand.source_page}",
            ]
            if cand.code:
                meta.append(f"`{cand.code}`")
            if cand.deadline_year:
                meta.append(f"deadline {cand.deadline_year}")
            if cand.target_value is not None:
                meta.append(
                    f"target {cand.target_value:g} {cand.unit or ''}".strip())
            if cand.responsible_org:
                meta.append(f"who: {cand.responsible_org}")
            st.markdown(
                " &nbsp;·&nbsp; ".join(meta), unsafe_allow_html=True)
            preview = " ".join(cand.text.split())
            st.caption(preview[:160] + ("…" if len(preview) > 160 else ""))

            a1, a2, a3, _ = st.columns([1.2, 1.2, 1.2, 6])
            if a1.button("Confirm", key=f"acc_{cand.id}", type="primary"):
                state.review.accept_candidate(cand.id)
                st.session_state[f"sel_{cand.id}"] = False
                st.rerun()
            with a2.container(key=f"danger-{cand.id}"):
                if st.button("Reject", key=f"rej_{cand.id}"):
                    state.review.reject_candidate(cand.id)
                    st.session_state[f"sel_{cand.id}"] = False
                    st.rerun()
            if a3.button("Edit", key=f"edit_{cand.id}"):
                st.session_state[f"editmode_{cand.id}"] = not st.session_state.get(
                    f"editmode_{cand.id}")
                st.rerun()

            with st.expander(f"Source — strategy, page {cand.source_page}"):
                st.markdown(
                    '<span class="pt-source-label">Source · Józsefváros '
                    f"Climate Strategy · p.{cand.source_page}</span>",
                    unsafe_allow_html=True)
                st.markdown(
                    f'<div class="pt-source">“{cand.source_excerpt}”</div>',
                    unsafe_allow_html=True)
                render_en(cand.source_excerpt[:1500])
                if cand.excerpt_on_page is False:
                    st.caption(
                        "We couldn't re-find this quote on the page — "
                        "worth a closer look.")

            if st.session_state.get(f"editmode_{cand.id}"):
                _edit(state, cand)


def _edit(state, cand) -> None:
    """Editing is opt-in — the default path is confirm/reject."""
    accepted = state.policy.commitments()
    parent_options = {
        "— on its own —": None,
        **{f"{c.code + ' – ' if c.code else ''}{c.title}": c.id
           for c in accepted},
    }
    e1, e2, e3 = st.columns([1.2, 1.8, 1.8])
    kind = e1.selectbox(
        "What is it", list(CandidateType),
        index=list(CandidateType).index(cand.suggested_type),
        format_func=lambda k: KIND_LABEL[k], key=f"kind_{cand.id}")
    title = e2.text_input("Short name", value=cand.normalized_title,
                          key=f"title_{cand.id}")
    parent = e3.selectbox("Part of", list(parent_options),
                          key=f"parent_{cand.id}")
    if st.button("Save as commitment", key=f"save_{cand.id}",
                 type="primary"):
        state.review.accept_candidate(
            cand.id, kind=kind, title=title.strip(),
            parent_id=parent_options[parent])
        st.session_state[f"editmode_{cand.id}"] = False
        st.rerun()
