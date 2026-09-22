"""One small visual system for Paper Trail.

Palette and component rules live here; screens inject this once via
`inject()`. Keyed containers (`st.container(key=...)`) render a stable
`st-key-*` class, which is what the selectors hook onto — no brittle
testid chains.
"""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
/* ---- palette ------------------------------------------------------------
   bg #F7F8FA · surface #FFF · muted #F1F3F5 · border #D9DEE5
   text #20242C / #68707D · accent #2F6F5E · danger #A04A43 · amber #8A6A1F */

/* calmer type scale ----------------------------------------------------- */
.stApp h1 { font-size: 1.9rem; font-weight: 700; }
.stApp h2 { font-size: 1.35rem; font-weight: 600; }
.stApp h3 { font-size: 1.1rem;  font-weight: 600; }
.stApp [data-testid="stCaptionContainer"] { color: #68707D; }

/* compact review rows ----------------------------------------------------
   keyed container per row: tight padding, left accent when selected      */
[class*="st-key-row-"] {
    background: #FFFFFF;
}
[class*="st-key-row-"] .stCheckbox { padding-top: 0.35rem; }

/* selected row — injected per row, see _selected() in screens */
.pt-selected {
    border-color: #2F6F5E !important;
    box-shadow: inset 3px 0 0 #2F6F5E;
}
/* rejected rows go quiet rather than alarming */
.pt-rejected { opacity: 0.6; }

/* badges ------------------------------------------------------------------ */
.pt-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 1px 7px;
    border-radius: 4px;
    border: 1px solid #D9DEE5;
    color: #68707D;
    background: #F1F3F5;
}
.pt-badge-ok    { color: #2F6F5E; border-color: #BFD8D0; background: #EEF5F2; }
.pt-badge-warn  { color: #8A6A1F; border-color: #E3D6B0; background: #FAF4E4; }
.pt-badge-quiet { opacity: 0.7; }

/* source / provenance block ---------------------------------------------- */
.pt-source {
    border-left: 3px solid #D9DEE5;
    padding: 0.4rem 0 0.4rem 0.9rem;
    color: #20242C;
    font-size: 0.92rem;
}
.pt-source-label {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase; color: #68707D;
}

/* machine translation — always secondary to the Hungarian source ---------- */
.pt-mt { color: #68707D; font-style: italic; font-size: 0.88rem; }

/* batch action bar — pinned to the bottom of the scroll area -------------- */
.st-key-batchbar {
    position: sticky;
    bottom: 0;
    z-index: 90;
    background: #FFFFFF;
    border-top: 1px solid #D9DEE5;
    padding: 0.5rem 0.25rem;
}

/* destructive buttons (reject) — restrained red --------------------------- */
[class*="st-key-danger-"] button,
.st-key-batchbar .st-key-danger button {
    color: #A04A43 !important;
    border-color: #D8B8B4 !important;
}
[class*="st-key-danger-"] button:hover {
    color: #7E3B35 !important;
    border-color: #A04A43 !important;
    background: #FAF1F0 !important;
}

/* evidence / commitment header blocks ------------------------------------- */
.pt-section {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em;
    text-transform: uppercase; color: #68707D;
    margin: 0.35rem 0 0.15rem;
}
.pt-arrow { color: #B7BEC8; margin: 0.15rem 0 0.15rem 1rem; }

/* filter row: keep pills/segmented control calm --------------------------- */
.st-key-filters { margin-bottom: 0.25rem; }
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def badge(text: str, kind: str = "") -> str:
    """Small uppercase label — `kind` picks ok/warn/quiet tint."""
    cls = "pt-badge" + (f" pt-badge-{kind}" if kind else "")
    return f'<span class="{cls}">{text}</span>'


def selected(key: str) -> None:
    """Left-accent a keyed row container (call only when selected)."""
    st.markdown(
        f"<style>.st-key-{key}{{border-color:#2F6F5E!important;"
        "box-shadow:inset 3px 0 0 #2F6F5E}}</style>",
        unsafe_allow_html=True,
    )


def quiet(key: str) -> None:
    """Dim a rejected row."""
    st.markdown(
        f"<style>.st-key-{key}{{opacity:.6}}</style>",
        unsafe_allow_html=True,
    )
