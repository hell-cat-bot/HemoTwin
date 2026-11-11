"""Coupled hemodynamic + fluid-consequence scenario matrix (v1 product).

Every row reports both sides of the tightrope: the PhysioTwin-v4.1 nadir
projection and the arithmetic fluid carried to the next session. This module
does not issue prescriptions; it is a bounded review aid.
"""
from __future__ import annotations

import numpy as np

from src.physiotwin_v4 import (
    counterfactual_batch, estimate_patient_posterior_params, params_to_batch,
    policy_schedule, segments_to_minutes, summarize_branch,
)
from src.session_twin.fluid import (
    REFERENCE_INTENSITY_ML_KG_H, calculate_fluid,
)

GOVERNANCE_LABEL = (
    "BOUNDED PHYSIOLOGICAL + ARITHMETIC SCENARIO MATRIX — SUPPORTING "
    "CLINICIAN TRADE-OFF REVIEW, NOT AN AUTONOMOUS PRESCRIPTION")

POLICIES = (
    ("HOLD_CURRENT_UF", "Hold current UF"),
    ("TAPER_75_PCT", "Taper to 75%"),
    ("TAPER_50_PCT", "Taper to 50%"),
    ("MIN_KEEP_OPEN_010_LH", "Keep-open 0.10 L/h"),
    ("PAUSE_30M_THEN_RESUME", "30-min pause, then resume"),
)

SEG_COLS = ("uf_seg_1_15", "uf_seg_16_30", "uf_seg_31_45", "uf_seg_46_60")


def _g(row, key: str, default=np.nan) -> float:
    try:
        v = row.get(key, default)
    except AttributeError:
        v = getattr(row, key, default)
    try:
        v = float(v)
        return v if np.isfinite(v) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _simulate_one(row, params, base_nadir: float,
                  exp_segments, policy: str,
                  custom_rate: float | None = None,
                  gain: float = 1.0):
    sbp = _g(row, "sbp_anchor", 120.0)
    hold = _g(row, "uf_at_anchor", _g(row, "uf_Lh", 0.5))
    state0 = {"D": np.array([_g(row, "D0", 0.0)]),
              "R": np.array([_g(row, "R0", 0.0)]),
              "C": np.array([_g(row, "C0", 0.0)]),
              "OH": np.array([_g(row, "OH0", 0.0)])}
    pdict = params_to_batch([params])
    uf_exp = segments_to_minutes(exp_segments).reshape(1, -1)
    if custom_rate is not None:
        uf = np.full((1, 60), max(float(custom_rate), 0.0), dtype=float)
    else:
        uf = policy_schedule(policy, hold).reshape(1, -1)
    out = counterfactual_batch(state0, pdict, np.array([sbp]),
                               np.array([base_nadir]), uf_exp, uf)
    out["sbp"] = out["B"] - float(gain) * (out["dh_policy"]
                                           - out["dh_expected"])
    return out, uf


def build_scenario_matrix(row, params=None, base_nadir: float | None = None,
                          expected_segments=None,
                          conformal: tuple[float, float] = (-28.9, 25.9),
                          next_duration_h: float = 4.0,
                          gain: float = 1.0) -> dict:
    params = params or estimate_patient_posterior_params(row)
    sbp = _g(row, "sbp_anchor", 120.0)
    if base_nadir is None:
        base_nadir = sbp
    hold = _g(row, "uf_at_anchor", _g(row, "uf_Lh", 0.5))
    goal = _g(row, "uf_goal_L", np.nan)
    removed = _g(row, "cum_uf_L", 0.0)
    if expected_segments is None:
        expected_segments = [_g(row, c, np.nan) for c in SEG_COLS]
    exp = np.asarray(expected_segments, dtype=float)
    if not np.all(np.isfinite(exp)):
        exp = np.asarray([_g(row, c, hold) for c in SEG_COLS], dtype=float)
    exp = np.maximum(exp, 0.0)

    scenarios: list[dict] = []
    hold_row: dict | None = None
    for name, label in POLICIES:
        out, uf = _simulate_one(row, params, float(base_nadir), exp, name,
                                gain=float(gain))
        summary = summarize_branch(out, name)
        mean_uf = float(np.mean(uf))
        end_total = removed + mean_uf  # L over the 60-min branch
        if np.isfinite(goal):
            end_total = min(end_total, goal)
        remaining_before = max(goal - removed, 0.0) if np.isfinite(goal) else np.nan
        remaining_after = max(goal - end_total, 0.0) if np.isfinite(goal) else np.nan
        q_left = (remaining_after / remaining_before
                  if np.isfinite(remaining_before) and remaining_before > 0
                  else 0.0)
        fluid = None
        if np.isfinite(goal) and goal > 0:
            try:
                fluid = calculate_fluid(
                    uf_goal_L=goal, uf_removed_L=end_total, q_left=q_left,
                    next_prescription_L=goal, next_duration_h=next_duration_h,
                    weight_kg=params.w_dry_kg)
            except (ValueError, TypeError):
                fluid = None
        left_l = (fluid["fluid_left_mL"] / 1000.0
                  if fluid is not None else remaining_after)
        next_volume = (fluid["next_session_volume_mL"] / 1000.0
                       if fluid is not None
                       and fluid.get("next_session_volume_mL") is not None
                       else None)
        next_intensity = (fluid["scenario_intensity_mL_kg_h"]
                          if fluid is not None else None)
        nadir = float(summary["projected_nadir_mmhg"])
        item = {
            "policy": name,
            "label": label,
            "mean_uf_l_h": mean_uf,
            "projected_nadir_mmhg": nadir,
            "nadir_band_90": [nadir + float(conformal[0]),
                              nadir + float(conformal[1])],
            "trajectory_min_mmhg": summary["trajectory_min_mmhg"],
            "nadir_minute": summary["trajectory_min_minute"],
            "nadir_series_mmhg": summary["nadir_series_mmhg"],
            "peak_plasma_deficit_l": summary["peak_deficit_l"],
            "delayed_refill_rate_end_l_h": summary["delayed_refill_rate_end_l_h"],
            "baroreflex_exhaustion_pct": summary["peak_baro_exhaustion_pct"],
            "clears_90_mmhg_nadir_floor": bool(nadir >= 90.0),
            "end_session_total_uf_l": float(end_total),
            "fluid_left_behind_l": float(left_l),
            "residual_over_dry_weight_kg": float(left_l),
            "next_session_required_uf_l": (float(next_volume)
                                           if next_volume is not None else None),
            "next_session_uf_intensity_ml_kg_h": (float(next_intensity)
                                                  if next_intensity is not None
                                                  else None),
            "reference_intensity_ml_kg_h": REFERENCE_INTENSITY_ML_KG_H,
        }
        if hold_row is None:
            hold_row = item
        scenarios.append(item)

    for item in scenarios:
        d_carry = item["fluid_left_behind_l"] - hold_row["fluid_left_behind_l"]
        d_lift = item["projected_nadir_mmhg"] - hold_row["projected_nadir_mmhg"]
        item["expected_nadir_stabilization_vs_hold_mmhg"] = float(d_lift)
        item["hemodynamic_gain_per_liter_carried_mmHg_per_l"] = (
            float(d_lift / d_carry) if abs(d_carry) > 1e-6 else None)

    r_cap = None
    if np.isfinite(goal) and params.w_dry_kg > 0:
        carry_req = max(
            0.0, REFERENCE_INTENSITY_ML_KG_H * params.w_dry_kg
            * float(next_duration_h) / 1000.0 - goal)
        uf_req = max(goal - removed - carry_req, 0.0)
        out, uf = _simulate_one(row, params, float(base_nadir), exp,
                                "CUSTOM_UF_RATE", custom_rate=uf_req,
                                gain=float(gain))
        summary = summarize_branch(out, "INVERSE_13_CAP")
        r_cap = {
            "uf_rate_l_h": float(uf_req),
            "projected_nadir_mmhg": float(summary["projected_nadir_mmhg"]),
            "nadir_band_90": [float(summary["projected_nadir_mmhg"])
                              + float(conformal[0]),
                              float(summary["projected_nadir_mmhg"])
                              + float(conformal[1])],
            "carry_forward_required_l": float(carry_req),
            "reference_intensity_ml_kg_h": REFERENCE_INTENSITY_ML_KG_H,
        }

    return {
        "gain": float(gain),
        "anchor": {
            "sbp_anchor": sbp,
            "base_nadir_mmhg": float(base_nadir),
            "uf_at_anchor_l_h": hold,
            "uf_goal_L": goal if np.isfinite(goal) else None,
            "uf_removed_L": removed,
            "dry_weight_kg": params.w_dry_kg,
            "plasma_deficit_l": _g(row, "D0", np.nan),
            "refill_rate_l_h": _g(row, "R0", np.nan),
            "baroreflex_exhaustion": _g(row, "C0", np.nan),
        },
        "scenarios": scenarios,
        "inverse_13_cap": r_cap,
        "governance_label": GOVERNANCE_LABEL,
        "assumptions": [
            "Hemodynamic projection is a mechanism-constrained model output, "
            "not an observed treatment effect.",
            "Fluid arithmetic uses the displayed branch's mean UF over 60 min.",
            "The 13 mL/kg/h reference is a flag, not a prescription limit.",
        ],
    }
