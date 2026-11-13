"""PhysioTwin-v4.1 core: 3-state Starling-baroreflex twin with anchor bridging.

Documented deviations from plan_argon_final.md (all forced by the repo's own
data contract):

1. The reported nadir is the 60-minute bridge endpoint B(60), not the minimum
   over [15, 60]. The nadir label excludes the anchor cuff, so mu can exceed
   SBP_anchor; when that happens the plan's min-identity is false. The raw
   trajectory minimum is returned alongside the endpoint.
2. The bridge baseline is a pre-anchor-only model (59 features). Forecast-v2's
   72-feature contract includes the observed future-UF oracle (features
   60-72), so it cannot serve as the "expected care" baseline in the plan's
   counterfactual decomposition.
3. gamma is allowed to be exactly 0. The plan's [0.25, 1.25] floor forces a
   correction even when the data prefer the baseline (the boundary-collapse
   failure the plan itself warns about).

Units: D, OH in litres; R, UF in L/h; C in [0, 1); tau in hours; beta_vol in
mmHg/L; beta_baro in mmHg. State derivatives use dt in hours.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Mapping

import numpy as np

EPS = 1e-9
MIN_PER_H = 60.0
D_MAX = 10.0
OH_MAX = 10.0
C_MAX = 0.999


@dataclass
class PhysioParamsV4:
    tau_refill_h: float = 22.0 / 60.0
    tau_baro_h: float = 0.5
    tau_rec_h: float = 1.0
    r_base_ml_kg_h: float = 4.3
    r_oh_ml_kg_h_per_l: float = 2.8
    k_refill: float = 1.0
    theta_crit: float = 0.065
    beta_vol_mmHg_per_l: float = 10.0
    beta_baro_mmHg: float = 12.0
    w_dry_kg: float = 60.0
    oh0_l: float = 0.5
    v_b0_l: float = 4.5


@dataclass
class StarlingBaroreflexState:
    d_deficit_l: float = 0.0
    r_refill_l_h: float = 0.0
    c_baro_exhaustion: float = 0.0
    oh_remaining_l: float = 0.0

    def as_array(self) -> np.ndarray:
        return np.array([self.d_deficit_l, self.r_refill_l_h,
                         self.c_baro_exhaustion, self.oh_remaining_l],
                        dtype=float)


# ---------------------------------------------------------------------------
# scalar RK4 (pre-anchor integration, unit tests)
# ---------------------------------------------------------------------------

def _rmax(oh_l: float, p: PhysioParamsV4) -> float:
    oh = max(float(oh_l), 0.0)
    w = max(float(p.w_dry_kg), 1.0)
    rmax = (w / 1000.0) * (
        float(p.r_base_ml_kg_h)
        + float(p.r_oh_ml_kg_h_per_l) * oh / (1.0 + 0.25 * oh)
    )
    return max(rmax, 1e-4)


def _derivs(d: float, r: float, c: float, oh: float,
            uf_l_h: float, p: PhysioParamsV4):
    rmax = _rmax(oh, p)
    d = min(max(d, 0.0), D_MAX)
    r = min(max(r, 0.0), rmax)
    c = min(max(c, 0.0), C_MAX)
    d_r = (rmax * np.tanh(p.k_refill * d / (rmax + EPS)) - r) / p.tau_refill_h
    d_d = float(uf_l_h) - r
    rbv = d / max(float(p.v_b0_l), 0.1)
    over = max(0.0, rbv - p.theta_crit)
    under = max(0.0, p.theta_crit - rbv)
    d_c = (over / p.tau_baro_h) * (1.0 - c) - (under / p.tau_rec_h) * c
    d_oh = -r
    return d_d, d_r, d_c, d_oh


def _clamp_state(d, r, c, oh, p: PhysioParamsV4):
    rmax = _rmax(oh, p)
    return (float(np.clip(d, 0.0, D_MAX)),
            float(np.clip(r, 0.0, rmax)),
            float(np.clip(c, 0.0, C_MAX)),
            float(np.clip(oh, 0.0, OH_MAX)))


def rk4_step_starling_baroreflex(state: StarlingBaroreflexState,
                                 uf_rate_l_h: float,
                                 params: PhysioParamsV4,
                                 dt_h: float = 1.0 / MIN_PER_H
                                 ) -> StarlingBaroreflexState:
    d, r, c, oh = state.as_array()
    k1 = _derivs(d, r, c, oh, uf_rate_l_h, params)
    k2 = _derivs(d + 0.5 * dt_h * k1[0], r + 0.5 * dt_h * k1[1],
                 c + 0.5 * dt_h * k1[2], oh + 0.5 * dt_h * k1[3],
                 uf_rate_l_h, params)
    k3 = _derivs(d + 0.5 * dt_h * k2[0], r + 0.5 * dt_h * k2[1],
                 c + 0.5 * dt_h * k2[2], oh + 0.5 * dt_h * k2[3],
                 uf_rate_l_h, params)
    k4 = _derivs(d + dt_h * k3[0], r + dt_h * k3[1],
                 c + dt_h * k3[2], oh + dt_h * k3[3],
                 uf_rate_l_h, params)
    out = [x + dt_h * (a + 2.0 * b + 2.0 * cc + e) / 6.0
           for x, a, b, cc, e in zip((d, r, c, oh), k1, k2, k3, k4)]
    out = _clamp_state(*out, params)
    return StarlingBaroreflexState(*out)


def integrate_pre_anchor(uf_by_minute: Iterable[float] | np.ndarray,
                         t_end_min: float,
                         params: PhysioParamsV4,
                         record_minutes: Iterable[int] | None = None,
                         ) -> dict[int, StarlingBaroreflexState]:
    """Integrate the session from t=0 to t_end using the causal UF stream.

    `uf_by_minute[m]` is the machine UF rate (L/h) at minute m. Values are
    forward-filled by the caller. Returns recorded states by minute, always
    including t_end_min (rounded down).
    """
    grid = np.asarray(list(uf_by_minute), dtype=float)
    if grid.ndim != 1:
        raise ValueError("uf_by_minute must be 1-D")
    end = int(np.floor(float(t_end_min)))
    if end < 0:
        raise ValueError("t_end_min must be >= 0")
    if end >= len(grid):
        raise ValueError(f"UF grid too short: need {end + 1}, got {len(grid)}")
    rec = {int(m) for m in (record_minutes or [])}
    rec.add(end)
    state = StarlingBaroreflexState(0.0, 0.0, 0.0, params.oh0_l)
    out: dict[int, StarlingBaroreflexState] = {0: state}
    for m in range(1, end + 1):
        state = rk4_step_starling_baroreflex(state, grid[m], params)
        if m in rec:
            out[m] = state
    return out


# ---------------------------------------------------------------------------
# vectorized RK4 (counterfactual branches, one row per anchor)
# ---------------------------------------------------------------------------

def _vec(p: Mapping[str, np.ndarray], key: str) -> np.ndarray:
    v = p[key]
    return v if isinstance(v, np.ndarray) else np.asarray(v, dtype=float)


def _vec_derivs(d, r, c, oh, uf, p: Mapping[str, np.ndarray]):
    w = np.maximum(_vec(p, "w_dry_kg"), 1.0)
    oh = np.clip(oh, 0.0, OH_MAX)
    rmax = (w / 1000.0) * (
        _vec(p, "r_base_ml_kg_h")
        + _vec(p, "r_oh_ml_kg_h_per_l") * oh / (1.0 + 0.25 * oh)
    )
    rmax = np.maximum(rmax, 1e-4)
    d = np.clip(d, 0.0, D_MAX)
    r = np.clip(r, 0.0, rmax)
    c = np.clip(c, 0.0, C_MAX)
    d_r = (rmax * np.tanh(_vec(p, "k_refill") * d / (rmax + EPS))
           - r) / _vec(p, "tau_refill_h")
    d_d = uf - r
    rbv = d / np.maximum(_vec(p, "v_b0_l"), 0.1)
    over = np.maximum(0.0, rbv - _vec(p, "theta_crit"))
    under = np.maximum(0.0, _vec(p, "theta_crit") - rbv)
    d_c = ((over / _vec(p, "tau_baro_h")) * (1.0 - c)
           - (under / _vec(p, "tau_rec_h")) * c)
    d_oh = -r
    return d_d, d_r, d_c, d_oh


def _vec_clamp(d, r, c, oh, p):
    w = np.maximum(_vec(p, "w_dry_kg"), 1.0)
    oh = np.clip(oh, 0.0, OH_MAX)
    rmax = (w / 1000.0) * (
        _vec(p, "r_base_ml_kg_h")
        + _vec(p, "r_oh_ml_kg_h_per_l") * oh / (1.0 + 0.25 * oh)
    )
    return (np.clip(d, 0.0, D_MAX),
            np.clip(r, 0.0, np.maximum(rmax, 1e-4)),
            np.clip(c, 0.0, C_MAX),
            oh)


def _rk4_step_vec(d, r, c, oh, uf, p, dt_h: float):
    k1 = _vec_derivs(d, r, c, oh, uf, p)
    k2 = _vec_derivs(d + 0.5 * dt_h * k1[0], r + 0.5 * dt_h * k1[1],
                     c + 0.5 * dt_h * k1[2], oh + 0.5 * dt_h * k1[3], uf, p)
    k3 = _vec_derivs(d + 0.5 * dt_h * k2[0], r + 0.5 * dt_h * k2[1],
                     c + 0.5 * dt_h * k2[2], oh + 0.5 * dt_h * k2[3], uf, p)
    k4 = _vec_derivs(d + dt_h * k3[0], r + dt_h * k3[1],
                     c + dt_h * k3[2], oh + dt_h * k3[3], uf, p)
    out = [x + dt_h * (a + 2.0 * b + 2.0 * cc + e) / 6.0
           for x, a, b, cc, e in zip((d, r, c, oh), k1, k2, k3, k4)]
    return _vec_clamp(*out, p)


def simulate_branch_batch(state0: Mapping[str, np.ndarray],
                          uf_matrix: np.ndarray,
                          params: Mapping[str, np.ndarray],
                          dt_min: float = 1.0) -> dict[str, np.ndarray]:
    """Simulate one 60-minute UF schedule per anchor.

    state0: D, R, C, OH arrays of length n (the pre-anchor state at t_a).
    uf_matrix: shape (n, T), L/h.
    Returns D/R/C/OH trajectories of shape (n, T+1).
    """
    uf = np.asarray(uf_matrix, dtype=float)
    if uf.ndim != 2:
        raise ValueError("uf_matrix must be (n, T)")
    n, t_steps = uf.shape
    d = np.asarray(state0["D"], dtype=float).copy()
    r = np.asarray(state0["R"], dtype=float).copy()
    c = np.asarray(state0["C"], dtype=float).copy()
    oh = np.asarray(state0["OH"], dtype=float).copy()
    if not (len(d) == len(r) == len(c) == len(oh) == n):
        raise ValueError("state0 arrays must have length n")
    out = {k: np.zeros((n, t_steps + 1), dtype=float)
           for k in ("D", "R", "C", "OH")}
    out["D"][:, 0], out["R"][:, 0], out["C"][:, 0], out["OH"][:, 0] = (
        d, r, c, oh)
    dt_h = float(dt_min) / MIN_PER_H
    for j in range(t_steps):
        d, r, c, oh = _rk4_step_vec(d, r, c, oh, uf[:, j], params, dt_h)
        out["D"][:, j + 1], out["R"][:, j + 1] = d, r
        out["C"][:, j + 1], out["OH"][:, j + 1] = c, oh
    return out


def phi_shape(dt_min: np.ndarray, tau_refill_min: float = 22.0) -> np.ndarray:
    """Normalized bridge shape, 0 at 0 and exactly 1 at 60 minutes."""
    dt = np.asarray(dt_min, dtype=float)
    denom = 1.0 - np.exp(-60.0 / float(tau_refill_min))
    return (1.0 - np.exp(-dt / float(tau_refill_min))) / max(denom, EPS)


def counterfactual_batch(state0: Mapping[str, np.ndarray],
                         params: Mapping[str, np.ndarray],
                         sbp_anchor: np.ndarray,
                         mu_expected: np.ndarray,
                         uf_expected_matrix: np.ndarray,
                         uf_policy_matrix: np.ndarray,
                         ) -> dict[str, np.ndarray]:
    """Boundary-bridged curves for one policy per anchor.

    SBP(Δt) = B(Δt) - [ΔH(policy) - ΔH(expected)]
    The reported `projected_nadir` is B(60) plus the endpoint correction.
    """
    exp = simulate_branch_batch(state0, uf_expected_matrix, params)
    pol = simulate_branch_batch(state0, uf_policy_matrix, params)
    n, t1 = pol["D"].shape
    dt = np.arange(t1, dtype=float)
    phi = phi_shape(dt)
    sbp0 = np.asarray(sbp_anchor, dtype=float)
    mu = np.asarray(mu_expected, dtype=float)
    b = sbp0[:, None] + (mu - sbp0)[:, None] * phi[None, :]
    beta_vol = _vec(params, "beta_vol_mmHg_per_l")[:, None]
    beta_baro = _vec(params, "beta_baro_mmHg")[:, None]
    d0 = np.asarray(state0["D"], dtype=float)[:, None]
    c0 = np.asarray(state0["C"], dtype=float)[:, None]
    dh_exp = beta_vol * (exp["D"] - d0) + beta_baro * (exp["C"] - c0)
    dh_pol = beta_vol * (pol["D"] - d0) + beta_baro * (pol["C"] - c0)
    sbp = b - (dh_pol - dh_exp)
    return {
        "sbp": sbp,
        "B": b,
        "D": pol["D"],
        "R": pol["R"],
        "C": pol["C"],
        "OH": pol["OH"],
        "dh_expected": dh_exp,
        "dh_policy": dh_pol,
        "phi": phi,
    }


def summarize_branch(traj: Mapping[str, np.ndarray],
                     policy: str) -> dict:
    """Scalar summary for one anchor (arrays are length-1 batches)."""
    sbp = np.asarray(traj["sbp"])[0]
    d = np.asarray(traj["D"])[0]
    r = np.asarray(traj["R"])[0]
    c = np.asarray(traj["C"])[0]
    seg = sbp[15:]
    return {
        "policy": policy,
        "projected_nadir_mmhg": float(sbp[-1]),
        "trajectory_min_mmhg": float(np.min(seg)),
        "trajectory_min_minute": int(np.argmin(seg) + 15),
        "nadir_series_mmhg": [float(x) for x in sbp],
        "peak_deficit_l": float(np.max(d)),
        "delayed_refill_rate_end_l_h": float(r[-1]),
        "peak_baro_exhaustion_pct": float(np.max(c) * 100.0),
    }


# ---------------------------------------------------------------------------
# expected-care schedules and policies
# ---------------------------------------------------------------------------

def segments_to_minutes(segments_l_h: Iterable[float], t_steps: int = 60
                        ) -> np.ndarray:
    """Piecewise-constant 60-minute schedule from four 15-minute segments."""
    seg = np.asarray(list(segments_l_h), dtype=float)
    if seg.shape != (4,):
        raise ValueError("need four segment means")
    out = np.empty(int(t_steps), dtype=float)
    q = max(int(t_steps) // 4, 1)
    for i in range(4):
        lo, hi = i * q, (i + 1) * q if i < 3 else int(t_steps)
        out[lo:hi] = seg[i]
    return np.maximum(out, 0.0)


def policy_schedule(name: str, hold_l_h: float, t_steps: int = 60) -> np.ndarray:
    hold = max(float(hold_l_h), 0.0)
    name = str(name).upper()
    if name in {"HOLD", "HOLD_CURRENT_UF", "HOLD_100"}:
        return np.full(int(t_steps), hold, dtype=float)
    if name in {"TAPER_75", "TAPER_75_PCT"}:
        return np.full(int(t_steps), 0.75 * hold, dtype=float)
    if name in {"TAPER_50", "TAPER_50_PCT"}:
        return np.full(int(t_steps), 0.50 * hold, dtype=float)
    if name in {"MIN_KEEP_OPEN_010_LH", "FLOOR_010", "FLOOR"}:
        return np.full(int(t_steps), min(0.10, hold) if hold > 0 else 0.0,
                       dtype=float)
    if name in {"PAUSE_30M_THEN_RESUME", "PAUSE_30", "PAUSE"}:
        out = np.empty(int(t_steps), dtype=float)
        out[:30] = 0.0
        out[30:] = hold
        return out
    if name.startswith("FRAC_"):
        try:
            frac = float(name.split("_", 1)[1])
        except ValueError as exc:
            raise ValueError(f"bad policy fraction: {name}") from exc
        return np.full(int(t_steps), max(frac, 0.0) * hold, dtype=float)
    if name == "ZERO":
        return np.zeros(int(t_steps), dtype=float)
    raise ValueError(f"unknown policy: {name}")


# ---------------------------------------------------------------------------
# 3-tier shrinkage / covariate prior
# ---------------------------------------------------------------------------

def _finite(x, default=np.nan) -> float:
    try:
        v = float(x)
        return v if np.isfinite(v) else float(default)
    except (TypeError, ValueError):
        return float(default)


def estimate_patient_posterior_params(row: Mapping | object,
                                      kappa: float = 10.0
                                      ) -> PhysioParamsV4:
    """Tier 1 constants + Tier 2 covariate prior + Tier 3 James-Stein blend.

    `row` may be a dict or a pandas Series. Tier-3 history is the retired v3
    twin's per-patient (k_pat, beta_pat); k_pat is normalized to the
    population 0.30/h before blending and beta_pat is clipped to the v4
    physiological bounds. n_prior = 0 returns the covariate prior exactly.
    """
    def g(key, default=np.nan):
        try:
            return row.get(key, default)  # type: ignore[union-attr]
        except AttributeError:
            return getattr(row, key, default)

    n_prior = int(_finite(g("n_prior", g("n_prior_sessions", 0)), 0))
    n_prior = max(n_prior, 0)
    dm = bool(_finite(g("dm", 0), 0) >= 0.5)
    age = _finite(g("age", 60), 60)
    frail = bool(dm or age >= 65)

    w_dry = _finite(g("dry_weight", np.nan))
    pre = _finite(g("pre_weight", np.nan))
    if not (np.isfinite(w_dry) and w_dry > 20.0):
        w_dry = pre if (np.isfinite(pre) and pre > 20.0) else 60.0
    oh0 = max(0.0, pre - w_dry) if (np.isfinite(pre) and pre > w_dry) else 0.5
    oh0 = float(np.clip(oh0, 0.0, 6.0))

    k0 = 1.0
    beta_vol0 = 12.0 if frail else 10.0
    beta_baro0 = 14.0 if frail else 12.0
    theta0 = 0.045 if frail else 0.065

    k_hist = np.nan
    beta_hist = np.nan
    k_pat = _finite(g("k_pat", np.nan))
    beta_pat = _finite(g("beta_pat", np.nan))
    if np.isfinite(k_pat):
        k_hist = float(np.clip(k_pat / 0.30, 0.4, 2.0))
    if np.isfinite(beta_pat):
        beta_hist = float(np.clip(beta_pat, 4.5, 24.0))

    w = n_prior / (n_prior + float(kappa)) if n_prior > 0 else 0.0
    k = (1.0 - w) * k0 + w * (k_hist if np.isfinite(k_hist) else k0)
    beta_vol = (1.0 - w) * beta_vol0 + w * (
        beta_hist if np.isfinite(beta_hist) else beta_vol0)
    beta_vol = float(np.clip(beta_vol, 4.5, 24.0))
    beta_baro = float(np.clip(beta_baro0 * (beta_vol / max(beta_vol0, EPS)),
                             6.0, 28.0))

    return PhysioParamsV4(
        k_refill=float(np.clip(k, 0.4, 2.0)),
        theta_crit=float(theta0),
        beta_vol_mmHg_per_l=beta_vol,
        beta_baro_mmHg=beta_baro,
        w_dry_kg=float(w_dry),
        oh0_l=oh0,
        v_b0_l=float(0.075 * w_dry),
    )


def params_to_batch(params_list: Iterable[PhysioParamsV4]) -> dict[str, np.ndarray]:
    rows = [asdict(p) for p in params_list]
    if not rows:
        return {}
    return {k: np.asarray([r[k] for r in rows], dtype=float) for k in rows[0]}


def state0_from_rows(table) -> dict[str, np.ndarray]:
    """Extract the pre-anchor state from a pandas DataFrame / dict of arrays."""
    return {
        "D": np.asarray(table["D0"], dtype=float),
        "R": np.asarray(table["R0"], dtype=float),
        "C": np.asarray(table["C0"], dtype=float),
        "OH": np.asarray(table["OH0"], dtype=float),
    }


# ---------------------------------------------------------------------------
# per-session causal UF grid
# ---------------------------------------------------------------------------

def session_uf_grid(d: Mapping, t_end_min: float) -> np.ndarray:
    """Forward-filled machine UF (L/h) on the integer-minute grid [0, t_end].

    Uses only records at or before each minute. If the machine stream is
    missing, falls back to zero (never a future record).
    """
    end = int(np.floor(float(t_end_min)))
    mt = np.asarray(d.get("mt", []), dtype=float)
    muf = np.asarray(d.get("muf", []), dtype=float)
    if len(mt) == 0 or len(muf) == 0:
        return np.zeros(end + 1, dtype=float)
    keep = np.isfinite(mt) & np.isfinite(muf) & (mt <= end + 1e-9)
    mt, muf = mt[keep], muf[keep]
    if len(mt) == 0:
        return np.zeros(end + 1, dtype=float)
    order = np.argsort(mt, kind="stable")
    mt, muf = mt[order], muf[order]
    idx = np.searchsorted(mt, np.arange(end + 1), side="right") - 1
    out = np.where(idx >= 0, muf[np.maximum(idx, 0)], muf[0])
    out = np.where(np.isfinite(out), out, 0.0)
    return np.maximum(out, 0.0)
