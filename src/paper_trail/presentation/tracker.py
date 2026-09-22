"""Screen 3 — The paper trail: confirmed commitments and evidence only."""

from __future__ import annotations

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
    evidence_kind,
    huf,
)
from .translate import note, render_en


def render(state) -> None:
    st.header("Paper trail")
    rows = state.metrics.trail()
    objectives = state.policy.commitments(CandidateType.OBJECTIVE)

    if not rows and not objectives:
        st.info("Nothing here yet — confirm some commitments and matches first.")
        return

    with_evidence = sum(1 for r in rows if r.evidence)
    with_target = sum(1 for r in rows if r.commitment.is_measurable)
    with_budget = sum(1 for r in rows if r.budgets)
    st.write(
        f"**{len(objectives)}** objective(s), **{len(rows)}** commitments — "
        f"**{with_evidence}** with evidence, "
        f"**{with_target}** with a measurable target, "
        f"**{with_budget}** with a confirmed budget figure."
    )
    note()

    # group rows under their parents for readability
    children: dict[int | None, list] = {}
    for r in rows:
        children.setdefault(r.commitment.parent_id, []).append(r)
    rows_by_id = {r.commitment.id: r for r in rows}

    for obj in objectives:
        st.subheader(
            f"{obj.code + ' — ' if obj.code else ''}{obj.title}"
        )
        render_en(obj.title)
        obj_row = rows_by_id.get(obj.id)
        if obj_row:
            _body(obj_row)
        kids = children.get(obj.id, [])
        if not kids:
            st.caption("No confirmed measures here yet.")
        for row in kids:
            _row(row)
    for row in children.get(None, []):
        if row.commitment.kind != CandidateType.OBJECTIVE:
            _row(row)

    st.divider()
    _timeline(state)


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
_MAX_BUDGET_LINES = 6


def _row(row) -> None:
    com = row.commitment
    title = f"**{com.code + ' — ' if com.code else ''}{com.title}**"
    title += f"  ·  `{KIND_LABEL[com.kind]}`"
    if row.status != Status.UNKNOWN:
        title += f"  ·  what we know: **{STATUS_LABEL[row.status]}**"
    st.markdown(title)
    render_en(com.title)
    st.caption(f"Józsefváros Climate Strategy, page {com.source_page}")

    details = []
    if com.is_measurable:
        details.append(f"target: {com.target_value:g} {com.unit}")
    if com.deadline_year:
        details.append(f"deadline: {com.deadline_year}")
    if com.responsible_org:
        details.append(f"who: {com.responsible_org}")
    if details:
        st.caption(" · ".join(details))
    _body(row)


def _body(row) -> None:
    # evidence grouped by what it proves, in the order the spec reads:
    # implementation → budget → supporting → related
    groups: dict[RelationshipType, list] = {}
    for ev, rel in zip(row.evidence, row.relationships):
        groups.setdefault(rel, []).append(ev)

    for rel in _GROUP_ORDER:
        items = groups.get(rel)
        if not items:
            continue
        st.markdown("↓")
        st.markdown(f"*{ _GROUP_HEAD[rel] }*")
        for ev in items:
            line = (f"- [{ev.title}]({ev.url}) — {ev.publisher} · "
                    f"{evidence_kind(ev.url, ev.title)}")
            if ev.published_on:
                line += f", {ev.published_on}"
            st.markdown(line)
            st.caption(
                f"  source suggests: {STATUS_LABEL[ev.status_hint]}"
                + (f" — “{ev.status_excerpt}”" if ev.status_excerpt else "")
            )

    for b in row.budgets[:_MAX_BUDGET_LINES]:
        st.caption(
            f"  {huf(b.amount_huf)} — {BUDGET_LABEL[b.kind]} "
            f"({b.fiscal_year or 'year unknown'}) — “{b.description}”  \n"
            f"  [source]({b.source_url})"
        )
    if len(row.budgets) > _MAX_BUDGET_LINES:
        st.caption(f"  … and {len(row.budgets) - _MAX_BUDGET_LINES} "
                   "more figures in the sources")
    for gap in row.gaps:
        st.markdown(f"- **Missing:** {gap}")
    st.write("")


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
