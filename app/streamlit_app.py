"""HemoTwin — Remote Operations Console.

Run:  streamlit run app/streamlit_app.py

Reads demo/demo_bundle.json (produced by scripts/train.py) so the demo works
offline, with no dataset download and no model inference at show time.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "demo" / "demo_bundle.json"

st.set_page_config(page_title="HemoTwin — Remote Operations Console",
                   page_icon="🩸", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
INK, MUTED, LINE = "#0F172A", "#64748B", "#E2E8F0"
TEAL, AMBER, RED, GREEN = "#0D9488", "#D97706", "#DC2626", "#16A34A"
BG, CARD = "#F6F8FB", "#FFFFFF"

st.markdown(f"""
<style>
  .stApp {{ background: {BG}; }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  #MainMenu, footer {{ visibility: hidden; }}
  html, body, [class*="css"] {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
      color: {INK};
  }}
  .block-container {{ padding: 3.4rem 2rem 3rem 2rem; max-width: 1500px; }}

  .ht-header {{
      display:flex; align-items:center; justify-content:space-between;
      padding: 0 0 14px 0; border-bottom: 1px solid {LINE}; margin-bottom: 18px;
  }}
  .ht-brand {{ display:flex; align-items:center; gap:12px; }}
  .ht-mark {{
      width:38px; height:38px; border-radius:10px; background:{INK}; color:#fff;
      display:flex; align-items:center; justify-content:center;
      font-weight:700; font-size:17px; letter-spacing:-.02em;
  }}
  .ht-title {{ color:{INK}; font-size:19px; font-weight:650; letter-spacing:-.02em; line-height:1.1; }}
  .ht-sub {{ font-size:12.5px; color:{MUTED}; margin-top:2px; }}
  .ht-meta {{ font-size:12px; color:{MUTED}; text-align:right; line-height:1.6; }}
  .ht-hook {{ font-size:12px; color:{TEAL}; font-weight:600; }}

  .ht-kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }}
  .ht-kpi {{
      background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:13px 15px;
  }}
  .ht-kpi .v {{ color:{INK}; font-size:25px; font-weight:680; letter-spacing:-.03em; line-height:1.05; }}
  .ht-kpi .l {{ font-size:11px; color:{MUTED};
                letter-spacing:.02em; margin-top:5px; }}

  .ht-card {{
      background:{CARD}; border:1px solid {LINE}; border-radius:12px;
      padding:12px 14px; margin-bottom:8px; position:relative;
  }}
  .ht-card.sel {{ border-color:{TEAL}; box-shadow:0 0 0 3px rgba(13,148,136,.10); }}
  .ht-chair {{ font-size:11px; color:{MUTED}; letter-spacing:.02em; }}
  .ht-pid {{ color:{INK}; font-size:14.5px; font-weight:620; margin-top:1px; }}
  .ht-dem {{ font-size:11.5px; color:{MUTED}; margin-top:1px; }}
  .ht-risk {{ color:{INK}; font-size:26px; font-weight:700; letter-spacing:-.03em; line-height:1; margin-top:8px; }}
  .ht-risk small {{ font-size:11px; font-weight:500; color:{MUTED}; letter-spacing:0; }}
  .ht-pill {{
      position:absolute; top:12px; right:12px; font-size:10.5px; font-weight:650;
      padding:3px 9px; border-radius:99px; letter-spacing:.03em;
  }}
  .p-red {{ background:#FEE2E2; color:{RED}; }}
  .p-amb {{ background:#FEF3C7; color:{AMBER}; }}
  .p-grn {{ background:#DCFCE7; color:{GREEN}; }}

  .ht-sec {{ font-size:11.5px; letter-spacing:.02em;
             color:{MUTED}; font-weight:650; margin:6px 0 8px 0; }}
  .ht-panel {{
      background:{CARD}; border:1px solid {LINE}; border-radius:12px;
      padding:16px 18px; margin-bottom:12px;
  }}
  .ht-big {{ color:{INK}; font-size:34px; font-weight:700; letter-spacing:-.03em; line-height:1; }}
  .ht-lab {{ font-size:11.5px; color:{MUTED}; margin-top:4px; }}

  .ht-whatif {{ border:1px solid {LINE}; border-radius:12px; padding:14px 15px;
                background:{CARD}; height:100%; }}
  .ht-whatif.rec {{ border-color:{TEAL}; box-shadow:0 0 0 3px rgba(13,148,136,.10); }}
  .ht-whatif .pol {{ font-size:12px; color:{MUTED}; font-weight:600; }}
  .ht-whatif .nad {{ color:{INK}; font-size:31px; font-weight:700; letter-spacing:-.03em; margin-top:6px; }}
  .ht-whatif .ci {{ font-size:12px; color:{MUTED}; }}
  .ht-whatif .cost {{ font-size:12px; margin-top:9px; color:{INK}; }}
  .ht-whatif .cost b {{ font-weight:650; }}
  .ht-rec {{ font-size:10.5px; color:{TEAL}; font-weight:700; letter-spacing:.02em; }}

  .ht-action {{
      background:#ECFDF5; border:1px solid #A7F3D0; border-left:4px solid {TEAL};
      border-radius:10px; padding:14px 16px; font-size:14px; line-height:1.5;
  }}
  .ht-warn {{
      background:#FFFBEB; border:1px solid #FDE68A; border-left:4px solid {AMBER};
      border-radius:10px; padding:12px 15px; font-size:13px; color:#78350F;
  }}
  .ht-foot {{ font-size:11px; color:{MUTED}; margin-top:26px;
              border-top:1px solid {LINE}; padding-top:10px; }}

  div[data-testid="stButton"] > button {{
      border-radius:8px; border:1px solid {LINE}; background:{CARD};
      font-size:12px; color:{INK}; padding:4px 10px; font-weight:600;
  }}
  div[data-testid="stButton"] > button:hover {{ border-color:{TEAL}; color:{TEAL}; }}
  .stTabs [data-baseweb="tab"] {{ font-size:13.5px; font-weight:600; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
def load_bundle(path: str = str(BUNDLE)) -> dict:
    # No st.cache_data here: the bundle is small, and caching by path alone
    # serves a stale trajectory after rebuild_demo.py rewrites the file.
    return json.loads(Path(path).read_text())


def risk_class(r: float) -> tuple[str, str]:
    if r >= 0.60:
        return "p-red", "ACT NOW"
    if r >= 0.35:
        return "p-amb", "WATCH"
    return "p-grn", "STABLE"


def fmt(x, nd=1, dash="--"):
    try:
        v = float(x)
        if v != v:
            return dash
        return f"{v:.{nd}f}"
    except Exception:  # noqa: BLE001
        return dash


# ---------------------------------------------------------------------------
def header(b: dict):
    m = b["metrics"]["test"]
    st.markdown(f"""
    <div class="ht-header">
      <div class="ht-brand">
        <div class="ht-mark">HT</div>
        <div>
          <div class="ht-title">HemoTwin <span style="color:{MUTED};font-weight:400">·</span>
            Remote Operations Console</div>
          <div class="ht-sub">Intradialytic hypotension · 15–60 min horizon ·
            <span class="ht-hook">Predict the crash. Price the fix.</span></div>
        </div>
      </div>
      <div class="ht-meta">
        Shift B · 08:00–16:00 · 8 chairs<br>
        Event model AUROC <b>{m['auroc']:.3f}</b> · threshold {b['meta']['threshold']:.2f}<br>
        Research prototype · not a medical device
      </div>
    </div>
    """, unsafe_allow_html=True)


def kpi_strip(b: dict, chairs: list[dict]):
    red = sum(1 for c in chairs if c["risk"] >= 0.60)
    amb = sum(1 for c in chairs if 0.35 <= c["risk"] < 0.60)
    ev = b["metrics"]["event_level"]
    m = b["metrics"]["test"]
    cols = [
        (f"{len(chairs)}", "chairs monitored"),
        (f"{red + amb}", f"need review · {red} imminent"),
        (f"{100*ev['detection_rate_all_sessions']:.0f}%",
         "crash sessions caught ≥15 min early"),
        (f"{100*ev['false_alarm_session_rate']:.0f}%",
         "uncomplicated sessions alarmed"),
    ]
    html = '<div class="ht-kpis">'
    for v, l in cols:
        html += f'<div class="ht-kpi"><div class="v">{v}</div><div class="l">{l}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def chair_card(c: dict, selected: bool) -> None:
    cls, label = risk_class(c["risk"])
    sel = " sel" if selected else ""
    dm = " · diabetic" if c.get("dm") else ""
    st.markdown(f"""
    <div class="ht-card{sel}">
      <div class="ht-pill {cls}">{label}</div>
      <div class="ht-chair">Chair {c['chair']}</div>
      <div class="ht-pid">Patient {c['pid']}</div>
      <div class="ht-dem">{fmt(c.get('age'),0)}y {c.get('sex','')}{dm} ·
        {fmt(c.get('vintage_years'),1)}y vintage</div>
      <div class="ht-risk">{100*c['risk']:.0f}<small>% risk in 15–60 min</small></div>
      <div class="ht-dem">SBP {fmt(c['sbp_now'],0)} ·
        {fmt(c['t_now_min']/60,1)}h into session</div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
def bp_chart(c: dict, band: dict) -> go.Figure:
    tr = pd.DataFrame(c["trajectory"])
    fc = pd.DataFrame(c["forecast"])
    t_now = c["t_now_min"]

    lo = band.get("lo", -12)
    hi = band.get("hi", 12)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tr.t, y=tr.sbp, mode="lines+markers",
                             name="Observed SBP",
                             line=dict(color=INK, width=2.2),
                             marker=dict(size=5, color=INK)))
    fig.add_trace(go.Scatter(x=fc.t, y=fc.sbp, mode="lines", name="Projected (hold UF)",
                             line=dict(color=TEAL, width=2.2, dash="dash")))
    fig.add_trace(go.Scatter(x=pd.concat([fc.t, fc.t[::-1]]),
                             y=pd.concat([fc.sbp + hi, (fc.sbp + lo)[::-1]]),
                             fill="toself", fillcolor="rgba(13,148,136,.13)",
                             line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_vline(x=t_now, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_hline(y=90, line=dict(color=RED, width=1.2, dash="dash"),
                  annotation_text="IDH threshold 90", annotation_position="bottom right",
                  annotation_font=dict(size=10, color=RED))
    fig.add_annotation(x=t_now, y=1.02, yref="paper", text="now",
                       showarrow=False, font=dict(size=10, color=MUTED))
    all_y = pd.concat([tr.sbp, fc.sbp])
    y_lo = max(40, float(all_y.min()) - 12)
    y_hi = float(all_y.max()) + 15
    fig.update_layout(
        height=300, margin=dict(l=8, r=8, t=16, b=8),
        plot_bgcolor=CARD, paper_bgcolor=CARD,
        xaxis=dict(title="minutes into session", gridcolor="#F1F5F9",
                   zeroline=False, title_font=dict(size=11)),
        yaxis=dict(title="systolic BP (mmHg)", gridcolor="#F1F5F9",
                   zeroline=False, title_font=dict(size=11), range=[y_lo, y_hi]),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
        font=dict(family="system-ui", size=11, color=INK),
        hovermode="x unified",
    )
    return fig


def frontier_chart(c: dict) -> go.Figure:
    cf = c["whatif"]
    colors = {"hold": RED, "taper25": TEAL, "pause": "#0F766E"}
    fig = go.Figure()
    for p in cf:
        fig.add_trace(go.Scatter(
            x=[p["fluid_left_L"]], y=[p["nadir"]],
            mode="markers+text", name=p["label"],
            marker=dict(size=18, color=colors.get(p["policy"], MUTED),
                        line=dict(color="white", width=2)),
            error_y=dict(type="data", symmetric=False,
                         array=[max(p["hi"] - p["nadir"], 0)],
                         arrayminus=[max(p["nadir"] - p["lo"], 0)],
                         color=colors.get(p["policy"], MUTED), thickness=1.5),
            text=[p["label"].split(" ")[0]], textposition="top center",
            textfont=dict(size=10, color=MUTED),
        ))
    fig.add_hline(y=90, line=dict(color=RED, width=1, dash="dash"))
    fig.update_layout(
        height=300, margin=dict(l=8, r=8, t=24, b=8),
        plot_bgcolor=CARD, paper_bgcolor=CARD, showlegend=False,
        xaxis=dict(title="fluid left behind at session end (L)",
                   gridcolor="#F1F5F9", zeroline=False, title_font=dict(size=11)),
        yaxis=dict(title="predicted nadir SBP (mmHg)",
                   gridcolor="#F1F5F9", zeroline=False, title_font=dict(size=11)),
        font=dict(family="system-ui", size=11, color=INK),
    )
    return fig


def drivers_panel(c: dict):
    dr = c.get("drivers", [])
    if not dr:
        return
    df = pd.DataFrame(dr)
    df["abs"] = df.contribution.abs()
    df = df.sort_values("abs")
    colors = [RED if d == "raises" else TEAL for d in df.direction]
    fig = go.Figure(go.Bar(
        x=df.contribution, y=df.label, orientation="h",
        marker_color=colors, marker_line_width=0,
        hovertemplate="%{y}<br>contribution %{x:.3f}<extra></extra>",
    ))
    fig.update_layout(
        height=250, margin=dict(l=8, r=8, t=8, b=8),
        plot_bgcolor=CARD, paper_bgcolor=CARD,
        xaxis=dict(title="contribution to risk (log-odds)", gridcolor="#F1F5F9",
                   zeroline=True, zerolinecolor=LINE, title_font=dict(size=10)),
        yaxis=dict(title="", tickfont=dict(size=10.5)),
        font=dict(family="system-ui", size=10.5, color=INK),
        bargap=0.45,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------------------
def session_view(b: dict, c: dict):
    band = b["metrics"]["twin"]["band"]
    tw = c["twin"]
    cf = {p["policy"]: p for p in c["whatif"]}
    hold = cf["hold"]
    best = min([p for p in c["whatif"] if p["policy"] != "hold"],
               key=lambda p: (p["fluid_left_L"] if p["nadir"] >= 90 else 99))

    st.markdown(f"""
    <div class="ht-sec">Chair {c['chair']} · session {c['session_id']}</div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.55, 1])

    with left:
        st.markdown('<div class="ht-panel">', unsafe_allow_html=True)
        st.plotly_chart(bp_chart(c, band), width="stretch",
                        config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown(f"""
        <div class="ht-panel">
          <div class="ht-lab">Predicted risk · next 15–60 min</div>
          <div class="ht-big" style="color:{RED if c['risk']>=.6 else (AMBER if c['risk']>=.35 else GREEN)}">
            {100*c['risk']:.0f}%</div>
          <div class="ht-lab">calibrated probability · model output, not a confidence interval</div>
          <hr style="border:none;border-top:1px solid {LINE};margin:13px 0">
          <div class="ht-lab">Twin state · fitted from {tw['n_prior_sessions']} prior sessions</div>
          <table style="width:100%;font-size:12.5px;margin-top:7px;border-collapse:collapse;color:{INK}">
            <tr><td style="color:{MUTED};padding:2px 0">Refill rate k</td>
                <td style="text-align:right;font-weight:600;color:{INK}">{tw['k_refill']:.2f} /h</td></tr>
            <tr><td style="color:{MUTED};padding:2px 0">BP sensitivity β</td>
                <td style="text-align:right;font-weight:600;color:{INK}">{tw['beta_bp']:.1f} mmHg/L</td></tr>
            <tr><td style="color:{MUTED};padding:2px 0">Volume removed</td>
                <td style="text-align:right;font-weight:600;color:{INK}">{fmt(tw['v_removed_L'],2)} L</td></tr>
            <tr><td style="color:{MUTED};padding:2px 0">Prescribed goal</td>
                <td style="text-align:right;font-weight:600;color:{INK}">{fmt(tw['v_target_L'],2)} L</td></tr>
          </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="ht-sec">What happens next · choose a policy</div>',
                unsafe_allow_html=True)

    cols = st.columns(3)
    for col, p in zip(cols, c["whatif"]):
        rec = p["policy"] == best["policy"]
        with col:
            st.markdown(f"""
            <div class="ht-whatif{' rec' if rec else ''}">
              <div class="pol">{p['label']}</div>
              <div class="nad" style="color:{RED if p['nadir']<90 else (AMBER if p['nadir']<100 else TEAL)}">
                {p['nadir']:.0f}<span style="font-size:14px;font-weight:500;color:{MUTED}"> mmHg nadir</span></div>
              <div class="ci">90% interval {p['lo']:.0f}–{p['hi']:.0f} ·
                {("immediately" if p["time_to_nadir_min"] <= 0 else f"nadir in {p['time_to_nadir_min']:.0f} min")}</div>
              <div class="cost">Fluid left behind: <b>{p['fluid_left_L']:.2f} L</b></div>
              <div class="cost" style="color:{MUTED}">Removed by end: {p['fluid_removed_L']:.2f} L</div>
              {f'<div class="ht-rec" style="margin-top:8px">lowest cost that avoids the crash</div>' if rec else ''}
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    a, bb = st.columns([1.2, 1])
    with a:
        st.markdown('<div class="ht-sec">Projected course</div>', unsafe_allow_html=True)
        st.plotly_chart(frontier_chart(c), width="stretch",
                        config={"displayModeBar": False})
    with bb:
        st.markdown('<div class="ht-sec">Why · top drivers</div>', unsafe_allow_html=True)
        drivers_panel(c)

    st.markdown('<div class="ht-sec">Recommended action</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ht-action">{c["action"]}</div>', unsafe_allow_html=True)

    st.write("")
    k1, k2, k3, _ = st.columns([1, 1, 1, 2])
    if k1.button("Accept", width="stretch", key=f"acc_{c['session_id']}"):
        st.session_state.setdefault("audit", []).append(
            f"Accepted · chair {c['chair']} · {c['session_id']} · {c['action'][:60]}")
        st.success("Logged to audit trail.")
    if k2.button("Modify", width="stretch", key=f"mod_{c['session_id']}"):
        st.session_state.setdefault("audit", []).append(
            f"Modified · chair {c['chair']} · {c['session_id']}")
        st.info("Dose edit recorded. Local safety limits always win.")
    if k3.button("Override", width="stretch", key=f"ovr_{c['session_id']}"):
        st.session_state.setdefault("audit", []).append(
            f"Overridden · chair {c['chair']} · {c['session_id']} · reason required")
        st.warning("Override logged with mandatory reason. Feeds the next retraining round.")


# ---------------------------------------------------------------------------
def trust_tab(b: dict):
    m = b["metrics"]
    t, ev, ppv = m["test"], m["event_level"], m["session_ppv"]
    r1, r2 = m["baselines"]["r1"], m["baselines"]["r2"]
    cal = m["calibration"]
    tw = m["twin"]

    st.markdown('<div class="ht-sec">Event model · patient-disjoint test split</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    for col, (v, l) in zip([c1, c2, c3, c4], [
        (f"{m['test']['auroc']:.3f}", f"AUROC · 95% CI {t['auroc_ci'][0]:.3f}–{t['auroc_ci'][1]:.3f}"),
        (f"{t['lift']:.1f}×", f"AUPRC lift over {100*t['prevalence']:.1f}% prevalence"),
        (f"{100*t['sens_at_spec90']:.0f}%", "sensitivity at 90% specificity"),
        (f"{100*ev['detection_rate_all_sessions']:.0f}%", "of all crash sessions caught"),
    ]):
        with col:
            st.markdown(f'<div class="ht-kpi"><div class="v">{v}</div>'
                        f'<div class="l">{l}</div></div>', unsafe_allow_html=True)

    st.write("")
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="ht-sec">Against clinical rules</div>', unsafe_allow_html=True)
        df = pd.DataFrame([
            {"Model / rule": "HemoTwin event model", "AUROC": t["auroc"],
             "Sens @ 90% spec": t["sens_at_spec90"]},
            {"Model / rule": "R1 · alarm when SBP is low", "AUROC": r1["auroc"],
             "Sens @ 90% spec": r1["sens_at_spec90"]},
            {"Model / rule": "R2 · extrapolate BP slope", "AUROC": r2["auroc"],
             "Sens @ 90% spec": r2["sens_at_spec90"]},
        ])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={
                         "AUROC": st.column_config.NumberColumn(format="%.3f"),
                         "Sens @ 90% spec": st.column_config.NumberColumn(format="%.3f"),
                     })

        st.markdown('<div class="ht-sec">Event-level, at the frozen operating point</div>',
                    unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ht-panel" style="font-size:13px;line-height:1.7">
          <b>{ev['detected']:,}</b> of <b>{ev['n_idh_sessions']:,}</b> crash sessions
          were flagged before onset
          (<b>{100*ev['detection_rate_all_sessions']:.1f}%</b>;
          {100*ev['detection_rate_evaluable']:.1f}% of the
          {ev['detected']+ev['missed']:,} with a usable warning window).<br>
          <b>{ev['no_anchor_window']}</b> sessions had no BP reading in the warnable
          window — a cuffing-cadence limit, not a model failure.<br>
          <b>{100*ev['false_alarm_session_rate']:.1f}%</b> of uncomplicated sessions
          received at least one alarm.<br>
          Of the sessions we flagged, <b>{100*ppv['session_ppv']:.0f}%</b> actually
          crashed ({ppv['sessions_flagged']:,} flagged).
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown('<div class="ht-sec">Calibration · held-out half of validation</div>',
                    unsafe_allow_html=True)
        rel = pd.DataFrame(cal["reliability"])
        if len(rel):
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                     line=dict(color=LINE, dash="dash"),
                                     name="perfect"))
            fig.add_trace(go.Scatter(x=rel.predicted, y=rel.observed, mode="lines+markers",
                                     line=dict(color=TEAL, width=2), marker=dict(size=6),
                                     name="observed"))
            fig.update_layout(height=260, margin=dict(l=8, r=8, t=8, b=8),
                              plot_bgcolor=CARD, paper_bgcolor=CARD,
                              xaxis=dict(title="predicted", gridcolor="#F1F5F9",
                                         title_font=dict(size=10)),
                              yaxis=dict(title="observed", gridcolor="#F1F5F9",
                                         title_font=dict(size=10)),
                              font=dict(family="system-ui", size=10.5, color=INK),
                              legend=dict(orientation="h", y=1.1, font=dict(size=10)))
            st.plotly_chart(fig, width="stretch",
                            config={"displayModeBar": False})
        st.markdown(f"""
        <div class="ht-panel" style="font-size:12.5px;line-height:1.7">
          Patient-disjoint test ECE: <b>{b['metrics']['test']['calibration']['ece']:.4f}</b>.<br>
          Validation holdout (row split): <b>{cal['ece_raw_holdout']:.3f}</b> raw →
          <b>{cal['ece_cal_holdout']:.3f}</b> after isotonic. The row split is optimistic;
          the test number is the one we treat as primary.
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="ht-sec">Twin validation</div>', unsafe_allow_html=True)
    vol = tw["volume"]
    band = tw["band"]
    pop = tw["population"]
    c1, c2, c3, c4 = st.columns(4)
    for col, (v, l) in zip([c1, c2, c3, c4], [
        (f"{vol.get('n', 0):,}", "sessions with measured weight loss"),
        (f"{vol.get('median_difference_L', float('nan')):+.2f} L",
         "median modelled − measured UF"),
        (f"{100*vol.get('within_0_5L_share', 0):.0f}%", "within 0.5 L of measured"),
        (f"±{abs(band.get('lo', 0)):.0f}/{abs(band.get('hi', 0)):.0f}",
         "5–95% nadir residual (mmHg)"),
    ]):
        with col:
            st.markdown(f'<div class="ht-kpi"><div class="v">{v}</div>'
                        f'<div class="l">{l}</div></div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="ht-panel" style="font-size:12.5px;line-height:1.7;margin-top:12px">
      Population twin parameters, fitted on {pop.get('n', 0):,} training sessions:
      refill rate <b>k = {pop['k_refill']:.2f}/h</b>, BP sensitivity
      <b>β = {pop['beta_bp']:.1f} mmHg/L</b>.
      The twin is validated two ways: (1) its integrated ultrafiltration is compared
      with the measured pre/post weight difference, and (2) its predicted nadir is
      compared with the observed nadir on held-out sessions. The interval shown on the
      dashboard is the 5–95% residual band from that held-out comparison.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ht-warn" style="margin-top:14px">'
                '<b>What this is not.</b> This is a research prototype. The cohort is '
                'Taiwanese and the model is internally validated. The Spanish '
                'transport check failed (AUROC 0.474 versus 0.720 internally) because '
                'the Spanish label is symptomatic hypotension, not nadir SBP under 90. '
                'We claim no external validity. Blood pressure is cuffed roughly every '
                '30 minutes. The counterfactual is an observational, within-policy-space '
                'simulation, not a randomised estimate of effect.</div>',
                unsafe_allow_html=True)


def about_tab(b: dict):
    st.markdown(f"""
    <div class="ht-panel" style="font-size:13.5px;line-height:1.8">
      <div class="ht-sec">What this is</div>
      A digital twin for haemodialysis. Three layers:
      an <b>event model</b> (LightGBM, 40 causal features, patient-disjoint split)
      that estimates the probability of the first hypotensive episode starting in the
      next 15–60 minutes, and a <b>physiological twin</b> that maintains a per-patient
      volume deficit state and simulates the rest of the session under alternative
      ultrafiltration policies.
      <div class="ht-sec" style="margin-top:18px">The model</div>
      dD/dt = UF(t)/60 − k·D &nbsp;&nbsp;·&nbsp;&nbsp; SBP(t) = SBP₀ − β·D(t)<br>
      Two parameters, because NIBP every 30 minutes does not identify more.
      k and β are fitted per patient from earlier sessions and shrunk toward the
      population median; SBP₀ is anchored to the current session.
      <div class="ht-sec" style="margin-top:18px">The counterfactual</div>
      87.2% of real sessions already taper ultrafiltration mid-session (median
      0.58 → 0.10 L/h). We are not proposing a new intervention. We are choosing
      <i>when</i> to apply the one that already happens, and pricing what it leaves
      behind.
      <div class="ht-sec" style="margin-top:18px">Data</div>
      HEMOBP (Lin et al., <i>Scientific Data</i> 2019, CC BY 4.0) —
      {b['metrics']['test']['n']:,} test anchors from 1,070 patients.
      Mendeley Dialysis Database (Gómez-Pulido, CC BY 4.0) — 97,640 sessions for
      session-level transport check, which failed; the analysis is in docs/EXTERNAL_VALIDATION.md. No proprietary data is included.
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get("audit"):
        st.markdown('<div class="ht-sec">Audit trail (this session)</div>',
                    unsafe_allow_html=True)
        for line in st.session_state["audit"][::-1]:
            st.markdown(f"- {line}")


# ---------------------------------------------------------------------------
def main():
    if not BUNDLE.exists():
        st.error("demo/demo_bundle.json not found. Run `python scripts/train.py` first.")
        st.stop()

    b = load_bundle()
    chairs = b["chairs"]

    header(b)
    kpi_strip(b, chairs)

    tab_console, tab_trust, tab_about = st.tabs(
        ["Console", "Validation & trust", "About the twin"])

    with tab_console:
        st.markdown('<div class="ht-sec">Chair board</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, c in enumerate(chairs):
            with cols[i % 4]:
                selected = st.session_state.get("sel") == c["session_id"]
                chair_card(c, selected)
                if st.button("Open", key=f"open_{c['session_id']}",
                             width="stretch"):
                    st.session_state["sel"] = c["session_id"]
                    selected = True
        st.write("")

        sel = st.session_state.get("sel", chairs[0]["session_id"])
        c = next((x for x in chairs if x["session_id"] == sel), chairs[0])
        session_view(b, c)

    with tab_trust:
        trust_tab(b)

    with tab_about:
        about_tab(b)

    st.markdown(
        '<div class="ht-foot">HemoTwin · research prototype · not a medical device · '
        'decision support only · HEMOBP &amp; Mendeley Dialysis Database, CC BY 4.0</div>',
        unsafe_allow_html=True)


if __name__ == "__main__":
    main()
