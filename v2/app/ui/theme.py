"""Cinematic medical digital-twin theme for the V2 console.

All visual tokens live here so the app and the deck share one language:
midnight navy, luminous cyan/teal, violet uncertainty, amber illustration,
and coral failure. No external fonts or network calls at runtime.
"""
from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[2] / "assets"

PALETTE = {
    "bg": "#050A12",
    "bg_2": "#07111F",
    "panel": "rgba(13, 23, 42, 0.78)",
    "line": "rgba(148, 163, 184, 0.16)",
    "line_strong": "rgba(148, 163, 184, 0.28)",
    "text": "#F4F8FB",
    "muted": "#93A4B8",
    "cyan": "#22D3EE",
    "teal": "#2DD4BF",
    "violet": "#A78BFA",
    "amber": "#FBBF24",
    "coral": "#FB7185",
    "good": "#34D399",
}

DISPLAY_FONT = '"Bahnschrift", "Segoe UI Variable Display", "Segoe UI", sans-serif'
BODY_FONT = '"Segoe UI", "Segoe UI Variable Text", system-ui, sans-serif'


@lru_cache(maxsize=4)
def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _asset(name: str, mime: str) -> str:
    path = ASSETS / name
    if not path.exists():
        return ""
    return f"data:{mime};base64,{_b64(str(path))}"


def inject_css() -> None:
    """Apply the global theme once per page render."""
    st.markdown(f"""
<style>
:root {{
  --ht-bg: {PALETTE['bg']};
  --ht-bg-2: {PALETTE['bg_2']};
  --ht-panel: {PALETTE['panel']};
  --ht-line: {PALETTE['line']};
  --ht-line-strong: {PALETTE['line_strong']};
  --ht-text: {PALETTE['text']};
  --ht-muted: {PALETTE['muted']};
  --ht-cyan: {PALETTE['cyan']};
  --ht-teal: {PALETTE['teal']};
  --ht-violet: {PALETTE['violet']};
  --ht-amber: {PALETTE['amber']};
  --ht-coral: {PALETTE['coral']};
  --ht-good: {PALETTE['good']};
  --ht-radius: 18px;
  --ht-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
}}

html, body, [class*="css"] {{
  font-family: {BODY_FONT};
  color: var(--ht-text);
}}
.stApp {{
  background:
    radial-gradient(900px 520px at 8% -8%, rgba(34, 211, 238, 0.14), transparent 62%),
    radial-gradient(820px 520px at 96% 2%, rgba(139, 92, 246, 0.10), transparent 60%),
    linear-gradient(180deg, #050A12 0%, #06101C 46%, #050A12 100%);
  background-attachment: fixed;
}}
.stApp::before {{
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.035) 1px, transparent 1px);
  background-size: 52px 52px;
  mask-image: radial-gradient(ellipse at 50% 0%, black 0%, transparent 72%);
}}
[data-testid="stHeader"] {{ background: transparent; z-index: 1000; }}
[data-testid="stToolbar"] {{ background: transparent; }}
[data-testid="stDecoration"], #MainMenu, footer {{ display: none !important; }}
.block-container {{ padding-top: 1.1rem; padding-bottom: 2.2rem; max-width: 1360px; }}
[data-testid="stSidebarCollapseButton"] {{ visibility: visible !important; }}
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] button {{
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(11, 21, 36, 0.92);
  color: #E6EEF8;
  transition: border-color 160ms ease, background 160ms ease;
}}
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stSidebarCollapseButton"] button:hover {{
  border-color: rgba(34, 211, 238, 0.55);
  background: rgba(15, 30, 48, 0.98);
}}
[data-testid="stExpandSidebarButton"]:focus-visible,
[data-testid="stSidebarCollapseButton"] button:focus-visible {{
  outline: 2px solid var(--ht-cyan);
  outline-offset: 2px;
}}

h1, h2, h3, h4, h5 {{
  font-family: {DISPLAY_FONT};
  color: var(--ht-text);
  letter-spacing: -0.02em;
}}
p, li, label, span, div {{ color: #CBD5E1; }}
a {{ color: #67E8F9; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
hr {{ border-color: var(--ht-line); }}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #060D18 0%, #050A12 100%);
  border-right: 1px solid rgba(148, 163, 184, 0.12);
}}
[data-testid="stSidebar"] * {{ color: #CBD5E1; }}
[data-testid="stSidebarNav"] {{ padding-top: 0.35rem; }}
[data-testid="stSidebarNav"] a {{
  border-radius: 10px;
  margin: 2px 8px;
  padding: 8px 10px;
  transition: background 160ms ease, border-color 160ms ease;
}}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(34, 211, 238, 0.08); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.16), rgba(45, 212, 191, 0.05));
  border: 1px solid rgba(34, 211, 238, 0.24);
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color: #93A4B8; }}

div[data-testid="stButton"] > button {{
  background: linear-gradient(145deg, rgba(15, 23, 42, 0.92), rgba(8, 14, 28, 0.96));
  border: 1px solid rgba(148, 163, 184, 0.20);
  border-radius: 14px;
  color: #E2E8F0;
  min-height: 3.15rem;
  font-family: {DISPLAY_FONT};
  font-size: 13px;
  letter-spacing: 0.01em;
  white-space: pre-line;
  line-height: 1.25;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}}
div[data-testid="stButton"] > button:hover {{
  border-color: rgba(34, 211, 238, 0.55);
  box-shadow: 0 10px 30px rgba(34, 211, 238, 0.10);
  transform: translateY(-1px);
}}
div[data-testid="stButton"] > button:focus-visible {{
  outline: 2px solid var(--ht-cyan);
  outline-offset: 2px;
}}
div[data-testid="stButton"] > button[kind="primary"] {{
  background: linear-gradient(135deg, #0E7490 0%, #0F766E 100%);
  border-color: rgba(34, 211, 238, 0.55);
  color: #FFFFFF;
}}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
div[data-testid="stNumberInput"] input {{
  background: rgba(8, 15, 28, 0.92) !important;
  border-color: rgba(148, 163, 184, 0.22) !important;
  color: #F4F8FB !important;
}}
input, textarea {{ color: #F4F8FB !important; }}
div[data-testid="stSlider"] [role="slider"] {{ background: var(--ht-cyan) !important; }}

button[data-baseweb="tab"] {{
  color: #93A4B8;
  font-family: {DISPLAY_FONT};
  letter-spacing: 0.01em;
}}
button[data-baseweb="tab"][aria-selected="true"] {{ color: #E6FFFB; }}
div[data-baseweb="tab-highlight"] {{ background: var(--ht-cyan); }}
div[data-baseweb="tab-border"] {{ background: rgba(148, 163, 184, 0.14); }}

div[data-testid="stAlert"] {{
  background: rgba(15, 23, 42, 0.92) !important;
  border: 1px solid rgba(148, 163, 184, 0.20) !important;
  border-left: 2px solid var(--ht-cyan) !important;
  border-radius: 12px !important;
  color: #E2E8F0 !important;
}}
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span,
div[data-testid="stAlert"] div {{ color: #E2E8F0 !important; }}
div[data-testid="stMetric"] {{
  background: linear-gradient(145deg, rgba(15, 23, 42, 0.86), rgba(7, 13, 26, 0.92));
  border: 1px solid var(--ht-line);
  border-radius: 14px;
  padding: 14px 16px;
}}
div[data-testid="stMetricLabel"] {{ color: var(--ht-muted); }}
div[data-testid="stMetricValue"] {{
  color: var(--ht-text);
  font-family: {DISPLAY_FONT};
}}
div[data-testid="stDataFrame"] {{
  border: 1px solid var(--ht-line);
  border-radius: 14px;
  overflow: hidden;
}}
details {{
  background: rgba(8, 15, 28, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 6px 12px;
}}
summary {{ color: #CBD5E1; }}

.ht-brandbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 0 16px;
}}
.ht-brand {{ display: flex; align-items: center; gap: 12px; }}
.ht-brand img {{ width: 40px; height: 40px; }}
.ht-wordmark {{
  font-family: {DISPLAY_FONT};
  font-size: 18px;
  letter-spacing: 0.16em;
  color: var(--ht-text);
  line-height: 1;
}}
.ht-brand small {{
  display: block;
  color: var(--ht-muted);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-top: 5px;
}}
.ht-status {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.ht-dot {{
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--ht-good);
  box-shadow: 0 0 12px rgba(52, 211, 153, 0.8);
}}

.ht-hero {{
  position: relative;
  border-radius: 24px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.18);
  min-height: 310px;
  padding: 34px 38px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-shadow: var(--ht-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  background-size: cover;
  background-position: center right;
}}
.ht-kicker {{
  font-family: {DISPLAY_FONT};
  font-size: 11px;
  letter-spacing: 0.20em;
  text-transform: uppercase;
  color: #67E8F9;
}}
.ht-display {{
  font-family: {DISPLAY_FONT};
  font-weight: 600;
  font-size: clamp(2.2rem, 4vw, 3.6rem);
  line-height: 1.02;
  color: #F8FAFC;
  margin: 12px 0 12px;
  max-width: 660px;
}}
.ht-display em {{ font-style: normal; color: #67E8F9; }}
.ht-lead {{
  font-size: 15px;
  line-height: 1.65;
  color: #B8C6D9;
  max-width: 560px;
}}
.ht-pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }}
.ht-pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--ht-line);
  background: rgba(15, 23, 42, 0.62);
  color: #B8C6D9;
  font-family: {DISPLAY_FONT};
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  white-space: nowrap;
}}
.ht-pill--ok {{ color: #6EE7B7; border-color: rgba(52, 211, 153, 0.34); background: rgba(52, 211, 153, 0.08); }}
.ht-pill--warn {{ color: #FCD34D; border-color: rgba(251, 191, 36, 0.34); background: rgba(251, 191, 36, 0.08); }}
.ht-pill--fail {{ color: #FDA4AF; border-color: rgba(251, 113, 133, 0.36); background: rgba(251, 113, 133, 0.08); }}
.ht-pill--info {{ color: #67E8F9; border-color: rgba(34, 211, 238, 0.34); background: rgba(34, 211, 238, 0.08); }}
.ht-pill--violet {{ color: #C4B5FD; border-color: rgba(167, 139, 250, 0.36); background: rgba(167, 139, 250, 0.08); }}

.ht-card {{
  position: relative;
  overflow: hidden;
  background: linear-gradient(145deg, rgba(15, 23, 42, 0.86), rgba(7, 13, 26, 0.93));
  border: 1px solid var(--ht-line);
  border-radius: var(--ht-radius);
  box-shadow: var(--ht-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  padding: 20px 22px;
}}
.ht-card::after {{
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(120deg, rgba(34, 211, 238, 0.07), transparent 38%);
}}
.ht-card--tight {{ padding: 15px 17px; }}
.ht-card--glow {{ border-color: rgba(34, 211, 238, 0.32); box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.06), var(--ht-shadow); }}
.ht-card h3, .ht-card h4 {{ margin: 0 0 6px; }}
.ht-card p {{ margin: 0; color: var(--ht-muted); font-size: 13px; line-height: 1.55; }}

.ht-metric-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
}}
.ht-metric {{
  background: linear-gradient(145deg, rgba(15, 23, 42, 0.86), rgba(7, 13, 26, 0.93));
  border: 1px solid var(--ht-line);
  border-radius: 14px;
  padding: 15px 16px;
  min-height: 92px;
}}
.ht-metric__label {{
  font-family: {DISPLAY_FONT};
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ht-muted);
}}
.ht-metric__value {{
  font-family: {DISPLAY_FONT};
  font-size: 32px;
  line-height: 1;
  color: var(--ht-text);
  margin: 9px 0 4px;
}}
.ht-metric__value--cyan {{ color: #67E8F9; }}
.ht-metric__value--violet {{ color: #C4B5FD; }}
.ht-metric__value--amber {{ color: #FCD34D; }}
.ht-metric__value--coral {{ color: #FDA4AF; }}
.ht-metric__sub {{ font-size: 11px; color: var(--ht-muted); line-height: 1.4; }}

.ht-section {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin: 30px 0 12px;
}}
.ht-section > div:first-child {{ flex: 0 0 auto; min-width: 280px; }}
.ht-section p {{ flex: 1 1 420px; }}
.ht-section h2 {{ margin: 0; font-size: 23px; }}
.ht-section p {{ margin: 0; color: var(--ht-muted); font-size: 13px; max-width: 560px; }}

.ht-callout {{
  border-left: 2px solid var(--ht-cyan);
  background: rgba(34, 211, 238, 0.06);
  border-radius: 0 12px 12px 0;
  padding: 11px 15px;
  color: #C7D6E6;
  font-size: 13px;
  line-height: 1.55;
}}
.ht-callout--warn {{ border-left-color: var(--ht-amber); background: rgba(251, 191, 36, 0.06); }}
.ht-callout--fail {{ border-left-color: var(--ht-coral); background: rgba(251, 113, 133, 0.06); }}

.ht-orb-card {{ display: flex; align-items: center; gap: 14px; }}
.ht-orb {{
  width: 112px;
  height: 112px;
  object-fit: contain;
  filter: drop-shadow(0 0 22px rgba(34, 211, 238, 0.32));
  animation: htFloat 7s ease-in-out infinite;
}}
@keyframes htFloat {{
  0%, 100% {{ transform: translateY(0) scale(1); }}
  50% {{ transform: translateY(-6px) scale(1.015); }}
}}

.ht-footer {{
  margin-top: 46px;
  padding-top: 16px;
  border-top: 1px solid var(--ht-line);
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  justify-content: space-between;
  color: #7F91A6;
  font-size: 12px;
}}
.ht-grid-2 {{ display: grid; grid-template-columns: 1.45fr 1fr; gap: 16px; }}
.ht-grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
.ht-grid-2 > .ht-card, .ht-grid-3 > .ht-card {{ height: 100%; }}

@media (max-width: 1300px) {{
  .ht-orb-card {{ flex-direction: column; align-items: flex-start; }}
  .ht-orb {{ width: 88px; height: 88px; }}
}}
@media (max-width: 980px) {{
  .ht-metric-grid, .ht-grid-3 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ht-grid-2 {{ grid-template-columns: 1fr; }}
  .ht-hero {{ min-height: 360px; padding: 24px; }}
}}
@media (max-width: 640px) {{
  .ht-metric-grid, .ht-grid-3 {{ grid-template-columns: 1fr; }}
  .ht-brandbar {{ flex-direction: column; align-items: flex-start; }}
  .ht-section {{ flex-direction: column; align-items: flex-start; }}
  .ht-section > div:first-child {{ min-width: 0; }}
  .ht-section p {{ flex: 0 0 auto; }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }}
}}
</style>
""", unsafe_allow_html=True)


def e(value) -> str:
    return html.escape(str(value), quote=True)


def pill(label: str, tone: str = "") -> str:
    cls = f"ht-pill ht-pill--{tone}" if tone else "ht-pill"
    return f'<span class="{cls}">{e(label)}</span>'


def metric(label: str, value: str, sub: str = "", tone: str = "") -> str:
    value_cls = f"ht-metric__value ht-metric__value--{tone}" if tone else "ht-metric__value"
    sub_html = f'<div class="ht-metric__sub">{e(sub)}</div>' if sub else ""
    return (
        f'<div class="ht-metric"><div class="ht-metric__label">{e(label)}</div>'
        f'<div class="{value_cls}">{e(value)}</div>{sub_html}</div>'
    )


def metric_row(items: list[dict]) -> str:
    cards = "".join(
        metric(item.get("label", ""), item.get("value", ""),
               item.get("sub", ""), item.get("tone", ""))
        for item in items
    )
    return f'<div class="ht-metric-grid">{cards}</div>'


def section(kicker: str, title: str, lead: str = "") -> str:
    lead_html = f"<p>{e(lead)}</p>" if lead else ""
    return (
        f'<div class="ht-section"><div><div class="ht-kicker">{e(kicker)}</div>'
        f'<h2>{e(title)}</h2></div>{lead_html}</div>'
    )


def card(body: str, tight: bool = False, glow: bool = False) -> str:
    cls = "ht-card" + (" ht-card--tight" if tight else "") + (" ht-card--glow" if glow else "")
    return f'<div class="{cls}">{body}</div>'


def callout(text: str, tone: str = "") -> str:
    cls = "ht-callout" + (f" ht-callout--{tone}" if tone else "")
    return f'<div class="{cls}">{e(text)}</div>'


def brandbar() -> str:
    mark = _asset("brand/mark.svg", "image/svg+xml")
    return f"""
<div class="ht-brandbar">
  <div class="ht-brand">
    <img src="{mark}" alt="HemoTwin mark"/>
    <div><div class="ht-wordmark">HEMOTWIN</div>
    <small>Chair-side session twin</small></div>
  </div>
  <div class="ht-status">
    <span class="ht-dot"></span>{pill("Research prototype", "warn")}
    {pill("Decision support, not prescription", "info")}
  </div>
</div>
"""


def hero(kicker: str, title_html: str, lead: str, pills: list[tuple[str, str]] | None = None) -> str:
    bg = _asset("3d/hero_kidney.jpg", "image/jpeg")
    pill_html = "".join(pill(label, tone) for label, tone in (pills or []))
    return f"""
<div class="ht-hero" style="background-image:
  linear-gradient(90deg, rgba(5,10,18,0.98) 0%, rgba(5,10,18,0.92) 38%, rgba(5,10,18,0.22) 72%, rgba(5,10,18,0.05) 100%),
  url('{bg}');">
  <div class="ht-kicker">{e(kicker)}</div>
  <div class="ht-display">{title_html}</div>
  <div class="ht-lead">{e(lead)}</div>
  <div class="ht-pills">{pill_html}</div>
</div>
"""


def orb_card(title: str, body: str) -> str:
    orb = _asset("3d/twin_orb.webp", "image/webp")
    return f"""
<div class="ht-card ht-card--glow">
  <div class="ht-orb-card">
    <img class="ht-orb" src="{orb}" alt="Digital twin state orb"/>
    <div><h3>{e(title)}</h3><p>{e(body)}</p></div>
  </div>
</div>
"""


def footer() -> str:
    return """
<div class="ht-footer">
  <span>HemoTwin V2 · research workflow prototype · not a medical device</span>
  <span>HEMOBP (Taiwan) 205,482 sessions · CC BY 4.0 · fold 2 untouched</span>
  <span>No treatment recommendation · no autonomous machine action</span>
</div>
"""
