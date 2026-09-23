"""Screen 1 — Check what we found in the strategy.

A compact review list: one row per commitment — a checkbox for batch
selection, the title itself as a link-style button that opens the
detail dialog, then type/status/page metadata. Unchecked means "not
selected" — it never rejects anything.
"""

from __future__ import annotations

import math

import streamlit as st

from ..domain.enums import CandidateType, ReviewStatus
from .filters import (
    STATUS_ALL,
    STATUS_CONFIRMED,
    STATUS_PENDING,
    STATUS_REJECTED,
    filter_candidates,
)
from .formatting import KIND_LABEL, display_title
from .translate import render_en

_PAGE = 15
_TYPE_OPTS = ["All", "Objectives", "Measures", "Targets"]
_STATUS_OPTS = [STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED,
                STATUS_ALL]
_COLS = [0.4, 4.6, 0.9, 1.15, 0.55, 0.85, 0.75]
_HEAD = ["", "Commitment", "Type", "Status", "Page", "Deadline", "Target"]


def _status_text(cand) -> str:
    if cand.review_status == ReviewStatus.ACCEPTED:
        return "Confirmed"
    if cand.review_status == ReviewStatus.REJECTED:
        return "Rejected"
    if cand.excerpt_on_page is False:
        return "Unclear"
    return "Needs review"


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

    st.text_input("Search commitments", placeholder="Search commitments…",
                  label_visibility="collapsed", key="cq",
                  on_change=_reset_page)
    f1, f2 = st.columns([1.6, 1.4])
    type_label = f1.segmented_control(
        "Type", _TYPE_OPTS, default="All", key="ct",
        label_visibility="collapsed", on_change=_reset_page) or "All"
    status_label = f2.pills(
        "Status", _STATUS_OPTS, default=STATUS_PENDING, key="cs",
        label_visibility="collapsed",
        on_change=_reset_page) or STATUS_PENDING

    visible = filter_candidates(
        cands, query=st.session_state.get("cq", "") or "",
        type_label=type_label, status_label=status_label)
    if not visible:
        if status_label == STATUS_PENDING and done:
            _all_reviewed(state)
            return
        st.caption("Nothing matches these filters.")
        return

    num_pages = max(1, math.ceil(len(visible) / _PAGE))
    page = min(st.session_state.get("cand_page", 1), num_pages)
    page_rows = visible[(page - 1) * _PAGE: page * _PAGE]

    with st.container(key="pthead", gap=None):
        h = st.columns(_COLS)
        for i, text in enumerate(_HEAD):
            if text:
                h[i].caption(f"**{text}**")

    inspected = st.session_state.get("detail_id")
    for cand in page_rows:
        _row(cand, inspected == cand.id)

    st.caption(
        f"{len(visible)} matching · page {page} of {num_pages} · "
        "selection applies to the rows on this page"
    )
    st.pagination(num_pages, key="cand_page")

    selected = [
        c.id for c in page_rows
        if st.session_state.get(f"csel_{c.id}")
    ]
    _batch_bar(state, page_rows, selected)
    _maybe_detail(state)


def _row(cand, inspected: bool) -> None:
    key = f"ptrow_sel_c_{cand.id}" if inspected else f"ptrow_c_{cand.id}"
    with st.container(key=key, gap=None):
        cols = st.columns(_COLS, vertical_alignment="center")
        cols[0].checkbox("Select", key=f"csel_{cand.id}",
                         label_visibility="collapsed")
        cols[1].button(display_title(cand.normalized_title),
                       key=f"hl_c_{cand.id}", type="tertiary",
                       on_click=_inspect, args=(cand.id,))
        cols[2].caption(KIND_LABEL[cand.suggested_type])
        cols[3].caption(_status_text(cand))
        cols[4].caption(str(cand.source_page))
        cols[5].caption(str(cand.deadline_year or "—"))
        cols[6].caption(
            f"{cand.target_value:g} {cand.unit or ''}".strip()
            if cand.target_value is not None else "—")


def _all_reviewed(state) -> None:
    st.success("All commitments reviewed.")
    c1, c2, c3, _ = st.columns([1.4, 1.4, 1.2, 4])
    c1.button("View confirmed", key="view_confirmed",
              on_click=_view, args=(STATUS_CONFIRMED,))
    c2.button("View rejected", key="view_rejected",
              on_click=_view, args=(STATUS_REJECTED,))
    c3.button("View all", key="view_all",
              on_click=_view, args=(STATUS_ALL,))


def _view(label: str) -> None:
    st.session_state["cs"] = label
    _reset_page()


def _reset_page() -> None:
    st.session_state["cand_page"] = 1


def _inspect(cand_id: int) -> None:
    st.session_state["detail_id"] = cand_id


def _set_selection(ids: list[int], on: bool) -> None:
    """Tick/untick visible checkboxes — plain widget state, so a simple
    assignment in a callback is enough."""
    for cid in ids:
        st.session_state[f"csel_{cid}"] = on


def _apply(state, ids: list[int], action: str) -> None:
    if action == "confirm":
        state.review.confirm_candidates(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} confirmed."
    else:
        state.review.reject_candidates(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} rejected."
    _set_selection(ids, False)


def _batch_bar(state, page_rows, selected: list[int]) -> None:
    ids = [c.id for c in page_rows]
    with st.container(key="ptbatch_c", horizontal=True,
                      vertical_alignment="center"):
        st.markdown(f"**{len(selected)} selected**"
                    if selected else "Nothing selected")
        st.button("Select page", type="tertiary", key="cand_selpage",
                  on_click=_set_selection, args=(ids, True))
        st.button("Clear", type="tertiary", disabled=not selected,
                  key="cand_clear",
                  on_click=_set_selection, args=(selected, False))
        st.button("Confirm selected", type="primary",
                  disabled=not selected, key="cand_confirm",
                  on_click=_apply, args=(state, selected, "confirm"))
        st.button("Reject selected", disabled=not selected,
                  key="cand_reject",
                  on_click=_apply, args=(state, selected, "reject"))


def _maybe_detail(state) -> None:
    did = st.session_state.get("detail_id")
    if did is None:
        return
    cand = state.policy.candidate(did)
    if cand is None:
        st.session_state["detail_id"] = None
        return
    candidate_detail(state, cand)


def _close_detail() -> None:
    st.session_state["detail_id"] = None


@st.dialog("Commitment", width="large", on_dismiss=_close_detail)
def candidate_detail(state, cand) -> None:
    """Detail dialog for one candidate — also opened from Step 2's
    search pick-list, where it is read-only for confirmed items."""
    st.markdown(f"**{cand.normalized_title}**")
    render_en(cand.normalized_title)

    meta = [
        KIND_LABEL[cand.suggested_type],
        _status_text(cand),
        f"strategy p.{cand.source_page}",
    ]
    if cand.deadline_year:
        meta.append(f"deadline {cand.deadline_year}")
    if cand.target_value is not None:
        meta.append(f"target {cand.target_value:g} {cand.unit or ''}".strip())
    if cand.responsible_org:
        meta.append(f"who: {cand.responsible_org}")
    st.caption(" · ".join(meta))

    st.markdown("**Official wording**")
    st.markdown(f"> {cand.source_excerpt[:1500]}")
    render_en(cand.source_excerpt[:1500])
    if cand.excerpt_on_page is False:
        st.caption("We couldn't re-find this quote on the page — "
                   "worth a closer look.")
    st.caption(f"Source · Józsefváros Climate Strategy · "
               f"page {cand.source_page}")

    if cand.review_status != ReviewStatus.UNREVIEWED:
        return

    st.divider()
    if st.toggle("Edit fields", key=f"ed_{cand.id}"):
        accepted = state.policy.commitments()
        parent_options = {
            "— on its own —": None,
            **{f"{c.code + ' – ' if c.code else ''}{c.title}": c.id
               for c in accepted},
        }
        kind = st.selectbox(
            "What is it", list(CandidateType),
            index=list(CandidateType).index(cand.suggested_type),
            format_func=lambda k: KIND_LABEL[k], key=f"kind_{cand.id}")
        title = st.text_input("Short name", value=cand.normalized_title,
                              key=f"title_{cand.id}")
        parent = st.selectbox("Part of", list(parent_options),
                              key=f"parent_{cand.id}")
        if st.button("Save as commitment", type="primary",
                     key=f"save_{cand.id}"):
            state.review.accept_candidate(
                cand.id, kind=kind, title=title.strip(),
                parent_id=parent_options[parent])
            st.session_state["_rev_msg"] = "Saved as a commitment."
            st.session_state["detail_id"] = None
            st.rerun()
    else:
        c1, c2 = st.columns(2)
        if c1.button("Confirm", type="primary", key=f"ok_{cand.id}",
                     width="stretch"):
            state.review.accept_candidate(cand.id)
            st.session_state["_rev_msg"] = "Confirmed."
            st.session_state["detail_id"] = None
            st.rerun()
        if c2.button("Reject", key=f"no_{cand.id}", width="stretch"):
            state.review.reject_candidate(cand.id)
            st.session_state["_rev_msg"] = "Rejected."
            st.session_state["detail_id"] = None
            st.rerun()
