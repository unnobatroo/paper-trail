"""Machine-translation display helper.

Hungarian source text stays canonical — English is rendered underneath in
a muted style and labelled as automatic translation (see MT_DISCLAIMER).
Everything is produced at runtime by the translation service; nothing is
hand-translated.
"""

from __future__ import annotations

import streamlit as st

from ..services.translation import MT_DISCLAIMER, get_translator


@st.cache_data(ttl="1d", show_spinner=False)
def _mt(text: str) -> str | None:
    t = get_translator()
    return t.translate(text) if t else None


def english(text: str | None) -> str | None:
    """English MT of Hungarian source text, honouring the sidebar toggle."""
    if not text or not st.session_state.get("show_en", True):
        return None
    return _mt(text)


def render_en(text: str | None) -> None:
    """Muted English rendering under the Hungarian original, if enabled."""
    en = english(text)
    if en:
        st.caption(f"EN · *{en}*")


def note() -> None:
    """One-page disclaimer, shown once when translations are on."""
    if get_translator() and st.session_state.get("show_en", True):
        st.caption(MT_DISCLAIMER)
