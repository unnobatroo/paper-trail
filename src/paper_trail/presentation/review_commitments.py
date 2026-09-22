"""Screen 1 — Check what we found in the strategy.

A native review table: one row per commitment, a checkbox column for
batch selection, a Details button per row opening a dialog, filters +
pagination as native widgets, and batch actions pinned in st.bottom.
Unchecked means "not selected" — it never rejects anything.
"""

from __future__ import annotations

import math

import pandas as pd
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
from .translate import render_en

_PAGE = 15
_TYPE_OPTS = ["All", "Objectives", "Measures", "Targets"]
_STATUS_OPTS = [STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED, STATUS_ALL]
_EDITABLE = ["Select"]
_READONLY = ["Commitment", "Type", "Status", "Page", "Deadline",
             "Target", "Details"]


def _status_text(cand) -> str:
    if cand.review_status == ReviewStatus.ACCEPTED:
        return "Confirmed"
    if cand.review_status == ReviewStatus.REJECTED:
        return "Rejected"
    if cand.excerpt_on_page is False:
        return "Unclear"
    return "Needs review"


def _frame(cands) -> pd.DataFrame:
    """Review table — index is the candidate id so checkbox edits and
    the Details button map straight back to the row's record.
    `Select` is pre-checked for ids in the forced-selection set (used by
    Select page / programmatic selection)."""
    forced = st.session_state.get("cand_forced", set())
    rows = [{
        "id": c.id,
        "Select": c.id in forced,
        "Commitment": c.normalized_title,
        "Type": KIND_LABEL[c.suggested_type],
        "Status": _status_text(c),
        "Page": c.source_page,
        "Deadline": c.deadline_year or "",
        "Target": (
            f"{c.target_value:g} {c.unit or ''}".strip()
            if c.target_value is not None else ""
        ),
        "Details": "Open",
    } for c in cands]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.set_index("id")


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
        st.caption("Nothing matches these filters.")
        return

    num_pages = max(1, math.ceil(len(visible) / _PAGE))
    page = min(st.session_state.get("cand_page", 1), num_pages)
    page_rows = visible[(page - 1) * _PAGE: page * _PAGE]

    t1, t2, _ = st.columns([2, 2, 6])
    t1.button("Select page", on_click=_select_page,
              args=([c.id for c in page_rows], True))
    t2.button("Clear selection", on_click=_select_page,
              args=([c.id for c in page_rows], False))

    # Details clicks report a row *position* — remember which ids are on
    # this page so the callback can map position -> candidate id.
    st.session_state["_cand_page_ids"] = [c.id for c in page_rows]

    # The editor key carries a generation number: data_editor widget
    # state can't be written programmatically, so Select-page/Clear
    # bump the generation -> a fresh editor mounts with pre-checked rows.
    gen = st.session_state.get("cand_gen", 0)
    edited = st.data_editor(
        _frame(page_rows),
        key=f"cand_editor_{gen}",
        on_change=_sync_forced,
        hide_index=True,
        num_rows="fixed",
        disabled=_READONLY,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select",
                                                      width="small"),
            "Commitment": st.column_config.TextColumn("Commitment",
                                                      width="large"),
            "Details": st.column_config.ButtonColumn(
                "Details", on_click=_open_detail, key="cand_detail",
                type="tertiary"),
        },
    )
    st.caption(
        f"{len(visible)} matching · page {page} of {num_pages} · "
        "selection applies to the rows on this page"
    )
    st.pagination(num_pages, key="cand_page")

    selected = [
        i for i, on in edited["Select"].items() if bool(on)
    ]
    _batch_bar(state, selected)
    _maybe_detail(state)


def _reset_page() -> None:
    st.session_state["cand_page"] = 1


def _sync_forced() -> None:
    """Manual (un)checking feeds back into the forced set so pagination
    doesn't resurrect a checkbox the user cleared. edited_rows is keyed
    by row position — map through the page's id list."""
    state_ = st.session_state.get(
        f"cand_editor_{st.session_state.get('cand_gen', 0)}") or {}
    page_ids = st.session_state.get("_cand_page_ids", [])
    forced = st.session_state.setdefault("cand_forced", set())
    for pos, cols in (state_.get("edited_rows") or {}).items():
        if "Select" not in cols:
            continue
        cid = page_ids[int(pos)] if 0 <= int(pos) < len(page_ids) else None
        if cid is None:
            continue
        (forced.add if cols["Select"] else forced.discard)(cid)


def _select_page(ids: list[int], on: bool) -> None:
    """Programmatic (un)check: rebuild the editor with those rows'
    Select column set — data_editor state is not writable directly."""
    forced = st.session_state.setdefault("cand_forced", set())
    (forced.update if on else forced.difference_update)(ids)
    st.session_state["cand_gen"] = st.session_state.get("cand_gen", 0) + 1


def _open_detail() -> None:
    click = st.session_state.get("cand_detail")
    if click is not None and getattr(click, "row", None) is not None:
        # .row is a position in the displayed page; map it to the id
        page_rows = st.session_state.get("_cand_page_ids", [])
        if 0 <= click.row < len(page_rows):
            st.session_state["detail_id"] = page_rows[click.row]


def _apply(state, ids: list[int], action: str) -> None:
    if action == "confirm":
        state.review.confirm_candidates(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} confirmed."
    else:
        state.review.reject_candidates(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} rejected."
    st.session_state["cand_forced"] = set()
    st.session_state["cand_gen"] = st.session_state.get("cand_gen", 0) + 1


def _batch_bar(state, selected: list[int]) -> None:
    with st.bottom:
        c1, c2, c3, c4 = st.columns([2.5, 2, 2, 1.5])
        c1.markdown(f"**{len(selected)} selected**"
                    if selected else "Nothing selected")
        c2.button("Confirm selected", type="primary", width="stretch",
                  disabled=not selected,
                  on_click=_apply, args=(state, selected, "confirm"))
        c3.button("Reject selected", width="stretch", disabled=not selected,
                  on_click=_apply, args=(state, selected, "reject"))
        c4.button("Clear", width="stretch", disabled=not selected,
                  on_click=_select_page, args=(selected, False))


def _maybe_detail(state) -> None:
    did = st.session_state.get("detail_id")
    if did is None:
        return
    cand = state.policy.candidate(did)
    if cand is None:
        st.session_state["detail_id"] = None
        return
    _detail(state, cand)


def _close_detail() -> None:
    st.session_state["detail_id"] = None


@st.dialog("Commitment", width="large", on_dismiss=_close_detail)
def _detail(state, cand) -> None:
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
