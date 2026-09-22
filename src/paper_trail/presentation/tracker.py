"""Screen 3 — The paper trail: confirmed commitments and evidence only.

Calm vertical reading: POLICY COMMITMENT → what the evidence shows →
what is still missing. Objectives stay as section headers.
"""

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
_MAX_BUDGET_LINES = 6


def render(state) -> None:
    st.header("Paper trail")
    rows = state.metrics.trail()
    objectives = state.policy.commitments(CandidateType.OBJECTIVE)

    if not rows and not objectives:
        st.info("Nothing here yet — confirm some commitments and matches first.")
        return

    with_evidence = sum(1 for r in rows if r.evidence)
    with_target = sum(1 for r in rows if r.commitment.is_measurable)
    st.caption(
        f"{len(objectives)} objective(s) · {len(rows)} commitments · "
        f"{with_evidence} with evidence · {with_target} with a measurable target"
    )

    # group rows under their parents for readability
    children: dict[int | None, list] = {}
    for r in rows:
        children.setdefault(r.commitment.parent_id, []).append(r)
    rows_by_id = {r.commitment.id: r for r in rows}

    for obj in objectives:
        st.subheader(
            f"{obj.code + ' — ' if obj.code else ''}{obj.title}")
        render_en(obj.title)
        obj_row = rows_by_id.get(obj.id)
        if obj_row:
            _block(obj_row)
        kids = children.get(obj.id, [])
        if not kids and not obj_row:
            st.caption("No confirmed measures here yet.")
        for row in kids:
            _block(row)
    for row in children.get(None, []):
        if row.commitment.kind != CandidateType.OBJECTIVE:
            _block(row)

    st.divider()
    _timeline(state)


def _block(row) -> None:
    """One commitment as a vertical trace: commitment → evidence → gaps."""
    com = row.commitment
    with st.container(border=True, key=f"trail-{com.id}"):
        st.markdown(
            '<span class="pt-section">Policy commitment</span>',
            unsafe_allow_html=True)
        st.markdown(
            f"**{com.code + ' — ' if com.code else ''}{com.title}**")
        render_en(com.title)

        meta = [KIND_LABEL[com.kind], f"strategy p.{com.source_page}"]
        if com.is_measurable:
            meta.append(f"target {com.target_value:g} {com.unit}")
        if com.deadline_year:
            meta.append(f"deadline {com.deadline_year}")
        if com.responsible_org:
            meta.append(f"who: {com.responsible_org}")
        st.caption(" · ".join(meta))

        if row.status != Status.UNKNOWN:
            st.markdown(
                f"What the evidence suggests: **{STATUS_LABEL[row.status]}**"
                + (f" — “{row.status_excerpt}”" if row.status_excerpt else ""))

        groups: dict[RelationshipType, list] = {}
        for ev, rel in zip(row.evidence, row.relationships):
            groups.setdefault(rel, []).append(ev)

        if groups:
            st.markdown(
                '<div class="pt-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<span class="pt-section">What we found</span>',
                unsafe_allow_html=True)
            for rel in _GROUP_ORDER:
                items = groups.get(rel)
                if not items:
                    continue
                st.markdown(f"*{ _GROUP_HEAD[rel] }*")
                for ev in items:
                    st.markdown(
                        f"- [{ev.title}]({ev.url}) — {ev.publisher} · "
                        f"{evidence_kind(ev.url, ev.title)}"
                        + (f", {ev.published_on}" if ev.published_on else ""))
                    st.caption(
                        f"  source suggests: {STATUS_LABEL[ev.status_hint]}"
                        + (f" — “{ev.status_excerpt}”"
                           if ev.status_excerpt else ""))

            if row.budgets:
                for b in row.budgets[:_MAX_BUDGET_LINES]:
                    st.caption(
                        f"  {huf(b.amount_huf)} — {BUDGET_LABEL[b.kind]} "
                        f"({b.fiscal_year or 'year unknown'}) — "
                        f"“{b.description}”  \n"
                        f"  [source]({b.source_url})")
                if len(row.budgets) > _MAX_BUDGET_LINES:
                    st.caption(f"  … and {len(row.budgets) - _MAX_BUDGET_LINES} "
                               "more figures in the sources")

        if row.gaps:
            st.markdown(
                '<div class="pt-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<span class="pt-section">What is still missing</span>',
                unsafe_allow_html=True)
            for gap in row.gaps:
                st.markdown(f"- {gap}")


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
