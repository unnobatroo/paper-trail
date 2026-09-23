"""Screen 2 — Find evidence, then check the possible matches.

Two states on one screen, sharing the same row language as Step 1:

1. commitments that haven't been searched yet — tick them, press one
   "Find evidence for N selected" button, watch a st.status panel;
2. pending matches — checkbox selects for batch actions, the evidence
   title is a link-style button that updates the inspector.
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
    title_groups,
    KIND_LABEL,
    evidence_kind,
    huf,
)
from .review_commitments import candidate_detail
from .translate import render_en
from .guidance import page_header, REL_HELP
from .style import label, quote, badge

_EVIDENCE_KINDS = (CandidateType.OBJECTIVE, CandidateType.MEASURE,
                   CandidateType.TARGET)


def render(state) -> None:
    page_header("Find evidence", "evidence")
    commitments = [
        c for c in state.policy.commitments() if c.kind in _EVIDENCE_KINDS
    ]
    if not commitments:
        st.info("Nothing to check yet — confirm some commitments first.")
        return

    # Keep progress and work in separate stable slots. Reusing the cleared
    # work slot for status coalesces Streamlit deltas and leaves stale rows.
    progress = st.container()
    workspace = st.empty()
    if st.session_state.get("_search_ids"):
        workspace.empty()
        with progress:
            _run_searches(state)
    else:
        with workspace.container():
            _workspace(state, commitments)


def _workspace(state, commitments):
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

    pending = [l for l in state.evidence.links() if l.review_status == ReviewStatus.UNREVIEWED]
    st.session_state.setdefault("evidence_phase", "Review matches" if pending else "Choose commitments")
    phase = st.segmented_control("Evidence workflow", ["Choose commitments", "Review matches"],
                                 key="evidence_phase", label_visibility="collapsed")
    if phase == "Review matches":
        _review_matches(state, commitments)
    else:
        _pick_list(state, commitments)


def _pick_list(state, commitments):
    searched = set(st.session_state.get("searched_ids", []))
    unsearched = [c for c in commitments if not state.evidence.links_for(c.id) and c.id not in searched]
    if not unsearched:
        st.success("All commitments searched. Review the matches to continue.")
        return
    groups = title_groups(unsearched, lambda c: c.title, lambda c: c.kind)
    st.caption(f"{len(groups)} commitments available to search · Click a title to inspect; check a box to select.")
    left, right = st.columns([1.6, 1], gap=24)
    with left:
        selected_groups = [g for g in groups if st.session_state.get(f"esel_{g[0].id}")]
        selected = [c.id for g in selected_groups for c in g]
        with st.container(key="ptbatch_s", gap=8):
            with st.container(horizontal=True, gap=8):
                st.button("Select all not searched", icon=":material/select_all:", type="tertiary", key="search_selall",
                          on_click=_set_search_sel, args=([g[0].id for g in groups], True))
                if selected:
                    st.button("Clear", icon=":material/deselect:", type="tertiary", key="search_clear",
                              on_click=_set_search_sel, args=([g[0].id for g in groups], False))
            st.button(f"Find evidence for {len(selected_groups)} selected", icon=":material/search:", type="primary",
                      disabled=not selected, key="primary_search_go", on_click=_queue_search, args=(selected,))
            if len(selected) > len(selected_groups):
                st.caption(f"Includes all {len(selected)} source mentions of the selected titles.")
        ids = [g[0].id for g in groups]
        if st.session_state.get("search_detail_id") not in ids:
            st.session_state["search_detail_id"] = ids[0]
        # Native pagination bounds the mobile list; selection survives page changes.
        pages = (len(groups) + 9) // 10
        page = min(st.session_state.get("search_page", 1), pages)
        with st.container(key="ptlist_s", gap=None, height=500):
            for group in groups[(page-1)*10:page*10]:
                com = group[0]
                active = com.id == st.session_state.search_detail_id
                with st.container(key=f"ptrow_{'sel_' if active else ''}s_{com.id}", gap=None):
                    with st.container(horizontal=True, gap=8):
                        st.checkbox(f"Select {display_title(com.title)}", key=f"esel_{com.id}",
                                    label_visibility="collapsed", width=24, persist_state="session")
                        with st.container(gap=None):
                            st.button(display_title(com.title), key=f"hl_s_{com.id}", type="tertiary",
                                      on_click=_inspect_search, args=(com.id,))
                            meta = [KIND_LABEL[com.kind].upper(), f"p.{com.source_page}", "Not searched"]
                            if len(group) > 1:
                                meta.append(f"{len(group)} source mentions")
                            st.caption(" · ".join(meta))
        if pages > 1:
            st.pagination(pages, key="search_page")
    with right:
        with st.container(key="ptinsp", gap=8):
            group = next(g for g in groups if g[0].id == st.session_state.search_detail_id)
            candidates = [state.policy.candidate(c.candidate_id) for c in group if c.candidate_id]
            candidates = [c for c in candidates if c]
            if candidates:
                candidate_detail(state, candidates, editable=False)
            else:
                st.subheader(display_title(group[0].title))
                quote(group[0].summary)


def _inspect_search(cid):
    st.session_state["search_detail_id"] = cid


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
    with st.status("Finding evidence", expanded=True) as status:
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
            st.session_state.setdefault("searched_ids", []).append(com.id)
            total += len(found)
            warnings.extend(state.evidence_svc.warnings)
            status.write(f"✓ {com.title}: {len(found)} possible matches")
        status.update(
            label=f"Search done — {total} possible matches.",
            state="complete", expanded=False)
    st.session_state["evidence_phase"] = "Review matches"
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
        st.success("No matches waiting for review.", icon=":material/task_alt:")
        st.caption("Choose commitments to search for more evidence, or read the confirmed paper trail.")
        return

    st.caption(f"{len(pending)} matches waiting for review · Inspect the source before confirming a relationship.")
    left, right = st.columns([1.6, 1], gap=24)
    ids = [link.id for _, link, _ in pending]
    if st.session_state.get("link_detail_id") not in ids:
        st.session_state["link_detail_id"] = ids[0]
    with left:
        selected = [lid for lid in ids if st.session_state.get(f"lsel_{lid}")]
        _batch_bar(state, pending, selected)
        pages = (len(pending) + 9) // 10
        page = min(st.session_state.get("evidence_page", 1), pages)
        with st.container(key="ptlist_e", gap=None, height=min(500, 112 * len(pending))):
            for com, link, ev in pending[(page-1)*10:page*10]:
                _link_row(com, link, ev, st.session_state.link_detail_id == link.id)
        if pages > 1:
            st.pagination(pages, key="evidence_page")
    with right:
        with st.container(key="ptinsp", gap=8):
            _maybe_detail(state)


def _link_row(com, link, ev, inspected):
    with st.container(key=f"ptrow_{'sel_' if inspected else ''}e_{link.id}", gap=None):
        with st.container(horizontal=True, gap=8):
            st.checkbox(f"Select {display_title(ev.title)} for {display_title(com.title)}",
                        key=f"lsel_{link.id}", label_visibility="collapsed", width=24, persist_state="session")
            with st.container(gap=None):
                st.button(display_title(ev.title), key=f"hl_e_{link.id}", type="tertiary",
                          on_click=_inspect_link, args=(link.id,))
                st.caption(f"For · {display_title(com.title)}")
                st.caption(" · ".join([ev.publisher or "Official source", str(ev.published_on or "Date unknown"),
                                       STATUS_LABEL[ev.status_hint].capitalize()]))


def _inspect_link(link_id: int) -> None:
    st.session_state["link_detail_id"] = link_id


def _set_link_sel(ids: list[int], on: bool) -> None:
    for lid in ids:
        st.session_state[f"lsel_{lid}"] = on


def _apply(state, ids: list[int], action: str) -> None:
    if action == "confirm":
        # per-link relationship choices made in the inspector win over the
        # suggested relationship
        rel = st.session_state.get("rel_choice", {})
        state.review.accept_links(ids, rel)
        st.session_state["_rev_msg"] = f"{len(ids)} match(es) confirmed."
    else:
        state.review.reject_links(ids)
        st.session_state["_rev_msg"] = f"{len(ids)} match(es) rejected."
    _set_link_sel(ids, False)


def _batch_bar(state, pending, selected: list[int]) -> None:
    with st.container(key="ptbatch_e", horizontal=True, vertical_alignment="center", gap=8):
        st.caption(f"{len(selected)} selected", width="content")
        st.button("Confirm selected", icon=":material/check:", type="primary", disabled=not selected, key="primary_link_confirm",
                  on_click=_apply, args=(state, selected, "confirm"))
        st.button("Reject selected", icon=":material/close:", disabled=not selected, key="danger_link_reject",
                  on_click=_apply, args=(state, selected, "reject"))
        if selected:
            st.button("Clear", icon=":material/deselect:", type="tertiary", key="link_clear",
                      on_click=_set_link_sel, args=(selected, False))


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


def _remember_rel(link_id: int) -> None:
    st.session_state.setdefault("rel_choice", {})[link_id] = (
        st.session_state[f"rel_{link_id}"])


def _detail(state, com, link, ev):
    label("Evidence inspector", level=2)
    st.subheader(display_title(ev.title))
    render_en(display_title(ev.title))
    st.caption(" · ".join([ev.publisher or "Official source", str(ev.published_on or "Date unknown"),
                           evidence_kind(ev.url, ev.title)]))
    label("Linked commitment")
    st.markdown(display_title(com.title))
    label("Matched excerpt")
    with st.container(height=220, border=False):
        quote(ev.snippet)
        render_en(ev.snippet)
    label("What this source reports")
    badge(STATUS_LABEL[ev.status_hint].capitalize())
    st.markdown(STATUS_SENTENCE[ev.status_hint])
    if ev.status_excerpt:
        quote(ev.status_excerpt)
    label("Why Paper Trail matched it")
    st.caption("; ".join(link.reasons) if link.reasons else "No matching explanation stored.")
    budgets = state.evidence.budgets_for_evidence(ev.id)
    if budgets:
        st.caption("Money mentioned: " + " · ".join(
            f"{huf(b.amount_huf)} ({BUDGET_LABEL[b.kind]})" for b in budgets[:4]))
    st.link_button("Read official source", ev.url, icon=":material/open_in_new:")
    rel = st.session_state.setdefault("rel_choice", {}).get(link.id, link.suggested_relationship)
    st.selectbox("Relationship", list(RelationshipType), index=list(RelationshipType).index(rel),
                 format_func=lambda r: REL_LABEL[r], key=f"rel_{link.id}",
                 help="How this source relates to the commitment. Confirming saves this relationship; source status is a separate assessment.",
                 on_change=_remember_rel, args=(link.id,))
    st.caption(REL_HELP[st.session_state[f"rel_{link.id}"]])
    st.caption("Applied when you confirm this selected match.")


def _models_cold(state) -> bool:
    """True when local model files aren't cached yet — the first search
    downloads ~2 GB, so the UI should say so instead of looking frozen.
    Hosted inference (Jina) downloads nothing."""
    s = state.settings
    if s.embed_model.startswith("jina") or s.reranker_model.startswith("jina"):
        return False
    cache = s.model_cache
    return not cache.exists() or not any(cache.iterdir())
