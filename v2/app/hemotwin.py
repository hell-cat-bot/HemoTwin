"""HemoTwin V2 — one console, four views.

Case lab (default), Live session, Session replay, Evidence & handoff. The
entrypoint owns the page config, the cinematic theme, the brand header/footer,
and the page nav.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
shell.header()

pages = [
    st.Page(
        "views/case_lab_page.py",
        title="Case lab",
        icon=":material/science:",
        default=True,
    ),
    st.Page(
        "manual_app.py",
        title="Live session",
        icon=":material/monitor_heart:",
    ),
    st.Page(
        "views/replay_page.py",
        title="Session replay",
        icon=":material/replay:",
    ),
    st.Page(
        "views/evidence_page.py",
        title="Evidence & handoff",
        icon=":material/verified_user:",
    ),
]
pg = st.navigation(pages, position="sidebar")
pg.run()

shell.footer()
