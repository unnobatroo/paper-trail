"""Screen 1 — Check what we found in the strategy."""

from __future__ import annotations

import streamlit as st

from ..domain.enums import CandidateType
from .formatting import KIND_LABEL


def render(state) -> None:
    st.header("Check what we found")
    queue = state.review.queue()
    accepted = state.policy.commitments()

    if not queue:
        if not accepted:
            st.info("Nothing to check yet — read the strategy from the sidebar.")
        else:
            st.success(f"All checked. {len(accepted)} commitments are on record.")
        return

    st.write(
        f"We found **{len(queue)}** possible commitments in the strategy. "
        "Check each one against the excerpt — confirm the ones that matter, "
        "reject the rest. Only confirmed items get used to find evidence."
    )
    if len(queue) > 10 and st.button(
        f"Skip the remaining {len(queue)} (I've confirmed what I need)",
        key="skip_rest",
    ):
        state.review.reject_all_pending()
        st.rerun()

    parent_options = {
        "— on its own —": None,
        **{
            f"{c.code + ' – ' if c.code else ''}{c.title}": c.id
            for c in accepted
        },
    }

    for cand in queue:
        label = KIND_LABEL[cand.suggested_type]
        with st.container(border=True):
            st.markdown(
                f"**{cand.normalized_title}**  \n"
                f"`{label}`"
                + (f" · code `{cand.code}`" if cand.code else "")
                + f" · page {cand.source_page} of the strategy"
            )
            st.write(cand.text)

            meta = []
            if cand.responsible_org:
                meta.append(f"who: {cand.responsible_org}")
            if cand.timeframe:
                meta.append(f"when: {cand.timeframe}")
            if cand.target_value is not None:
                meta.append(f"target: {cand.target_value:g} {cand.unit or ''}".strip())
            if cand.deadline_year:
                meta.append(f"deadline: {cand.deadline_year}")
            if meta:
                st.caption(" · ".join(meta))

            with st.expander(
                f"Where the strategy says this (page {cand.source_page})"
            ):
                st.caption(cand.source_excerpt)
                if not cand.excerpt_on_page:
                    st.caption("We couldn't re-find this quote on the page — "
                               "worth a closer look.")

            c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.8, 0.8])
            kind = c1.selectbox(
                "What is it",
                list(CandidateType),
                index=list(CandidateType).index(cand.suggested_type),
                format_func=lambda k: KIND_LABEL[k],
                key=f"kind_{cand.id}",
            )
            title = c2.text_input(
                "Short name", value=cand.normalized_title, key=f"title_{cand.id}"
            )
            parent = c3.selectbox(
                "Part of", list(parent_options),
                format_func=lambda k: k,
                key=f"parent_{cand.id}",
            )
            c4.write("")
            if c4.button("Confirm", key=f"acc_{cand.id}", type="primary"):
                state.review.accept_candidate(
                    cand.id, kind=kind, title=title.strip(),
                    parent_id=parent_options[parent],
                )
                st.rerun()
            if c4.button("Reject", key=f"rej_{cand.id}"):
                state.review.reject_candidate(cand.id)
                st.rerun()
