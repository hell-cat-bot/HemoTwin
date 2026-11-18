"""Home: the live Blender bay.

The bay is a separate Vite build served from Streamlit's static folder so the
whole demo runs from one `streamlit run` command. It fills the viewport below
the instrument bar; a downward scroll hands off to the chair board (see
static/sim/embed.html).
"""
from __future__ import annotations

from urllib.parse import urljoin

import streamlit as st

# Streamlit Cloud serves the app under /~/+/; build an absolute URL from the
# app's own base so st.iframe keeps that prefix. Relative strings are treated
# as local file paths by st.iframe in Streamlit 1.66.
try:
    _base = st.context.url or "/"
except Exception:  # no request context (tests/imports)
    _base = "/"
_base = _base.rstrip("/") + "/"
if "/~/" not in _base and _base.startswith("https://") \
        and ".streamlit.app" in _base:
    _base += "~/+/"
SIM_URL = urljoin(_base, "app/static/sim/embed.html")

st.markdown("""
<style>
[data-testid="stMainBlockContainer"] {
  max-width: none; padding: var(--ht-bar-h) 0 0;
}
[data-testid="stMainBlockContainer"] > div { gap: 0 !important; }
.st-key-home_frame,
.st-key-home_frame [data-testid="stElementContainer"] { margin: 0; gap: 0; }
/* st.iframe pins its container to the height= parameter through flex-basis;
   release it so the bay fits the viewport exactly, with no dead space. */
.st-key-home_frame [data-testid="stElementContainer"] {
  flex: 0 0 auto !important;
  height: calc(100vh - var(--ht-bar-h)) !important;
  min-height: 420px;
}
.st-key-home_frame iframe {
  display: block; width: 100%; border: 0; height: 100% !important;
}
</style>
""", unsafe_allow_html=True)

with st.container(key="home_frame"):
    st.iframe(SIM_URL, height=860)
