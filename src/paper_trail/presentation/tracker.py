"""Screen 3 — The paper trail: read-only inspection.

Left: commitments grouped under their objectives as compact rows.
Right: the selected commitment's full trail — promise → evidence →
what's still missing. No selection or review controls live here.
"""

from __future__ import annotations

import re

import streamlit as st

from ..domain.enums import (
    CandidateType,
    RelationshipType,
    ReviewStatus,
    Status,
)
from .formatting import (
    BUDGET_LABEL,
    KIND_LABEL,
    STATUS_LABEL,
    display_title,
    evidence_kind,
    huf,
)
from .translate import render_en

_GROUP_ORDER = [
    RelationshipType.DIRECT_IMPLEMENTATION,
    RelationshipType.BUDGET,
    RelationshipType.SUPPORTING,
    RelationshipType.INDIRECT,
]
_GROUP_HEAD = {
    RelationshipType.DIRECT_IMPLEMENTATION: "Implementation evidence",
    RelationshipType.BUDGET: "Budget information",
    RelationshipType.SUPPORTING: "Supporting evidence",
    RelationshipType.INDIRECT: "Related information",
}
_STATUS_BADGE_COLOR = {
    Status.COMPLETED: "green",
    Status.IN_IMPLEMENTATION: "green",
    Status.IN_PREPARATION: "orange",
    Status.ANNOUNCED: "orange",
    Status.PLANNED: "orange",
    Status.BUDGET: "blue",
    Status.BACKGROUND: "gray",
}
_FILTER_OPTS = ["All", "Has evidence", "Missing evidence",
                "Measurable target"]
_MAX_BUDGET_LINES = 6


def _norm_title(title: str) -> str:
    """Presentation dedupe only: strip markdown/heading artefacts so
    '**NINCS UTCA ZÖLD NÉLKÜL **' and 'Nincs utca zöld nélkül' collapse
    into one visible row. Provenance stays on the kept record."""
    t = re.sub(r"[*_#`>]+", "", title or "")
    t = re.sub(r"\s+", " ", t).strip().strip(".:–—-").strip()
    return t.casefold()


def _dedupe(rows) -> list[tuple]:
    """Collapse exact (normalized title, kind) duplicates.

    Returns [(row, mentions)] — keeps the row with the most evidence.
    Genuinely different records (different kind) are never merged."""
    best: dict[tuple, list] = {}
    for r in rows:
        key = (_norm_title(r.commitment.title), r.commitment.kind)
        best.setdefault(key, []).append(r)
    out = []
    for group in best.values():
        group.sort(key=lambda r: len(r.evidence), reverse=True)
        out.append((group[0], len(group)))
    return out


def _evidence_note(row) -> str:
    n = len(row.evidence)
    if not n:
        return "no evidence yet"
    return f"{n} evidence source{'s' if n > 1 else ''}"


def render(state) -> None:
    st.header("Paper trail")
    rows = state.metrics.trail()
    if not rows:
        st.info("Nothing here yet — confirm some commitments and "
                "matches first.")
        return

    deduped = _dedupe(rows)
    with_evidence = sum(1 for r, _ in deduped if r.evidence)
    with_target = sum(1 for r, _ in deduped if r.commitment.is_measurable)
    st.caption(
        f"{len(deduped)} commitments · {with_evidence} with evidence · "
        f"{with_target} measurable targets"
    )

    flt = st.pills("Show", _FILTER_OPTS, default="All", key="trail_filter",
                   label_visibility="collapsed") or "All"
    shown = [(r, m) for r, m in deduped if _matches(r, flt)]

    # group rows under their parent objective
    by_id = {r.commitment.id: (r, m) for r, m in shown}
    children: dict[int | None, list] = {}
    for r, m in shown:
        children.setdefault(r.commitment.parent_id, []).append((r, m))
    objectives = [
        (r, m) for r, m in shown
        if r.commitment.kind == CandidateType.OBJECTIVE
    ]
    orphans = [
        (r, m) for r, m in children.get(None, [])
        if r.commitment.kind != CandidateType.OBJECTIVE
    ]

    sel = st.session_state.get("trail_sel")

    left, right = st.columns([1.5, 1], gap="large")
    with left:
        if not shown:
            st.caption("Nothing matches this filter.")
        for obj_row, mentions in objectives:
            obj = obj_row.commitment
            kids = children.get(obj.id, [])
            _objective_group(state, obj_row, mentions, kids, sel)
        for row, mentions in orphans:
            _trail_row(row, mentions, sel)
    with right:
        with st.container(key="ptinsp"):
            _inspector(state, by_id, shown)

    st.divider()
    _timeline(state)


def _matches(row, flt: str) -> bool:
    if flt == "Has evidence":
        return bool(row.evidence)
    if flt == "Missing evidence":
        return not row.evidence
    if flt == "Measurable target":
        return row.commitment.is_measurable
    return True


def _objective_group(state, obj_row, mentions, kids, sel) -> None:
    obj = obj_row.commitment
    with st.container(key=f"ptg_{obj.id}", gap=None):
        with st.container(key=f"ptghead_{obj.id}", gap=None):
            st.button(
                f"{obj.code + ' · ' if obj.code else ''}"
                f"{display_title(obj.title)}",
                key=f"hl_t_{obj.id}", type="tertiary",
                on_click=_inspect, args=(obj.id,))
            n = len(kids) + 1
            ev = sum(1 for r, _ in [(obj_row, mentions), *kids]
                     if r.evidence)
            st.caption(
                f"{n} commitment{'s' if n != 1 else ''} · "
                f"{ev} with evidence · {n - ev} still missing evidence")
        for row, mentions in kids:
            _trail_row(row, mentions, sel)


def _trail_row(row, mentions, sel, grouped: bool = False) -> None:
    com = row.commitment
    key = (f"ptt_sel_{com.id}" if sel == com.id else f"ptt_{com.id}")
    with st.container(key=key, gap=None):
        st.button(display_title(com.title), key=f"hl_t_{com.id}",
                  type="tertiary", on_click=_inspect, args=(com.id,))
        meta = [
            KIND_LABEL[com.kind].upper(),
            f"p.{com.source_page}" if com.source_page else "—",
        ]
        if com.deadline_year:
            meta.append(f"deadline {com.deadline_year}")
        meta.append(_evidence_note(row))
        if mentions > 1:
            meta.append(f"{mentions} source mentions")
        st.caption(" · ".join(meta))


def _inspect(com_id: int) -> None:
    st.session_state["trail_sel"] = com_id


def _inspector(state, by_id, shown) -> None:
    sel = st.session_state.get("trail_sel")
    row = by_id.get(sel, (None, 0))[0] if sel in by_id else None
    if row is None:
        if not shown:
            st.caption("Select a commitment to read its trail.")
            return
        row, _ = shown[0]
        st.session_state["trail_sel"] = row.commitment.id
    mentions = by_id.get(row.commitment.id, (row, 1))[1]
    _trail_detail(state, row, mentions)


def _trail_detail(state, row, mentions: int) -> None:
    com = row.commitment
    st.subheader(com.title)
    render_en(com.title)

    meta = [KIND_LABEL[com.kind].upper()]
    if com.source_page:
        meta.append(f"Strategy · p.{com.source_page}")
    if com.deadline_year:
        meta.append(f"Deadline {com.deadline_year}")
    if com.is_measurable:
        meta.append(f"Target {com.target_value:g} {com.unit}")
    if com.responsible_org:
        meta.append(f"who: {com.responsible_org}")
    if mentions > 1:
        meta.append(f"{mentions} source mentions")
    st.caption(" · ".join(meta))
    if row.status != Status.UNKNOWN:
        st.badge(f"Source says: {STATUS_LABEL[row.status]}",
                 color=_STATUS_BADGE_COLOR.get(row.status, "gray"))

    # --- promise ------------------------------------------------------
    st.markdown("**PROMISE**")
    cand = (state.policy.candidate(com.candidate_id)
            if com.candidate_id else None)
    excerpt = cand.source_excerpt if cand else com.summary
    if excerpt:
        st.markdown(f"> {excerpt[:1500]}")
        render_en(excerpt[:1500])
    else:
        st.caption("No source wording stored for this commitment.")

    # --- evidence -----------------------------------------------------
    groups: dict[RelationshipType, list] = {}
    for ev, rel in zip(row.evidence, row.relationships):
        groups.setdefault(rel, []).append(ev)

    st.markdown("**IMPLEMENTATION**")
    impl = groups.get(RelationshipType.DIRECT_IMPLEMENTATION, [])
    if impl:
        for ev in impl:
            _evidence_line(ev)
        if row.status_excerpt:
            st.caption(f"“{row.status_excerpt}”")
    else:
        st.caption("No confirmed implementation evidence yet.")

    support = [ev for rel in (RelationshipType.SUPPORTING,
                              RelationshipType.INDIRECT)
               for ev in groups.get(rel, [])]
    if support:
        st.markdown("**SUPPORTING EVIDENCE**")
        for ev in support:
            _evidence_line(ev)

    budget_items = groups.get(RelationshipType.BUDGET, [])
    if budget_items or row.budgets:
        st.markdown("**BUDGET**")
        for ev in budget_items:
            _evidence_line(ev)
        for b in row.budgets[:_MAX_BUDGET_LINES]:
            st.caption(
                f"{huf(b.amount_huf)} — {BUDGET_LABEL[b.kind]} "
                f"({b.fiscal_year or 'year unknown'}) — "
                f"“{b.description}”  \n"
                f"[source]({b.source_url})")
        if len(row.budgets) > _MAX_BUDGET_LINES:
            st.caption(f"… and {len(row.budgets) - _MAX_BUDGET_LINES} "
                       "more figures in the sources")

    # --- gaps ----------------------------------------------------------
    if row.gaps:
        st.markdown("**STILL MISSING**")
        for gap in row.gaps:
            st.markdown(f"- {gap}")


def _evidence_line(ev) -> None:
    meta = [ev.publisher or "official source"]
    if ev.published_on:
        meta.append(str(ev.published_on))
    meta.append(STATUS_LABEL[ev.status_hint])
    st.markdown(f"- [{ev.title}]({ev.url})")
    st.caption(" · ".join(meta))


def _timeline(state) -> None:
    st.subheader("Dates we know")
    events: list[tuple[int, str]] = []
    for com in state.policy.commitments():
        if com.deadline_year:
            events.append((com.deadline_year, f"deadline — {com.title}"))
    for link in state.evidence.links():
        if link.review_status != ReviewStatus.ACCEPTED:
            continue
        ev = state.evidence.evidence(link.evidence_id)
        if ev and ev.published_on:
            events.append((ev.published_on.year, f"published — {ev.title}"))
    if not events:
        st.caption("No confirmed dates yet.")
        return
    for year, label in sorted(set(events)):
        st.caption(f"**{year}** — {label}")
