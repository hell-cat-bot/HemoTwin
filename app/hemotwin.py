"""HemoTwin V2 — one console, five views.

Case lab (default), Chair board, Live session, Session replay, Evidence &
handoff. The entrypoint owns the page config, the Continuum theme, the
instrument bar, and the footer.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import sim_build  # noqa: E402

# Rebuild the 3D bay when sim/ drifted from the committed build. No-op when
# current (fresh clones ship the prebuilt bay + matching stamp); on failure
# the committed build is served and the reason printed. See src/sim_build.py.
_status, _detail = sim_build.ensure_synced()
if _status != "current":
    print(f"[sim] bay {_status}: {_detail}")

import streamlit as st  # noqa: E402

from app.ui import shell  # noqa: E402
from app.ui.theme import inject_css  # noqa: E402

st.set_page_config(
    page_title="HemoTwin — Chair-side session twin",
    page_icon=str(ROOT / "assets" / "brand" / "mark.svg"),
    layout="wide",
    initial_sidebar_state="auto",
)
inject_css()

pages = [
    st.Page(
        "views/home_page.py",
        title="Home",
        default=True,
    ),
    st.Page(
        "views/case_lab_page.py",
        title="Case lab",
    ),
    st.Page(
        "views/chair_board_page.py",
        title="Chair board",
    ),
    st.Page(
        "manual_app.py",
        title="Live session",
    ),
    st.Page(
        "views/replay_page.py",
        title="Session replay",
    ),
    st.Page(
        "views/evidence_page.py",
        title="Evidence & handoff",
    ),
]

shell.header(pages)
pg = st.navigation(pages, position="hidden")
pg.run()

shell.footer()
