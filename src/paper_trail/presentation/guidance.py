"""Short, contextual explanations of the existing review workflow."""
import streamlit as st

from ..domain.enums import RelationshipType


REL_HELP = {
    RelationshipType.DIRECT_IMPLEMENTATION: "The source directly documents work on this commitment. It may describe planned, ongoing or completed work; check the excerpt.",
    RelationshipType.SUPPORTING: "The source adds relevant context or supporting detail, but does not directly establish implementation.",
    RelationshipType.BUDGET: "The source records an estimated cost, approved funding or reported spending. A money figure alone does not prove completion.",
    RelationshipType.INDIRECT: "The source concerns related work, but its connection to this commitment is indirect.",
    RelationshipType.UNRELATED: "The source does not establish a useful relationship to this commitment.",
}

_GUIDES = {
    "commitments": (
        "Check the promise against the original strategy before confirming it.",
        [
            ("Inspect or select", "Click a title to read it. Check a box to include it in a batch action. These actions are independent."),
            ("Objective · measure · target", "An objective states an intended outcome. A measure describes an action. A target states a specific result to aim for, often with a value or deadline."),
            ("Confirmed", "Accepted as a commitment from the strategy. This does not mean the work is complete."),
            ("Source mentions", "Repeated, identically titled records share a display row. Each original passage remains available in the inspector."),
        ],
    ),
    "evidence": (
        "Search official sources, then review how each match relates to a commitment.",
        [
            ("Choose → search → review", "Select commitments and run one batch search. Review the resulting matches before they appear in the paper trail."),
            ("Match", "A suggested connection for you to check, not a confirmed finding. Read the matched excerpt and the official source."),
            ("Status", "What the matched source text reports: announced, planned, in preparation, in progress or completed. Background and unclear do not establish implementation."),
            ("Relationship", "How the source relates to the commitment. Your choice is saved when you confirm the selected match."),
        ],
    ),
    "trail": (
        "Read confirmed commitments and their reviewed evidence, grouped by policy objective.",
        [
            ("Read-only", "Click a commitment to inspect its trail. Review decisions are made in Check commitments and Find evidence."),
            ("Implementation", "Reviewed sources linked directly to the commitment. The displayed status describes what those sources report."),
            ("Supporting evidence", "Relevant context and indirect links, separate from direct implementation evidence."),
            ("Still missing", "Gaps in the records reviewed so far. Missing evidence does not establish that no work took place."),
        ],
    ),
}


def page_header(title, context):
    description, definitions = _GUIDES[context]
    with st.container(key="pt_pagehead", horizontal=True, vertical_alignment="top", gap=16):
        with st.container(gap=4):
            st.title(title, anchor=False)
            st.caption(description)
        with st.popover("Review guide", icon=":material/help_outline:", type="tertiary", key="pt_guide"):
            st.subheader("How to read this view", anchor=False)
            for term, definition in definitions:
                st.markdown(f"**{term}**  \n{definition}")
