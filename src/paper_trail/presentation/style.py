"""The only custom stylesheet — config.toml owns colours/typography.

CSS here covers what theme options cannot express: workspace width,
compact review rows, link-style headline buttons, the inspected-row
state, the inline batch bar, the paper-trail objective groups and the
inspector column. Everything is targeted through stable ``st-key-*``
hooks or ``pt-*`` classes — no broad DOM selectors.
"""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
:root {
  --pt-bg: #f6f7f8;
  --pt-surface: #ffffff;
  --pt-surface-muted: #f1f3f4;
  --pt-text: #20252b;
  --pt-text-muted: #6c747d;
  --pt-border: #d9dee3;
  --pt-accent: #2f6f5e;
  --pt-accent-hover: #245748;
  --pt-accent-soft: #e8f2ee;
  --pt-radius: 7px;
}

/* keep the working area readable on wide screens */
.block-container {
  max-width: 1320px;
  padding-top: 2rem;
  padding-bottom: 3rem;
}

/* ---- compact review rows ------------------------------------------
   Row containers are keyed ptrow_<scope>_<id>; the inspected row uses
   ptrow_sel_<scope>_<id> so one substring selector covers both. */
[class*="st-key-ptrow"] {
  padding: 6px 10px 6px 4px;
  border-bottom: 1px solid var(--pt-border);
}
[class*="st-key-ptrow"]:hover { background: #fafbfb; }
[class*="st-key-ptrow_sel"] {
  background: var(--pt-accent-soft);
  box-shadow: inset 3px 0 0 var(--pt-accent);
}
/* tighten the checkbox column inside rows */
[class*="st-key-ptrow"] .stCheckbox { padding-top: 2px; }

/* column header row above a list */
.st-key-pthead {
  padding: 2px 10px 6px 4px;
  border-bottom: 1px solid var(--pt-border);
}

/* ---- headline buttons: text-like, underlined on hover --------------
   Every "inspect this record" button is keyed hl_<scope>_<id>. */
[class*="st-key-hl_"] button {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
  min-height: 0 !important;
  height: auto !important;
  width: auto !important;
  max-width: 100% !important;
  color: var(--pt-text) !important;
  font-weight: 600 !important;
  text-align: left !important;
  justify-content: flex-start !important;
}
[class*="st-key-hl_"] button:hover {
  color: var(--pt-accent) !important;
  text-decoration: underline !important;
  background: transparent !important;
}
[class*="st-key-hl_"] button:focus-visible {
  outline: 2px solid var(--pt-accent) !important;
  outline-offset: 3px !important;
  border-radius: 3px !important;
}
[class*="st-key-ptrow_sel"] [class*="st-key-hl_"] button,
[class*="st-key-ptt_sel"] [class*="st-key-hl_"] button {
  color: var(--pt-accent) !important;
}

/* ---- batch action bar ----------------------------------------------
   A keyed horizontal container rendered right under the list. */
[class*="st-key-ptbatch"] {
  gap: .6rem;
  padding: .65rem .85rem;
  margin: .8rem 0 .4rem;
  border: 1px solid var(--pt-border);
  border-radius: var(--pt-radius);
  background: var(--pt-surface);
}

/* ---- inspector column ------------------------------------------------ */
.st-key-ptinsp {
  border-left: 1px solid var(--pt-border);
  padding-left: 1.4rem;
  min-height: 420px;
}

/* ---- paper trail: grouped objective list -----------------------------
   ptg_<id> wraps one objective group, ptghead_<id> is its header,
   ptt_<id> / ptt_sel_<id> are the compact child rows. */
[class*="st-key-ptg_"] {
  margin-bottom: .9rem;
  border: 1px solid var(--pt-border);
  border-radius: var(--pt-radius);
  overflow: hidden;
  background: var(--pt-surface);
}
[class*="st-key-ptghead_"] {
  padding: .6rem .9rem;
  background: var(--pt-surface-muted);
  border-bottom: 1px solid var(--pt-border);
}
[class*="st-key-ptt_"] {
  padding: .55rem .9rem;
  border-bottom: 1px solid var(--pt-border);
}
[class*="st-key-ptt_"]:hover { background: #fafbfb; }
[class*="st-key-ptt_sel"] {
  background: var(--pt-accent-soft);
  box-shadow: inset 3px 0 0 var(--pt-accent);
}

/* ---- sidebar navigation: quiet, left-aligned ------------------------- */
[class*="st-key-nav_"] button { justify-content: flex-start; }
</style>
"""


def inject() -> None:
    # st.html strips style-only content — markdown injection is the
    # reliable path for a document-wide <style> block
    st.markdown(_CSS, unsafe_allow_html=True)
