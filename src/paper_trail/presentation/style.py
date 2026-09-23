"""Single stylesheet for the review workspace; keyed hooks only."""
from html import escape
import streamlit as st

_CSS = """
<style>
:root {
  --pt-bg: #f6f7f8; --pt-surface: #ffffff; --pt-surface-muted: #f1f3f4;
  --pt-text: #20252b; --pt-text-muted: #606a74; --pt-border: #d9dee3;
  --pt-accent: #2f6f5e; --pt-accent-hover: #245748; --pt-accent-soft: #e8f2ee;
  --pt-danger: #a8473f; --pt-radius: 7px;
  --space-1: 4px; --space-2: 8px; --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px;
}
.stMainBlockContainer { max-width: 1320px; padding-top: 4rem; padding-bottom: 3rem; }
.st-key-pt_breadcrumb { color: var(--pt-text-muted); letter-spacing: .045em; }
.st-key-pt_pagehead { padding-bottom: 16px; border-bottom: 1px solid var(--pt-border); }
.st-key-pt_pagehead h1 { padding-top: 0; padding-bottom: 8px; letter-spacing: -.02em; }
.st-key-pt_guide button { color: var(--pt-text-muted); }
[class*="st-key-ptlist_"] {
  background: var(--pt-surface); border: 1px solid var(--pt-border);
  border-radius: var(--pt-radius); overflow: hidden;
}
[class*="st-key-ptrow_"], [class*="st-key-ptt_"] {
  padding: 11px 12px; border-bottom: 1px solid var(--pt-border);
}
[class*="st-key-ptrow_"]:hover, [class*="st-key-ptt_"]:hover { background: #fafbfb; }
[class*="st-key-ptrow_sel_"], [class*="st-key-ptt_sel_"] {
  background: var(--pt-accent-soft); box-shadow: inset 3px 0 0 var(--pt-accent);
}
[class*="st-key-ptrow_sel_"]:hover, [class*="st-key-ptt_sel_"]:hover { background: var(--pt-accent-soft); }
[class*="st-key-hl_"] button {
  background: transparent !important; border: 0 !important;
  box-shadow: none !important; padding: 0 !important; min-height: 24px !important;
  height: auto !important; color: var(--pt-text) !important;
  text-align: left !important; justify-content: flex-start !important;
}
[class*="st-key-hl_"] button p { font-weight: 600; line-height: 1.4; overflow-wrap: anywhere; }
[class*="st-key-hl_"] button:hover { color: var(--pt-accent) !important; text-decoration: underline; }
[class*="st-key-hl_"] button:focus-visible {
  outline: 2px solid var(--pt-accent) !important; outline-offset: 3px; border-radius: 3px;
}
[class*="st-key-ptbatch_"] {
  padding: 8px 12px; border: 1px solid var(--pt-border);
  border-radius: var(--pt-radius); background: var(--pt-surface);
}
.st-key-ptinsp { border-left: 1px solid var(--pt-border); padding-left: 24px; min-height: 480px; }
.pt-label { margin: 12px 0 4px; padding: 0; text-transform: uppercase; letter-spacing: .06em;
  font-size: .72rem; line-height: 1.4; font-weight: 700; color: var(--pt-text-muted); }
.pt-quote { margin: 0; border-left: 3px solid var(--pt-border); padding-left: 12px;
  color: var(--pt-text); line-height: 1.55; white-space: normal; overflow-wrap: anywhere; }
.pt-gap { padding: 10px 12px; background: var(--pt-surface-muted); border-radius: 7px;
  color: var(--pt-text-muted); font-size: .87rem; line-height: 1.55; }
.pt-badge { display: inline-flex; padding: 2px 6px; border: 1px solid var(--pt-border);
  border-radius: 4px; font-size: .7rem; font-weight: 600; color: var(--pt-text-muted);
  background: var(--pt-surface-muted); text-transform: uppercase; letter-spacing: .025em; }
[class*="st-key-ptg_"] { border: 1px solid var(--pt-border); border-radius: 7px;
  overflow: hidden; background: var(--pt-surface); }
[class*="st-key-ptghead_"] { padding: 10px 12px; background: var(--pt-surface-muted);
  border-bottom: 1px solid var(--pt-border); }
[class*="st-key-nav_"] button { display: block !important; justify-content: flex-start !important; text-align: left !important; min-height: 34px; padding: 4px 10px; }
[class*="st-key-nav_"] button p { width: 100%; text-align: left; }
[class*="st-key-nav_active_"] button { background: var(--pt-accent-soft); color: var(--pt-accent); }
[class*="st-key-nav_"] button:focus-visible, [class*="st-key-ptbatch_"] button:focus-visible {
  outline: 2px solid var(--pt-accent); outline-offset: 3px;
}
[class*="st-key-primary_"] button:not(:disabled) {
  background: var(--pt-accent); color: white; border-color: var(--pt-accent);
}
[class*="st-key-primary_"] button:not(:disabled):hover { background: var(--pt-accent-hover); }
[class*="st-key-danger_"] button:not(:disabled) {
  color: var(--pt-danger); background: white; border-color: #e3c4c0;
}
@media (max-width: 640px) {
  .stMainBlockContainer { padding: 4rem 1rem 1rem; }
  .st-key-pt_pagehead { display: block; }
  .st-key-pt_guide { margin-top: 8px; }
  .st-key-ptinsp { border-left: 0; border-top: 1px solid var(--pt-border); padding: 16px 0 0; min-height: 0; }
}
</style>
"""


def inject():
    st.html(_CSS)


def label(text, *, level=4):
    st.html(f'<h{level} class="pt-label">{escape(text)}</h{level}>')


def quote(text):
    st.html(f'<blockquote class="pt-quote">{escape(text)}</blockquote>')


def gaps(items):
    st.html('<div class="pt-gap">' + '<br>'.join(escape(item) for item in items) + '</div>')


def badge(text):
    st.html(f'<span class="pt-badge">{escape(text)}</span>', width="content")
