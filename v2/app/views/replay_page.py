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
    "Watch the research forecast draw forward, then the recorded cuffs and UF "
    "steps roll in at their real times. Click a cuff, scrub the timeline, or "
    "try a what-if card.",
    pills=[("Retrospective", "info"), ("Curated sessions", ""),
           ("Display-only", "warn")]),
    unsafe_allow_html=True)
st.markdown(ui_theme.callout(
    "Curated retrospective replay. The shadow display never triggers an alarm; "
    "what-if paths are mechanism illustrations from the failed twin experiment "
    "(G7). No treatment recommendation and no machine action.", "warn"),
    unsafe_allow_html=True)
st.markdown("""
<style>
.st-key-replay_frame {
  background: var(--ht-chrome);
  border: 1px solid #15211E;
  border-radius: 12px;
  padding: 10px;
  margin-top: 14px;
  overflow: hidden;
}
.st-key-replay_frame iframe {
  display: block;
  border-radius: 8px;
  background: #05080B;
}
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
