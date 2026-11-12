"""HemoTwin session-state twin: protocol review and fluid accounting.

Real manual/CSV entry, session-state mirror, shadow risk display, deterministic
protocol pathway, pure fluid arithmetic, and append-only local demo evidence.
No clinical-utility or treatment-effect claim.

The digital-twin surface (W3) is display-only: observational patient history
from the frozen v3 table, the conditional session expectation under the
observed UF trajectory, and the substrate self-measurement. The twin informs
and records; it never gates the protocol pathway and never prescribes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from math import isfinite
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import forecast_serve as FS  # noqa: E402
from src import manual_console as C  # noqa: E402
from src.session_twin.audit import append_event  # noqa: E402
from src.session_twin.engine import recommend  # noqa: E402
from src.session_twin.fluid import calculate_fluid  # noqa: E402
from src.session_twin.protocol import ProtocolError, load_protocol  # noqa: E402
from app.ui import theme as ui_theme  # noqa: E402

# Local demo evidence target. Overridable so automated page tests (and other
# non-demo runs) can append to a scratch file instead of the demo log; an unset
# or empty variable keeps the original demo path.
AUDIT_PATH = Path(os.environ.get("HEMOTWIN_AUDIT_PATH")
                  or ROOT / "demo" / "task01r_audit.jsonl")
SYMPTOMS = ["Dizziness", "Nausea", "Vomiting", "Cramping", "Yawning",
            "Restlessness", "Pallor", "Sweating", "Blurred vision",
            "Near-syncope", "Other"]
SBP_RANGE = (40.0, 250.0)
DBP_RANGE = (20.0, 150.0)

st.markdown(ui_theme.page_head(
    "Live session",
    "Enter a real session",
    "Mirror the state at the chair, validate the cuff, walk the unit's review "
    "pathway, and compute the fluid arithmetic. No prescription is produced.",
    pills=[("Research prototype", "warn"),
           ("Display-only · no machine action", "sage")]),
    unsafe_allow_html=True)

try:
    PROTOCOL = load_protocol()
except ProtocolError as exc:
    st.error(f"Protocol configuration error: {exc}")
    st.stop()

if "cuffs" not in st.session_state:
    st.session_state.cuffs = []
if "recommendation" not in st.session_state:
    st.session_state.recommendation = None
if "risk_result" not in st.session_state:
    st.session_state.risk_result = None
if "assessment_notes" not in st.session_state:
    st.session_state.assessment_notes = None
if "forecast_result" not in st.session_state:
    st.session_state.forecast_result = None
if "forecast_source" not in st.session_state:
    st.session_state.forecast_source = "manual"

PLAYBACK = ROOT / "demo" / "fold0_playback.json"
PB = json.loads(PLAYBACK.read_text()) if PLAYBACK.exists() else None


def _bounded(value, limits: tuple[float, float]) -> float | None:
    """Return a finite float within the documented range, else None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    low, high = limits
    return number if isfinite(number) and low <= number <= high else None


def _latest_raw_cuff(cuffs: list[dict]) -> dict | None:
    """Latest cuff by elapsed time, falling back to entry order."""
    latest = None
    latest_t = None
    for cuff in cuffs:
        try:
            t = float(cuff.get("t"))
        except (TypeError, ValueError):
            continue
        if not isfinite(t) or t < 0:
            continue
        if latest_t is None or t >= latest_t:
            latest, latest_t = cuff, t
    if latest is None and cuffs:
        return cuffs[-1]
    return latest


def _load_playback():
    s = PB["sessions"][int(st.session_state.get("pb_select", 0))]
    st.session_state["sid"] = s["start"]["session_id"]
    st.session_state["pre"] = s["start"]["pre_weight"]
    st.session_state["dry"] = s["start"]["dry_weight"]
    st.session_state["age"] = int(s["start"]["age"] or 60)
    st.session_state["sex"] = s["start"]["sex"]
    st.session_state["dm"] = int(s["start"]["dm"] or 0)
    st.session_state["vintage"] = float(s["start"]["vintage_years"] or 0.0)
    st.session_state["month"] = int(s["start"]["month"] or 1)
    st.session_state.cuffs = s["cuffs"]
    st.session_state.recommendation = None
    st.session_state.risk_result = None
    st.session_state.assessment_notes = None
    # The forecast card serves retrospective playback sessions from the frozen
    # fold-0 context; any later manual edit of the cuffs falls back to the
    # limited-history manual mode.
    st.session_state.forecast_source = "playback"
    st.session_state.forecast_result = None


model_dir, _threshold = C.model_paths()
# Derived from the selected artifact prefix, never hard-coded, so a smoke or
# fallback model is reported honestly instead of inheriting the full model tag.
MODEL_VERSION = f"task02:{model_dir.parent.name}/{model_dir.name}"
with st.sidebar:
    st.header("Session start")
    sid = st.text_input("Pseudonymous patient/session ID", "manual_demo", key="sid")
    pre = st.number_input("Pre-weight (kg)", 20.0, 300.0, 68.0, 0.1, key="pre")
    dry = st.number_input("Dry/target weight (kg)", 20.0, 200.0, 65.0, 0.1, key="dry")
    uf_goal = st.number_input("Current-session UF goal (L)", 0.0, 20.0, 3.0, 0.1)
    next_rx = st.number_input("Next-session baseline removal (L)", 0.0, 20.0, 2.0, 0.1)
    next_hours = st.number_input("Next-session duration (hours)", 0.5, 8.0, 4.0, 0.5)
    age = st.number_input("Age", 18, 120, 60, key="age")
    sex = st.selectbox("Sex", ["M", "F"], key="sex")
    dm = st.selectbox("Diabetes", [0, 1], index=0, key="dm")
    vintage = st.number_input("Dialysis vintage (years)", 0.0, 60.0, 3.0, 0.5, key="vintage")
    month = st.selectbox("Month", list(range(1, 13)), index=2, key="month")
    role = st.selectbox("Role label (simulation only)", ["RN", "TECH", "NEPHROLOGIST"], key="role")
    st.caption("Role is recorded as a label; no authentication or authorization is implemented.")
    current_clock = st.number_input(
        "Current session clock (min; 0 = latest cuff)", 0, 1440, 0, 1,
        key="current_clock")
    st.caption("When set above 0, the latest cuff is checked against this clock; "
               "a cuff older than 60 minutes is stale and is not shown as current.")
    st.caption(f"Shadow model directory: {model_dir.name}")
    if not str(sid or "").strip():
        st.warning("Enter a pseudonymous session ID (no patient identifiers). "
                   "Evaluation and evidence append are blocked while it is empty.")
    if PB:
        st.selectbox("Retrospective playback session", range(len(PB["sessions"])),
                     format_func=lambda i: PB["sessions"][i]["session_id"], key="pb_select")
        st.button("Load retrospective playback", on_click=_load_playback)
    if st.button("Load example cuffs"):
        st.session_state.cuffs = [
            {"t": 0, "sbp": 140, "dbp": 80, "uf": 1.3},
            {"t": 30, "sbp": 132, "dbp": 76, "uf": 1.3},
            {"t": 60, "sbp": 124, "dbp": 72, "uf": 1.3},
            {"t": 90, "sbp": 116, "dbp": 68, "uf": 1.3},
        ]
        st.session_state.recommendation = None
        st.session_state.risk_result = None
        st.session_state.assessment_notes = None
        st.session_state.forecast_source = "manual"
        st.session_state.forecast_result = None
    if st.button("Clear cuffs"):
        st.session_state.cuffs = []
        st.session_state.recommendation = None
        st.session_state.risk_result = None
        st.session_state.assessment_notes = None
        st.session_state.forecast_source = "manual"
        st.session_state.forecast_result = None

sid_label = str(sid or "").strip()
current_time_min = float(current_clock) if current_clock > 0 else None
start = {"session_id": sid_label, "pre_weight": pre, "dry_weight": dry, "age": age,
         "sex": sex, "dm": dm, "vintage_years": vintage, "month": month}

left, right = st.columns([1.45, 1])
with left:
    st.subheader("Cuff and current assessment")
    with st.form("add_cuff", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        t = c1.number_input("Elapsed (min)", 0.0, 1440.0, 0.0, 1.0)
        sbp = c2.number_input("SBP", 40.0, 250.0, 120.0, 1.0)
        dbp = c3.number_input("DBP", 20.0, 150.0, 70.0, 1.0)
        uf = c4.number_input("UF (L/h)", 0.0, 6.0, 1.0, 0.1)
        c5, c6 = st.columns([1, 1.6])
        cum = c5.number_input("Cumulative UF (L, optional)", 0.0, 20.0, 0.0, 0.1)
        c6.caption("Optional. When absent, cumulative UF is reconstructed from "
                   "the cuff rates.")
        if st.form_submit_button("Add cuff"):
            st.session_state.cuffs.append({
                "t": t, "sbp": sbp, "dbp": dbp, "uf": uf,
                "cumulative_uf": cum if cum > 0 else None,
            })
            st.session_state.recommendation = None
            st.session_state.risk_result = None
            st.session_state.assessment_notes = None
            st.session_state.forecast_source = "manual"
            st.session_state.forecast_result = None

    uploaded = st.file_uploader("Or import cuff CSV (elapsed_min,sbp,dbp,uf_Lh[,cumulative_uf])",
                                type=["csv"])
    if uploaded is None:
        st.session_state.pop("csv_digest", None)
        st.session_state.pop("csv_error", None)
    else:
        payload = uploaded.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != st.session_state.get("csv_digest"):
            st.session_state["csv_digest"] = digest
            try:
                st.session_state.cuffs = C.parse_csv(payload.decode("utf-8"))
                st.session_state.recommendation = None
                st.session_state.risk_result = None
                st.session_state.assessment_notes = None
                st.session_state.forecast_source = "manual"
                st.session_state.forecast_result = None
                st.session_state.pop("csv_error", None)
                st.success("CSV loaded.")
            except Exception as exc:  # noqa: BLE001
                st.session_state["csv_error"] = str(exc)
        if st.session_state.get("csv_error"):
            st.error(f"CSV error: {st.session_state['csv_error']}")

    if st.session_state.cuffs:
        st.dataframe(st.session_state.cuffs, width="stretch")

    symptoms = st.multiselect("Current symptoms / observed prodrome", SYMPTOMS)
    symptom_any = bool(symptoms)
    clinician_concern = st.checkbox("Clinician concern (immediate review)")
    position = st.selectbox("Current position", ["Seated", "Supine", "Legs raised", "Other"])

    if st.button("Evaluate assessment", type="primary",
                 disabled=not st.session_state.cuffs):
        if not sid_label:
            st.error("Evaluation blocked: the pseudonymous session ID is empty. "
                     "Enter a session ID (no patient identifiers) to evaluate; "
                     "nothing was evaluated or written.")
        else:
            cuffs = list(st.session_state.cuffs)
            # The shadow score is optional. Missing/corrupt local Task 02
            # artifacts must degrade to "unavailable", not block the protocol
            # and fluid-accounting path.
            try:
                risk = C.score_session(start, cuffs, model_dir=model_dir,
                                       current_time_min=current_time_min)
            except Exception as exc:  # noqa: BLE001
                risk = {
                    "scorable": False,
                    "reason": f"Shadow model unavailable: {exc}",
                    "risk": None,
                    "threshold": None,
                    "as_of_min": None,
                    "warnings": [],
                }
            session, validation_warnings, validation_error = C.validate_session(
                start, cuffs, current_time_min=current_time_min)
            stale_error = bool(validation_error
                               and "stale" in validation_error.lower())
            if validation_error is None and session is not None:
                current_sbp = float(session["es"][-1])
                current_dbp = float(session["ed"][-1])
                sbp_drop = (float(session["es"][0] - session["es"][-1])
                            if len(session["es"]) >= 2 else None)
                t_min = float(session["as_of_min"])
                uf_rate = float(session["cuff_uf"][-1])
                uf_removed = float(session["cuff_cum"][-1])
                notes = None
                if not risk.get("scorable"):
                    notes = {"validation_error": None,
                             "risk_reason": risk.get("reason"),
                             "warnings": list(risk.get("warnings") or [])}
            else:
                # A stale cuff is not a current reading. Only a fresh,
                # individually valid raw cuff may survive a validation failure.
                latest_raw = None if stale_error else _latest_raw_cuff(cuffs)
                current_sbp = (_bounded(latest_raw.get("sbp"), SBP_RANGE)
                               if latest_raw else None)
                current_dbp = (_bounded(latest_raw.get("dbp"), DBP_RANGE)
                               if latest_raw else None)
                sbp_drop = None
                t_min = None
                uf_rate = None
                uf_removed = None
                notes = {
                    "validation_error": validation_error or "session validation failed",
                    "risk_reason": (risk.get("reason")
                                    if risk.get("reason") != validation_error
                                    else None),
                    "warnings": list(validation_warnings),
                }
            snapshot = {
                "session_id": sid_label,
                "t_min": t_min,
                "sbp": current_sbp,
                "dbp": current_dbp,
                "sbp_drop_from_session_baseline": sbp_drop,
                "symptom_any": symptom_any,
                "symptoms": symptoms,
                "clinician_concern": clinician_concern,
                "position": position,
                "uf_rate_Lh": uf_rate,
                "uf_goal_L": float(uf_goal),
                "uf_removed_L": uf_removed,
                "role": role,
                "risk_shadow": {
                    "available": bool(risk.get("scorable")),
                    "score": risk.get("risk"),
                    "threshold": risk.get("threshold"),
                    "as_of_min": risk.get("as_of_min"),
                    "model_version": MODEL_VERSION,
                },
            }
            rec = recommend(snapshot, PROTOCOL)
            st.session_state.risk_result = risk
            st.session_state.recommendation = rec
            st.session_state.assessment_notes = notes
            # Display-only conditional forecast, optional like the shadow
            # score: absent/stale model or uncomputable state degrades to an
            # "unavailable" note and never blocks the protocol pathway.
            try:
                forecast_result = FS.forecast({
                    "start": start, "cuffs": list(cuffs),
                    "source": st.session_state.get("forecast_source",
                                                   "manual"),
                })
            except Exception as exc:  # noqa: BLE001
                forecast_result = {"mode": None,
                                   "reason": f"forecast unavailable: {exc}",
                                   "authority": "display_only"}
            st.session_state.forecast_result = forecast_result
            append_event(AUDIT_PATH, recommendation=rec, event_type="displayed",
                         role=role)

with right:
    st.subheader("Review state")
    rec = st.session_state.recommendation
    if rec is None:
        st.markdown(ui_theme.callout(
            "Add cuffs, record current findings, and evaluate."),
            unsafe_allow_html=True)
    else:
        colors = {"URGENT_CLINICAL_REVIEW": "fail", "REVIEW_NOW": "warn",
                  "INSUFFICIENT_INFORMATION": "sage", "NO_ALERT": "ok"}
        st.markdown(
            ui_theme.pill(rec["state"].replace("_", " "),
                          colors.get(rec["state"], "")),
            unsafe_allow_html=True,
        )
        st.write(rec["state_reason_text"])
        notes = st.session_state.get("assessment_notes") or {}
        if notes.get("validation_error"):
            st.error("Session validation failed: "
                     + str(notes["validation_error"])
                     + " No raw session baseline or cumulative UF was used; an "
                     "observed current BP is shown only when it is individually "
                     "within the documented range.")
        if notes.get("risk_reason"):
            st.warning("Shadow scoring unavailable: "
                       + str(notes["risk_reason"]))
        for warning in notes.get("warnings") or []:
            st.warning("Validation warning: " + str(warning))
        snapshot = rec["snapshot"]
        t_snapshot = snapshot.get("t_min")
        sbp_snapshot = snapshot.get("sbp")
        t_text = (f"{t_snapshot:.0f} min" if t_snapshot is not None
                  else "time unavailable")
        sbp_text = (f"SBP {sbp_snapshot:.0f} mmHg" if sbp_snapshot is not None
                    else "SBP unavailable")
        st.caption(f"Computed from the protocol rules and the values entered "
                   f"at evaluation (session {snapshot['session_id']}, {t_text}, "
                   f"{sbp_text}); the shadow score is not an input.")
        shadow = rec["risk_shadow"]
        st.metric("Shadow research risk",
                  f"{100 * shadow['score']:.1f}%" if shadow["score"] is not None else "unavailable")
        st.caption(f"Shadow status: {shadow['status']} | authority: "
                   f"{shadow['authority']} (display only). This score does not "
                   "trigger, suppress, or downgrade the pathway.")
        if shadow["score"] is not None and shadow["threshold"] is not None:
            st.caption(f"Frozen raw-score threshold {shadow['threshold']} | as of "
                       f"{shadow['as_of_min']:.0f} min | model: "
                       f"{shadow['model_version']}")
        if rec["data_quality"]:
            st.warning("Missing/invalid: " + ", ".join(rec["data_quality"]))
        st.caption(f"Protocol: {rec['protocol_label']} ({rec['protocol_version']}) | "
                   f"role label: {rec['role_simulation']}")

        st.markdown("**Protocol pathway**")
        st.dataframe([{
            "Step": s["sequence"], "Action": s["title"],
            "Available": "yes" if s["available"] else "no",
            "Role scope": ", ".join(s["roles"]),
            "Suppressed because": s["reason_code"] or "",
            "Instruction": s["instruction"],
        } for s in rec["pathway"]], width="stretch")

        st.markdown("**UF fluid-accounting scenario**")
        removed = rec["snapshot"].get("uf_removed_L")
        if removed is None:
            st.warning("Fluid scenario blocked: valid removed-UF volume is "
                       "unavailable. Re-evaluate with a valid session; no zero "
                       "volume was assumed.")
        else:
            q_pct = st.slider("Percentage of remaining-planned UF left unremoved",
                              0, 100, 25, 5)
            extra = st.number_input("Additional fluid to account for (L)",
                                    0.0, 5.0, 0.0, 0.1)
            st.caption(f"Cuff-only reconstructed removed UF: {float(removed):.2f} L. "
                       "An optionally entered cumulative value is not used.")
            try:
                fluid = calculate_fluid(
                    uf_goal_L=uf_goal,
                    uf_removed_L=float(removed),
                    q_left=q_pct / 100.0,
                    additional_fluid_L=extra,
                    next_prescription_L=next_rx,
                    next_duration_h=next_hours,
                    weight_kg=dry,
                )
                st.dataframe([{
                    "Metric": "Fluid left this session (L)",
                    "Value": round(fluid["fluid_left_mL"] / 1000.0, 2)},
                    {"Metric": "Carry-forward including entered fluid (L)",
                     "Value": round(fluid["carry_forward_mL"] / 1000.0, 2)},
                    {"Metric": "Scenario next-session volume (L)",
                     "Value": (round(fluid["next_session_volume_mL"] / 1000.0, 2)
                               if fluid["next_session_volume_mL"] is not None else "missing")},
                    {"Metric": "Scenario next-session intensity (mL/kg/h)",
                     "Value": (round(fluid["scenario_intensity_mL_kg_h"], 1)
                               if fluid["scenario_intensity_mL_kg_h"] is not None else fluid["intensity_status"])},
                ], width="stretch")
                if float(removed) > float(uf_goal):
                    st.caption("Recorded cuff-only removal exceeds the current-session "
                               "UF goal; remaining volume is treated as zero in this "
                               "scenario.")
                if fluid["scenario_over_reference"]:
                    st.warning("The scenario's illustrative intensity exceeds the "
                               "13 mL/kg/h reference flag. This is not a prescription "
                               "limit or a determination of feasibility.")
                for assumption in fluid["assumptions"]:
                    st.caption(assumption)
            except ValueError as exc:
                st.error(f"Fluid calculation blocked: {exc}")

        # WHAT HAPPENS NEXT — conditional forecast card. Display-only with the
        # same authority semantics as the shadow score (authority="display_
        # only"): it never gates, suppresses, or alters the protocol pathway,
        # and a stale/absent model degrades to an unavailable note.
        st.markdown("**WHAT HAPPENS NEXT — conditional forecast "
                    "(observational)**")
        fc = st.session_state.get("forecast_result")
        if fc is None:
            st.caption("Forecast unavailable: not computed for this evaluation.")
        elif fc.get("mode") is None:
            st.caption("Forecast unavailable: "
                       + str(fc.get("reason") or "not computable for this "
                                                "session state") + ".")
        else:
            if fc["mode"] == "playback_full":
                st.caption("Mode: retrospective playback — full feature "
                           f"reconstruction from the frozen fold-0 context "
                           f"(anchor minute {float(fc['anchor_min']):.0f}, the "
                           "session's own model anchor; conditional on the UF "
                           "trajectory actually observed after that minute). "
                           "This is not a live forecast.")
            elif fc["mode"] == "manual_limited":
                st.warning("LIMITED-HISTORY FORECAST — OUT-OF-DISTRIBUTION "
                           "RISK. This session has no prior-session history, "
                           "no machine telemetry, and no observed future-UF "
                           "trajectory, and the refit was trained on "
                           "retrospective anchors with an observable "
                           "trajectory. Treat the numbers below as "
                           "research output only.")
            st.metric("Forecast nadir, next 60 min (observational)",
                      f"{float(fc['nadir_mean']):.1f} mmHg")
            lo, hi = fc["nadir_band"]
            st.caption(f"Dev-fold 95% residual band: {lo:.1f}–{hi:.1f} mmHg "
                       f"(source: {fc.get('band_source')}).")
            st.caption(f"Endpoint forecasts: 30-min {float(fc['p30']):.1f} "
                       f"mmHg | 60-min {float(fc['p60']):.1f} mmHg.")
            missing = list(fc.get("features_missing") or [])
            missing_text = (f"{fc['features_available']} of "
                            f"{fc['n_features']} model features available"
                            if fc.get("features_available") is not None else
                            "feature availability unknown")
            if missing:
                shown = ", ".join(missing[:10])
                more = (f" … and {len(missing) - 10} more"
                        if len(missing) > 10 else "")
                missing_text += ("; missing (never imputed): " + shown + more)
            st.caption(missing_text + ".")
        st.caption("Display only: the forecast never gates, suppresses, or "
                   "alters the protocol pathway.")
        st.caption("Observational conditional forecast under the observed UF "
                   "trajectory — not a validated what-if effect, not a "
                   "treatment recommendation, not a safety layer.")

        st.markdown("**Record review event**")
        recorded_role = str(rec["snapshot"].get("role") or "")
        st.caption(f"Evidence records the role label used when this assessment "
                   f"was evaluated: {recorded_role}. Role labels are not "
                   "authenticated or enforced.")
        with st.form("audit"):
            event_type = st.selectbox("Event", ["confirmed", "dismissed", "override"])
            step_id = st.selectbox("Step or action", [s["id"] for s in rec["pathway"]])
            reason = st.text_area("Reason / note")
            st.caption("Do not enter patient identifiers (name, medical record "
                       "number, date of birth, contact details, or other "
                       "identifiers) in the reason. The text is stored verbatim "
                       "in local demo evidence.")
            if st.form_submit_button("Append local evidence"):
                if not sid_label:
                    st.error("Evidence append blocked: the pseudonymous session ID "
                             "is empty. Nothing was written.")
                elif not str(rec["snapshot"].get("session_id") or "").strip():
                    st.error("Evidence append blocked: the evaluated assessment has "
                             "no session ID. Re-evaluate with a session ID.")
                else:
                    append_event(AUDIT_PATH, recommendation=rec, event_type=event_type,
                                 role=recorded_role, action=step_id, reason=reason)
                    st.success(f"Appended to {AUDIT_PATH}")
        st.caption("Local demo evidence only: append-only JSONL, not "
                   "tamper-evident, not authenticated, and not an immutable "
                   "clinical audit record.")

# Digital-twin surface for the active session is intentionally not shipped in
# V2; the Case lab carries the v4 twin surface. The live page keeps the
# validated forecast, protocol and fluid arithmetic only.

st.divider()
st.caption("Local demo · no network, machine actuation, authentication, or "
           "clinical-effectiveness claim.")
