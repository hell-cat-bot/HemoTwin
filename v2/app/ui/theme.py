"""Continuum theme for the HemoTwin V2 console.

One visual language across the console and the 3D landing: a dark instrument
bar pinned above a light mist workspace, deep teal for measurement, amber for
caution, brick for risk, sage for uncertainty. No gradients, no glows, no
external fonts or network calls at runtime.
"""
from __future__ import annotations

import html

import streamlit as st

PALETTE = {
    "bg": "#EFF3F2",
    "surface": "#FFFFFF",
    "surface_2": "#F7FAF9",
    "ink": "#141C1E",
    "muted": "#5C6B6D",
    "dim": "#7E8B8C",
    "line": "#DCE4E1",
    "line_2": "#C6D2CE",
    "accent": "#17756A",
    "accent_bright": "#5EEAD4",
    "accent_soft": "#E4F1ED",
    "warn": "#A8641B",
    "warn_soft": "#FBF4E8",
    "risk": "#B23C2C",
    "risk_soft": "#F9EDEA",
    "good": "#1F7A4D",
    "sage": "#7D8B7C",
    "chrome": "#080D10",
}

DISPLAY_FONT = '"Segoe UI Variable Display", "Segoe UI", sans-serif'
BODY_FONT = '"Segoe UI", "Segoe UI Variable Text", system-ui, sans-serif'
MONO_FONT = '"Cascadia Mono", Consolas, "SF Mono", monospace'


def inject_css() -> None:
    """Apply the global Continuum theme once per page render."""
    st.markdown(f"""
<style>
:root {{
  --ht-bg: {PALETTE['bg']};
  --ht-surface: {PALETTE['surface']};
  --ht-surface-2: {PALETTE['surface_2']};
  --ht-ink: {PALETTE['ink']};
  --ht-muted: {PALETTE['muted']};
  --ht-dim: {PALETTE['dim']};
  --ht-line: {PALETTE['line']};
  --ht-line-2: {PALETTE['line_2']};
  --ht-accent: {PALETTE['accent']};
  --ht-accent-bright: {PALETTE['accent_bright']};
  --ht-accent-soft: {PALETTE['accent_soft']};
  --ht-warn: {PALETTE['warn']};
  --ht-warn-soft: {PALETTE['warn_soft']};
  --ht-risk: {PALETTE['risk']};
  --ht-risk-soft: {PALETTE['risk_soft']};
  --ht-good: {PALETTE['good']};
  --ht-sage: {PALETTE['sage']};
  --ht-chrome: {PALETTE['chrome']};
  --ht-mono: {MONO_FONT};
  --ht-radius: 12px;
}}

html, body, [class*="css"] {{
  font-family: {BODY_FONT};
  color: var(--ht-ink);
}}
.stApp {{
  background:
    radial-gradient(1100px 480px at 82% -14%, rgba(23, 117, 106, 0.06), transparent 62%),
    var(--ht-bg);
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] {{ background: transparent; }}
[data-testid="stDecoration"], #MainMenu, footer {{ display: none !important; }}
[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 1240px;
  padding: 88px 26px 40px;
}}
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] {{
  border-radius: 8px;
  border: 1px solid var(--ht-line);
  background: var(--ht-surface);
  color: var(--ht-ink);
}}
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stSidebarCollapseButton"] button:hover {{
  border-color: var(--ht-accent);
  color: var(--ht-accent);
}}

h1, h2, h3, h4, h5 {{
  font-family: {DISPLAY_FONT};
  color: var(--ht-ink);
  letter-spacing: -0.015em;
}}
[data-testid="stHeadingWithActionElements"] h2 {{
  font-size: 20px !important;
  font-weight: 650 !important;
  margin: 6px 0 8px !important;
}}
[data-testid="stHeadingWithActionElements"] h3 {{
  font-size: 17px !important;
  font-weight: 600 !important;
  margin: 4px 0 6px !important;
}}
p, li, label, span, div {{ color: var(--ht-ink); }}
a {{ color: var(--ht-accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
hr {{ border-color: var(--ht-line); }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
  color: var(--ht-muted) !important;
  font-size: 11.5px;
  line-height: 1.5;
}}

[data-testid="stSidebar"] {{
  background: var(--ht-surface-2);
  border-right: 1px solid var(--ht-line);
  padding-top: 66px;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {{
  color: var(--ht-muted);
}}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
  font-family: {MONO_FONT} !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ht-muted);
}}

div[data-testid="stButton"] > button {{
  background: var(--ht-surface);
  border: 1px solid var(--ht-line-2);
  border-radius: 8px;
  color: var(--ht-ink);
  min-height: 2.65rem;
  font-family: {BODY_FONT};
  font-size: 12.5px;
  font-weight: 500;
  white-space: pre-line;
  line-height: 1.3;
  transition: border-color 150ms ease, color 150ms ease, background 150ms ease;
}}
div[data-testid="stButton"] > button:hover {{
  border-color: var(--ht-accent);
  color: var(--ht-accent);
  background: var(--ht-surface-2);
}}
div[data-testid="stButton"] > button:focus-visible {{
  outline: 2px solid var(--ht-accent);
  outline-offset: 2px;
}}
div[data-testid="stButton"] > button[kind="primary"] {{
  background: var(--ht-accent);
  border-color: var(--ht-accent);
  color: #FFFFFF;
}}
div[data-testid="stButton"] > button[kind="primary"]:hover {{
  background: #0F5F56;
  border-color: #0F5F56;
  color: #FFFFFF;
}}
div[data-testid="stButton"] > button[kind="tertiary"] {{
  border-color: transparent;
  background: transparent;
  color: var(--ht-accent);
}}

div[data-baseweb="input"], div[data-baseweb="select"] > div,
div[data-baseweb="base-input"], div[data-baseweb="textarea"] {{
  border-radius: 8px !important;
  background: var(--ht-surface) !important;
}}
input, textarea {{ color: var(--ht-ink) !important; }}
div[data-testid="stSlider"] [role="slider"] {{ background: var(--ht-accent) !important; }}

button[data-baseweb="tab"] {{
  color: var(--ht-muted);
  font-family: {BODY_FONT};
  font-size: 13px;
  font-weight: 500;
}}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--ht-ink); }}
div[data-baseweb="tab-highlight"] {{ background: var(--ht-accent); }}
div[data-baseweb="tab-border"] {{ background: var(--ht-line); }}

div[data-testid="stAlert"] {{
  border-radius: 10px !important;
  border: 1px solid var(--ht-line) !important;
  font-size: 13px;
}}
div[data-testid="stAlert"] p {{ font-size: 13px; }}
div[data-testid="stMetric"] {{
  background: var(--ht-surface);
  border: 1px solid var(--ht-line);
  border-radius: 10px;
  padding: 12px 14px;
}}
div[data-testid="stMetricLabel"] {{
  color: var(--ht-muted);
  font-family: {MONO_FONT};
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}}
div[data-testid="stMetricValue"] {{
  color: var(--ht-ink);
  font-family: {DISPLAY_FONT};
  font-size: 24px;
}}
div[data-testid="stMetricDelta"] {{ font-size: 11px; }}
div[data-testid="stDataFrame"] {{
  border: 1px solid var(--ht-line);
  border-radius: 10px;
  overflow: hidden;
}}
details {{
  background: var(--ht-surface);
  border: 1px solid var(--ht-line);
  border-radius: 10px;
  padding: 4px 12px;
}}
summary {{ color: var(--ht-ink); font-size: 13px; font-weight: 600; }}
div[data-testid="stExpander"] details {{ background: var(--ht-surface-2); }}

/* Fixed instrument bar: the dark chrome shared with the 3D landing. It spans
   the viewport so the header does not jump when a page opens a sidebar. */
div[data-testid="stLayoutWrapper"]:has(> .st-key-ht_topbar) {{
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000000;
  width: 100%;
  margin: 0;
  padding: 0;
  background: transparent;
}}
.st-key-ht_topbar {{
  --ht-nav-fs: 12px;
  --ht-nav-ls: 0.08em;
  background: var(--ht-chrome);
  border-bottom: 1px solid #15211E;
  border-radius: 0;
  padding: 9px max(26px, calc((100vw - 1240px) / 2 + 26px));
  margin-bottom: 0;
}}
.st-key-ht_topbar [data-testid="stHorizontalBlock"] {{
  align-items: center;
  gap: 0;
  flex-wrap: nowrap;
}}
/* Brand flexes; the six links and the status cluster stay anchored right, so
   their x-positions are identical on every view. */
.st-key-ht_topbar [data-testid="stColumn"]:first-child {{
  flex: 1 1 auto !important;
  width: auto !important;
  min-width: 0;
}}
.st-key-ht_topbar [data-testid="stColumn"]:nth-child(n+2):nth-child(-n+7) {{
  flex: 0 0 82px !important;
  width: 82px !important;
  min-width: 0;
}}
.st-key-ht_topbar [data-testid="stColumn"]:last-child {{
  flex: 0 0 108px !important;
  width: 108px !important;
}}
.st-key-ht_topbar [data-testid="stPageLink"] {{ text-align: center; }}
/* Streamlit paints the label's inner markdown <p> with the body ink color,
   which is unreadable on the dark bar; let it inherit the link color. */
.st-key-ht_topbar [data-testid="stPageLink"] a * {{ color: inherit !important; }}
.st-key-ht_topbar [data-testid="stPageLink"] a {{
  color: #E4EDEA;
  font-family: {MONO_FONT};
  font-size: var(--ht-nav-fs);
  font-weight: 600;
  letter-spacing: var(--ht-nav-ls);
  text-transform: uppercase;
  padding: 7px 2px;
  background: transparent !important;
  border-radius: 0 !important;
  border-bottom: 1.5px solid transparent;
  justify-content: center;
  transition: color 140ms ease, border-color 140ms ease;
}}
.st-key-ht_topbar [data-testid="stPageLink"] a p {{
  font-family: {MONO_FONT};
  font-size: var(--ht-nav-fs);
  font-weight: 600;
  letter-spacing: var(--ht-nav-ls);
  line-height: 1.2;
  margin: 0;
}}
.st-key-ht_topbar [data-testid="stPageLink"] a:hover {{
  color: #E7F1EE;
  text-decoration: none;
}}
/* The active view is wrapped in this keyed container by the shell. */
.st-key-ht_nav_active [data-testid="stPageLink"] a,
.st-key-ht_topbar [data-testid="stPageLink"] a[aria-current="page"] {{
  color: var(--ht-accent-bright) !important;
  border-bottom-color: var(--ht-accent-bright) !important;
}}

.ht-brand {{ display: flex; align-items: center; gap: 10px; }}
.ht-brand__mark {{
  width: 22px; height: 22px;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid #24534B;
  border-radius: 5px;
  background: #0E211D;
  color: var(--ht-accent-bright);
  font-family: {MONO_FONT};
  font-size: 11px;
  font-weight: 700;
}}
.ht-brand__word {{
  font-family: {DISPLAY_FONT};
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.2em;
  color: #EDF5F2;
}}
.ht-brand__ver {{
  font-family: {MONO_FONT};
  font-size: 9px;
  letter-spacing: 0.08em;
  color: #6E8380;
  border: 1px solid #1E2D29;
  border-radius: 4px;
  padding: 1px 5px;
}}
.ht-topright {{ display: flex; justify-content: flex-end; }}
.ht-live {{
  display: inline-flex; align-items: center; gap: 7px;
  font-family: {MONO_FONT};
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #CBDCD7;
  white-space: nowrap;
}}
.ht-live i {{
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--ht-accent-bright);
  box-shadow: 0 0 0 3px rgba(94, 234, 212, 0.14);
}}

.ht-pagehead {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 22px;
  padding-bottom: 18px;
  margin-bottom: 22px;
  border-bottom: 1px solid var(--ht-line);
}}
.ht-pagehead__main {{ max-width: 760px; }}
.ht-pagehead__side {{ display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }}
.ht-title {{
  font-family: {DISPLAY_FONT};
  font-size: clamp(1.55rem, 2.6vw, 2.15rem);
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--ht-ink);
  margin: 8px 0 8px;
}}
.ht-lead {{
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--ht-muted);
  max-width: 660px;
}}

.ht-kicker {{
  font-family: {MONO_FONT};
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ht-accent);
}}
.ht-pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border-radius: 999px;
  border: 1px solid var(--ht-line-2);
  background: var(--ht-surface);
  color: var(--ht-muted);
  font-family: {MONO_FONT};
  font-size: 9.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}}
.ht-pill--ok {{ color: var(--ht-good); border-color: #BFDCCB; background: #EEF7F1; }}
.ht-pill--warn {{ color: var(--ht-warn); border-color: #E8D3B2; background: var(--ht-warn-soft); }}
.ht-pill--fail {{ color: var(--ht-risk); border-color: #E4C3BD; background: var(--ht-risk-soft); }}
.ht-pill--info {{ color: var(--ht-accent); border-color: #BFDAD4; background: var(--ht-accent-soft); }}
.ht-pill--sage {{ color: #5F6E5E; border-color: #CFD7CB; background: #F1F4EF; }}
.ht-pills {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 2px; }}

.ht-section {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 22px;
  margin: 30px 0 12px;
}}
.ht-section > div:first-child {{ flex: 0 0 auto; }}
.ht-section h2 {{
  margin: 6px 0 0;
  font-size: 21px;
  font-weight: 600;
}}
.ht-section p {{
  margin: 0;
  color: var(--ht-muted);
  font-size: 13px;
  line-height: 1.6;
  max-width: 540px;
}}

.ht-card {{
  background: var(--ht-surface);
  border: 1px solid var(--ht-line);
  border-radius: var(--ht-radius);
  box-shadow: 0 1px 2px rgba(20, 28, 30, 0.04);
  padding: 18px 20px;
}}
.ht-card--tight {{ padding: 14px 16px; }}
.ht-card--glow {{ border-color: rgba(23, 117, 106, 0.4); box-shadow: 0 0 0 3px var(--ht-accent-soft); }}
.ht-card h3, .ht-card h4 {{ margin: 0 0 6px; font-size: 15px; }}
.ht-card p {{ margin: 0; color: var(--ht-muted); font-size: 12.5px; line-height: 1.55; }}

.ht-metric-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
}}
.ht-metric {{
  background: var(--ht-surface);
  border: 1px solid var(--ht-line);
  border-radius: 10px;
  padding: 13px 15px;
  min-height: 84px;
}}
.ht-metric__label {{
  font-family: {MONO_FONT};
  font-size: 9.5px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ht-muted);
}}
.ht-metric__value {{
  font-family: {DISPLAY_FONT};
  font-size: 27px;
  font-weight: 600;
  line-height: 1;
  color: var(--ht-ink);
  margin: 9px 0 4px;
}}
.ht-metric__value--cyan {{ color: var(--ht-accent); }}
.ht-metric__value--violet {{ color: var(--ht-sage); }}
.ht-metric__value--amber {{ color: var(--ht-warn); }}
.ht-metric__value--coral {{ color: var(--ht-risk); }}
.ht-metric__sub {{ font-size: 11px; color: var(--ht-muted); line-height: 1.45; }}

.ht-callout {{
  border-left: 2px solid var(--ht-accent);
  background: var(--ht-accent-soft);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  color: var(--ht-ink);
  font-size: 12.5px;
  line-height: 1.55;
}}
.ht-callout--warn {{ border-left-color: var(--ht-warn); background: var(--ht-warn-soft); }}
.ht-callout--fail {{ border-left-color: var(--ht-risk); background: var(--ht-risk-soft); }}

.ht-footer {{
  margin-top: 44px;
  padding-top: 14px;
  border-top: 1px solid var(--ht-line);
  display: flex;
  flex-wrap: wrap;
  gap: 6px 22px;
  justify-content: space-between;
  color: var(--ht-muted);
  font-family: {MONO_FONT};
  font-size: 9.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}}
.ht-footer span {{ color: var(--ht-muted); }}
.ht-grid-2 {{ display: grid; grid-template-columns: 1.45fr 1fr; gap: 14px; }}
.ht-grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
.ht-grid-2 > .ht-card, .ht-grid-3 > .ht-card {{ height: 100%; }}

@media (max-width: 1200px) {{
  .st-key-case_buttons [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; row-gap: 8px; }}
  .st-key-case_buttons [data-testid="stColumn"] {{
    flex: 1 1 28% !important;
    width: auto !important;
    min-width: 150px;
  }}
  [data-testid="stWidgetLabel"] p {{ font-size: 12px; }}
}}
@media (max-width: 1120px) {{
  .st-key-ht_topbar {{ padding-left: 20px; padding-right: 20px; --ht-nav-fs: 11px; --ht-nav-ls: 0.05em; }}
  .ht-pagehead {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
  .ht-pagehead__side {{ justify-content: flex-start; }}
  .st-key-ht_topbar [data-testid="stColumn"]:nth-child(n+2):nth-child(-n+7) {{
    flex-basis: 68px !important;
    width: 68px !important;
  }}
  .st-key-ht_topbar [data-testid="stColumn"]:last-child {{
    flex-basis: 30px !important;
    width: 30px !important;
  }}
  .st-key-ht_topbar .ht-brand__word {{ font-size: 11.5px; letter-spacing: 0.14em; }}
  .st-key-ht_topbar .ht-live span {{ display: none; }}
}}
@media (max-width: 980px) {{
  .ht-metric-grid, .ht-grid-3 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ht-grid-2 {{ grid-template-columns: 1fr; }}
  .ht-pagehead {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
  .ht-pagehead__side {{ justify-content: flex-start; }}
  .ht-section {{ flex-direction: column; gap: 6px; }}
}}
@media (max-width: 760px) {{
  .st-key-ht_topbar {{ --ht-nav-fs: 9px; --ht-nav-ls: 0.04em; }}
  .st-key-ht_topbar .ht-brand__ver {{ display: none; }}
  .st-key-ht_topbar .ht-live span {{ display: none; }}
}}
@media (max-width: 640px) {{
  .ht-metric-grid, .ht-grid-3 {{ grid-template-columns: 1fr; }}
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


def page_head(kicker: str, title: str, lead: str = "",
              pills: list[tuple[str, str]] | None = None) -> str:
    side = ""
    if pills:
        side = ('<div class="ht-pagehead__side">'
                + "".join(pill(label, tone) for label, tone in pills)
                + "</div>")
    lead_html = f'<p class="ht-lead">{e(lead)}</p>' if lead else ""
    return f"""
<div class="ht-pagehead">
  <div class="ht-pagehead__main">
    <div class="ht-kicker">{e(kicker)}</div>
    <div class="ht-title">{e(title)}</div>
    {lead_html}
  </div>
  {side}
</div>
"""


def card(body: str, tight: bool = False, glow: bool = False) -> str:
    cls = "ht-card" + (" ht-card--tight" if tight else "") + (" ht-card--glow" if glow else "")
    return f'<div class="{cls}">{body}</div>'


def callout(text: str, tone: str = "") -> str:
    cls = "ht-callout" + (f" ht-callout--{tone}" if tone else "")
    return f'<div class="{cls}">{e(text)}</div>'


def brand_html() -> str:
    return """
<div class="ht-brand">
  <span class="ht-brand__mark">H</span>
  <span class="ht-brand__word">HEMOTWIN</span>
  <span class="ht-brand__ver">V2</span>
</div>
"""


def status_html() -> str:
    return ('<div class="ht-topright"><span class="ht-live"><i></i>'
            '<span>Local demo</span></span></div>')


def footer() -> str:
    return """
<div class="ht-footer">
  <span>HemoTwin V2 · research workflow prototype · not a medical device</span>
  <span>HEMOBP (Taiwan) 205,482 sessions · CC BY 4.0 · fold 2 untouched</span>
  <span>No treatment recommendation · no autonomous machine action</span>
</div>
"""
