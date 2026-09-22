"""Screen 2 — Check the possible matches.

Same interaction model as the commitment review: a native table of
pending evidence links, checkbox batch selection, a Details button per
row opening a dialog (snippet + relationship choice + single-link
actions), and batch actions pinned in st.bottom.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..domain.enums import CandidateType, RelationshipType, ReviewStatus
from .formatting import (
    BUDGET_LABEL,
    REL_LABEL,
    STATUS_LABEL,
    STATUS_SENTENCE,
    evidence_kind,
    huf,
)
from .translate import english, render_en

_EVIDENCE_KINDS = (CandidateType.OBJECTIVE, CandidateType.MEASURE,
                   CandidateType.TARGET)
_READONLY = ["Evidence", "For", "Source says", "Publisher", "Date",
             "Suggested", "Details"]


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

    # --- commitments needing searches -------------------------------------
    pending: list[tuple] = []  # (commitment, link, evidence)
    for com in commitments:
        links = state.evidence.links_for(com.id)
        to_check = [l for l in links
                    if l.review_status == ReviewStatus.UNREVIEWED]
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(
                f"**{com.title}**"
                + (f" · `{com.code}`" if com.code else "")
                + f"  — p.{com.source_page}, "
                + (f"{len(to_check)} to check"
                   if to_check else
                   (f"{len(links)} checked" if links else "not searched yet"))
            )
            if not links:
                if st.button("Find evidence", key=f"find_{com.id}",
                             type="primary"):
                    _search(state, com)
        for link in to_check:
            ev = state.evidence.evidence(link.evidence_id)
            if ev is not None:
                pending.append((com, link, ev))

    if not pending:
        st.caption("No matches waiting for review.")
        return

    t1, t2, _ = st.columns([2, 2, 6])
    t1.button("Select all", on_click=_select,
              args=([l.id for _, l, _ in pending], True))
    t2.button("Clear selection", on_click=_select,
              args=([l.id for _, l, _ in pending], False))

    st.session_state["_link_row_ids"] = [l.id for _, l, _ in pending]
    gen = st.session_state.get("link_gen", 0)
    edited = st.data_editor(
        _frame(pending),
        key=f"link_editor_{gen}",
        on_change=_sync_forced,
        hide_index=True,
        num_rows="fixed",
        disabled=_READONLY,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select",
                                                      width="small"),
            "Evidence": st.column_config.TextColumn("Evidence",
                                                    width="large"),
            "Details": st.column_config.ButtonColumn(
                "Details", on_click=_open_detail, key="link_detail",
                type="tertiary"),
        },
    )

    selected = [i for i, on in edited["Select"].items() if bool(on)]
    _batch_bar(state, selected)
    _maybe_detail(state)


def _frame(pending) -> pd.DataFrame:
    """Pending links indexed by link id."""
    forced = st.session_state.get("link_forced", set())
    rows = [{
        "id": link.id,
        "Select": link.id in forced,
        "Evidence": ev.title,
        "For": com.title[:60],
        "Source says": STATUS_LABEL[ev.status_hint],
        "Publisher": ev.publisher or "official source",
        "Date": str(ev.published_on or ""),
        "Suggested": REL_LABEL[link.suggested_relationship],
        "Details": "Open",
    } for com, link, ev in pending]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.set_index("id")


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


def _sync_forced() -> None:
    """edited_rows is keyed by row position — map through the rendered
    link id list."""
    state_ = st.session_state.get(
        f"link_editor_{st.session_state.get('link_gen', 0)}") or {}
    ids = st.session_state.get("_link_row_ids", [])
    forced = st.session_state.setdefault("link_forced", set())
    for pos, cols in (state_.get("edited_rows") or {}).items():
        if "Select" not in cols:
            continue
        lid = ids[int(pos)] if 0 <= int(pos) < len(ids) else None
        if lid is None:
            continue
        (forced.add if cols["Select"] else forced.discard)(lid)


def _select(ids: list[int], on: bool) -> None:
    """Rebuild the editor with those rows pre-(un)checked — data_editor
    widget state is not writable, so we remount it via a new key."""
    forced = st.session_state.setdefault("link_forced", set())
    (forced.update if on else forced.difference_update)(ids)
    st.session_state["link_gen"] = st.session_state.get("link_gen", 0) + 1


def _open_detail() -> None:
    click = st.session_state.get("link_detail")
    if click is not None and getattr(click, "row", None) is not None:
        ids = st.session_state.get("_link_row_ids", [])
        if 0 <= click.row < len(ids):
            st.session_state["link_detail_id"] = ids[click.row]


def _apply(state, ids: list[int], action: str) -> None:
    if action == "confirm":
        # per-link relationship choices made in dialogs win over the
        # suggested relationship
        rel = st.session_state.get("rel_choice", {})
        state.review.accept_links(ids, rel)
        st.session_state["_rev_msg"] = f"{len(ids)} match(es) confirmed."
    else:
        state.review.reject_links(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} match(es) rejected."
    st.session_state["link_forced"] = set()
    st.session_state["link_gen"] = st.session_state.get("link_gen", 0) + 1


def _batch_bar(state, selected: list[int]) -> None:
    with st.bottom:
        c1, c2, c3, c4 = st.columns([2.5, 2, 2, 1.5])
        c1.markdown(f"**{len(selected)} selected**"
                    if selected else "Nothing selected")
        c2.button("Confirm matches", type="primary", width="stretch",
                  disabled=not selected,
                  on_click=_apply, args=(state, selected, "confirm"))
        c3.button("Reject selected", width="stretch", disabled=not selected,
                  on_click=_apply, args=(state, selected, "reject"))
        c4.button("Clear", width="stretch", disabled=not selected,
                  on_click=_select, args=(selected, False))


def _maybe_detail(state) -> None:
    lid = st.session_state.get("link_detail_id")
    if lid is None:
        return
    link = state.evidence.link(lid)
    ev = state.evidence.evidence(link.evidence_id) if link else None
    com = (state.policy.commitment(link.commitment_id) if link else None)
    if link is None or ev is None or com is None:
        st.session_state["link_detail_id"] = None
        return
    _detail(state, com, link, ev)


def _close_detail() -> None:
    st.session_state["link_detail_id"] = None


def _remember_rel(link_id: int) -> None:
    st.session_state.setdefault("rel_choice", {})[link_id] = (
        st.session_state[f"rel_{link_id}"])


@st.dialog("Possible match", width="large", on_dismiss=_close_detail)
def _detail(state, com, link, ev) -> None:
    st.markdown(f"**[{ev.title}]({ev.url})**")
    render_en(ev.title)
    meta = [
        evidence_kind(ev.url, ev.title),
        ev.publisher or "official source",
        ev.url.split("/")[2] if "//" in ev.url else ev.url,
    ]
    if ev.published_on:
        meta.append(f"published {ev.published_on}")
    st.caption(" · ".join(meta))
    st.caption(f"Possible match for: {com.title}")

    st.markdown(f"*{STATUS_SENTENCE[ev.status_hint]}*"
                + (f" — “{ev.status_excerpt}”" if ev.status_excerpt else ""))
    if link.reasons:
        st.caption("Why it might be related: " + "; ".join(link.reasons))

    budgets = state.evidence.budgets_for_evidence(ev.id)
    if budgets:
        st.caption("Money mentioned: " + " · ".join(
            f"{huf(b.amount_huf)} ({BUDGET_LABEL[b.kind]})"
            for b in budgets[:4]))

    st.markdown("**What the page says**")
    st.markdown(f"> {ev.snippet[:1500]}")
    en = english(ev.snippet[:1500])
    if en:
        st.caption(f"EN · *{en}*")

    st.divider()
    rel = st.session_state.setdefault("rel_choice", {}).get(
        link.id, link.suggested_relationship)
    st.selectbox(
        "What does it prove",
        list(RelationshipType),
        index=list(RelationshipType).index(rel),
        format_func=lambda r: REL_LABEL[r],
        key=f"rel_{link.id}",
        on_change=_remember_rel, args=(link.id,),
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm match", type="primary", width="stretch",
                 key=f"lok_{link.id}"):
        state.review.accept_link(
            link.id, st.session_state.get(f"rel_{link.id}",
                                        link.suggested_relationship))
        st.session_state["_rev_msg"] = "Match confirmed."
        st.session_state["link_detail_id"] = None
        st.rerun()
    if c2.button("Reject", width="stretch", key=f"lno_{link.id}"):
        state.review.reject_link(link.id)
        st.session_state["_rev_msg"] = "Match rejected."
        st.session_state["link_detail_id"] = None
        st.rerun()


def _models_cold(state) -> bool:
    """True when local model files aren't cached yet — the first search
    downloads ~2 GB, so the UI should say so instead of looking frozen.
    Hosted inference (Jina) downloads nothing."""
    s = state.settings
    if s.embed_model.startswith("jina") or s.reranker_model.startswith("jina"):
        return False
    cache = s.model_cache
    return not cache.exists() or not any(cache.iterdir())
