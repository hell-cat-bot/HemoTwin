"""4-block causal state vector at an intra-session anchor.

Block 1 static EHR, block 2 strictly-prior patient memory + James-Stein
shrinkage, block 3 pre-anchor intra-session dynamics, block 4 latent
Starling-baroreflex state. Nothing in blocks 1-4 uses a record after the
anchor minute.
"""
from __future__ import annotations

import numpy as np

from src.physiotwin_v4 import estimate_patient_posterior_params

STATIC_KEYS = ("age", "sex_M", "dm", "vintage_years", "dry_weight",
               "pre_weight", "uf_goal_L", "dia_temp")
DYNAMIC_KEYS = ("sbp_now", "dbp_now", "map_now", "sbp_mean_15",
                "sbp_min_15", "sbp_slope_15", "sbp_mean_30", "sbp_min_30",
                "sbp_slope_30", "sbp_mean_60", "sbp_min_60", "sbp_slope_60",
                "sbp_drop_from_max", "sbp_std_30", "pulse_pressure",
                "map_slope_30", "uf_Lh", "uf_slope_15", "uf_slope_30",
                "uf_var_30", "cum_uf_L", "frac_uf_done", "elapsed_min",
                "gap_since_last", "n_bp_so_far")


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


def build_causal_state_vector(row, params=None, kappa: float = 10.0) -> dict:
    params = params or estimate_patient_posterior_params(row, kappa=kappa)
    n_prior = int(_g(row, "n_prior_sessions", _g(row, "n_prior", 0)))
    n_prior = max(n_prior, 0)
    weight = n_prior / (n_prior + float(kappa)) if n_prior > 0 else 0.0
    uf = _g(row, "uf_at_anchor", _g(row, "uf_Lh", 0.0))
    refill = _g(row, "R0", 0.0)
    return {
        "static_ehr_state": {k: _g(row, k) for k in STATIC_KEYS},
        "inter_session_memory_state": {
            "n_prior_sessions": n_prior,
            "shrinkage_weight": float(weight),
            "kappa": float(kappa),
            "k_refill": float(params.k_refill),
            "theta_crit": float(params.theta_crit),
            "beta_vol_mmHg_per_l": float(params.beta_vol_mmHg_per_l),
            "beta_baro_mmHg": float(params.beta_baro_mmHg),
            "w_dry_kg": float(params.w_dry_kg),
        },
        "intra_session_dynamic_state": {k: _g(row, k) for k in DYNAMIC_KEYS},
        "latent_starling_baroreflex_state": {
            "plasma_deficit_l": _g(row, "D0", 0.0),
            "refill_rate_l_h": refill,
            "baroreflex_exhaustion": _g(row, "C0", 0.0),
            "overhydration_remaining_l": _g(row, "OH0", 0.0),
            "refill_deficit_l_h": float(uf - refill),
            "tau_refill_min": float(params.tau_refill_h * 60.0),
            "tau_baro_min": float(params.tau_baro_h * 60.0),
        },
    }


def flatten_state_vector(sv: dict) -> dict:
    out = {}
    for block, values in sv.items():
        for key, value in values.items():
            out[f"{block}.{key}"] = value
    return out
