"""Session replay page entrypoint.

A native fourth view in the V2 console. The retrospective replay is a
self-contained HTML view (built from ``sim/replay.html``) embedded with its own
header/footer suppressed so the app shell remains the frame.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ui import theme as ui_theme  # noqa: E402

ASSET = ROOT / "assets" / "replay" / "replay.html"

st.markdown(ui_theme.page_head(
    "Session replay",
    "Prediction, then the record",
    "The forecast draws first, then recorded cuffs and UF steps follow at "
    "their real times. Click a cuff or scrub the timeline.",
    pills=[("Retrospective", "info"), ("Curated sessions", ""),
           ("Display-only", "warn")]),
    unsafe_allow_html=True)
st.markdown(ui_theme.callout(
    "Curated retrospective replay · display-only shadow model, never an alarm "
    "· no treatment recommendation or machine action.", "warn"),
    unsafe_allow_html=True)
st.markdown("""
<style>
.st-key-replay_frame { margin-top: 6px; overflow: hidden; }
.st-key-replay_frame iframe { display: block; border: 0; background: transparent; }
</style>
""", unsafe_allow_html=True)

if not ASSET.exists():
    st.error(
        "Replay asset is missing. Build `sim/replay.html` and copy it to "
        "`v2/assets/replay/replay.html`.")
    st.stop()

html = ASSET.read_text(encoding="utf-8")
embed = html.replace(
    "</head>",
    "<style>"
    "html,body{overflow:hidden!important;scrollbar-width:none}"
    "body::-webkit-scrollbar{display:none}"
    "body.embed .topbar{display:none!important}"
    "body.embed footer{display:none!important}"
    "body.embed .wrap{padding-top:0!important;max-width:none!important}"
    "</style></head>",
    1,
).replace(
    "</body>",
    "<script>document.body.classList.add('embed');</script></body>",
    1,
)
with st.container(key="replay_frame"):
    st.iframe(embed, height="content")
st.caption(
    "Source: curated demo sessions; synthetic patient illustration; shadow "
    "risk recomputed with the shipped fold-0 model. Recorded readings and UF "
    "steps are real; the scene and forecast paths are illustrative.")
