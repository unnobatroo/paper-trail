"""Commitment review: titles inspect, checkboxes select source records."""
from __future__ import annotations

import math
import streamlit as st

from ..domain.enums import CandidateType, ReviewStatus
from .filters import (STATUS_ALL, STATUS_CONFIRMED, STATUS_PENDING,
                      STATUS_REJECTED, filter_candidates)
from .formatting import KIND_LABEL, display_title, title_groups
from .translate import render_en
from .guidance import page_header
from .style import label, quote, badge

_PAGE = 10
_TYPE_OPTS = ["All", "Objectives", "Measures", "Targets"]
_STATUS_OPTS = [STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED, STATUS_ALL]


def _status_text(cand):
    if cand.review_status == ReviewStatus.ACCEPTED:
        return "Confirmed"
    if cand.review_status == ReviewStatus.REJECTED:
        return "Rejected"
    return "Unclear" if cand.excerpt_on_page is False else "Needs review"


def render(state):
    page_header("Check commitments", "commitments")
    cands = state.policy.candidates()
    if not cands:
        st.info("Nothing to check yet — read the strategy from the sidebar.")
        return
    if msg := st.session_state.pop("_rev_msg", None):
        st.success(msg)
    remaining = sum(c.review_status == ReviewStatus.UNREVIEWED for c in cands)
    st.caption(f"{len(cands)} source mentions · {len(cands)-remaining} reviewed · {remaining} left")
    if not remaining and st.session_state.get("cs", STATUS_PENDING) == STATUS_PENDING:
        _all_reviewed()
        return

    left, right = st.columns([1.6, 1], gap=24)
    with left:
        st.text_input("Search commitments", placeholder="Search commitments…", icon=":material/search:",
                      label_visibility="collapsed", key="cq", on_change=_reset_page)
        type_label = st.segmented_control("Type", _TYPE_OPTS, default="All", key="ct",
                          label_visibility="collapsed", on_change=_reset_page) or "All"
        status = st.pills("Status", _STATUS_OPTS, default=STATUS_PENDING, key="cs",
                          label_visibility="collapsed", on_change=_reset_page) or STATUS_PENDING
        visible = filter_candidates(cands, query=st.session_state.get("cq", ""),
                                    type_label=type_label, status_label=status)
        groups = title_groups(visible, lambda c: c.normalized_title, lambda c: c.suggested_type)
        if not groups:
            st.caption("Nothing matches these filters.")
            return
        pages = max(1, math.ceil(len(groups) / _PAGE))
        page = min(st.session_state.get("cand_page", 1), pages)
        groups = groups[(page-1)*_PAGE:page*_PAGE]
        ids = [g[0].id for g in groups]
        if st.session_state.get("detail_id") not in ids:
            st.session_state["detail_id"] = ids[0]
        selected_groups = [g for g in groups if st.session_state.get(f"csel_{g[0].id}")]
        selected = [c.id for g in selected_groups for c in g]
        _batch_bar(state, groups, selected_groups, selected)
        with st.container(key="ptlist_c", gap=None):
            for group in groups:
                _row(group, st.session_state.detail_id == group[0].id)
        st.caption(f"Page {page} of {pages} · Selection applies to this page.")
        if pages > 1:
            st.pagination(pages, key="cand_page")
    with right:
        with st.container(key="ptinsp", gap="small"):
            group = next(g for g in groups if g[0].id == st.session_state.detail_id)
            candidate_detail(state, group)


def _row(group, inspected):
    cand = group[0]
    key = f"ptrow_{'sel_' if inspected else ''}c_{cand.id}"
    with st.container(key=key, gap=None):
        with st.container(horizontal=True, gap=8, vertical_alignment="top"):
            st.checkbox(f"Select {display_title(cand.normalized_title)}", key=f"csel_{cand.id}",
                        label_visibility="collapsed", width=24)
            with st.container(gap=None):
                st.button(display_title(cand.normalized_title), key=f"hl_c_{cand.id}",
                          type="tertiary", on_click=_inspect, args=(cand.id,))
                statuses = list(dict.fromkeys(_status_text(c) for c in group))
                meta = [KIND_LABEL[cand.suggested_type].upper(), "/".join(statuses),
                        "p." + ", ".join(str(p) for p in dict.fromkeys(c.source_page for c in group))]
                if len(group) > 1:
                    meta.append(f"{len(group)} source mentions")
                st.caption(" · ".join(meta))


def _all_reviewed():
    st.success("All commitments reviewed.", icon=":material/task_alt:")
    with st.container(horizontal=True, gap=8):
        for text, status in [("View confirmed", STATUS_CONFIRMED),
                             ("View rejected", STATUS_REJECTED), ("View all", STATUS_ALL)]:
            st.button(text, on_click=_view, args=(status,))


def _view(status):
    st.session_state["cs"] = status
    _reset_page()


def _reset_page():
    st.session_state["cand_page"] = 1


def _inspect(cid):
    st.session_state["detail_id"] = cid


def _set_selection(ids, on):
    for cid in ids:
        st.session_state[f"csel_{cid}"] = on


def _apply(state, ids, representatives, action):
    if action == "confirm":
        state.review.confirm_candidates(ids)
    else:
        state.review.reject_candidates(ids)
    st.session_state["_rev_msg"] = f"{len(ids)} source mentions {'confirmed' if action == 'confirm' else 'rejected'}."
    _set_selection(representatives, False)


def _batch_bar(state, groups, selected_groups, selected):
    representatives = [g[0].id for g in selected_groups]
    with st.container(key="ptbatch_c", horizontal=True, vertical_alignment="center", gap=8):
        st.caption(f"{len(selected_groups)} selected", width="content")
        st.button("Confirm selected", icon=":material/check:", type="primary", key="primary_confirm_c", disabled=not selected,
                  on_click=_apply, args=(state, selected, representatives, "confirm"))
        st.button("Reject selected", icon=":material/close:", key="danger_reject_c", disabled=not selected,
                  on_click=_apply, args=(state, selected, representatives, "reject"))
        if selected:
            st.button("Clear", icon=":material/deselect:", type="tertiary", on_click=_set_selection, args=(representatives, False))
        if len(selected) > len(selected_groups):
            st.caption(f"Includes {len(selected)} source mentions.")


def candidate_detail(state, group, *, editable=True):
    """Inline inspector. Choosing a source mention never changes a review."""
    cand = group[0]
    label("Commitment inspector", level=2)
    st.subheader(display_title(cand.normalized_title))
    render_en(display_title(cand.normalized_title))
    if len(group) > 1:
        cand = st.selectbox("Source mention", group,
                            format_func=lambda c: f"p.{c.source_page} · {_status_text(c)} · mention {c.id}",
                            key=f"mention_c_{group[0].id}")
    with st.container(horizontal=True, gap=8, vertical_alignment="center"):
        badge(_status_text(cand))
        st.caption(f"{KIND_LABEL[cand.suggested_type].capitalize()} · Page {cand.source_page}", width="content")
    if cand.deadline_year or cand.timeframe:
        st.markdown(f"**Deadline** · {cand.deadline_year or cand.timeframe}")
    if cand.target_value is not None:
        st.markdown(f"**Target** · {cand.target_value:g} {cand.unit or ''}")
    if cand.responsible_org:
        st.caption(cand.responsible_org)
    label("Official Hungarian text")
    quote(cand.source_excerpt)
    render_en(cand.source_excerpt)
    if cand.excerpt_on_page is False:
        st.caption("We couldn't re-find this quote on the page — worth a closer look.")
    doc = next((d for d in state.policy.documents() if d.id == cand.document_id), None)
    if doc and doc.url:
        st.link_button(f"Strategy · page {cand.source_page}", doc.url.split('#')[0] + f"#page={cand.source_page}", icon=":material/open_in_new:")
    else:
        st.caption(f"Source · Józsefváros Climate Strategy · page {cand.source_page}")
    if editable and cand.review_status == ReviewStatus.UNREVIEWED:
        with st.expander("Edit", icon=":material/edit:"):
            st.caption("Saving confirms this source mention as a commitment.")
            accepted = state.policy.commitments()
            parents = {"— on its own —": None, **{
                f"{c.code or ''} · {display_title(c.title)} [{c.id}]": c.id for c in accepted}}
            with st.form(f"edit_{cand.id}"):
                kind = st.selectbox("Commitment type", list(CandidateType),
                    index=list(CandidateType).index(cand.suggested_type), format_func=lambda k: KIND_LABEL[k])
                title = st.text_input("Short name", value=display_title(cand.normalized_title))
                parent = st.selectbox("Part of", list(parents))
                if st.form_submit_button("Save as commitment", type="primary"):
                    if not title.strip():
                        st.error("Enter a short name.")
                    else:
                        state.review.accept_candidate(cand.id, kind=kind, title=title.strip(), parent_id=parents[parent])
                        st.session_state["_rev_msg"] = "Saved as a commitment."
                        st.rerun()
