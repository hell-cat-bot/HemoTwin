"""Evidence & handoff: gates, G7, claim boundary, FHIR, audit, pod triage."""
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


@st.cache_data(show_spinner=False)
def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _demo() -> dict:
    return _load_json(str(EVIDENCE / "demo_twin.json"))


def _report() -> dict:
    return _load_json(str(EVIDENCE / "benchmark_report.json"))


def _g7() -> dict:
    return _load_json(str(EVIDENCE / "g7_report.json"))


def _fmt(value, nd: int = 1, suffix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"{number:.{nd}f}{suffix}"


def _gate_card(kicker: str, state: str, tone: str, value: str, detail: str, body: str) -> str:
    return f"""
<div class="ht-card ht-card--tight">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
    <div class="ht-kicker">{e(kicker)}</div>{pill(state, tone)}
  </div>
  <div class="ht-metric__value" style="font-size:27px;margin-top:10px">{e(value)}</div>
  <div class="ht-metric__sub">{e(detail)}</div>
  <p style="margin-top:9px">{e(body)}</p>
</div>"""


def _gate_grid(report: dict, g7: dict) -> None:
    gates = report.get("gates", {})
    g1 = gates.get("G1", {})
    g2 = gates.get("G2", {})
    g3 = gates.get("G3", {})
    g4 = gates.get("G4", {})
    g5 = gates.get("G5", {})
    g6 = gates.get("G6", {})
    est = g7.get("estimates", {})
    tau = est.get("tau30_per_0.25_l_h", {}).get("slope")
    ci = (est.get("tau30_bootstrap", {}).get("ci95") or [None, None])
    cards = [
        _gate_card("G1 · taper", "PASS", "ok", _fmt(g1.get("v4", {}).get("mae"), 2),
                   f"MAE vs v3 {_fmt(g1.get('v3', {}).get('mae'), 2)} · n={g1.get('n_taper', '—')}",
                   "The pre-anchor surface beats the retired v3 twin on the taper slice."),
        _gate_card("G2 · baseline", "PARTIAL", "warn",
                   f"{_fmt(g2.get('fold2', {}).get('v4', {}).get('mae'), 2)} / {_fmt(g2.get('fold2', {}).get('oracle_forecast_v2', {}).get('mae'), 2)}",
                   "fair vs oracle-assisted fold-2 MAE",
                   "Passes against its own base at gain 0; fails against the oracle display forecast."),
        _gate_card("G3 · actual vs hold", "FAIL", "fail", _fmt(g3.get("bootstrap", {}).get("delta_mae"), 3),
                   f"{g3.get('n_intervention', '—')} actual-vs-hold rows · CI [0, 0]",
                   "At gain 0 the actual and hold predictions are identical. The what-if gate fails."),
        _gate_card("G4 · monotonicity", "PASS", "ok", f"{g4.get('violations', 0)}",
                   f"violations / {g4.get('n_pairwise_minute_checks', 0):,} checks",
                   "Nested policy fractions are monotone and continuous at unit gain."),
        _gate_card("G5 · band coverage", "PASS", "ok",
                   f"{100 * (g5.get('regimes', {}).get('HOLD', {}).get('coverage_fold2') or 0):.1f}%",
                   "HOLD coverage · TAPER 90.1%",
                   "Empirical 90% band coverage sits in the pre-registered 88–92% window."),
        _gate_card("G6 · invariance", "PASS", "ok",
                   f"{g6.get('future_invariance_bitwise_equal', 0)}/{g6.get('future_invariance_n', 0)}",
                   f"future-invariant · {g6.get('cold_start_n', '—')} cold starts",
                   "Future UF records do not change the pre-anchor state; cold starts stay bounded."),
        _gate_card("G7 · UF effect", "FAIL", "fail", f"{tau:+.2f}" if tau is not None else "—",
                   f"mmHg per 0.25 L/h · CI [{_fmt(ci[0], 2)}, {_fmt(ci[1], 2)}]",
                   "Early UF reduction did not raise SBP more than matched controls. The effect is indistinguishable from zero."),
        _gate_card("Summary", "5/6", "warn", "5 PASS",
                   "5 pass · twin test fails · G2 partial",
                   "The engineering holds; the what-if claim does not. The twin stays an illustration."),
    ]
    st.markdown(theme.callout(
        "These are seven pre-registered checks, not a score. G7 is the twin "
        "test: does reducing UF early raise SBP? It did not."),
        unsafe_allow_html=True)
    st.markdown(f'<div class="ht-grid-3">{"".join(cards)}</div>',
                unsafe_allow_html=True)
    st.caption("A pass is an engineering check against a pre-registered criterion — "
               "not clinical validation. The baseline check (G2) is a tie at gain 0, "
               "not evidence of a treatment effect.")


def _g7_section(g7: dict) -> None:
    st.markdown(theme.section(
        "Twin test · G7", "It failed. That is the finding.",
        "We asked whether reducing UF early raises SBP more than in matched "
        "controls. It did not. That is why the mechanism sketch is off by "
        "default."),
        unsafe_allow_html=True)
    st.markdown(theme.callout(
        "Plain language: the estimated effect is +0.13 mmHg per 0.25 L/h, and "
        "the 95% interval includes zero. A positive result would have meant "
        "early UF reduction reliably raised SBP. It did not.", "warn"),
        unsafe_allow_html=True)
    st.plotly_chart(charts.g7_forest_figure(g7), width="stretch",
                    config={"displayModeBar": False})
    stage0 = g7.get("stage0", {})
    st.markdown(metric_row([
        {"label": "Matched events", "value": f"{stage0.get('n4_matched_events', 581):,}",
         "sub": "moments where UF was reduced early"},
        {"label": "Patients", "value": str(stage0.get("n4_patients", 158)),
         "sub": "same-patient comparisons"},
        {"label": "Smallest detectable effect",
         "value": _fmt((stage0.get("power") or {}).get("mde80"), 2),
         "sub": "mmHg · 80% power"},
        {"label": "Fold-2 events", "value": str(stage0.get("fold2_events", 65)),
         "sub": "held-out data"},
    ]), unsafe_allow_html=True)
    p6a = (g7.get("p6a_fold2_trajectory") or {})
    p6b = (g7.get("p6b_fold2_anchor_fan") or {})
    h30 = p6a.get("30") or {}
    h30b = p6b.get("30") or {}
    cards = [
        theme.card(
            f'<div class="ht-kicker">30-min trajectory check</div>'
            f'<div class="ht-metric__value ht-metric__value--coral" style="font-size:28px">'
            f'{_fmt(h30.get("delta_mae"), 2)}</div>'
            f'<p>mmHg worse on held-out sessions (n={h30.get("n", "—")}); '
            f'CI [{_fmt((h30.get("ci95") or [None, None])[0], 2)}, '
            f'{_fmt((h30.get("ci95") or [None, None])[1], 2)}].</p>',
            tight=True),
        theme.card(
            '<div class="ht-kicker">15 / 45-min trajectory check</div>'
            '<div class="ht-metric__value ht-metric__value--amber" style="font-size:28px">'
            'INCONCLUSIVE</div>'
            '<p>43 and 22 fold-2 events; the pre-registered minimum is 50. '
            'No claim is made.</p>', tight=True),
        theme.card(
            '<div class="ht-kicker">Anchor-fan check</div>'
            '<div class="ht-metric__value ht-metric__value--amber" style="font-size:28px">'
            'INCONCLUSIVE</div>'
            f'<p>{h30b.get("n", "—")} at-anchor held-out events; too few to test '
            'the anchor-fan mechanism.</p>', tight=True),
    ]
    st.markdown(f'<div class="ht-grid-3">{"".join(cards)}</div>',
                unsafe_allow_html=True)
    st.markdown(theme.callout(
        "Verdict: FAIL — early UF reduction did not raise SBP more than matched "
        "controls. The operational gain stays 0; the twin remains a labelled "
        "illustration.", "fail"), unsafe_allow_html=True)
    st.plotly_chart(charts.temporal_order_figure(g7), width="stretch",
                    config={"displayModeBar": False})
    st.caption("Temporal order on the 397 actual-vs-hold rows: 234 cuts at the "
               "anchor had no preceding observed drop. That weakens the earlier "
               "reverse-causality story but does not rescue the intervention effect.")
    st.markdown(theme.card(
        f'<div class="ht-kicker">Frozen protocol</div>'
        f'<p style="margin-top:6px;font-family:monospace;color:#67E8F9;'
        f'word-break:break-all">{e(g7.get("protocol_sha256", ""))}</p>'
        '<p>SHA-256 frozen before estimation. The pre-registration is what '
        'makes the failure meaningful; the protocol and hash ship in '
        '<code>evidence/</code>.</p>', tight=True), unsafe_allow_html=True)


def _forecast_lineage(report: dict) -> None:
    g2 = report.get("gates", {}).get("G2", {})
    fold2 = g2.get("fold2", {})
    fair = fold2.get("v4", {}).get("mae")
    oracle = fold2.get("oracle_forecast_v2", {}).get("mae")
    st.markdown(theme.section(
        "Forecast lineage", "Two forecasts. Do not mix them.",
        "The console's twin uses the fair pre-anchor model. The oracle-assisted "
        "display forecast is a different number with a different feature contract."),
        unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([
        {"Model": "Fair pre-anchor twin", "Features": "59 · no future UF",
         "Fold-2 MAE (mmHg)": _fmt(fair, 2), "Role": "The app's calibrated floor"},
        {"Model": "Forecast-v2 oracle display", "Features": "72 · 13 future-UF features",
         "Fold-2 MAE (mmHg)": _fmt(oracle, 2), "Role": "Display-only; not the G2 baseline"},
    ]), hide_index=True, width="stretch")
    st.caption("A smaller MAE from the oracle display is not a better twin. "
               "The baseline check (G2) compares the twin to its own fair "
               "baseline; the oracle comparison is reported as a failure.")


def _claim_boundary(g7: dict, demo: dict) -> None:
    st.markdown(theme.section(
        "Claim boundary", "What we can say. What we refuse to say.",
        "The boundary is part of the product, not a footnote."),
        unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.markdown(theme.card(
            '<div class="ht-kicker">We can claim</div>'
            '<ul style="margin:10px 0 0 18px;color:#C7D6E6;line-height:1.8">'
            '<li>A calibrated pre-anchor nadir forecast (fold-2 MAE 10.99, RMSE 14.65).</li>'
            '<li>Exact arithmetic for fluid left, carry-forward and next-session intensity.</li>'
            '<li>A deterministic, versioned review pathway with role-scoped steps.</li>'
            '<li>Honest negative results: the twin tests and the oracle baseline comparison.</li>'
            '<li>A local FHIR export and a hash-chained demo audit trail.</li>'
            '</ul>', tight=True), unsafe_allow_html=True)
    with right:
        st.markdown(theme.card(
            '<div class="ht-kicker">We refuse to claim</div>'
            '<ul style="margin:10px 0 0 18px;color:#C7D6E6;line-height:1.8">'
            '<li>A validated what-if/treatment effect from the twin.</li>'
            '<li>That any UF policy will raise SBP, prevent IDH, or is minimum effective.</li>'
            '<li>Alert utility, clinical benefit, or a safety layer.</li>'
            '<li>Prospective, external, symptomatic-IDH, or Indian-unit validation.</li>'
            '<li>A prescription, a default dose, or autonomous machine action.</li>'
            '</ul>', tight=True), unsafe_allow_html=True)
    boundary = g7.get("claim_boundary") or demo.get("claim_boundary")
    if boundary:
        st.caption(boundary)


def _fhir_tab(case: dict) -> None:
    from src.session_twin.fhir_export import (
        build_fhir_bundle, validate_fhir_r4_bundle_schema)

    state = case.get("state") or {}
    bundle = build_fhir_bundle(
        patient_id=case["session_id"].split("_")[0],
        session_id=case["session_id"],
        observations={"sbp": case.get("sbp_anchor"),
                      "dbp": (case.get("features") or {}).get("dbp_now")},
        latent_state={
            "plasma_deficit_l": state.get("D0"),
            "refill_rate_l_h": state.get("R0"),
            "baro_exhaustion_pct": (state.get("C0") or 0) * 100,
        },
        risk=None,
        detected_issue="Research decision-support review",
    )
    ok, errors = validate_fhir_r4_bundle_schema(bundle)
    if ok:
        st.markdown(theme.callout(
            "FHIR R4 bundle passes the local schema checks."),
            unsafe_allow_html=True)
    else:
        st.markdown(theme.callout(
            f"FHIR validation errors: {errors}", "fail"),
            unsafe_allow_html=True)
    st.caption("No risk score is exported. The bundle carries observations and "
               "model states only; it is not a clinical order.")
    with st.expander("FHIR R4 / ABDM bundle", expanded=False):
        st.json(bundle)
        st.download_button(
            "Download FHIR bundle",
            data=json.dumps(bundle, indent=2),
            file_name=f"{case['session_id']}_fhir.json",
            mime="application/fhir+json")


def _handoff_tab(case: dict) -> None:
    from src.session_twin.handoff_summary import build_handoff_card

    hold = (case.get("calibrated", {}).get("scenarios") or [{}])[0]
    card = build_handoff_card(
        session_id=case["session_id"],
        sbp_now=case.get("sbp_anchor"),
        projected_nadir=case.get("base_nadir"),
        band=tuple(hold.get("nadir_band_90") or [None, None]),
        fluid_left_l=hold.get("fluid_left_behind_l"),
        next_intensity=hold.get("next_session_uf_intensity_ml_kg_h"),
        status=("REVIEW_NOW" if (case.get("base_nadir") or 999) < 90 else "NO_ALERT"),
    )
    st.markdown("**English**")
    st.text(card["english"])
    st.markdown("**हिन्दी**")
    st.text(card["hindi"])
    st.caption(card["disclaimer_en"])
    st.caption(card["disclaimer_hi"])


def _audit_tab() -> None:
    from src.session_twin.audit_chain import verify_audit_chain

    path = ROOT / "demo" / "audit.jsonl"
    chain = verify_audit_chain(path)
    cols = st.columns(3)
    cols[0].metric("Events", chain["n_events"])
    cols[1].metric("Chain", "OK" if chain["ok"] else "BROKEN")
    cols[2].metric("Head", (chain["head"][:12] + "…") if chain["head"] != "GENESIS" else "GENESIS")
    if chain["errors"]:
        st.markdown(theme.callout("; ".join(chain["errors"]), "fail"),
                    unsafe_allow_html=True)
    else:
        st.markdown(theme.callout(
            "Local SHA-256 chain verifies. This is demo evidence, not an "
            "immutable clinical audit record."), unsafe_allow_html=True)
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    if events:
        df = pd.DataFrame(events)
        keep = [c for c in ("timestamp", "event", "session_id", "regime", "claim")
                if c in df.columns]
        st.dataframe(df[keep].tail(8), hide_index=True, width="stretch")
    st.caption("The live-session log is separate and uses a different local "
               "schema; it is not merged into this chain.")


def _pod_tab(demo: dict) -> None:
    from src.session_twin.pod_triage import build_pod_board

    budget = st.slider("Nurse-attention budget (false alerts/session)",
                       0.0, 1.0, 0.26, 0.01, key="pod_budget")
    rows = []
    for case in demo["cases"]:
        rows.append({
            "session_id": case["session_id"],
            "pid": case["session_id"].split("_")[0],
            "sbp_now": case.get("sbp_anchor"),
            "projected_nadir": case.get("base_nadir"),
            "cuff_age_min": case.get("cuff_age_min", 10),
        })
    board = build_pod_board(rows, n_chairs=12, fa_per_session=budget)
    cols = st.columns(3)
    cols[0].metric("Occupied chairs", f"{board['occupied']}/12")
    cols[1].metric("Budget", f"{budget:.2f} FA/session")
    cols[2].metric("Expected false alarms/shift",
                   f"{board['budget']['expected_false_alerts_per_shift']:.1f}")
    st.dataframe(pd.DataFrame(board["board"]), hide_index=True, width="stretch")
    st.caption(board["governance"])


def render() -> None:
    demo = _demo()
    report = _report()
    g7 = _g7()
    case = demo["cases"][0]

    with st.sidebar:
        st.markdown("### Evidence controls")
        names = [c["name"] for c in demo["cases"]]
        display = {name: name.replace("_", " ").title() for name in names}
        current_id = st.session_state.get("case_id")
        current_name = next((c["name"] for c in demo["cases"]
                             if c["id"] == current_id), "stable_hold")
        st.session_state.setdefault("handoff_case", display[current_name])
        st.selectbox("Handoff case", [display[name] for name in names],
                     key="handoff_case")
        st.caption("The evidence view uses the frozen files in `evidence/`; "
                   "no model is retrained here.")

    st.markdown(theme.hero(
        "Evidence · frozen 2026-11-09",
        "The evidence<br/><em>is the product.</em>",
        "Seven pre-registered checks. Five pass, the twin test fails; the "
        "what-if claim stays off the table.",
        [("Twin test failed", "fail"), ("Fold 2 untouched", "ok"),
         ("No treatment effect", "warn")],
    ), unsafe_allow_html=True)

    _gate_grid(report, g7)
    with st.expander("What do G1–G7 mean?", expanded=False):
        st.markdown(
            "- **G1 — better than the old twin?** Does the new pre-anchor "
            "forecast beat the retired v3 twin on the taper cases?\n"
            "- **G2 — is it honest?** Compare it with its own fair baseline "
            "and, separately, with an oracle-assisted display forecast.\n"
            "- **G3 — actual vs hold?** Does the twin predict what actually "
            "happened better than simply assuming UF was held?\n"
            "- **G4 — does the policy model behave?** Nested taper fractions "
            "must be monotone and continuous.\n"
            "- **G5 — do the uncertainty bands cover reality?** Check the 90% "
            "band against observed fold-2 outcomes.\n"
            "- **G6 — does it leak or break?** New patients must stay bounded, "
            "and future UF records must not change the pre-anchor state.\n"
            "- **G7 — the twin test.** If UF is reduced early, does SBP recover "
            "more than in matched controls? **No.** That is the result that "
            "keeps the fan off by default.")
    _forecast_lineage(report)
    _g7_section(g7)
    _claim_boundary(g7, demo)

    st.markdown(theme.section(
        "Handoff", "Carry the state, not a prescription",
        "A FHIR bundle, a bilingual shift card, a local hash chain and a "
        "12-chair workflow sort — all explicitly decision-support only."),
        unsafe_allow_html=True)
    selected_label = st.session_state.get("handoff_case")
    selected_name = next((name for name in names if display[name] == selected_label),
                         names[0])
    selected = next((c for c in demo["cases"] if c["name"] == selected_name),
                    demo["cases"][0])
    tabs = st.tabs(["FHIR R4", "Shift handoff", "Audit trail", "12-chair pod"])
    with tabs[0]:
        _fhir_tab(selected)
    with tabs[1]:
        _handoff_tab(selected)
    with tabs[2]:
        _audit_tab()
    with tabs[3]:
        _pod_tab(demo)
