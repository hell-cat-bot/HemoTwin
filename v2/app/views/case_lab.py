"""Case lab: the judge-facing showpiece built on the frozen v4 evidence."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from app.ui import charts
from app.ui import theme
from app.ui.theme import e, metric_row, pill

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"
INSPECTION = EVIDENCE / "case_inspection.json"

ROLE_CODES = {
    "Dialysis nurse": "RN",
    "Dialysis technician": "TECH",
    "Nephrologist": "NEPHROLOGIST",
}

REGIME_LABELS = {
    "hold": "hold",
    "moderate": "moderate",
    "aggressive": "aggressive",
    "mixed": "mixed",
    "pause": "paused UF",
    "zero_reference": "paused UF",
    "synthetic": "synthetic",
}


def _regime_label(regime: str) -> str:
    return REGIME_LABELS.get(regime, regime.replace("_", " "))

ARCHETYPES = [
    ("stable_hold", "Stable", "No crash. Forecast within 1 mmHg."),
    ("taper", "Taper", "UF tapered; observed within 1 mmHg of forecast."),
    ("pause", "Paused UF", "UF paused and resumed; forecast within 1 mmHg."),
    ("true_crash", "True crash", "Observed nadir 78. High pre-session risk."),
    ("stale_cuff", "Stale cuff", "42-minute-old reading. The guardrail refuses to guess."),
]

EXTRA_CASES = [
    ("g1_taper_showcase", "Showcase", "v3 missed by 21 mmHg; v4 within 3."),
]

CASE_NOTES = {
    "stable_hold": ("Forecast 160 vs observed nadir 160; no crash. The value is the "
                    "calm baseline and the explicit fluid arithmetic.", ""),
    "taper": ("The nurse tapered UF and the observed nadir (129) met the forecast "
              "(129). A good trade-off conversation, not a crash prediction.", ""),
    "pause": ("UF paused and resumed; observed 117 vs forecast 118 — within 1 mmHg "
              "and no crash. The model handled the pause.", ""),
    "true_crash": ("Pre-session risk 70%; forecast 82; observed nadir 78. The "
                   "protocol state is REVIEW_NOW. The product buys time to react "
                   "and seek advice; it does not prescribe a dose.", "fail"),
    "stale_cuff": ("The last cuff is 42 minutes old. There is no current BP, so the "
                   "system returns INSUFFICIENT_INFORMATION instead of guessing. This "
                   "is the guardrail that keeps the demo honest.", "fail"),
    "g1_taper_showcase": ("v3 predicted 148; v4 predicted 124; observed 127. Within "
                          "3 mmHg, and no crash.", ""),
}


@st.cache_data(show_spinner=False)
def _load_json(path: str, mtime: float) -> dict:
    # mtime is part of the cache key so rebuilt evidence is picked up.
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _demo() -> dict:
    path = EVIDENCE / "demo_twin.json"
    return _load_json(str(path), path.stat().st_mtime)


def demo_case(name: str) -> dict | None:
    return next((c for c in _demo()["cases"] if c["name"] == name), None)


def _report() -> dict:
    path = EVIDENCE / "benchmark_report.json"
    return _load_json(str(path), path.stat().st_mtime)


def _inspection() -> dict:
    if not INSPECTION.exists():
        return {}
    return _load_json(str(INSPECTION), INSPECTION.stat().st_mtime)


def _view_case(case: dict) -> dict:
    """Merge the per-cuff inspection sidecar without touching the evidence file."""
    base = [{**c, "index": i} for i, c in enumerate(case.get("cuffs") or [])]
    entry = (_inspection().get("cases") or {}).get(case["id"]) or {}
    extra = entry.get("cuffs") or []
    if len(extra) == len(base):
        keys = ("dbp", "uf_lh", "cum_uf_l", "twin", "projection_sbp")
        base = [{**cuff, **{k: e[k] for k in keys if k in e}}
                for cuff, e in zip(base, extra)]
    return {**case, "cuffs": base}


def _anchor_index(cuffs: list[dict]) -> int | None:
    if not cuffs:
        return None
    return min(range(len(cuffs)),
               key=lambda i: abs(float(cuffs[i].get("rel") or 0.0)))


def _selection_index(event, cuffs: list[dict]) -> int | None:
    if not cuffs:
        return None
    try:
        points = event.selection.points
    except (AttributeError, KeyError, TypeError):
        try:
            points = event["selection"]["points"]
        except (AttributeError, KeyError, TypeError):
            points = []
    fallback_x = None
    for point in points or []:
        try:
            raw = point.get("customdata") if isinstance(point, dict) else None
        except AttributeError:
            raw = None
        if not raw:
            try:
                fallback_x = float(point.get("x"))
            except (AttributeError, TypeError, ValueError):
                pass
            continue
        try:
            idx = int(raw[0])
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(cuffs):
            return idx
    if fallback_x is not None:
        nearest = min(
            ((abs(float(c.get("rel") or 0.0) - fallback_x), i)
             for i, c in enumerate(cuffs)),
            default=None)
        if nearest is not None and nearest[0] <= 1.0:
            return nearest[1]
    return None


def _safe_float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt(value, nd: int = 1, suffix: str = "") -> str:
    number = _safe_float(value)
    if number is None:
        return "—"
    return f"{number:.{nd}f}{suffix}"


def _pick(case_id: str, case_name: str) -> None:
    st.session_state["case_id"] = case_id
    st.session_state["case_select"] = case_name.replace("_", " ").title()


def _sync_from_select() -> None:
    demo = _demo()
    display = {c["name"]: c["name"].replace("_", " ").title() for c in demo["cases"]}
    label = st.session_state.get("case_select")
    selected = next((c for c in demo["cases"] if display[c["name"]] == label), None)
    if selected:
        st.session_state["case_id"] = selected["id"]


def _state_tone(state: str) -> str:
    return {
        "URGENT_CLINICAL_REVIEW": "fail",
        "REVIEW_NOW": "warn",
        "NO_ALERT": "ok",
        "INSUFFICIENT_INFORMATION": "sage",
    }.get(state, "")


def _protocol_panel(case: dict, role_code: str, stale: bool) -> None:
    from src.session_twin.engine import recommend
    from src.session_twin.protocol import load_protocol

    protocol = load_protocol()
    first = case.get("first_sbp") or case.get("sbp_anchor") or 120.0
    snapshot = {
        "sbp": None if stale else case.get("sbp_anchor"),
        "t_min": case.get("t_anchor"),
        "sbp_drop_from_session_baseline": (
            None if stale else max(0.0, float(first) - float(case["sbp_anchor"]))),
        "uf_rate_Lh": case.get("uf_rate_lh"),
        "uf_goal_L": case.get("uf_goal_l"),
        "uf_removed_L": case.get("uf_removed_l"),
        "symptom_any": False,
        "clinician_concern": False,
        "role": role_code,
        # The shadow model is intentionally not scored in V2; no invented number.
        "risk_shadow": {
            "available": False, "score": None, "threshold": None,
            "as_of_min": None, "model_version": None,
        },
    }
    result = recommend(snapshot, protocol)
    tone = _state_tone(result["state"])
    state_label = result["state"].replace("_", " ")
    st.markdown(
        f'<div class="ht-card ht-card--glow">'
        f'<div class="ht-kicker">Deterministic protocol state · role {e(result["role_simulation"])}</div>'
        f'<div style="display:flex;align-items:center;gap:10px;margin:10px 0 8px">'
        f'{pill(state_label, tone)}</div>'
        f'<p>{e(result["state_reason_text"])}</p>'
        f'<p style="margin-top:8px;font-size:11px">'
        f'Protocol {e(result["protocol_version"])} · research status · '
        f'shadow risk not scored · the forecast never gates this state.</p>'
        f'</div>',
        unsafe_allow_html=True)

    pathway = result.get("pathway") or []
    available = [s for s in pathway if s.get("available")]
    st.markdown("**Next review steps**")
    if available:
        for step in available[:3]:
            st.markdown(
                f"**{step['sequence']}. {e(step['title'])}**  \n"
                f"{e(step['instruction'])}  \n"
                f"<span style='color:var(--ht-muted);font-size:12px'>Roles: "
                f"{e(', '.join(step['roles']))}</span>",
                unsafe_allow_html=True)
    else:
        st.caption("No step is currently available; the pathway is blocked by missing data.")
    with st.expander("Full protocol pathway", expanded=False):
        for step in pathway:
            badge = ("available" if step.get("available")
                     else f"blocked — {step.get('reason_code', 'condition')}")
            st.markdown(
                f"**{step['sequence']}. {e(step['title'])}**  \n"
                f"{e(step['instruction'])}  \n"
                f"<span style='color:var(--ht-muted);font-size:12px'>Roles: "
                f"{e(', '.join(step['roles']))} · {e(badge)}</span>",
                unsafe_allow_html=True)
    st.caption("Configured research protocol. Not a validated workflow, "
               "prescription, or medical device.")


def _state_inspector(case: dict) -> None:
    from src.session_twin.state_vector import build_causal_state_vector

    row = dict(case.get("features") or {})
    row.update({k: (case.get("state") or {}).get(k) for k in
                ("D0", "R0", "C0", "OH0", "n_prior_sessions", "k_pat",
                 "beta_pat", "dry_weight", "pre_weight", "uf_at_anchor")})
    try:
        sv = build_causal_state_vector(row)
    except Exception as exc:  # noqa: BLE001 - display-only panel
        st.info(f"State vector unavailable: {exc}")
        return
    cols = st.columns(4)
    blocks = [
        ("Block 1 · static EHR", [
            ("Age", _fmt(sv["static_ehr_state"].get("age"), 0, " yr")),
            ("Dry weight", _fmt(sv["static_ehr_state"].get("dry_weight"), 1, " kg")),
            ("UF goal", _fmt(sv["static_ehr_state"].get("uf_goal_L"), 2, " L")),
            ("Dialysate temp", _fmt(sv["static_ehr_state"].get("dia_temp"), 1, " °C")),
        ]),
        ("Block 2 · patient memory", [
            ("Prior sessions", _fmt(sv["inter_session_memory_state"].get("n_prior_sessions"), 0)),
            ("Shrinkage", _fmt(sv["inter_session_memory_state"].get("shrinkage_weight"), 3)),
            ("k_refill", _fmt(sv["inter_session_memory_state"].get("k_refill"), 3)),
            ("β_vol", _fmt(sv["inter_session_memory_state"].get("beta_vol_mmHg_per_l"), 1, " mmHg/L")),
        ]),
        ("Block 3 · intra-session", [
            ("SBP now", _fmt(sv["intra_session_dynamic_state"].get("sbp_now"), 0, " mmHg")),
            ("SBP slope 30", _fmt(sv["intra_session_dynamic_state"].get("sbp_slope_30"), 1, " mmHg/h")),
            ("UF rate", _fmt(sv["intra_session_dynamic_state"].get("uf_Lh"), 2, " L/h")),
            ("Cumulative UF", _fmt(sv["intra_session_dynamic_state"].get("cum_uf_L"), 2, " L")),
        ]),
        ("Block 4 · latent ODE", [
            ("Plasma deficit", _fmt(sv["latent_starling_baroreflex_state"].get("plasma_deficit_l"), 2, " L")),
            ("Refill rate", _fmt(sv["latent_starling_baroreflex_state"].get("refill_rate_l_h"), 2, " L/h")),
            ("Baro exhaustion", _fmt(100.0 * (sv["latent_starling_baroreflex_state"].get("baroreflex_exhaustion") or 0.0), 1, " %")),
            ("Refill gap", _fmt(sv["latent_starling_baroreflex_state"].get("refill_deficit_l_h"), 2, " L/h")),
        ]),
    ]
    for col, (title, items) in zip(cols, blocks):
        with col:
            st.markdown(f"**{title}**")
            for label, value in items:
                st.metric(label, value)
    st.caption("All four blocks use only records at or before the anchor. "
               "The latent ODE state is a model state, not a measurement.")


def _shap_panel(case: dict) -> None:
    from src.forecast_serve import explain_pre_anchor_drivers

    if case.get("synthetic_demo"):
        st.info("Synthetic demo — no patient attribution is computed.")
        return
    result = explain_pre_anchor_drivers(case.get("features") or {}, top_k=5)
    if not result.get("available"):
        st.info(result.get("reason", "Attribution unavailable."))
        return
    st.plotly_chart(charts.shap_bar_figure(result), width="stretch",
                    config={"displayModeBar": False})
    totals = result.get("block_totals_mmHg") or {}
    cols = st.columns(3)
    for col, key, label in zip(
            cols,
            ("STATIC_EHR", "PATIENT_HISTORY_MEMORY", "DYNAMIC_INTRA_SESSION"),
            ("Static EHR", "Patient memory", "Intra-session")):
        with col:
            st.metric(label, _fmt(totals.get(key), 1, " mmHg"))
    st.caption("TreeSHAP on the fair 59-feature pre-anchor model. The future-UF "
               "oracle block is excluded; these are associations, not causal effects.")


def _fluid_table(case: dict, stale: bool) -> None:
    """Fluid arithmetic plus the uncalibrated per-policy SBP sketch."""
    if stale:
        st.markdown(theme.callout(
            "Projection and fluid arithmetic withheld: the last cuff is "
            f"{case.get('cuff_age_min', 0):.0f} minutes old. A current BP is "
            "required before the trade-off can be computed.", "warn"),
            unsafe_allow_html=True)
        return
    scenarios = (case.get("calibrated", {}).get("scenarios") or [])
    sketch = {s.get("policy"): s for s in
              ((case.get("illustration") or {}).get("scenarios") or [])}
    hold = scenarios[0] if scenarios else {}
    band = hold.get("nadir_band_90") or [None, None]
    shared = []
    if hold.get("projected_nadir_mmhg") is not None:
        shared.append(pill(
            f"Calibrated +60 min · "
            f"{_fmt(hold.get('projected_nadir_mmhg'), 1)} mmHg", "info"))
    if band[0] is not None and band[1] is not None:
        shared.append(pill(
            f"90% band · {_fmt(band[0], 0)}–{_fmt(band[1], 0)} mmHg", ""))
    floor_ok = hold.get("clears_90_mmhg_nadir_floor")
    if floor_ok is not None:
        shared.append(pill(
            "Clears the 90 mmHg floor" if floor_ok
            else "Below the 90 mmHg floor",
            "ok" if floor_ok else "fail"))
    st.markdown("".join(shared), unsafe_allow_html=True)
    st.caption("Calibrated, gain 0 · shared by every policy; the pre-anchor "
               "model carries no UF→SBP effect.")

    hold_left = hold.get("fluid_left_behind_l")
    has_fluid = any(
        _safe_float(s.get("fluid_left_behind_l")) is not None
        for s in scenarios)
    rows = []
    for scenario in scenarios:
        sketch_row = sketch.get(scenario.get("policy")) or {}
        left = scenario.get("fluid_left_behind_l")
        delta = None
        if has_fluid:
            left_v = _safe_float(left)
            hold_v = _safe_float(hold_left)
            if left_v is not None and hold_v is not None:
                delta = left_v - hold_v
        row = {
            "UF policy": scenario.get("label", ""),
            "Mean UF · +60 min (L/h)": scenario.get("mean_uf_l_h"),
        }
        if has_fluid:
            row["Fluid left (L)"] = left
            row["Δ fluid left vs hold (L)"] = delta
        row["Expected SBP +60 (mmHg)"] = sketch_row.get("projected_nadir_mmhg")
        row["Δ SBP vs hold (mmHg)"] = sketch_row.get(
            "expected_nadir_stabilization_vs_hold_mmhg")
        rows.append(row)
    table = pd.DataFrame(rows)
    numeric = list(table.columns[1:])
    table[numeric] = table[numeric].apply(pd.to_numeric, errors="coerce")
    config = {
        "Mean UF · +60 min (L/h)": st.column_config.NumberColumn(
            format="%.2f"),
        "Expected SBP +60 (mmHg)": st.column_config.NumberColumn(
            format="%.1f", help="Uncalibrated mechanism sketch, not a "
                                "validated treatment effect."),
        "Δ SBP vs hold (mmHg)": st.column_config.NumberColumn(
            format="%+.1f", help="Sketch gain against holding the current UF."),
    }
    if has_fluid:
        config.update({
            "Fluid left (L)": st.column_config.NumberColumn(format="%.2f"),
            "Δ fluid left vs hold (L)": st.column_config.NumberColumn(
                format="%+.2f"),
        })
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config=config)
    if table["Expected SBP +60 (mmHg)"].notna().any():
        st.caption("Expected SBP is the retired twin's mechanism sketch "
                   "(G7 failed): a support layer, not a validated treatment "
                   "effect. Fluid arithmetic is exact; neither is a "
                   "prescription.")
    elif has_fluid:
        st.caption("Fluid arithmetic only; not a prescription or a validated "
                   "treatment effect.")
    else:
        st.caption("This session has no recorded UF goal, so the "
                   "fluid-bank arithmetic is unavailable. The UF schedule "
                   "still differs by policy.")


def render() -> None:
    demo = _demo()
    cases = demo["cases"]
    by_id = {c["id"]: c for c in cases}
    by_name = {c["name"]: c for c in cases}
    names = [c["name"] for c in cases]
    display = {name: name.replace("_", " ").title() for name in names}
    options = [display[name] for name in names]
    default = by_name.get("taper", cases[0])
    st.session_state.setdefault("case_id", default["id"])
    st.session_state.setdefault("case_select", display[default["name"]])
    if st.session_state["case_id"] not in by_id:
        st.session_state["case_id"] = default["id"]
        st.session_state["case_select"] = display[default["name"]]

    # Another view can set case_id without touching the widget-backed label.
    expected = display[by_id[st.session_state["case_id"]]["name"]]
    if st.session_state.get("case_select") != expected:
        st.session_state["case_select"] = expected

    with st.sidebar:
        st.markdown("### Case lab controls")
        st.selectbox("All curated cases", options, key="case_select",
                     on_change=_sync_from_select)
        role_label = st.selectbox("Review role", list(ROLE_CODES), key="role_label")
        show_ill = st.toggle(
            "Show mechanism sketch",
            value=False,
            key="show_ill",
            help="Dashed fan: uncalibrated mechanism sketch, not a measured effect.")
        st.caption("205,482 QC-eligible HEMOBP sessions · fold 2 untouched · "
                   "Spanish-frame AUROC 0.474 (transport failed).")

    case = by_id[st.session_state["case_id"]]
    stale = bool(case.get("synthetic_demo")) or (
        float(case.get("cuff_age_min") or 0) > 35)
    hold = (case.get("calibrated", {}).get("scenarios") or [{}])[0]

    st.markdown(theme.page_head(
        "Case lab · frozen v4 evidence",
        "See the pressure falling. Show the trade-off.",
        "A calibrated forecast, exact fluid arithmetic, and a review "
        "pathway — not a prescription engine.",
        pills=[("205,482 sessions", "info"), ("Fold 2 untouched", "ok"),
               ("Display-only", "warn")],
    ), unsafe_allow_html=True)

    picker, showcase = st.columns([3.2, 1], vertical_alignment="bottom")
    with picker:
        st.markdown('<div class="ht-kicker">Pick a case</div>',
                    unsafe_allow_html=True)
    with showcase:
        with st.popover("Showcase case", use_container_width=True):
            for name, label, desc in EXTRA_CASES:
                item = by_name[name]
                st.button(
                    f"{label} · {item['sbp_anchor']:.0f}→{item['base_nadir']:.0f}",
                    key=f"pick_{name}", width="stretch",
                    on_click=_pick, args=(item["id"], name))
                st.caption(desc)

    with st.container(key="case_buttons"):
        cols = st.columns(5)
        for col, (name, label, _desc) in zip(cols, ARCHETYPES):
            item = by_name[name]
            with col:
                st.button(
                    f"{label} · {item['sbp_anchor']:.0f}→{item['base_nadir']:.0f}",
                    key=f"pick_{name}", width="stretch",
                    on_click=_pick, args=(item["id"], name))

    st.markdown(theme.section(
        "Selected case",
        f"{case['name'].replace('_', ' ').title()} · {case['session_id']}",
        f"Anchor {case['t_anchor']:.0f} min · {_regime_label(case['regime'])} · "
        f"{'synthetic guardrail' if case.get('synthetic_demo') else 'real HEMOBP session'}."),
        unsafe_allow_html=True)
    chips = []
    if case.get("synthetic_demo"):
        chips.append(pill("Synthetic demo — not a patient record", "warn"))
    if stale:
        chips.append(pill(f"Cuff age {case.get('cuff_age_min', 0):.0f} min", "fail"))
    if chips:
        st.markdown('<div class="ht-pills">' + "".join(chips) + "</div>",
                    unsafe_allow_html=True)

    st.markdown(metric_row([
        {"label": "SBP at anchor", "value": _fmt(case["sbp_anchor"], 0),
         "sub": "observed at the anchor", "tone": ""},
        {"label": "Calibrated +60 min",
         "value": "—" if stale else _fmt(case["base_nadir"], 1),
         "sub": ("withheld: no current BP" if stale
                 else "fair pre-anchor forecast · gain 0"),
         "tone": "cyan"},
        {"label": "Observed nadir", "value": _fmt(case.get("observed_nadir"), 0),
         "sub": "ground truth · not a model input", "tone": "amber"},
    ]), unsafe_allow_html=True)

    view = _view_case(case)
    cuffs = view.get("cuffs") or []
    anchor_idx = _anchor_index(cuffs)
    reset_n = int(st.session_state.get("fan_reset", 0))
    chart_key = f"fan_{case['id']}_{reset_n}"
    prior_idx = _selection_index(st.session_state.get(chart_key), cuffs)
    selected_idx = anchor_idx if prior_idx is None else prior_idx
    selected = cuffs[selected_idx] if selected_idx is not None else None

    left, right = st.columns([1.55, 1.0], gap="large")
    with left:
        selected_rel = None
        if selected is not None and selected_idx != anchor_idx:
            selected_rel = float(selected.get("rel") or 0.0)
        event = st.plotly_chart(
            charts.fan_figure(view, show_ill, show_projection=not stale,
                              selected_rel=selected_rel),
            width="stretch", config={"displayModeBar": False},
            key=chart_key, on_select="rerun", selection_mode="points")
        clicked_idx = _selection_index(event, cuffs)
        if clicked_idx is not None:
            selected_idx = clicked_idx
            selected = cuffs[clicked_idx]
        if show_ill:
            st.markdown(theme.callout(
                "Dashed lines are an uncalibrated mechanism sketch at unit "
                "gain. Do not read them as treatment effects.", "warn"),
                unsafe_allow_html=True)
        if cuffs:
            inspect_rel = (float(selected.get("rel") or 0.0)
                           if selected is not None and selected_idx != anchor_idx
                           else None)
            if inspect_rel is None:
                st.caption("Click any cuff point to inspect its SBP, DBP, UF, "
                           "and twin state at that minute.")
            else:
                cap_col, reset_col = st.columns([3.1, 1.6])
                cap_col.caption(
                    f"Inspecting the cuff at {inspect_rel:+.0f} min. The "
                    "recorded values and twin state are in the right panel.")
                if reset_col.button("Back to anchor", key=f"reset_{case['id']}"):
                    st.session_state["fan_reset"] = reset_n + 1
                    st.rerun()
        else:
            st.caption("No cuff points are available to inspect for this "
                       "synthetic guardrail case.")
    with right:
        state = case.get("state") or {}
        twin = (selected or {}).get("twin") or {}
        is_anchor = selected is None or selected_idx == anchor_idx
        if selected is None or is_anchor:
            title = "Twin at the anchor"
        else:
            title = f"Twin · {float(selected['rel']):+.0f} min"
        st.markdown(theme.card(
            f'<div class="ht-kicker">{e(title)}</div>'
            '<p style="margin-top:6px">Recorded vitals for this minute plus '
            'the latent Starling–baroreflex state from the UF stream.</p>',
            tight=True), unsafe_allow_html=True)

        if selected is None:
            sbp_v = None if stale else case.get("sbp_anchor")
            dbp_v = (case.get("features") or {}).get("dbp_now")
            uf_v = case.get("uf_rate_lh")
            cum_v = case.get("uf_removed_l")
            d_v, r_v = state.get("D0"), state.get("R0")
            c_v, oh_v = state.get("C0"), state.get("OH0")
        else:
            sbp_v, dbp_v = selected.get("sbp"), selected.get("dbp")
            uf_v, cum_v = selected.get("uf_lh"), selected.get("cum_uf_l")
            d_v, r_v = twin.get("D"), twin.get("R")
            c_v, oh_v = twin.get("C"), twin.get("OH")

        c1, c2 = st.columns(2)
        c1.metric("SBP · mmHg", _fmt(sbp_v, 0))
        c2.metric("DBP · mmHg", _fmt(dbp_v, 0))
        c1.metric("UF rate · L/h", _fmt(uf_v, 2))
        c2.metric("UF removed · L", _fmt(cum_v, 2))
        if selected is not None and not is_anchor:
            projection = selected.get("projection_sbp")
            if projection is not None and selected.get("phase") == "after":
                st.caption(
                    f"Calibrated projection at this minute: {float(projection):.1f} "
                    f"mmHg · observed {float(selected['sbp']):.0f} mmHg.")
            elif selected.get("phase") == "before":
                st.caption("Pre-anchor cuff: the calibrated forecast starts at "
                           "the anchor.")
        st.markdown("**Latent twin state**")
        t1, t2 = st.columns(2)
        t1.metric("Plasma deficit · L", _fmt(d_v, 2))
        t2.metric("Refill rate · L/h", _fmt(r_v, 2))
        t1.metric("Baro exhaustion · %", _fmt(
            100.0 * float(c_v) if c_v is not None else None, 1))
        t2.metric("Overhydration · L", _fmt(oh_v, 2))
        st.caption("Latent values are model states, not measurements.")

    with st.expander("How to read this chart", expanded=False):
        st.markdown(
            "- **Solid teal** — validated pre-anchor forecast at calibrated gain 0.\n"
            "- **Shaded band** — 90% nadir interval, widened along the path for display; not a per-minute confidence band.\n"
            "- **Amber diamonds** — observed cuffs after the anchor; hover shows the calibrated value at that minute.\n"
            "- **Click a cuff** — SBP, DBP, UF and the twin state at that minute.\n"
            "- **Dashed fan** — mechanism sketch; hidden by default.")
    note, note_tone = CASE_NOTES.get(case["name"], ("", ""))
    if note:
        st.markdown(theme.callout(note, note_tone), unsafe_allow_html=True)

    st.markdown(theme.section(
        "Fluid arithmetic", "What each policy changes",
        "The calibrated +60 min is policy-independent; the expected SBP "
        "column is an uncalibrated sketch; the fluid arithmetic is exact."),
        unsafe_allow_html=True)

    _fluid_table(case, stale)

    st.markdown(theme.section(
        "Decision support", "What the unit's protocol says next",
        "Measured criteria set the review state; the forecast never gates it."),
        unsafe_allow_html=True)
    _protocol_panel(case, ROLE_CODES[role_label], stale)

    with st.expander("4-block causal state vector · anchor only", expanded=False):
        _state_inspector(case)
    with st.expander("TreeSHAP attribution — fair pre-anchor model", expanded=False):
        _shap_panel(case)

    cta1, cta2, _ = st.columns([1, 1, 2])
    with cta1:
        if st.button("Open the evidence →", key="open_evidence", type="primary",
                     width="stretch"):
            st.switch_page("views/evidence_page.py")
    with cta2:
        next_name = "taper" if case["name"] != "taper" else "pause"
        next_case = by_name[next_name]
        if st.button(f"Next: {next_name.replace('_', ' ')} →", key="next_case",
                     width="stretch"):
            _pick(next_case["id"], next_name)
            st.rerun()
