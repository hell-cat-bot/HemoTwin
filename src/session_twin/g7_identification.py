"""G7 non-reactive UF step-down identification utilities.

Pure, data-free functions for the pre-registered experiment in
`artifacts/physiotwin_v4/g7_protocol.md`. Events are selected using only
pre-event data; outcomes are attached afterwards and never used for inclusion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from src.physiotwin_v4 import (
    PhysioParamsV4, integrate_pre_anchor, params_to_batch,
    session_uf_grid, simulate_branch_batch,
)

HORIZONS: tuple[tuple[int, float], ...] = ((15, 10.0), (30, 12.5), (45, 15.0))
HORIZON_MINUTES = tuple(h for h, _ in HORIZONS)
DOSE_BAND = (0.20, 0.80)
DOSE_UNIT = 0.25
STABILITY_WINDOW = 30.0
LAST_CUFF_MAX_AGE = 15.0


@dataclass
class Event:
    session_id: str
    pid: str
    fold: int
    t_anchor: float | None
    t_e: float
    u_prev: float
    u_new: float
    dose_l_h: float
    dose_units: float
    held_until: float
    sbp_now: float
    sbp_min: float
    slope: float
    last_change: float
    n_cuffs: int
    cum_uf_l: float
    oh0_l: float
    deltas: dict[int, float | None] = field(default_factory=dict)
    pre_change: float | None = None
    dh: dict[int, float] = field(default_factory=dict)
    is_stable: bool = False
    is_e1a: bool = False
    anchor_aligned: bool = False


@dataclass
class Control:
    session_id: str
    pid: str
    fold: int
    t_c: float
    sbp_now: float
    sbp_min: float
    slope: float
    last_change: float
    n_cuffs: int
    cum_uf_l: float
    oh0_l: float
    deltas: dict[int, float | None] = field(default_factory=dict)
    pre_change: float | None = None


def _finite_arrays(et, es):
    et = np.asarray(et, dtype=float)
    es = np.asarray(es, dtype=float)
    ok = np.isfinite(et) & np.isfinite(es)
    et, es = et[ok], es[ok]
    order = np.argsort(et, kind="stable")
    return et[order], es[order]


def session_end(d: Mapping) -> float:
    vals = []
    for key in ("et", "mt"):
        arr = np.asarray(d.get(key, []), dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr):
            vals.append(float(arr.max()))
    return max(vals) if vals else float("nan")


def dedupe_machine(mt, muf) -> tuple[np.ndarray, np.ndarray]:
    mt = np.asarray(mt, dtype=float)
    muf = np.asarray(muf, dtype=float)
    ok = np.isfinite(mt) & np.isfinite(muf)
    mt, muf = mt[ok], muf[ok]
    if len(mt) == 0:
        return mt, muf
    order = np.argsort(mt, kind="stable")
    mt, muf = mt[order], muf[order]
    keep = np.ones(len(mt), dtype=bool)
    for i in range(len(mt) - 2, -1, -1):
        if mt[i] == mt[i + 1]:
            keep[i] = False
    return mt[keep], muf[keep]


def uf_steps(mt, muf, end_min: float) -> list[dict]:
    """Machine UF changes with the time the new rate leaves +/-0.05 L/h."""
    mt, muf = dedupe_machine(mt, muf)
    if len(mt) < 2 or not np.isfinite(end_min):
        return []
    steps = []
    for i in range(1, len(mt)):
        new = float(muf[i])
        held_until = float(end_min)
        for j in range(i + 1, len(mt)):
            if abs(float(muf[j]) - new) > 0.05:
                held_until = float(mt[j])
                break
        if held_until <= mt[i]:
            continue
        steps.append({
            "t": float(mt[i]),
            "prev": float(muf[i - 1]),
            "new": new,
            "held_until": held_until,
        })
    return steps


def _slope_per_hour(t: np.ndarray, s: np.ndarray) -> float:
    if len(t) < 2 or t[-1] <= t[0]:
        return 0.0
    return float(np.polyfit(t, s, 1)[0] * 60.0)


def pre_stability(et, es, t_e: float, window: float = STABILITY_WINDOW,
                  sbp_level: float = 115.0, sbp_floor: float = 110.0,
                  last_drop: float = -3.0,
                  slope_floor: float = -4.0) -> dict | None:
    """Pre-event stability using only cuffs at or before t_e."""
    et, es = _finite_arrays(et, es)
    if len(et) == 0:
        return None
    m = (et >= t_e - window) & (et <= t_e)
    if int(m.sum()) < 2:
        return None
    t, s = et[m], es[m]
    if t_e - t[-1] > LAST_CUFF_MAX_AGE:
        return None
    sbp_now = float(s[-1])
    sbp_min = float(s.min())
    last_change = float(s[-1] - s[-2])
    slope = _slope_per_hour(t, s)
    ok = (sbp_now >= sbp_level and sbp_min >= sbp_floor
          and last_change >= last_drop and slope >= slope_floor)
    return {
        "ok": bool(ok),
        "t_now": float(t[-1]),
        "sbp_now": sbp_now,
        "sbp_min": sbp_min,
        "last_change": last_change,
        "slope": slope,
        "n_cuffs": int(len(t)),
    }


def nearest_cuff(et, es, target: float, tol: float):
    et, es = _finite_arrays(et, es)
    if len(et) == 0:
        return None
    j = int(np.argmin(np.abs(et - target)))
    if abs(float(et[j]) - float(target)) <= float(tol):
        return float(et[j]), float(es[j])
    return None


def outcome_deltas(et, es, t_e: float, sbp_now: float,
                   held_until: float, t_anchor: float | None,
                   held_min: int = 30) -> dict[int, float | None]:
    out: dict[int, float | None] = {}
    for h, tol in HORIZONS:
        if h > held_min:
            out[h] = None
            continue
        if t_anchor is not None and t_e + h > t_anchor + 1e-9:
            out[h] = None
            continue
        if held_until - t_e < h - 1e-9:
            out[h] = None
            continue
        c = nearest_cuff(et, es, t_e + h, tol)
        out[h] = None if c is None else float(c[1] - sbp_now)
    return out


def pre_change(et, es, t_e: float, sbp_now: float) -> float | None:
    c = nearest_cuff(et, es, t_e - STABILITY_WINDOW, 10.0)
    return None if c is None else float(sbp_now - c[1])


def cumulative_uf(d: Mapping, t_e: float) -> float:
    grid = session_uf_grid(d, max(0.0, float(t_e)))
    return float(np.sum(grid) / 60.0)


def session_oh0(d: Mapping) -> float:
    try:
        pre = float(d.get("pre", np.nan))
        dry = float(d.get("dry", np.nan))
    except (TypeError, ValueError):
        return 0.5
    if np.isfinite(pre) and np.isfinite(dry) and pre > dry:
        return float(np.clip(pre - dry, 0.0, 6.0))
    return 0.5


def scan_step_events(d: Mapping, session_id: str, pid: str, fold: int,
                     t_anchor: float | None,
                     min_dose: float = DOSE_BAND[0],
                     max_dose: float = DOSE_BAND[1],
                     require_stable: bool = True,
                     anchor_mode: bool = True,
                     t_min: float = 30.0,
                     t_max: float = 120.0,
                     window: float = STABILITY_WINDOW,
                     last_drop: float = -3.0) -> list[Event]:
    """Qualifying UF step-down events (selection uses pre-event data only)."""
    et, es = _finite_arrays(d.get("et", []), d.get("es", []))
    mt, muf = dedupe_machine(d.get("mt", []), d.get("muf", []))
    end = session_end(d)
    if len(et) < 2 or len(mt) < 2 or not np.isfinite(end):
        return []
    oh0 = session_oh0(d)
    out: list[Event] = []
    for st in uf_steps(mt, muf, end):
        dose = st["prev"] - st["new"]
        if dose < min_dose - 1e-9 or dose > max_dose + 1e-9:
            continue
        t_e = st["t"]
        if t_e < t_min - 1e-9:
            continue
        if anchor_mode:
            if t_anchor is None or t_e + 30.0 > t_anchor + 1e-9:
                continue
        elif t_e > t_max + 1e-9:
            continue
        stab = pre_stability(et, es, t_e, window=window,
                             last_drop=last_drop)
        if stab is None or (require_stable and not stab["ok"]):
            continue
        deltas = outcome_deltas(et, es, t_e, stab["sbp_now"],
                                st["held_until"], t_anchor, held_min=45)
        if deltas.get(30) is None:
            continue
        out.append(Event(
            session_id=session_id, pid=pid, fold=fold,
            t_anchor=t_anchor, t_e=t_e, u_prev=st["prev"], u_new=st["new"],
            dose_l_h=float(dose), dose_units=float(dose / DOSE_UNIT),
            held_until=float(st["held_until"]),
            sbp_now=stab["sbp_now"], sbp_min=stab["sbp_min"],
            slope=stab["slope"], last_change=stab["last_change"],
            n_cuffs=stab["n_cuffs"],
            cum_uf_l=cumulative_uf(d, t_e), oh0_l=oh0,
            deltas=deltas,
            pre_change=pre_change(et, es, t_e, stab["sbp_now"]),
            is_stable=bool(stab["ok"]),
        ))
    return out


def scan_controls(d: Mapping, session_id: str, pid: str, fold: int,
                  t_anchor: float | None, anchor_mode: bool = True,
                  t_min: float = 30.0, t_max: float = 120.0,
                  held_tol: float = 0.03,
                  window: float = STABILITY_WINDOW,
                  last_drop: float = -3.0) -> list[Control]:
    """Stable times with UF held constant (same-patient control candidates)."""
    et, es = _finite_arrays(d.get("et", []), d.get("es", []))
    mt, muf = dedupe_machine(d.get("mt", []), d.get("muf", []))
    end = session_end(d)
    if len(et) < 2 or len(mt) < 2 or not np.isfinite(end):
        return []
    oh0 = session_oh0(d)
    grid = session_uf_grid(d, end)
    out: list[Control] = []
    seen: set[int] = set()
    for t_c in et:
        if t_c < t_min - 1e-9:
            continue
        if anchor_mode:
            if t_anchor is None or t_c + 30.0 > t_anchor + 1e-9:
                continue
        elif t_c > t_max + 1e-9:
            continue
        key = int(round(t_c))
        if key in seen:
            continue
        lo = max(int(np.floor(t_c - window)), 0)
        hi = min(int(np.floor(t_c + window)), len(grid) - 1)
        if hi <= lo:
            continue
        seg = grid[lo:hi + 1]
        if float(seg.max() - seg.min()) > held_tol:
            continue
        stab = pre_stability(et, es, t_c, window=window,
                             last_drop=last_drop)
        if stab is None or not stab["ok"]:
            continue
        deltas = outcome_deltas(et, es, t_c, stab["sbp_now"], float(end),
                                t_anchor, held_min=30)
        if deltas.get(30) is None:
            continue
        seen.add(key)
        out.append(Control(
            session_id=session_id, pid=pid, fold=fold, t_c=float(t_c),
            sbp_now=stab["sbp_now"], sbp_min=stab["sbp_min"],
            slope=stab["slope"], last_change=stab["last_change"],
            n_cuffs=stab["n_cuffs"],
            cum_uf_l=cumulative_uf(d, t_c), oh0_l=oh0,
            deltas=deltas,
            pre_change=pre_change(et, es, t_c, stab["sbp_now"]),
        ))
    return out


def event_dh(d: Mapping, event: Event, params: PhysioParamsV4,
             horizons=HORIZON_MINUTES) -> dict[int, float]:
    """Unit-gain ODE stress difference (hold minus step) at each horizon."""
    t_end = max(0.0, float(event.t_e) - 1.0)
    grid = session_uf_grid(d, t_end)
    rec = integrate_pre_anchor(grid, t_end, params,
                               record_minutes=[int(np.floor(t_end))])
    st = rec.get(int(np.floor(t_end)))
    if st is None:
        return {}
    steps = int(max(horizons))
    pd = params_to_batch([params])
    state0 = {
        "D": np.array([st.d_deficit_l]),
        "R": np.array([st.r_refill_l_h]),
        "C": np.array([st.c_baro_exhaustion]),
        "OH": np.array([st.oh_remaining_l]),
    }
    hold = simulate_branch_batch(
        state0, np.full((1, steps), float(event.u_prev)), pd)
    step = simulate_branch_batch(
        state0, np.full((1, steps), float(event.u_new)), pd)
    d0 = float(st.d_deficit_l)
    c0 = float(st.c_baro_exhaustion)
    bv = float(params.beta_vol_mmHg_per_l)
    bb = float(params.beta_baro_mmHg)
    dh_hold = bv * (hold["D"][0] - d0) + bb * (hold["C"][0] - c0)
    dh_step = bv * (step["D"][0] - d0) + bb * (step["C"][0] - c0)
    return {int(h): float(dh_hold[int(h)] - dh_step[int(h)])
            for h in horizons}


def match_pairs(events: list[Event], controls_by_pid: Mapping[str, list[Control]],
                horizon: int = 30) -> list[dict]:
    """Within-patient matched pairs; controls are different sessions."""
    pairs = []
    for ev in events:
        cands = [
            c for c in controls_by_pid.get(ev.pid, [])
            if c.pid == ev.pid
            and c.session_id != ev.session_id
            and abs(c.t_c - ev.t_e) <= 15.0
            and abs(c.sbp_now - ev.sbp_now) <= 12.0
            and c.deltas.get(horizon) is not None
            and ev.deltas.get(horizon) is not None
        ]
        if not cands:
            continue
        y_c = float(np.mean([c.deltas[horizon] for c in cands]))
        pre_vals = [c.pre_change for c in cands if c.pre_change is not None]
        pairs.append({
            "pid": ev.pid,
            "session_id": ev.session_id,
            "t_e": ev.t_e,
            "dose_units": ev.dose_units,
            "dose_l_h": ev.dose_l_h,
            "dh": ev.dh.get(horizon),
            "outcome": float(ev.deltas[horizon] - y_c),
            "pre_change": (None if ev.pre_change is None or not pre_vals
                           else float(ev.pre_change - np.mean(pre_vals))),
            "d_sbp_now": float(ev.sbp_now - np.mean([c.sbp_now for c in cands])),
            "d_cum_uf": float(ev.cum_uf_l - np.mean([c.cum_uf_l for c in cands])),
            "d_oh0": float(ev.oh0_l - np.mean([c.oh0_l for c in cands])),
            "n_controls": int(len(cands)),
            "e1a": bool(ev.is_e1a),
        })
    return pairs


def _design(pairs: list[dict], x_key: str, y_key: str) -> tuple[np.ndarray, np.ndarray]:
    rows = [p for p in pairs if p.get(x_key) is not None
            and p.get(y_key) is not None]
    if not rows:
        return np.empty((0, 4)), np.empty(0)
    y = np.asarray([p[y_key] for p in rows], dtype=float)
    X = np.column_stack([
        np.ones(len(rows)),
        np.asarray([p[x_key] for p in rows], dtype=float),
        np.asarray([p.get("d_sbp_now", 0.0) for p in rows], dtype=float),
        np.asarray([p.get("d_cum_uf", 0.0) for p in rows], dtype=float),
    ])
    return X, y


def fit_fe_dr(pairs: list[dict], x_key: str = "dose_units",
              y_key: str = "outcome") -> dict:
    X, y = _design(pairs, x_key, y_key)
    if len(y) < 5:
        return {"n": int(len(y)), "slope": float("nan"),
                "intercept": float("nan"), "sigma": float("nan")}
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    sigma = float(np.sqrt(np.sum(resid ** 2) / dof))
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = float(np.sqrt(max(xtx_inv[1, 1] * sigma ** 2, 0.0)))
    return {
        "n": int(len(y)),
        "slope": float(beta[1]),
        "intercept": float(beta[0]),
        "se": se,
        "sigma": sigma,
        "n_patients": int(len({p["pid"] for p in pairs})),
    }


def bootstrap_slope(pairs: list[dict], x_key: str = "dose_units",
                    y_key: str = "outcome", n_boot: int = 1000,
                    seed: int = 20261109) -> dict:
    by_pid: dict[str, list[dict]] = {}
    for p in pairs:
        by_pid.setdefault(p["pid"], []).append(p)
    pids = list(by_pid)
    if not pids:
        return {"ci95": [float("nan"), float("nan")],
                "p_le_0": float("nan"), "n_boot": 0}
    rng = np.random.default_rng(seed)
    slopes = np.empty(int(n_boot), dtype=float)
    for b in range(int(n_boot)):
        samp = rng.choice(pids, size=len(pids), replace=True)
        boot = [p for pid in samp for p in by_pid[pid]]
        slopes[b] = fit_fe_dr(boot, x_key, y_key)["slope"]
    slopes = slopes[np.isfinite(slopes)]
    if len(slopes) == 0:
        return {"ci95": [float("nan"), float("nan")],
                "p_le_0": float("nan"), "n_boot": 0}
    return {
        "ci95": [float(np.quantile(slopes, 0.025)),
                 float(np.quantile(slopes, 0.975))],
        "p_le_0": float(np.mean(slopes <= 0.0)),
        "n_boot": int(len(slopes)),
    }


def mde_power(outcomes: np.ndarray, pids: np.ndarray,
              n_events: int, fallback_deff: float = 1.5) -> dict:
    """MDE_80% = 2.80 * sigma_delta * sqrt(DEFF / N)."""
    y = np.asarray(outcomes, dtype=float)
    p = np.asarray(pids, dtype=object)
    ok = np.isfinite(y)
    y, p = y[ok], p[ok]
    if len(y) < 5:
        return {"sigma": float("nan"), "icc": float("nan"),
                "deff": float(fallback_deff), "se": float("nan"),
                "mde80": float("nan"), "n": int(len(y))}
    sigma = float(np.std(y, ddof=1))
    groups = [y[p == u] for u in np.unique(p)]
    groups = [g for g in groups if len(g) >= 2]
    icc = 0.0
    if len(groups) >= 2:
        grand = float(np.mean(y))
        ssb = sum(len(g) * (float(np.mean(g)) - grand) ** 2 for g in groups)
        ssw = sum(float(np.sum((g - np.mean(g)) ** 2)) for g in groups)
        dfb = len(groups) - 1
        dfw = max(len(y) - len(groups), 1)
        msb = ssb / max(dfb, 1)
        msw = ssw / dfw
        denom = msb + (np.mean([len(g) for g in groups]) - 1.0) * msw
        if denom > 0:
            icc = float(np.clip((msb - msw) / denom, 0.0, 1.0))
    mean_m = float(np.mean([len(g) for g in groups])) if groups else 1.0
    deff = 1.0 + max(mean_m - 1.0, 0.0) * icc
    deff = float(max(deff, 1.0))
    se = sigma * np.sqrt(deff / max(int(n_events), 1))
    return {
        "sigma": sigma,
        "icc": icc,
        "deff": deff,
        "se": float(se),
        "mde80": float(2.80 * se),
        "n": int(len(y)),
    }


def temporal_order_diagnostic(d: Mapping, t_anchor: float,
                              sbp_anchor: float,
                              horizon: float = 60.0) -> dict:
    """Post-anchor cuff density and whether a UF cut followed an observed drop."""
    et, es = _finite_arrays(d.get("et", []), d.get("es", []))
    mt, muf = dedupe_machine(d.get("mt", []), d.get("muf", []))
    end = session_end(d)
    post = (et > t_anchor) & (et <= t_anchor + horizon)
    n_cuffs = int(post.sum())
    steps = [s for s in uf_steps(mt, muf, end)
             if t_anchor - 1e-9 <= s["t"] <= t_anchor + horizon + 1e-9
             and (s["prev"] - s["new"]) >= 0.20]
    if not steps:
        return {"n_cuffs": n_cuffs, "cut": False, "class": "no_cut"}
    first = min(steps, key=lambda s: s["t"])
    before = et[(et <= first["t"] + 1e-9)]
    before_s = es[(et <= first["t"] + 1e-9)]
    if len(before) == 0:
        return {"n_cuffs": n_cuffs, "cut": True, "class": "no_observed_cuff"}
    last_sbp = float(before_s[-1])
    drop = last_sbp <= sbp_anchor - 10.0 or last_sbp < 90.0
    if first["t"] <= t_anchor + 1.0:
        cls = "at_anchor_after_drop" if drop else "at_anchor_no_drop"
    else:
        cls = "intermediate_after_drop" if drop else "intermediate_no_drop"
    return {"n_cuffs": n_cuffs, "cut": True, "cut_time": float(first["t"]),
            "class": cls, "last_sbp_before_cut": last_sbp}
