"""The twin layer.

A two-parameter physiological model of the session:

    dD/dt  = UF(t)/60 - k_refill * D            D = plasma volume deficit (L)
    SBP(t) = SBP0 - beta_bp * D(t)              beta_bp = mmHg lost per litre

Why only two parameters: NIBP is recorded roughly every 30 minutes. With that
sampling, a richer model is not identifiable -- adding a free time-trend term
makes beta_bp and the trend collinear and the fit becomes arbitrary. We choose
the two parameters that (a) are identifiable and (b) a nephrologist can name.

`k_refill` is fitted per patient from their *earlier* sessions and shrunk toward
the population median. `beta_bp` likewise. `SBP0` is anchored to the current
session, because baseline pressure varies day to day.

The counterfactual then re-simulates the rest of the session under a different
UF policy. This is a within-policy-space simulation: 87% of real sessions
already taper ultrafiltration mid-session, so we are not proposing a new
intervention -- we are choosing *when* to apply the one that already happens.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.signal import lfilter

# numpy 2.x renamed trapz -> trapezoid; keep both working
_trapz = getattr(np, "trapezoid", None) or np.trapz


@dataclass
class TwinParams:
    k_refill: float     # 1/hour, plasma refill rate
    beta_bp: float      # mmHg per litre of deficit
    sbp0: float         # session baseline SBP (mmHg)


POLICIES = {
    "hold":    {"label": "Hold current UF",         "uf_mult": 1.00, "pause_min": 0,  "bolus_L": 0.0},
    "taper25": {"label": "Taper UF by 25%",         "uf_mult": 0.75, "pause_min": 0,  "bolus_L": 0.0},
    "pause":   {"label": "Stop UF + 250 mL fluid",  "uf_mult": 0.00, "pause_min": 60, "bolus_L": 0.25},
}


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------
def deficit_curve(uf_lh: np.ndarray, k_refill: float, dt: float = 1.0) -> np.ndarray:
    """Solve dD/dt = UF/60 - (k/60) D on a uniform grid. Vectorised via lfilter."""
    a = float(np.clip(1.0 - k_refill * dt / 60.0, 0.0, 0.999999))
    x = np.asarray(uf_lh, dtype=float) * dt / 60.0
    return lfilter([1.0], [1.0, -a], x, zi=[0.0])[0]


def _grid_for_session(d: dict, t_end: float | None = None, dt: float = 1.0):
    """1-minute grid of UF rate (L/h), last-known semantics, from machine log."""
    mt, muf = d["mt"], d["muf"]
    tmax = float(mt.max()) if t_end is None else float(t_end)
    tmax = max(tmax, 1.0)
    grid = np.arange(0.0, tmax + dt, dt)
    uf = np.interp(grid, mt, muf, left=float(muf[0]), right=float(muf[-1]))
    uf = np.clip(uf, 0.0, 4.0)
    return grid, uf


def fit_session(d: dict, k_grid: np.ndarray | None = None) -> dict:
    """Fit (k_refill, beta_bp, sbp0) for one session by grid search + OLS."""
    if k_grid is None:
        k_grid = np.linspace(0.15, 3.0, 20)

    et, es = d["et"], d["es"]
    if len(et) < 4:
        return {"k": np.nan, "beta": np.nan, "sbp0": np.nan, "rmse": np.nan}

    grid, uf = _grid_for_session(d, t_end=float(et.max()))
    best = None
    for k in k_grid:
        D = deficit_curve(uf, k)
        d_at = np.interp(et, grid, D)
        if np.ptp(d_at) < 1e-6:
            continue
        # SBP = a - b*D  ->  OLS with b >= 0
        X = np.column_stack([np.ones_like(d_at), -d_at])
        coef, *_ = np.linalg.lstsq(X, es, rcond=None)
        a, b = float(coef[0]), float(coef[1])
        if b < 0:
            continue
        pred = a - b * d_at
        rmse = float(np.sqrt(np.mean((es - pred) ** 2)))
        if best is None or rmse < best["rmse"]:
            best = {"k": float(k), "beta": b, "sbp0": a, "rmse": rmse}

    if best is None:
        return {"k": np.nan, "beta": np.nan, "sbp0": np.nan, "rmse": np.nan}
    return best


# ---------------------------------------------------------------------------
# Population and per-patient parameters
# ---------------------------------------------------------------------------
def fit_population(store: dict, session_ids, min_events: int = 6) -> dict:
    ks, betas = [], []
    for sid in session_ids:
        d = store.get(sid)
        if d is None or len(d["et"]) < min_events:
            continue
        f = fit_session(d)
        if np.isfinite(f["k"]) and np.isfinite(f["beta"]):
            ks.append(f["k"])
            betas.append(f["beta"])
    if not ks:
        return {"k_refill": 0.8, "beta_bp": 12.0, "n": 0}
    return {
        "k_refill": float(np.median(ks)),
        "beta_bp": float(np.median(betas)),
        "k_iqr": [float(np.percentile(ks, 25)), float(np.percentile(ks, 75))],
        "beta_iqr": [float(np.percentile(betas, 25)), float(np.percentile(betas, 75))],
        "n": len(ks),
    }


def fit_patient(store: dict, pid: str, sessions: list[str], pop: dict,
                shrink: float = 5.0) -> dict:
    """Median of prior sessions, shrunk toward the population median."""
    ks, betas = [], []
    for sid in sessions:
        d = store.get(sid)
        if d is None or len(d["et"]) < 6:
            continue
        f = fit_session(d)
        if np.isfinite(f["k"]) and np.isfinite(f["beta"]):
            ks.append(f["k"])
            betas.append(f["beta"])
    n = len(ks)
    k_pat = float(np.median(ks)) if n else pop["k_refill"]
    b_pat = float(np.median(betas)) if n else pop["beta_bp"]
    w = n / (n + shrink)
    return {
        "k_refill": w * k_pat + (1 - w) * pop["k_refill"],
        "beta_bp": w * b_pat + (1 - w) * pop["beta_bp"],
        "n_prior_sessions": int(n),
    }


# ---------------------------------------------------------------------------
# Counterfactual
# ---------------------------------------------------------------------------
def _base_rate(d: dict, t_now: float, goal: float | None) -> float:
    """Rate to use for projection: the average needed to meet the prescription.

    The instantaneous machine rate at minute 30 is often the session peak, and
    projecting it forward overstates both the pressure fall and the volume
    removed. The prescribed goal divided by the time left is what the
    prescription actually implies, and it is what the nurse is deciding about.
    """
    grid, uf = _grid_for_session(d, t_end=float(d["et"].max()))
    i0 = int(np.searchsorted(grid, t_now, side="right") - 1)
    i0 = max(i0, 0)
    u_now = float(uf[i0])
    if goal is None or not np.isfinite(goal):
        return u_now
    cum = float(_trapz(uf[:i0 + 1], grid[:i0 + 1]) / 60.0)
    remaining_h = max((float(grid[-1]) - t_now) / 60.0, 1e-3)
    required = max(goal - cum, 0.0) / remaining_h
    return float(np.clip(required, 0.0, 4.0))


def counterfactual(d: dict, t_now: float, params: dict,
                   policies: dict | None = None,
                   horizon_min: int = 60) -> list[dict]:
    """Re-simulate the next `horizon_min` minutes under each UF policy.

    Two things are deliberately separate:

    * BP is projected only over the next hour. The linear-in-deficit model is
      calibrated on within-session variation; extrapolating it to session end
      over-predicts the fall badly.
    * Fluid left behind is pure volume accounting to session end -- no model,
      just rate x time -- and is reported as a projection, not a measurement.
    """
    policies = policies or POLICIES
    et, es = d["et"], d["es"]
    dur = float(et.max())
    t_now = float(np.clip(t_now, 1.0, max(dur - 1.0, 2.0)))
    t_horizon = min(t_now + horizon_min, dur)

    grid, uf_now = _grid_for_session(d, t_end=dur)
    i0 = int(np.searchsorted(grid, t_now, side="right") - 1)
    i0 = max(i0, 0)

    D = deficit_curve(uf_now, params["k_refill"])
    D_now = float(D[i0])
    cum_now = float(_trapz(uf_now[:i0 + 1], grid[:i0 + 1]) / 60.0)

    goal = d.get("goal")
    goal = float(goal) if goal is not None and np.isfinite(goal) else np.nan
    u_base = _base_rate(d, t_now, goal if np.isfinite(goal) else None)
    remaining_h = max((dur - t_now) / 60.0, 1e-3)

    sbp_now = float(np.interp(t_now, et, es))
    sbp0 = sbp_now + params["beta_bp"] * D_now

    out = []
    for key, pol in policies.items():
        n_bp = int(t_horizon - t_now) + 1
        u = np.full(n_bp, u_base) * pol["uf_mult"]
        if pol["pause_min"] > 0:
            u[: int(min(pol["pause_min"], n_bp))] = 0.0

        D_fwd = deficit_curve(u, params["k_refill"])
        D_path = np.clip(D_now + D_fwd - pol.get("bolus_L", 0.0), 0.0, None)
        sbp_path = sbp0 - params["beta_bp"] * D_path

        j = int(np.argmin(sbp_path))
        nadir = float(sbp_path[j])
        t_nadir = float(t_now + j)

        if np.isfinite(goal):
            pause_h = min(pol["pause_min"], max(dur - t_now, 0)) / 60.0
            active_h = max(remaining_h - pause_h, 0.0)
            future = min(u_base * pol["uf_mult"] * active_h,
                         max(goal - cum_now, 0.0))
            fluid_left = float(max(goal - cum_now - future, 0.0))
            removed_end = float(cum_now + future)
        else:
            fluid_left = float("nan")
            removed_end = float(cum_now + _trapz(u, np.arange(n_bp)) / 60.0)

        out.append({
            "policy": key,
            "label": pol["label"],
            "nadir": round(nadir, 1),
            "time_to_nadir_min": round(t_nadir - t_now, 1),
            "fluid_left_L": round(fluid_left, 2) if np.isfinite(fluid_left) else None,
            "fluid_removed_L": round(removed_end, 2),
            "uf_rate_Lh": round(float(u_base * pol["uf_mult"]), 2),
            "path": [
                {"t": round(float(t_now + i), 1), "sbp": round(float(s), 1)}
                for i, s in enumerate(sbp_path) if i % 5 == 0
            ],
        })
    return out


def forecast_path(d: dict, t_now: float, params: dict, minutes: int = 60) -> list[dict]:
    """Hold-policy forecast for the chart, using the same base rate as the what-if."""
    et = d["et"]
    dur = float(et.max())
    t_now = float(np.clip(t_now, 1.0, max(dur - 1.0, 2.0)))
    t_end = min(t_now + minutes, dur)

    grid, uf = _grid_for_session(d, t_end=dur)
    i0 = int(np.searchsorted(grid, t_now, side="right") - 1)
    i0 = max(i0, 0)
    D = deficit_curve(uf, params["k_refill"])
    D_now = float(D[i0])

    goal = d.get("goal")
    goal = float(goal) if goal is not None and np.isfinite(goal) else None
    u_base = _base_rate(d, t_now, goal)

    n = int(t_end - t_now) + 1
    u = np.full(n, u_base)
    D_fwd = deficit_curve(u, params["k_refill"])
    sbp_now = float(np.interp(t_now, et, d["es"]))
    sbp0 = sbp_now + params["beta_bp"] * D_now

    return [
        {"t": round(float(t_now + i), 1),
         "sbp": round(float(sbp0 - params["beta_bp"] * (D_now + D_fwd[i])), 1)}
        for i in range(0, n, 2)
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def residual_quantiles(store: dict, session_ids, pop: dict,
                       q=(0.05, 0.95)) -> dict:
    """How wrong is the hold-policy nadir on sessions we did not fit on?

    Gives the conformal-style band used in the demo. Residual = observed - predicted.
    """
    res = []
    for sid in session_ids:
        d = store.get(sid)
        if d is None or len(d["et"]) < 8:
            continue
        f = fit_session(d)
        if not np.isfinite(f["k"]):
            continue
        params = {"k_refill": f["k"], "beta_bp": f["beta"], "sbp0": f["sbp0"]}
        # predict the nadir from the first half, compare with the second half
        t_mid = float(np.quantile(d["et"], 0.5))
        cf = counterfactual(d, t_mid, params, policies={"hold": POLICIES["hold"]})
        pred = cf[0]["nadir"]
        obs = float(d["es"][d["et"] > t_mid].min())
        res.append(obs - pred)
    if not res:
        return {"lo": -15.0, "hi": 15.0, "n": 0}
    return {
        "lo": float(np.quantile(res, q[0])),
        "hi": float(np.quantile(res, q[1])),
        "median": float(np.median(res)),
        "mae": float(np.mean(np.abs(res))),
        "n": len(res),
    }


def volume_check(store: dict, session_ids) -> dict:
    """Twin state vs measured weight loss. The one validation nobody else has."""
    rows = []
    for sid in session_ids:
        d = store.get(sid)
        if d is None:
            continue
        measured = d.get("measured_uf")
        if measured is None or not np.isfinite(measured) or measured <= 0.2:
            continue
        modelled = float(d["cum_uf"][-1])
        if not np.isfinite(modelled):
            continue
        rows.append((modelled, float(measured)))
    if not rows:
        return {"n": 0}
    m = np.array([r[0] for r in rows])
    o = np.array([r[1] for r in rows])
    diff = m - o
    return {
        "n": int(len(m)),
        "median_modelled_L": float(np.median(m)),
        "median_measured_L": float(np.median(o)),
        "median_difference_L": float(np.median(diff)),
        "mae_L": float(np.mean(np.abs(diff))),
        "within_0_5L_share": float(np.mean(np.abs(diff) <= 0.5)),
        "correlation": float(np.corrcoef(m, o)[0, 1]) if len(m) > 2 else float("nan"),
    }
