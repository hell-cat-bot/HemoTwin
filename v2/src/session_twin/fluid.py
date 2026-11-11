"""Pure volumetric UF scenario arithmetic.

All formulas use mL, kg, and hours internally. No physiological response,
treatment benefit, or prescription safety is inferred.
"""
from __future__ import annotations

from math import isfinite

REFERENCE_INTENSITY_ML_KG_H = 13.0
ASSUMPTIONS = (
    "Arithmetic only; not a prediction of patient response or prescription safety.",
    "Additional fluid is assumed to remain in the patient until session end.",
    "Carry-forward is added to the next-session baseline only in this displayed scenario.",
    "The 13 mL/kg/h value is a reference flag, not a prescription limit.",
)


def _finite_nonnegative(name: str, value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(v) or v < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return v


def _optional_nonnegative(value) -> float | None:
    if value is None:
        return None
    v = float(value)
    if not isfinite(v) or v < 0:
        return None
    return v


def calculate_fluid(*, uf_goal_L, uf_removed_L, q_left,
                    additional_fluid_L=0.0,
                    next_prescription_L=None,
                    next_duration_h=None,
                    weight_kg=None) -> dict:
    goal_mL = _finite_nonnegative("uf_goal_L", uf_goal_L) * 1000.0
    removed_mL = _finite_nonnegative("uf_removed_L", uf_removed_L) * 1000.0
    q = float(q_left)
    if not isfinite(q) or not 0.0 <= q <= 1.0:
        raise ValueError("q_left must be within [0, 1]")
    extra_mL = _finite_nonnegative("additional_fluid_L", additional_fluid_L) * 1000.0

    remaining_mL = max(goal_mL - removed_mL, 0.0)
    left_mL = q * remaining_mL
    carry_mL = left_mL + extra_mL

    p0 = _optional_nonnegative(next_prescription_L)
    duration = _optional_nonnegative(next_duration_h)
    weight = _optional_nonnegative(weight_kg)

    next_volume = p0 * 1000.0 + carry_mL if p0 is not None else None
    baseline_intensity = None
    scenario_intensity = None
    reasons: list[str] = []
    if p0 is None:
        reasons.append("missing_next_prescription")
    if duration is None or duration <= 0:
        reasons.append("missing_duration")
    if weight is None or weight <= 0:
        reasons.append("missing_weight")

    if p0 is not None and duration and weight:
        baseline_intensity = (p0 * 1000.0) / (weight * duration)
        scenario_intensity = next_volume / (weight * duration)

    if not reasons:
        intensity_status = "ok"
    elif len(reasons) == 1:
        intensity_status = reasons[0]
    else:
        intensity_status = "missing_inputs"

    baseline_over = (baseline_intensity > REFERENCE_INTENSITY_ML_KG_H
                     if baseline_intensity is not None else None)
    scenario_over = (scenario_intensity > REFERENCE_INTENSITY_ML_KG_H
                     if scenario_intensity is not None else None)

    return {
        "remaining_uf_mL": remaining_mL,
        "remaining_uf_status": "ok",
        "fluid_left_mL": left_mL,
        "carry_forward_mL": carry_mL,
        "carry_forward_status": "ok",
        "next_session_volume_mL": next_volume,
        "next_session_volume_status": "ok" if next_volume is not None else "missing",
        "baseline_intensity_mL_kg_h": baseline_intensity,
        "scenario_intensity_mL_kg_h": scenario_intensity,
        "intensity_status": intensity_status,
        "missing_for_intensity": reasons,
        "reference_intensity_mL_kg_h": REFERENCE_INTENSITY_ML_KG_H,
        "baseline_over_reference": baseline_over,
        "scenario_over_reference": scenario_over,
        "assumptions": list(ASSUMPTIONS),
    }
