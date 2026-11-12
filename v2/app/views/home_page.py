"""Home: the live Blender bay, followed by the console handoff.

The bay is a separate Vite build served from Streamlit's static folder so the
whole demo runs from one `streamlit run` command.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ui import theme  # noqa: E402

SIM_URL = "/app/static/sim/embed.html"

st.markdown("""
<style>
[data-testid="stMainBlockContainer"] { max-width: none; padding: 56px 0 0; }
[data-testid="stMainBlockContainer"] > div { gap: 0 !important; }
.st-key-home_frame,
.st-key-home_frame > [data-testid="stLayoutWrapper"],
.st-key-home_frame [data-testid="stElementContainer"] {
  margin: 0; gap: 0;
}
.st-key-home_frame [data-testid="stElementContainer"],
.st-key-home_frame iframe {
  display: block; width: 100%; border: 0;
  height: calc(100vh - 56px) !important;
}
.st-key-home_band {
  background: var(--ht-bg);
  border-top: 1px solid var(--ht-line);
  padding: 34px max(26px, calc((100vw - 1240px) / 2 + 26px)) 46px;
}
.st-key-home_band [data-testid="stHorizontalBlock"] { margin-top: 18px; }
.st-key-home_band [data-testid="stPageLink"] a {
  display: flex; align-items: center; justify-content: center;
  padding: 11px 18px; border: 1px solid var(--ht-line);
  border-radius: 10px; background: var(--ht-surface);
  color: var(--ht-ink); font-family: {mono}; font-size: 12px;
  font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
}
.st-key-home_band [data-testid="stColumn"]:first-child [data-testid="stPageLink"] a {
  background: var(--ht-accent); border-color: var(--ht-accent); color: #F2FFFB;
}
.st-key-home_band [data-testid="stPageLink"] a:hover {
  border-color: var(--ht-accent); color: var(--ht-accent);
  text-decoration: none;
}
.st-key-home_band [data-testid="stColumn"]:first-child [data-testid="stPageLink"] a:hover {
  color: #F2FFFB; background: #135F56;
}
</style>
""".replace("{mono}", theme.MONO_FONT), unsafe_allow_html=True)

with st.container(key="home_frame"):
    st.iframe(SIM_URL, height=860)

with st.container(key="home_band"):
    st.markdown(theme.section(
        "The console",
        "Five views, one twin",
        "The bay is the live demonstration. The console is the record: "
        "pre-session risk, the frozen forecast, the retrospective replay, "
        "and the claim boundary."),
        unsafe_allow_html=True)
    st.markdown(
        "".join(theme.pill(label, tone) for label, tone in [
            ("Home · live 3D bay", "info"),
            ("Fold 2 · patient-disjoint", ""),
            ("Display-only", "warn"),
        ]),
        unsafe_allow_html=True)
    cols = st.columns([1.1, 1.1, 4], gap="small")
    with cols[0]:
        st.page_link("views/chair_board_page.py",
                     label="Enter the chair board →")
    with cols[1]:
        st.page_link("views/case_lab_page.py", label="Open the case lab")
