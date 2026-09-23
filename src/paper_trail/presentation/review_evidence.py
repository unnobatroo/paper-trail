"""Screen 2 — Find evidence, then check the possible matches.

Two states on one screen, sharing the same row language as Step 1:

1. commitments that haven't been searched yet — tick them, press one
   "Find evidence for N selected" button, watch a st.status panel;
2. pending matches — checkbox selects for batch actions, the evidence
   title is a link-style button that opens the detail dialog.
"""

from __future__ import annotations

import streamlit as st

from ..domain.enums import CandidateType, RelationshipType, ReviewStatus
from .formatting import (
    BUDGET_LABEL,
    REL_LABEL,
    STATUS_LABEL,
    STATUS_SENTENCE,
    display_title,
    evidence_kind,
    huf,
)
from .review_commitments import candidate_detail
from .translate import english, render_en

_EVIDENCE_KINDS = (CandidateType.OBJECTIVE, CandidateType.MEASURE,
                   CandidateType.TARGET)
_COLS = [0.4, 4.2, 2.4, 1.4, 0.9, 1.3]
_HEAD = ["", "Evidence", "For", "Source says", "Published", "Suggested"]


def render(state) -> None:
    st.header("Find evidence")
    commitments = [
        c for c in state.policy.commitments() if c.kind in _EVIDENCE_KINDS
    ]
    if not commitments:
        st.info("Nothing to check yet — confirm some commitments first.")
        return

    # a queued search replaces the work area with a progress panel
    if st.session_state.get("_search_ids"):
        _run_searches(state)
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

    _pick_list(state, commitments)
    _review_matches(state, commitments)


# --- phase 1: choose commitments to search ---------------------------------

def _pick_list(state, commitments) -> None:
    unsearched = [
        c for c in commitments
        if not state.evidence.links_for(c.id)
    ]
    if not unsearched:
        return

    st.subheader("Choose what to search")
    st.caption(
        f"{len(unsearched)} commitment(s) haven't been checked against "
        "official sources yet."
    )
    for com in unsearched:
        with st.container(key=f"ptrow_s_{com.id}", gap=None):
            cols = st.columns([0.4, 6, 2], vertical_alignment="center")
            cols[0].checkbox("Select", key=f"esel_{com.id}",
                             label_visibility="collapsed")
            cols[1].button(display_title(com.title), key=f"hl_s_{com.id}",
                           type="tertiary",
                           on_click=_inspect_cand, args=(com,))
            meta = [f"strategy p.{com.source_page}" if com.source_page
                    else "strategy"]
            if com.deadline_year:
                meta.append(f"deadline {com.deadline_year}")
            cols[2].caption(" · ".join(meta) + " · not searched yet")

    selected = [
        c.id for c in unsearched
        if st.session_state.get(f"esel_{c.id}")
    ]
    with st.container(key="ptbatch_s", horizontal=True,
                      vertical_alignment="center"):
        st.markdown(f"**{len(selected)} selected**"
                    if selected else "Nothing selected")
        st.button("Select all not searched", type="tertiary",
                  key="search_selall",
                  on_click=_set_search_sel,
                  args=([c.id for c in unsearched], True))
        st.button("Clear", type="tertiary", disabled=not selected,
                  key="search_clear",
                  on_click=_set_search_sel, args=(selected, False))
        st.button(
            f"Find evidence for {len(selected)} selected"
            if selected else "Find evidence",
            type="primary", disabled=not selected, key="search_go",
            on_click=_queue_search, args=(selected,))

    _maybe_cand_detail(state)


def _inspect_cand(com) -> None:
    if com.candidate_id is not None:
        st.session_state["detail_id"] = com.candidate_id


def _maybe_cand_detail(state) -> None:
    did = st.session_state.get("detail_id")
    if did is None:
        return
    cand = state.policy.candidate(did)
    if cand is None:
        st.session_state["detail_id"] = None
        return
    candidate_detail(state, cand)


def _set_search_sel(ids: list[int], on: bool) -> None:
    for cid in ids:
        st.session_state[f"esel_{cid}"] = on


def _queue_search(ids: list[int]) -> None:
    st.session_state["_search_ids"] = ids
    _set_search_sel(ids, False)


def _run_searches(state) -> None:
    """Runs instead of the work area while a search is queued."""
    ids = st.session_state.pop("_search_ids", [])
    coms = [state.policy.commitment(i) for i in ids]
    coms = [c for c in coms if c]
    if _models_cold(state):
        st.info("Paper Trail is downloading its language models — "
                "this only happens the first time.")
    total = 0
    warnings: list[str] = []
    with st.status("Searching official sources…", expanded=True) as status:
        for com in coms:
            status.write(f"● Reading sources for “{com.title}”…")
            try:
                found = state.evidence_svc.find_evidence(
                    com, progress=status.write)
            except Exception as exc:
                status.update(label="The search didn't finish.",
                              state="error")
                st.error("We couldn't load the evidence model or finish "
                         f"the search. The details: {type(exc).__name__}.")
                return
            total += len(found)
            warnings.extend(state.evidence_svc.warnings)
            status.write(f"✓ {com.title}: {len(found)} possible matches")
        status.update(
            label=f"Search done — {total} possible matches.",
            state="complete", expanded=False)
    st.session_state["_found_msg"] = total
    st.session_state["_found_warn"] = warnings
    st.rerun()


# --- phase 2: review pending matches ----------------------------------------

def _review_matches(state, commitments) -> None:
    pending: list[tuple] = []  # (commitment, link, evidence)
    for com in commitments:
        for link in state.evidence.links_for(com.id):
            if link.review_status != ReviewStatus.UNREVIEWED:
                continue
            ev = state.evidence.evidence(link.evidence_id)
            if ev is not None:
                pending.append((com, link, ev))

    if not pending:
        st.caption("No matches waiting for review.")
        return

    st.subheader("Check the matches")
    st.caption(
        "The status under each match describes what that specific source "
        "passage says about this commitment — the same long report can "
        "honestly say different things for different commitments."
    )

    with st.container(key="pthead", gap=None):
        h = st.columns(_COLS)
        for i, text in enumerate(_HEAD):
            if text:
                h[i].caption(f"**{text}**")

    inspected = st.session_state.get("link_detail_id")
    for com, link, ev in pending:
        _link_row(com, link, ev, inspected == link.id)

    selected = [
        l.id for _, l, _ in pending
        if st.session_state.get(f"lsel_{l.id}")
    ]
    _batch_bar(state, pending, selected)
    _maybe_detail(state)


def _link_row(com, link, ev, inspected: bool) -> None:
    key = (f"ptrow_sel_e_{link.id}" if inspected
           else f"ptrow_e_{link.id}")
    with st.container(key=key, gap=None):
        cols = st.columns(_COLS, vertical_alignment="center")
        cols[0].checkbox("Select", key=f"lsel_{link.id}",
                         label_visibility="collapsed")
        cols[1].button(ev.title, key=f"hl_e_{link.id}",
                       type="tertiary",
                       on_click=_inspect_link, args=(link.id,))
        cols[2].caption(com.title[:70])
        cols[3].caption(STATUS_LABEL[ev.status_hint])
        cols[4].caption(str(ev.published_on or "—"))
        cols[5].caption(REL_LABEL[link.suggested_relationship])


def _inspect_link(link_id: int) -> None:
    st.session_state["link_detail_id"] = link_id


def _set_link_sel(ids: list[int], on: bool) -> None:
    for lid in ids:
        st.session_state[f"lsel_{lid}"] = on


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
    _set_link_sel(ids, False)


def _batch_bar(state, pending, selected: list[int]) -> None:
    ids = [l.id for _, l, _ in pending]
    with st.container(key="ptbatch_e", horizontal=True,
                      vertical_alignment="center"):
        st.markdown(f"**{len(selected)} selected**"
                    if selected else "Nothing selected")
        st.button("Select all", type="tertiary", key="link_selpage",
                  on_click=_set_link_sel, args=(ids, True))
        st.button("Clear", type="tertiary", disabled=not selected,
                  key="link_clear",
                  on_click=_set_link_sel, args=(selected, False))
        st.button("Confirm matches", type="primary",
                  disabled=not selected, key="link_confirm",
                  on_click=_apply, args=(state, selected, "confirm"))
        st.button("Reject selected", disabled=not selected,
                  key="link_reject",
                  on_click=_apply, args=(state, selected, "reject"))


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
