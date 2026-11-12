"""Plotly figures for the HemoTwin V2 console and deck."""
from __future__ import annotations

import math

import plotly.graph_objects as go

ACCENT = "#17756A"
TEAL = "#0F8F80"
SAGE = "#7D8B7C"
AMBER = "#A8641B"
RISK = "#B23C2C"
GOOD = "#1F7A4D"
INK = "#141C1E"
MUTED = "#5C6B6D"
GRID = "#E6EDEA"
SURFACE = "#FFFFFF"


def apply_theme(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", color=MUTED, size=12),
        title=dict(font=dict(family="Segoe UI Variable Display, Segoe UI, "
                                  "sans-serif", color=INK, size=16)),
        margin=dict(l=8, r=8, t=58, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=11)),
        hoverlabel=dict(
            bgcolor=SURFACE, bordercolor="rgba(23,117,106,.4)",
            font=dict(color=INK, family="Segoe UI")),
        hovermode="x unified",
    )
    fig.update_xaxes(
        gridcolor=GRID, zeroline=False, linecolor="#DCE4E1", automargin=True,
        tickfont=dict(color=MUTED), title_font=dict(color=MUTED))
    fig.update_yaxes(
        gridcolor=GRID, zeroline=False, linecolor="#DCE4E1", automargin=True,
        tickfont=dict(color=MUTED), title_font=dict(color=MUTED))
    return fig


def _cuff_custom(cuffs: list[dict]) -> list[list]:
    out = []
    for c in cuffs:
        dbp = c.get("dbp")
        uf = c.get("uf_lh")
        projection = c.get("projection_sbp")
        out.append([
            c.get("index"),
            "—" if dbp is None else f"{float(dbp):.0f}",
            "—" if uf is None else f"{float(uf):.2f}",
            "—" if projection is None else f"{float(projection):.0f}",
        ])
    return out


def fan_figure(case: dict, show_illustration: bool = False,
               show_projection: bool = True,
               selected_rel: float | None = None) -> go.Figure:
    fig = go.Figure()
    cuffs = case.get("cuffs", [])
    before = [c for c in cuffs if c.get("phase") == "before"]
    after = [c for c in cuffs if c.get("phase") == "after"]

    # Projection first, cuffs last: the band fill must not sit above the
    # observed markers or it swallows their click events.
    hold = (case.get("calibrated", {}).get("scenarios") or [{}])[0]
    y = hold.get("nadir_series_mmhg") or []
    if show_projection and y:
        x = list(range(len(y)))
        nadir = float(hold.get("projected_nadir_mmhg") or y[-1])
        band = hold.get("nadir_band_90") or [nadir, nadir]
        lo_off = float(band[0]) - nadir
        hi_off = float(band[1]) - nadir
        fig.add_trace(go.Scatter(
            x=x + x[::-1],
            y=[v + hi_off for v in y] + [v + lo_off for v in y][::-1],
            fill="toself", fillcolor="rgba(23, 117, 106, 0.10)",
            line=dict(width=0), name="90% nadir band",
            hoverinfo="skip", legendrank=3))
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", name="Projection · gain 0",
            line=dict(color=ACCENT, width=2.6), legendrank=4,
            hoverinfo="skip"))
    elif not show_projection:
        fig.add_annotation(
            x=0.02, y=0.5, xref="x domain", yref="paper",
            text="No current BP — projection withheld",
            showarrow=False, font=dict(color=AMBER, size=12),
            bgcolor="rgba(255,255,255,.94)", borderpad=6)

    if show_illustration:
        colors = [SAGE, AMBER, RISK, GOOD, "#6E9E94"]
        for scenario, color in zip(
                case.get("illustration", {}).get("scenarios", []), colors):
            series = scenario.get("nadir_series_mmhg") or []
            fig.add_trace(go.Scatter(
                x=list(range(len(series))), y=series, mode="lines",
                name=f"Illustration · {scenario.get('label', '')}",
                line=dict(color=color, dash="dash", width=1.3),
                opacity=0.8, hoverinfo="skip"))

    if before:
        fig.add_trace(go.Scatter(
            x=[c["rel"] for c in before], y=[c["sbp"] for c in before],
            mode="lines+markers", name="Observed · before anchor",
            line=dict(color=INK, width=2.2),
            marker=dict(color=INK, size=7,
                        line=dict(color=SURFACE, width=2)),
            customdata=_cuff_custom(before), legendrank=1,
            hovertemplate=("%{x:.0f} min · SBP %{y:.0f} · DBP "
                           "%{customdata[1]} · UF %{customdata[2]}"
                           "<extra></extra>")))
    if after:
        fig.add_trace(go.Scatter(
            x=[c["rel"] for c in after], y=[c["sbp"] for c in after],
            mode="markers", name="Observed · ground truth",
            marker=dict(color=AMBER, size=11, symbol="diamond",
                        line=dict(color=SURFACE, width=1.5)),
            customdata=_cuff_custom(after), legendrank=2,
            hovertemplate=("%{x:.0f} min · SBP %{y:.0f} · calib "
                           "%{customdata[3]} · DBP %{customdata[1]} · UF "
                           "%{customdata[2]}<extra></extra>")))

    fig.add_hline(y=90, line_dash="dot", line_color="rgba(178,60,44,.55)",
                  annotation_text="90 mmHg floor",
                  annotation_font=dict(color=RISK, size=11),
                  annotation_position="top right")
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(20,28,30,.28)")
    fig.add_annotation(
        x=0, y=1.04, xref="x", yref="paper", text="anchor",
        showarrow=False, font=dict(color=MUTED, size=11),
        xanchor="left")
    if selected_rel is not None:
        fig.add_vline(x=float(selected_rel), line_dash="dot",
                      line_color="rgba(23,117,106,.6)", line_width=1.4)
        fig.add_annotation(
            x=float(selected_rel), y=0.02, yref="paper",
            text=f"inspecting {float(selected_rel):+.0f} min",
            showarrow=False, font=dict(color=ACCENT, size=10),
            bgcolor="rgba(255,255,255,.94)", borderpad=3,
            xanchor="left")
    fig.update_layout(xaxis_title="Minutes from anchor",
                      yaxis_title="Systolic BP (mmHg)")
    fig.update_xaxes(showspikes=True, spikemode="across",
                     spikecolor="rgba(23,117,106,.4)",
                     spikethickness=1, spikedash="dot")
    if not show_projection:
        fig.update_xaxes(range=[-102, 64])
        fig.update_yaxes(range=[60, 180])
    return apply_theme(fig, 430)


def g7_forest_figure(g7: dict) -> go.Figure:
    est = g7.get("estimates", {})
    rows = [
        ("Early-UF effect", est.get("tau30_per_0.25_l_h", {}).get("slope"),
         (est.get("tau30_bootstrap", {}).get("ci95") or [None, None]),
         "mmHg per 0.25 L/h"),
        ("Twin gain", est.get("gamma_struct", {}).get("slope"),
         (est.get("gamma_struct_bootstrap", {}).get("ci95") or [None, None]),
         "gain"),
        ("Pre-trend check", est.get("tau_pre", {}).get("slope"),
         (est.get("tau_pre_bootstrap", {}).get("ci95") or [None, None]),
         "mmHg"),
        ("Sham-time check", est.get("sham", {}).get("mean"),
         (est.get("sham", {}).get("ci95") or [None, None]),
         "mmHg"),
    ]
    p6a = (g7.get("p6a_fold2_trajectory") or {}).get("30") or {}
    if p6a.get("delta_mae") is not None:
        rows.append(("Trajectory check", p6a.get("delta_mae"),
                     (p6a.get("ci95") or [None, None]), "mmHg"))

    labels, values, los, his, colors = [], [], [], [], []
    for label, value, ci, _unit in rows:
        if value is None:
            continue
        labels.append(label)
        values.append(float(value))
        los.append(float(ci[0]) if ci[0] is not None else float(value))
        his.append(float(ci[1]) if ci[1] is not None else float(value))
        if los[-1] <= 0 <= his[-1]:
            colors.append("rgba(92,107,109,.65)")
        else:
            colors.append(RISK if values[-1] > 0 else GOOD)

    fig = go.Figure()
    for i, (label, value, lo, hi, color) in enumerate(
            zip(labels, values, los, his, colors)):
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[i, i], mode="lines",
            line=dict(color=color, width=2.4), hoverinfo="skip",
            showlegend=False))
        fig.add_trace(go.Scatter(
            x=[value], y=[i], mode="markers",
            marker=dict(color=color, size=11,
                        line=dict(color=SURFACE, width=2)),
            hovertemplate=f"{label}<br>{value:.2f} [{lo:.2f}, {hi:.2f}]<extra></extra>",
            showlegend=False))
    fig.add_vline(x=0, line_color="rgba(20,28,30,.35)", line_width=1)
    fig.update_yaxes(tickvals=list(range(len(labels))), ticktext=labels,
                     autorange="reversed")
    fig.update_layout(xaxis_title="Estimate (95% bootstrap CI)",
                      showlegend=False)
    return apply_theme(fig, 360)


def temporal_order_figure(g7: dict) -> go.Figure:
    classes = (g7.get("temporal_order") or {}).get("classes", {})
    order = [
        ("at_anchor_no_drop", "Cut at anchor · no prior drop"),
        ("at_anchor_after_drop", "Cut at anchor · after a drop"),
        ("intermediate_after_drop", "Intermediate cuff · after a drop"),
        ("intermediate_no_drop", "Intermediate cuff · no drop"),
        ("no_cut", "No qualifying cut"),
    ]
    labels = [label for key, label in order if key in classes]
    values = [classes[key] for key, _ in order if key in classes]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=[ACCENT, SAGE, AMBER, "#6E9E94", "rgba(92,107,109,.45)"]),
        text=[str(v) for v in values], textposition="outside",
        textfont=dict(color=INK, size=11),
        hovertemplate="%{y}: %{x}<extra></extra>"))
    fig.update_layout(xaxis_title="G3 rows (n=397)", showlegend=False)
    fig.update_yaxes(autorange="reversed")
    return apply_theme(fig, 300)


def shap_bar_figure(result: dict) -> go.Figure:
    downward = result.get("top_downward") or []
    stabilizing = result.get("top_stabilizing") or []
    labels = [d["feature"] for d in downward] + [s["feature"] for s in stabilizing]
    values = [d["contribution_mmHg"] for d in downward] + [
        s["contribution_mmHg"] for s in stabilizing]
    colors = [RISK] * len(downward) + [GOOD] * len(stabilizing)
    fig = go.Figure(go.Bar(
        x=values[::-1], y=labels[::-1], orientation="h",
        marker=dict(color=colors[::-1]),
        hovertemplate="%{y}: %{x:.2f} mmHg<extra></extra>"))
    fig.add_vline(x=0, line_color="rgba(20,28,30,.3)", line_width=1)
    fig.update_layout(xaxis_title="TreeSHAP contribution (mmHg)",
                      showlegend=False)
    return apply_theme(fig, 330)


def scenario_fluid_figure(case: dict) -> go.Figure | None:
    scenarios = case.get("calibrated", {}).get("scenarios") or []
    rows = [(s.get("label", ""), s.get("fluid_left_behind_l"))
            for s in scenarios
            if s.get("fluid_left_behind_l") is not None
            and math.isfinite(float(s.get("fluid_left_behind_l")))]
    if not rows:
        return None
    labels = [r[0] for r in rows]
    values = [float(r[1]) for r in rows]
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker=dict(color=ACCENT),
        text=[f"{v:.2f} L" for v in values], textposition="outside",
        textfont=dict(color=INK, size=11),
        hovertemplate="%{x}: %{y:.2f} L<extra></extra>"))
    fig.update_layout(yaxis_title="Fluid carried forward (L)",
                      showlegend=False)
    return apply_theme(fig, 280)
