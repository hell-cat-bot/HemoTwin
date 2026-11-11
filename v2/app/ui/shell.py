"""Shared shell for the HemoTwin V2 console."""
from __future__ import annotations

import streamlit as st

from app.ui import theme


def header() -> None:
    st.markdown(theme.brandbar(), unsafe_allow_html=True)


def footer() -> None:
    st.markdown(theme.footer(), unsafe_allow_html=True)


def page_intro(kicker: str, title: str, lead: str, pills=None) -> None:
    st.markdown(theme.section(kicker, title, lead), unsafe_allow_html=True)
    if pills:
        st.markdown(
            "".join(theme.pill(label, tone) for label, tone in pills),
            unsafe_allow_html=True)
