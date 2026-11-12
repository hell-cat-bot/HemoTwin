"""Shared shell for the HemoTwin V2 console."""
from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st

from app.ui import theme

NAV_LABELS = ["Case lab", "Chairs", "Live", "Replay", "Evidence"]


def _current_page(pages):
    # st.page_link exposes no active marker; derive it from the request URL.
    path = urlparse(getattr(st.context, "url", None) or "").path.strip("/")
    segment = path.split("/")[-1] if path else ""
    for page in pages:
        if (page.url_path or "").strip("/") == segment:
            return page
    return pages[0]


def header(pages) -> None:
    """Dark instrument bar shared by every view, above the light workspace."""
    active = _current_page(pages)
    with st.container(key="ht_topbar"):
        cols = st.columns(
            [2.6, 1, 1, 1, 1, 1.1, 1.35], gap="small", vertical_alignment="center")
        with cols[0]:
            st.markdown(theme.brand_html(), unsafe_allow_html=True)
        for col, page, label in zip(cols[1:6], pages, NAV_LABELS):
            with col:
                if page is active:
                    with st.container(key="ht_nav_active"):
                        st.page_link(page, label=label)
                else:
                    st.page_link(page, label=label)
        with cols[6]:
            st.markdown(theme.status_html(), unsafe_allow_html=True)


def footer() -> None:
    st.markdown(theme.footer(), unsafe_allow_html=True)


def page_intro(kicker: str, title: str, lead: str, pills=None) -> None:
    st.markdown(theme.section(kicker, title, lead), unsafe_allow_html=True)
    if pills:
        st.markdown(
            "".join(theme.pill(label, tone) for label, tone in pills),
            unsafe_allow_html=True)
