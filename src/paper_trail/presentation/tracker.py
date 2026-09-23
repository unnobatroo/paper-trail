"""Screen 3 — The paper trail: read-only inspection.

Left: commitments grouped under their objectives as compact rows.
Right: the selected commitment's full trail — promise → evidence →
what's still missing. No selection or review controls live here.
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
    display_title,
    title_groups,
    huf,
)
from .translate import render_en
from .guidance import page_header
from .style import label, quote, gaps, badge

_FILTER_OPTS = ["All", "Has evidence", "Missing evidence",
                "Measurable target"]
_MAX_BUDGET_LINES = 6


def _dedupe(rows):
    """Keep all original trail rows behind each display title."""
    return title_groups(rows, lambda r: r.commitment.title, lambda r: r.commitment.kind)


def _objective_groups(groups):
    """Use recorded parents or explicit code ancestry, never semantic guessing.

    Resolve before filtering so children remain visible when their objective
    does not match the evidence filter. Duplicate IDs map to the same heading.
    """
    by_id = {r.commitment.id: g for g in groups for r in g}
    objectives = [g for g in groups if g[0].commitment.kind == CandidateType.OBJECTIVE]

    def parent(group):
        for row in group:
            p = by_id.get(row.commitment.parent_id)
            if p is not None and p is not group:
                return p
        code = group[0].commitment.code or ""
        ancestors = [g for g in objectives if g is not group and g[0].commitment.code
                     and code.startswith(g[0].commitment.code + ".")]
        return max(ancestors, key=lambda g: len(g[0].commitment.code)) if ancestors else None

    grouped = {}
    for group in groups:
        root, seen = group, set()
        while root[0].commitment.id not in seen:
            seen.add(root[0].commitment.id)
            p = parent(root)
            if p is None:
                break
            root = p
        key = root[0].commitment.id if root[0].commitment.kind == CandidateType.OBJECTIVE else None
        grouped.setdefault(key, []).append(group)
    return grouped, by_id


def render(state) -> None:
    page_header("Paper trail", "trail")
    rows = state.metrics.trail()
    if not rows:
        st.info("Nothing here yet — confirm some commitments and "
                "matches first.")
        return

    groups = _dedupe(rows)
    with_evidence = sum(any(r.evidence for r in group) for group in groups)
    st.caption(f"{len(groups)} commitments · {with_evidence} with evidence · Read-only")
    flt = st.pills("Show", _FILTER_OPTS, default="All", key="trail_filter",
                   label_visibility="collapsed") or "All"
    grouped, by_id = _objective_groups(groups)
    ordered = sorted(grouped.items(), key=lambda item: item[0] is None)
    shown = [g for _, children in ordered for g in children if any(_matches(r, flt) for r in g)]
    if not shown:
        st.caption("Nothing matches this filter.")
        return
    shown_ids = {g[0].commitment.id for g in shown}
    if st.session_state.get("trail_sel") not in shown_ids:
        st.session_state["trail_sel"] = shown[0][0].commitment.id
    selected = st.session_state.trail_sel
    left, right = st.columns([1.6, 1], gap=24)
    with left, st.container(height=500, border=False, key="trail_list"):
        for root_id, children in ordered:
            visible = [g for g in children if g[0].commitment.id in shown_ids]
            if not visible:
                continue
            root = by_id[root_id][0].commitment if root_id else None
            with st.container(key=f"ptg_{root_id}", gap=None):
                with st.container(key=f"ptghead_{root_id}", gap=None):
                    st.markdown("**" + (f"{root.code + ' · ' if root.code else ''}{display_title(root.title)}"
                                         if root else "Other commitments") + "**")
                    st.caption(f"{len(visible)} commitments · {sum(any(r.evidence for r in g) for g in visible)} with evidence")
                for group in visible:
                    _trail_row(group, selected)
    with right:
        with st.container(key="ptinsp"):
            group = next(g for g in shown if g[0].commitment.id == selected)
            row = group[0]
            if len(group) > 1:
                row = st.selectbox("Source mention", group,
                    format_func=lambda r: f"p.{r.commitment.source_page} · {len(r.evidence)} evidence source{'s' if len(r.evidence) != 1 else ''} · mention {r.commitment.id}",
                    key=f"trail_mention_{selected}")
            _trail_detail(state, row, len(group))
    with st.expander("Dates we know", icon=":material/calendar_month:"):
        _timeline(state)


def _matches(row, flt: str) -> bool:
    if flt == "Has evidence":
        return bool(row.evidence)
    if flt == "Missing evidence":
        return not row.evidence
    if flt == "Measurable target":
        return row.commitment.is_measurable
    return True


def _trail_row(group, selected):
    row = group[0]
    com = row.commitment
    with st.container(key=f"ptt_{'sel_' if selected == com.id else ''}{com.id}", gap=None):
        st.button(display_title(com.title), key=f"hl_t_{com.id}", type="tertiary",
                  on_click=_inspect, args=(com.id,))
        meta = [KIND_LABEL[com.kind].upper(), f"p.{com.source_page}" if com.source_page else "Strategy"]
        if com.deadline_year:
            meta.append(f"deadline {com.deadline_year}")
        if len(group) > 1:
            meta.append(f"{len(group)} source mentions")
        st.caption(" · ".join(meta))
        sources = {e.url for r in group for e in r.evidence}
        note = (f"{len(sources)} evidence source{'s' if len(sources) != 1 else ''}"
                if sources else "No evidence yet")
        statuses = list(dict.fromkeys(STATUS_LABEL[r.status].capitalize() for r in group if r.status != Status.UNKNOWN))
        st.caption(" · ".join([note, *statuses]))


def _inspect(com_id: int) -> None:
    st.session_state["trail_sel"] = com_id


def _trail_detail(state, row, mentions: int) -> None:
    com = row.commitment
    label("Selected paper trail", level=2)
    st.subheader(display_title(com.title))
    render_en(display_title(com.title))

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
        badge(f"Source says: {STATUS_LABEL[row.status]}")

    # --- promise ------------------------------------------------------
    label("Promise")
    cand = (state.policy.candidate(com.candidate_id)
            if com.candidate_id else None)
    excerpt = cand.source_excerpt if cand else com.summary
    if excerpt:
        quote(excerpt)
        render_en(excerpt)
    else:
        st.caption("No source wording stored for this commitment.")

    # --- evidence -----------------------------------------------------
    groups: dict[RelationshipType, list] = {}
    for ev, rel in zip(row.evidence, row.relationships):
        groups.setdefault(rel, []).append(ev)

    impl = groups.get(RelationshipType.DIRECT_IMPLEMENTATION, [])
    if impl:
        label("Implementation")
        for ev in impl:
            _evidence_line(ev)
        if row.status_excerpt:
            st.caption(f"“{row.status_excerpt}”")

    support = [ev for rel in (RelationshipType.SUPPORTING,
                              RelationshipType.INDIRECT)
               for ev in groups.get(rel, [])]
    if support:
        label("Supporting evidence")
        for ev in support:
            _evidence_line(ev)

    budget_items = groups.get(RelationshipType.BUDGET, [])
    if budget_items or row.budgets:
        label("Budget")
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
        label("Still missing")
        gaps(row.gaps)


def _evidence_line(ev) -> None:
    meta = [ev.publisher or "official source"]
    if ev.published_on:
        meta.append(str(ev.published_on))
    meta.append(STATUS_LABEL[ev.status_hint])
    st.markdown(f":material/open_in_new: [{display_title(ev.title)}]({ev.url})")
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
