"""The twin layer (v2).

A two-parameter physiological model of the session:

    dD/dt  = UF(t)/60 - k_refill * D            D = plasma volume deficit (L)
    SBP(t) = a - beta_bp * D(t)                 beta_bp = mmHg lost per litre

Why only two parameters: NIBP is recorded roughly every 30 minutes. With that
sampling, a richer model is not identifiable -- adding a free time-trend term
makes beta_bp and the trend collinear and the fit becomes arbitrary. We choose
the two parameters that (a) are identifiable and (b) a nephrologist can name.

v2 changes (see docs/UPGRADE_LOG.md, measured on 4,015 held-out sessions):

1. **"Hold" continues the machine's programme, not a flat rate.** The hold
   profile continues the recent trend of the logged UF rate and stops when the
   prescription is met -- a real machine stops removing fluid at the goal, and
   the v1 projection kept draining past the goal for the whole horizon.
   Held-out nadir MAE 12.2 -> 9.5 mmHg; systematic bias +5.0 -> +1.6 mmHg;
   false crash-projections 3.7% -> 1.1%.
2. **The counterfactual engine sweeps, not just cards.** `taper_sweep` scores
   every taper fraction 0-100% and `min_effective_taper` returns the cheapest
   intervention whose predicted nadir stays above threshold.
3. **A thermal lever.** `cool` policy: dialysate temperature shifts the SBP
   path by `beta_T` mmHg per degree; the coefficient ships from the cohort fit
   (see scripts/fit_thermal.py) with the Cochrane range (3-6 mmHg/degC) as its
   sanity check.
4. **The uncertainty band is out-of-sample and clamped to physiology.** It is
   fitted on prior-session parameters only (the v1 band was fitted in-sample)
   and its lower edge can no longer render impossible numbers.
5. **Within-session reconciliation was tried and REVERTED.** Correcting the
   state against the current session's cuffs looked like the textbook twin
   move; on held-out sessions it degraded nadir MAE from 9.5 to 17+ mmHg --
   three to six noisy cuffs at a 30-minute cadence cannot identify a
   correction. Same identifiability lesson as v1's gamma term. The innovation
   (observed minus projected at the last cuff) survives as a display-only
   tracking diagnostic, never fed back into the projection.

`k_refill` is fitted per patient from their *earlier* sessions and shrunk toward
the population median. `beta_bp` likewise. The session intercept `a` is anchored
to the session itself, because baseline pressure varies day to day.

The counterfactual re-simulates the rest of the session under a different UF
policy. This is a within-policy-space simulation: 87% of real sessions already
taper ultrafiltration mid-session, so we are not proposing a new intervention --
we are choosing *when* to apply the one that already happens.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

# numpy 2.x renamed trapz -> trapezoid; keep both working
_trapz = getattr(np, "trapezoid", None) or np.trapz

# Population priors (HEMOBP). Per-session k is only identifiable down to
# ~0.1/h: on a 30-minute cuff cadence k and beta are collinear (k modulates
# the curvature of the deficit curve, and 4-6 cuffs cannot see curvature --
# when the grid floor was dropped to 0.02, 44% of session fits piled onto it).
# The grid floor of 0.10 sits just below the literature range: measured plasma
# refill in HD is 5.2 +/- 2.9 mL/min (~0.31 L/h), typical 0.12-0.36 L/h, up to
# ~0.8 L/h in volume-overloaded patients (Mitsides 2019, PMID 31288231).
POP_K_REFILL = 0.30      # 1/hour  (literature median ~0.31 L/h)
POP_BETA_BP = 19.6       # mmHg per litre
# Immediate refill fraction (v3): the share of removed volume that re-enters
# the plasma within minutes, before the slow k*D term acts. Measured plasma
# refill in HD runs at 4.2-7.2 mL/h/kg over the first hour and scales with the
# UF rate -- refill ~= 30-50% of removal early in the session (Wang,
# Kidney360 2023, 180,319 Crit-Line sessions). The forward projection applies
# dD/dt = (1-phi)*UF/60 - k*D. phi=0.45 cut held-out nadir MAE 9.59 -> 8.65 on
# the frozen benchmark but dropped crash-projection recall 0.371 -> 0.285
# (below the pre-registered 0.30 gate) and was DISCARDED; phi=0.30 -- the
# lower edge of the measured range -- is the shipped trade-off. Parameters
# (k, beta) stay identified on the base structure; phi enters the forward
# simulation only. A learned out-of-fold residual corrector was tried on top
# and made held-out MAE WORSE (lab evidence: research/twin_lab2.py).
POP_PHI = 0.30
# Thermal coefficient: mmHg of SBP per degree C of dialysate cooling. Cochrane
# (Tsujimoto 2019): fixed cooling 1-2.2 degC -> end-dialysis MAP +6.5 mmHg,
# i.e. ~+3-6 mmHg per degree. A direct within-patient fit on HEMOBP delivered
# temperatures came out at -0.9 +/- 1.0 mmHg/degC (scripts/fit_thermal.py) --
# the cohort's temperature variation is too small and too confounded with
# prescription practice to identify the effect, so the shipped coefficient is
# the conservative end of the RCT range, and the attempt is documented.
POP_BETA_T = 3.5
K_GRID = np.linspace(0.10, 1.5, 30)


@dataclass
class TwinParams:
    k_refill: float     # 1/hour, plasma refill rate
    beta_bp: float      # mmHg per litre of deficit
    beta_T: float = POP_BETA_T   # mmHg per degree C of dialysate temperature
    sbp0: float = 120.0  # session baseline SBP (mmHg)


POLICIES = {
    "hold":    {"label": "Hold current UF",         "uf_mult": 1.00, "pause_min": 0,  "bolus_L": 0.0},
    "taper25": {"label": "Taper UF by 25%",         "uf_mult": 0.75, "pause_min": 0,  "bolus_L": 0.0},
    "pause":   {"label": "Stop UF + 250 mL fluid",  "uf_mult": 0.00, "pause_min": 60, "bolus_L": 0.25},
    "cool10":  {"label": "Cool dialysate −1.0 °C",  "uf_mult": 1.00, "pause_min": 0,  "bolus_L": 0.0,
                "temp_delta_C": -1.0,
                "cost": "cold discomfort (shivering RR 8.3, Cochrane 2019); IDH rate ratio 0.67 (0.48-0.93, 2025 meta); not for patients who shiver"},
}
POLICIES["taper25"]["cost"] = "fluid left behind at session end"
POLICIES["pause"]["cost"] = "largest fluid deficit; saline bolus adds intake"
POLICIES["hold"]["cost"] = "highest crash risk"


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------
def deficit_curve(uf_lh: np.ndarray, k_refill: float, dt: float = 1.0,
                  phi: float = 0.0) -> np.ndarray:
    """Solve dD/dt = (1-phi)*UF/60 - (k/60) D on a uniform grid. Vectorised.

    phi = POP_PHI in projections; 0 when fitting the per-session parameters,
    which are identified under the base structure (see POP_PHI above).
    """
    a = float(np.clip(1.0 - k_refill * dt / 60.0, 0.0, 0.999999))
    x = np.asarray(uf_lh, dtype=float) * (1.0 - phi) * dt / 60.0
    return lfilter([1.0], [1.0, -a], x, zi=[0.0])[0]


def deficit_derivative(D: float, uf_lh: float, k_refill: float,
                       phi: float = 0.0) -> float:
    """dD/dt in L/min. UF is L/h and k is 1/h, so both terms need a /60."""
    return ((1.0 - phi) * float(uf_lh) / 60.0
            - float(k_refill) * float(D) / 60.0)


def deficit_path(uf_lh: np.ndarray, k_refill: float, phi: float = 0.0,
                 d0: float = 0.0, dt: float = 1.0) -> np.ndarray:
    """State at the start of each minute, including the initial state.

    Unlike `deficit_curve` (which starts from zero and is used for fitting),
    this preserves an existing deficit: with UF=0 and bolus=0 the path decays
    by the stated -kD term instead of staying flat or re-accumulating.
    """
    uf = np.asarray(uf_lh, dtype=float)
    if not np.isfinite(k_refill) or not np.isfinite(phi):
        return np.full(len(uf) + 1, np.nan)
    a = float(np.clip(1.0 - float(k_refill) * dt / 60.0, 0.0, 0.999999))
    x = (1.0 - float(phi)) * uf * dt / 60.0
    out = np.empty(len(uf) + 1, dtype=float)
    out[0] = float(d0)
    d = float(d0)
    for i in range(len(uf)):
        d = a * d + x[i]
        out[i + 1] = d
    return out


def last_observation(ts, vals, t: float) -> tuple[float, int]:
    """Last observed value at or before t; (NaN, -1) if none."""
    ts = np.asarray(ts, dtype=float)
    vals = np.asarray(vals, dtype=float)
    if len(ts) == 0 or not np.isfinite(t):
        return float("nan"), -1
    idx = int(np.searchsorted(ts, float(t), side="right") - 1)
    if idx < 0:
        return float("nan"), -1
    return float(vals[idx]), idx


def causal_uf_grid(d: dict, t_now: float, dt: float = 1.0):
    """LOCF UF grid from session start to t_now using only records <= t_now.

    Returns (grid, uf, coverage). `coverage` is false when the log does not
    start at session start (first record after minute 1) or when any minute in
    the requested interval has no known rate. Times before the first record are
    NaN, never extrapolated from the future.
    """
    mt = np.asarray(d.get("mt", []), dtype=float)
    muf = np.asarray(d.get("muf", []), dtype=float)
    t = float(t_now)
    if len(mt) == 0 or not np.isfinite(t) or t < 0:
        return np.array([]), np.array([]), False
    m = mt <= t
    if not m.any():
        return np.array([]), np.array([]), False
    mtp, mufp = mt[m], muf[m]
    tmax = float(np.floor(t))
    grid = np.arange(0.0, tmax + dt, dt)
    idx = np.searchsorted(mtp, grid, side="right") - 1
    uf = np.full(len(grid), np.nan)
    valid = idx >= 0
    uf[valid] = mufp[idx[valid]]
    coverage = bool(mtp[0] <= 1.0 and np.isfinite(uf).all())
    return grid, uf, coverage


def causal_uf_state(d: dict, t_now: float) -> dict:
    """Causal UF state at t_now: last-known rate, cumulative removal, grid."""
    grid, uf, coverage = causal_uf_grid(d, t_now)
    if len(grid) == 0:
        return {"grid": grid, "uf": uf, "coverage": False,
                "uf_now": float("nan"), "cum_now": float("nan")}
    return {
        "grid": grid,
        "uf": uf,
        "coverage": coverage,
        "uf_now": float(uf[-1]) if coverage else float("nan"),
        "cum_now": float(_trapz(uf, grid) / 60.0) if coverage else float("nan"),
    }


def twin_state_at(d: dict, t_now: float, k_refill: float,
                  phi: float = POP_PHI) -> dict:
    """Causal twin state at t_now; D_now is the state at the anchor."""
    st = causal_uf_state(d, t_now)
    D_now = float("nan")
    if st["coverage"] and np.isfinite(k_refill):
        # The state at t is after t one-minute inputs; grid has t+1 points.
        D_now = float(deficit_path(st["uf"][:-1], k_refill, phi=phi,
                                   d0=0.0)[-1])
    return {**st, "D_now": D_now}


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
        k_grid = K_GRID

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
# Population and per-patient parameters (with a fit cache)
# ---------------------------------------------------------------------------
def fit_all_sessions(store: dict, session_ids) -> dict:
    """Fit every session once. Patient history = medians over cached fits."""
    fits: dict[str, dict] = {}
    for sid in session_ids:
        d = store.get(sid)
        if d is None or len(d["et"]) < 6:
            continue
        fits[sid] = fit_session(d)
    return fits


def fit_sessions_batch(store: dict, session_ids, progress_every: int = 25000) -> dict:
    """fit_session for many sessions, vectorised over the k grid.

    Same grid, same OLS, same beta >= 0 constraint as fit_session -- the OLS
    is solved in closed form instead of lstsq, and the 30 deficit curves are
    integrated with one lfilter call per k. Roughly an order of magnitude
    faster, which is what makes the full-cohort fit (205k sessions) a
    minutes-scale step for the feature builder. Results are cached by the
    caller; FITS-style caching must be invalidated if fit_session semantics
    change.
    """
    out: dict[str, dict] = {}
    n_done = 0
    for sid in session_ids:
        d = store.get(sid)
        if d is None or len(d["et"]) < 6:
            continue
        et, es = d["et"], d["es"]
        grid, uf = _grid_for_session(d, t_end=float(et.max()))
        # D(k, t) for every grid k at once
        a = np.clip(1.0 - K_GRID / 60.0, 0.0, 0.999999)
        D = np.empty((len(K_GRID), len(uf)))
        for ki, ak in enumerate(a):
            D[ki] = lfilter([1.0], [1.0, -ak], uf / 60.0, zi=[0.0])[0]
        d_at = _interp_rows(grid, D, et)
        best = None
        if np.ptp(d_at, axis=1).max() > 1e-6:
            x = -d_at                                   # regressor
            xm = x.mean(axis=1, keepdims=True)
            ym = es.mean()
            sxx = ((x - xm) ** 2).sum(axis=1)
            sxy = ((x - xm) * (es - ym)).sum(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                b = np.where(sxx > 1e-9, sxy / np.maximum(sxx, 1e-12), np.nan)
            aa = ym - b * xm[:, 0]
            pred = aa[:, None] + b[:, None] * x
            rmse = np.sqrt(((es - pred) ** 2).mean(axis=1))
            ok = (b >= 0) & np.isfinite(b) & (np.ptp(d_at, axis=1) >= 1e-6)
            if ok.any():
                idx = np.argmin(np.where(ok, rmse, np.inf))
                if np.isfinite(rmse[idx]):
                    best = {"k": float(K_GRID[idx]), "beta": float(b[idx]),
                            "sbp0": float(aa[idx]), "rmse": float(rmse[idx])}
        out[sid] = best if best is not None else {
            "k": np.nan, "beta": np.nan, "sbp0": np.nan, "rmse": np.nan}
        n_done += 1
        if progress_every and n_done % progress_every == 0:
            print(f"    fitted {n_done:,} sessions", flush=True)
    return out


def fit_session_causal(d: dict) -> dict:
    """Fit (k, beta, sbp0) on a LOCF UF grid, not linear interpolation.

    Only observations up to the last validated machine record are used. A
    session whose machine log does not cover session start is not fit.
    """
    et = np.asarray(d.get("et", []), dtype=float)
    es = np.asarray(d.get("es", []), dtype=float)
    mt = np.asarray(d.get("mt", []), dtype=float)
    if len(et) < 4 or len(mt) < 1:
        return _nan_fit()
    t_end = min(float(et.max()), float(mt.max()))
    et_used = et[et <= t_end]
    es_used = es[et <= t_end]
    if len(et_used) < 4:
        return _nan_fit()
    grid, uf, coverage = causal_uf_grid(d, t_end)
    if not coverage or len(uf) < 2:
        return _nan_fit()
    best = None
    for k in K_GRID:
        D = deficit_curve(uf, k)
        d_at = np.interp(et_used, grid, D)
        if np.ptp(d_at) < 1e-6:
            continue
        X = np.column_stack([np.ones_like(d_at), -d_at])
        coef, *_ = np.linalg.lstsq(X, es_used, rcond=None)
        a, b = float(coef[0]), float(coef[1])
        if b < 0:
            continue
        pred = a - b * d_at
        rmse = float(np.sqrt(np.mean((es_used - pred) ** 2)))
        if best is None or rmse < best["rmse"]:
            best = {"k": float(k), "beta": b, "sbp0": a, "rmse": rmse}
    if best is None:
        return _nan_fit()
    return {
        **best,
        "feasible": True,
        "n_cuffs": int(len(et_used)),
        "t_end": float(t_end),
        "k_at_floor": bool(np.isclose(best["k"], K_GRID[0])),
        "k_at_ceiling": bool(np.isclose(best["k"], K_GRID[-1])),
        "beta_zero": bool(best["beta"] <= 1e-9),
    }


def _fit_one_causal(d: dict, a_all: np.ndarray, min_cuffs: int = 6) -> dict:
    """One causal-LOCF per-session fit, vectorised over the k grid."""
    et = np.asarray(d.get("et", []), dtype=float)
    es = np.asarray(d.get("es", []), dtype=float)
    mt = np.asarray(d.get("mt", []), dtype=float)
    if len(et) < min_cuffs or len(mt) < 1:
        return _nan_fit()
    t_end = min(float(et.max()), float(mt.max()))
    et_used = et[et <= t_end]
    es_used = es[et <= t_end]
    if len(et_used) < min(4, min_cuffs):
        return _nan_fit()
    grid, uf, coverage = causal_uf_grid(d, t_end)
    if not coverage or len(uf) < 2:
        return _nan_fit()
    D = np.empty((len(K_GRID), len(uf)))
    for ki, ak in enumerate(a_all):
        D[ki] = lfilter([1.0], [1.0, -ak], uf / 60.0, zi=[0.0])[0]
    d_at = _interp_rows(grid, D, et_used)
    best = None
    if np.ptp(d_at, axis=1).max() > 1e-6:
        x = -d_at
        xm = x.mean(axis=1, keepdims=True)
        ym = es_used.mean()
        sxx = ((x - xm) ** 2).sum(axis=1)
        sxy = ((x - xm) * (es_used - ym)).sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            b = np.where(sxx > 1e-9, sxy / np.maximum(sxx, 1e-12), np.nan)
        aa = ym - b * xm[:, 0]
        pred = aa[:, None] + b[:, None] * x
        rmse = np.sqrt(((es_used - pred) ** 2).mean(axis=1))
        ok = (b >= 0) & np.isfinite(b) & (np.ptp(d_at, axis=1) >= 1e-6)
        if ok.any():
            idx = int(np.argmin(np.where(ok, rmse, np.inf)))
            if np.isfinite(rmse[idx]):
                best = {"k": float(K_GRID[idx]), "beta": float(b[idx]),
                        "sbp0": float(aa[idx]), "rmse": float(rmse[idx]),
                        "feasible": True, "n_cuffs": int(len(et_used)),
                        "t_end": float(t_end),
                        "k_at_floor": bool(np.isclose(K_GRID[idx], K_GRID[0])),
                        "k_at_ceiling": bool(np.isclose(K_GRID[idx], K_GRID[-1])),
                        "beta_zero": bool(b[idx] <= 1e-9)}
    return best if best is not None else _nan_fit()


def fit_sessions_batch_causal(store: dict, session_ids,
                              progress_every: int = 25000) -> dict:
    """Vectorised causal-LOCF version of fit_sessions_batch for Task 01."""
    out: dict[str, dict] = {}
    n_done = 0
    a_all = np.clip(1.0 - K_GRID / 60.0, 0.0, 0.999999)
    for sid in session_ids:
        d = store.get(sid)
        if d is None:
            continue
        out[sid] = _fit_one_causal(d, a_all)
        n_done += 1
        if progress_every and n_done % progress_every == 0:
            print(f"    causal fits {n_done:,} sessions", flush=True)
    return out


def _nan_fit() -> dict:
    return {"k": np.nan, "beta": np.nan, "sbp0": np.nan, "rmse": np.nan,
            "feasible": False, "n_cuffs": 0, "t_end": np.nan,
            "k_at_floor": False, "k_at_ceiling": False, "beta_zero": False}


def _interp_rows(grid: np.ndarray, D: np.ndarray, et: np.ndarray) -> np.ndarray:
    """np.interp row-wise: (K, T) curves sampled at et -> (K, len(et))."""
    out = np.empty((D.shape[0], len(et)))
    for i in range(D.shape[0]):
        out[i] = np.interp(et, grid, D[i])
    return out


def _median_finite(vals: list[float], fallback: float) -> float:
    v = np.array([x for x in vals if np.isfinite(x)], dtype=float)
    return float(np.median(v)) if len(v) else fallback


def fit_population(store: dict, session_ids, min_events: int = 6,
                   fits: dict | None = None) -> dict:
    if fits is None:
        fits = fit_all_sessions(store, session_ids)
    ks, betas = [], []
    for sid in session_ids:
        f = fits.get(sid)
        if f is None or len(store[sid]["et"]) < min_events:
            continue
        if np.isfinite(f["k"]) and np.isfinite(f["beta"]):
            ks.append(f["k"])
            betas.append(f["beta"])
    if not ks:
        return {"k_refill": POP_K_REFILL, "beta_bp": POP_BETA_BP, "n": 0}
    return {
        "k_refill": float(np.median(ks)),
        "beta_bp": float(np.median(betas)),
        "k_iqr": [float(np.percentile(ks, 25)), float(np.percentile(ks, 75))],
        "beta_iqr": [float(np.percentile(betas, 25)), float(np.percentile(betas, 75))],
        "n": len(ks),
    }


def fit_patient(store: dict, pid: str, sessions: list[str], pop: dict,
                shrink: float = 5.0, fits: dict | None = None) -> dict:
    """Median of prior sessions, shrunk toward the population median."""
    if fits is None:
        fits = fit_all_sessions(store, sessions)
    ks, betas = [], []
    for sid in sessions:
        f = fits.get(sid)
        if f is None:
            d = store.get(sid)
            if d is None or len(d["et"]) < 6:
                continue
            f = fit_session(d)
        if np.isfinite(f["k"]) and np.isfinite(f["beta"]):
            ks.append(f["k"])
            betas.append(f["beta"])
    n = len(ks)
    k_pat = _median_finite(ks, pop.get("k_refill", POP_K_REFILL))
    b_pat = _median_finite(betas, pop.get("beta_bp", POP_BETA_BP))
    w = n / (n + shrink)
    return {
        "k_refill": w * k_pat + (1 - w) * pop.get("k_refill", POP_K_REFILL),
        "beta_bp": w * b_pat + (1 - w) * pop.get("beta_bp", POP_BETA_BP),
        "beta_T": POP_BETA_T,
        "n_prior_sessions": int(n),
    }


# ---------------------------------------------------------------------------
# Tracking diagnostic (display only -- never fed back into the projection)
# ---------------------------------------------------------------------------
def innovation(d: dict, t_now: float, params: dict) -> dict:
    """Observed minus projected SBP at the most recent cuff (display only).

    Uses only cuffs at or before t_now and the causal UF grid. Deliberately
    never fed back into the projection: at a 30-minute cuff cadence the
    correction is not identifiable (it degraded held-out nadir MAE from 9.5
    to 17+ mmHg in the v2 benchmark).
    """
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    m = et <= float(t_now)
    if not m.any():
        return {"innovation": 0.0, "n_used": 0}
    state = twin_state_at(d, t_now, params.get("k_refill", np.nan))
    if not np.isfinite(state["D_now"]) or not np.isfinite(params.get("beta_bp", np.nan)):
        return {"innovation": 0.0, "n_used": int(m.sum())}
    grid, uf, coverage = causal_uf_grid(d, t_now)
    if not coverage:
        return {"innovation": 0.0, "n_used": int(m.sum())}
    D_curve = deficit_path(uf[:-1], params["k_refill"], phi=POP_PHI, d0=0.0)
    D_at = np.interp(et[m], grid, D_curve)
    a_eff = float(es[m][0]) + float(params["beta_bp"]) * float(D_at[0])
    pred = a_eff - float(params["beta_bp"]) * D_at
    return {
        "innovation": float(es[m][-1] - pred[-1]),
        "n_used": int(m.sum()),
    }


# ---------------------------------------------------------------------------
# The hold profile: the machine's programme continues, the goal is respected
# ---------------------------------------------------------------------------
def hold_profile(grid: np.ndarray, uf: np.ndarray, i0: int,
                 t_now: float, horizon: int, goal: float | None,
                 cum_now: float, uf_mult: float = 1.0,
                 trend_min: float = 45.0) -> np.ndarray:
    """UF rate (L/h) for the next `horizon` minutes under "keep the machine".

    Continues the LOCF trend of the last `trend_min` known minutes (machine
    programmes are constant or linear), scaled by `uf_mult`, and stops the
    moment the prescription is met. It never uses a future session end: the
    goal and cumulative removal are known at the anchor.
    """
    n = int(max(horizon, 1)) + 1
    j1 = int(np.searchsorted(grid, max(float(grid[i0]) - trend_min, 0.0)))
    j1 = min(j1, i0)
    slope = ((float(uf[i0]) - float(uf[j1])) /
             max(float(grid[i0]) - float(grid[j1]), 1e-9)) * uf_mult
    t_fut = np.arange(n, dtype=float)
    u = float(uf[i0]) * uf_mult + slope * t_fut
    u = np.clip(u, 0.0, 4.0)
    if goal is not None and np.isfinite(goal):
        remaining = max(float(goal) - float(cum_now), 0.0)
        cum = np.cumsum(u) / 60.0
        over = cum > remaining
        if over.any():
            u[int(np.argmax(over)):] = 0.0
    return u


# ---------------------------------------------------------------------------
# Counterfactual
# ---------------------------------------------------------------------------
def simulate_policy(d: dict, t_now: float, params: dict, policy: dict,
                    horizon: int = 60,
                    planned_duration: float | None = None) -> dict:
    """Simulate one UF policy from the causal state at t_now.

    The projection starts from the existing deficit `D_now`, so a pause makes
    the deficit decay by `-kD` rather than staying flat. No policy resumes UF
    at an unreported goal-chasing rate: after a pause the rate stays zero
    unless the caller supplies an explicit `resume_rate`. Fluid left behind is
    only computed when a causal `planned_duration` is supplied; observed
    session end is never used here.
    """
    label = policy.get("label", policy.get("policy", "policy"))
    out = {
        "policy": policy.get("policy"),
        "label": label,
        "cost": policy.get("cost"),
        "feasible": False,
        "reason": None,
        "nadir": float("nan"),
        "time_to_nadir_min": None,
        "fluid_left_L": None,
        "fluid_removed_L": None,
        "uf_rate_Lh": None,
        "path": [],
        "D_now": float("nan"),
        "D_path": [],
        "uf_path": [],
        "temperature_delta_C": float(policy.get("temp_delta_C", 0.0) or 0.0),
    }
    state = causal_uf_state(d, t_now)
    if not state["coverage"] or not np.isfinite(state["uf_now"]):
        out["reason"] = "UF log does not cover session start"
        return out
    k_refill = float(params.get("k_refill", np.nan))
    beta_bp = float(params.get("beta_bp", np.nan))
    if not np.isfinite(k_refill) or not np.isfinite(beta_bp):
        out["reason"] = "patient twin parameters unavailable"
        return out

    grid, uf = state["grid"], state["uf"]
    i0 = len(grid) - 1
    goal = d.get("goal")
    goal = float(goal) if goal is not None and np.isfinite(goal) else None
    cum_now = float(state["cum_now"])
    pause_min = int(policy.get("pause_min", 0) or 0)
    uf_mult = float(policy.get("uf_mult", 1.0))

    def _profile(n_min: int) -> np.ndarray:
        if pause_min >= n_min:
            return np.zeros(n_min + 1)
        u = hold_profile(grid, uf, i0, t_now, n_min, goal, cum_now,
                         uf_mult=uf_mult)
        if pause_min > 0:
            u[:pause_min] = 0.0
            resume = policy.get("resume_rate")
            if resume is None:
                u[pause_min:] = 0.0   # no unreported auto-resume
            else:
                u[pause_min:] = float(resume)
        return u

    u = _profile(int(horizon))
    D_now = float(deficit_path(uf[:-1], k_refill, phi=POP_PHI, d0=0.0)[-1])
    if not np.isfinite(D_now):
        out["reason"] = "twin state unavailable"
        return out
    D_path = deficit_path(u[:-1], k_refill, phi=POP_PHI, d0=D_now)
    bolus = float(policy.get("bolus_L", 0.0) or 0.0)
    D_eff = np.clip(D_path - bolus, 0.0, None)

    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    m = et <= float(t_now)
    if not m.any():
        out["reason"] = "no observed cuff at or before anchor"
        return out
    sbp_now = float(es[m][-1])
    sbp_path = sbp_now - beta_bp * (D_eff - D_now)
    temp = float(policy.get("temp_delta_C", 0.0) or 0.0)
    if temp:
        beta_T = float(params.get("beta_T", POP_BETA_T))
        ramp = np.clip(np.arange(len(sbp_path)) / 10.0, 0.0, 1.0)
        # A negative temperature delta (cooling) must RAISE SBP.
        sbp_path = sbp_path - beta_T * temp * ramp

    j = int(np.argmin(sbp_path))
    nadir = float(sbp_path[j])
    fluid_removed = float(_trapz(u, np.arange(len(u))) / 60.0)
    fluid_left = None
    if (planned_duration is not None and np.isfinite(planned_duration)
            and planned_duration > t_now):
        rem = int(max(planned_duration - t_now, 1))
        u_full = _profile(rem)
        removal_full = float(_trapz(u_full, np.arange(len(u_full))) / 60.0)
        if goal is not None:
            fluid_left = float(max(goal - cum_now - removal_full, 0.0))

    out.update({
        "feasible": True,
        "nadir": round(nadir, 1),
        "time_to_nadir_min": float(j),
        "fluid_left_L": round(fluid_left, 2) if fluid_left is not None else None,
        "fluid_removed_L": round(fluid_removed, 2),
        "uf_rate_Lh": round(float(u[0]), 2),
        "path": [
            {"t": round(float(t_now + i), 1), "sbp": round(float(s), 1)}
            for i, s in enumerate(sbp_path) if i % 5 == 0
        ],
        "sbp_path": sbp_path,
        "D_now": round(float(D_now), 4),
        "D_path": D_eff,
        "uf_path": u,
    })
    return out


def counterfactual(d: dict, t_now: float, params: dict,
                   policies: dict | None = None,
                   horizon_min: int = 60,
                   planned_duration: float | None = None) -> list[dict]:
    """Re-simulate the next `horizon_min` minutes under each UF policy."""
    policies = policies or POLICIES
    out = []
    for key, pol in policies.items():
        r = simulate_policy(d, t_now, params, pol, horizon=horizon_min,
                            planned_duration=planned_duration)
        # Raw arrays are for research callers; the console bundle must stay
        # JSON-serialisable.
        r.pop("sbp_path", None)
        r.pop("D_path", None)
        r.pop("uf_path", None)
        r["policy"] = key
        r["label"] = pol["label"]
        r["cost"] = pol.get("cost")
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Policy sweep: the frontier, and the minimum effective taper
# ---------------------------------------------------------------------------
def taper_sweep(d: dict, t_now: float, params: dict,
                fracs: np.ndarray | None = None,
                horizon_min: int = 60,
                planned_duration: float | None = None) -> list[dict]:
    """Score every taper fraction from 0 to 100% over the next hour.

    The frontier is a simulation, not a validated recommendation. Fluid left
    behind is only available with a causal planned duration.
    """
    if fracs is None:
        fracs = np.arange(0.0, 1.0001, 0.05)
    rows = []
    for f in fracs:
        f = float(np.clip(f, 0.0, 1.0))
        r = simulate_policy(
            d, t_now, params,
            {"uf_mult": 1.0 - f, "label": f"Taper {100*f:.0f}%"},
            horizon=horizon_min, planned_duration=planned_duration)
        rows.append({
            "taper_frac": round(f, 2),
            "nadir": r["nadir"] if r["feasible"] else float("nan"),
            "fluid_left_L": r["fluid_left_L"],
            "feasible": bool(r["feasible"]),
        })
    return rows


def min_effective_taper(sweep: list[dict], band: dict | None = None,
                        target: float = 90.0,
                        use_band: bool = True) -> dict | None:
    """The cheapest taper whose predicted nadir clears the target.

    With a band, the *lower edge* of the nadir interval must clear the target
    (a conservative recommendation); without one, the point estimate must.
    Returns None when no taper in the sweep clears it. Callers must not
    silently fall back to a point estimate.
    """
    lo = (band or {}).get("lo")
    for row in sweep:
        if not np.isfinite(row.get("nadir", float("nan"))):
            continue
        nadir_check = row["nadir"] + (lo if (use_band and lo is not None) else 0.0)
        if nadir_check >= target:
            return row
    return None


# ---------------------------------------------------------------------------
# Forecast for the chart (hold policy)
# ---------------------------------------------------------------------------
def forecast_path(d: dict, t_now: float, params: dict, minutes: int = 60,
                  planned_duration: float | None = None) -> list[dict]:
    """Hold-policy forecast for the chart, from the causal state at t_now."""
    r = simulate_policy(d, t_now, params, POLICIES["hold"], horizon=minutes,
                        planned_duration=planned_duration)
    return r["path"]


def fit_population_for_fold(store: dict, fit_pids, fits: dict | None = None) -> dict:
    """Population twin prior from fit-role patients of one outer fold only."""
    keep = {str(p) for p in fit_pids}
    sids = [sid for sid in store if sid.rsplit("_", 1)[0] in keep]
    return fit_population(store, sids, fits=fits)


def twin_state_table(store: dict, pop: dict | None = None,
                     fit_pids=None, fits: dict | None = None) -> "pd.DataFrame":
    """Per-session patient parameters from STRICTLY EARLIER sessions.

    The table the event model's twin-state features consume (the "digital
    thread"): for every session, the median of the patient's prior session
    fits shrunk to the population prior -- the same empirical-Bayes rule the
    console uses live. Fits come from fit_sessions_batch (verified equivalent
    to fit_session).

    `pop` must be the fit-role population prior for the relevant outer fold.
    If it is omitted, the prior is recomputed from `fit_pids` when supplied;
    otherwise a legacy all-session prior is used with a warning. Corrected
    feature builders must pass `pop` or `fit_pids`.
    """
    import pandas as pd

    if fits is None:
        fits = fit_sessions_batch(store, list(store.keys()))
    by_pid: dict[str, list[str]] = {}
    for sid in store:
        by_pid.setdefault(sid.rsplit("_", 1)[0], []).append(sid)

    if pop is None:
        if fit_pids is not None:
            pop = fit_population_for_fold(store, fit_pids, fits=fits)
        else:
            print("  [warning] twin_state_table without a fit-population prior "
                  "(legacy all-session prior); corrected paths must pass pop",
                  flush=True)
            k_all = [f["k"] for f in fits.values() if np.isfinite(f["k"])]
            b_all = [f["beta"] for f in fits.values() if np.isfinite(f["beta"])]
            pop = {
                "k_refill": float(np.median(k_all)) if k_all else POP_K_REFILL,
                "beta_bp": float(np.median(b_all)) if b_all else POP_BETA_BP,
            }
    pop_k = float(pop["k_refill"])
    pop_b = float(pop["beta_bp"])

    rows = []
    for pid, sids in by_pid.items():
        sids.sort(key=lambda s: s.rsplit("_", 1)[1])
        prior: list[tuple[float, float]] = []
        for sid in sids:
            f = fits.get(sid)
            if f is not None and np.isfinite(f["k"]) and prior:
                n = len(prior)
                w = n / (n + 5.0)
                k_med = float(np.median([p[0] for p in prior]))
                b_med = float(np.median([p[1] for p in prior]))
                rows.append((sid, w * k_med + (1 - w) * pop_k,
                             w * b_med + (1 - w) * pop_b, n))
            else:
                rows.append((sid, pop_k, pop_b, len(prior)))
            if f is not None and np.isfinite(f["k"]):
                prior.append((f["k"], f["beta"]))
    return pd.DataFrame(rows, columns=["session_id", "k_pat", "beta_pat", "n_prior"])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def residual_quantiles(store: dict, session_ids, pop: dict,
                       q=(0.05, 0.95), fits: dict | None = None) -> dict:
    """How wrong is the hold-policy nadir on sessions we did not fit on?

    Out-of-sample by construction: parameters come from the patient's STRICTLY
    EARLIER sessions -- the same rule the console uses live. (The v1 band was
    fitted in-sample: its parameters had seen the second half of the session
    they predicted.) A stratified band by prior-session count was also tried
    and dropped: on held-out data the newer patients were not the noisier
    ones, so a conditional band would have been decoration, not information.
    """
    by_pid: dict[str, list[str]] = {}
    for sid in session_ids:
        d = store.get(sid)
        if d is None or len(d["et"]) < 8:
            continue
        by_pid.setdefault(sid.rsplit("_", 1)[0], []).append(sid)
    for pid in by_pid:
        by_pid[pid].sort(key=lambda s: s.rsplit("_", 1)[1])

    if fits is None:
        fits = fit_all_sessions(store, [s for lst in by_pid.values() for s in lst])

    res: list[float] = []
    for pid, sids in by_pid.items():
        prior_fits: list[dict] = []
        for sid in sids:
            d = store[sid]
            ks = [f["k"] for f in prior_fits if np.isfinite(f["k"])]
            if len(ks) >= 1:
                k_pat = _median_finite([f["k"] for f in prior_fits], pop["k_refill"])
                b_pat = _median_finite([f["beta"] for f in prior_fits], pop["beta_bp"])
                w = len(ks) / (len(ks) + 5.0)
                params = {"k_refill": w * k_pat + (1 - w) * pop["k_refill"],
                          "beta_bp": w * b_pat + (1 - w) * pop["beta_bp"]}
            else:
                params = {"k_refill": pop["k_refill"], "beta_bp": pop["beta_bp"]}

            dur = float(d["et"].max())
            t_mid = max(dur * 0.40, 30.0)
            after = d["es"][(d["et"] > t_mid) & (d["et"] <= t_mid + 60.0)]
            if len(after):
                cf = counterfactual(d, t_mid, params,
                                    policies={"hold": POLICIES["hold"]})
                res.append(float(after.min()) - cf[0]["nadir"])

            f = fits.get(sid)
            if f is None and len(d["et"]) >= 6:
                f = fit_session(d)
                fits[sid] = f
            if f is not None and np.isfinite(f["k"]):
                prior_fits.append(f)

    if not res:
        return {"lo": -15.0, "hi": 15.0, "n": 0}
    arr = np.array(res)
    return {
        "lo": float(np.quantile(arr, q[0])),
        "hi": float(np.quantile(arr, q[1])),
        "median": float(np.median(arr)),
        "mae": float(np.mean(np.abs(arr))),
        "n": int(len(arr)),
    }


def volume_check(store: dict, session_ids) -> dict:
    """Machine-integrated UF vs the measured pre/post weight difference.

    This is a data-integrity check (mass balance between the machine's fluid
    accounting and the scale), not a validation of the twin's physiological
    state; the state itself is validated by the held-out nadir error above.
    """
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
