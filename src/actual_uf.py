"""Task 01: actual-UF oracle, regimes, and forecast helpers.

The actual future UF trajectory is an evaluation oracle. It is constructed
from a machine-only stream (no cuff/BP QC), carried forward as a step
function, and never used to build the anchor state.
"""
from __future__ import annotations

import numpy as np

from . import labels as L
from . import twin as T

HORIZON = 60
REGIME_ORDER = ("pause", "aggressive", "moderate", "hold", "mixed",
                "zero_reference", "unobservable")


def oracle_future_uf(d: dict, t: float, horizon: int = HORIZON) -> dict:
    """Return the actual 60-minute future UF vector and reference rate.

    Observable only when the machine log covers session start and has a
    record at or after t+horizon. No extrapolation beyond the validated
    observation end.
    """
    t = float(t)
    mt = np.asarray(d.get("mt", []), dtype=float)
    if len(mt) == 0:
        return {"observable": False, "reason": "no machine records",
                "future": None, "reference": float("nan")}
    if float(mt.max()) < t + horizon - 1e-9:
        return {"observable": False,
                "reason": "machine log ends before t+60",
                "future": None, "reference": float("nan")}
    grid, uf, coverage = T.causal_uf_grid(d, t + horizon)
    if not coverage or len(grid) < int(np.floor(t + horizon)) + 1:
        return {"observable": False,
                "reason": "machine log does not cover session start",
                "future": None, "reference": float("nan")}
    i0 = int(np.floor(t))
    future = uf[i0 + 1:i0 + horizon + 1]
    if len(future) != horizon or not np.isfinite(future).all():
        return {"observable": False, "reason": "future UF vector incomplete",
                "future": None, "reference": float("nan")}
    ref_window = uf[max(0, i0 - 15):i0 + 1]
    reference = float(np.median(ref_window)) if len(ref_window) else float("nan")
    return {
        "observable": True,
        "reason": None,
        "future": future,
        "reference": reference,
        "grid": grid,
        "uf": uf,
        "t": t,
        "horizon": horizon,
    }


def classify_regime(future, reference, horizon: int = HORIZON) -> str:
    """Frozen Task 01 regime precedence.

    1 pause: first 15 min all zero.
    2 aggressive: first 15 min all <=50% of reference (not all zero).
    3 moderate: first 15 min all in (50%, 80%] of reference.
    4 hold: all 60 min within +/-5% of reference.
    5 mixed: any other observable pattern.
    Zero-reference and unobservable are separate states.
    """
    if future is None:
        return "unobservable"
    fut = np.asarray(future, dtype=float)
    if len(fut) < 15 or not np.isfinite(fut).all():
        return "unobservable"
    ref = float(reference)
    if not np.isfinite(ref):
        return "unobservable"
    if ref == 0.0:
        return "zero_reference"
    first = fut[:15]
    if np.all(first == 0.0):
        return "pause"
    if np.all(first <= 0.5 * ref) and not np.all(first == 0.0):
        return "aggressive"
    if np.all((first > 0.5 * ref) & (first <= 0.8 * ref)):
        return "moderate"
    if np.all((fut >= 0.95 * ref - 1e-9) & (fut <= 1.05 * ref + 1e-9)):
        return "hold"
    return "mixed"


def task01_anchor(et, t_min: float = 90.0) -> tuple[int, float] | tuple[None, None]:
    """First observed cuff at/after t_min with at least two earlier cuffs."""
    et = np.asarray(et, dtype=float)
    for i, t in enumerate(et):
        if t < t_min:
            continue
        if int(np.sum(et < t)) >= 2:
            return int(i), float(t)
    return None, None


def cuffs_in_window(et, t: float, horizon: int = HORIZON):
    et = np.asarray(et, dtype=float)
    m = (et > float(t)) & (et <= float(t) + horizon)
    cuffs = et[m]
    offsets = np.rint(cuffs - float(t)).astype(int)
    return cuffs, offsets


def observed_nadir(et, es, t: float, horizon: int = HORIZON) -> float:
    et = np.asarray(et, dtype=float)
    es = np.asarray(es, dtype=float)
    m = (et > float(t)) & (et <= float(t) + horizon)
    return float(es[m].min()) if m.any() else float("nan")


def persistence_nadir(sbp_anchor: float) -> float:
    return float(sbp_anchor)


def linear_nadir(et, es, t: float, offsets, slope_bound: float = 1.0,
                 sbp_clip=(40.0, 250.0)) -> float:
    """Causal last-two-cuff linear extrapolation, clinically bounded."""
    et = np.asarray(et, dtype=float)
    es = np.asarray(es, dtype=float)
    m = et <= float(t)
    if m.sum() < 2:
        return float("nan")
    t1 = float(et[m][-1])
    t0 = float(et[m][-2])
    s1 = float(es[m][-1])
    s0 = float(es[m][-2])
    if t1 <= t0:
        return float("nan")
    slope = float(np.clip((s1 - s0) / (t1 - t0), -slope_bound, slope_bound))
    preds = np.clip(s1 + slope * np.asarray(offsets, dtype=float),
                    sbp_clip[0], sbp_clip[1])
    return float(np.min(preds)) if len(preds) else float("nan")


def actual_uf_forecast(d: dict, t: float, params: dict, future,
                       horizon: int = HORIZON) -> dict:
    """Integrate the actual future UF vector from the causal state at t."""
    state = T.causal_uf_state(d, t)
    if not state["coverage"] or not np.isfinite(state["uf_now"]):
        return {"feasible": False, "reason": "UF log does not cover session start"}
    k = float(params.get("k_refill", np.nan))
    beta = float(params.get("beta_bp", np.nan))
    if not np.isfinite(k) or not np.isfinite(beta):
        return {"feasible": False, "reason": "patient twin parameters unavailable"}
    D_now = T.twin_state_at(d, t, k)["D_now"]
    if not np.isfinite(D_now):
        return {"feasible": False, "reason": "twin state unavailable"}
    fut = np.asarray(future, dtype=float)
    if len(fut) != horizon or not np.isfinite(fut).all():
        return {"feasible": False, "reason": "future UF vector incomplete"}
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    m = et <= float(t)
    if not m.any():
        return {"feasible": False, "reason": "no observed cuff at anchor"}
    sbp_now = float(es[m][-1])
    D_path = T.deficit_path(fut, k, phi=T.POP_PHI, d0=D_now)
    sbp_path = sbp_now - beta * (D_path - D_now)
    return {
        "feasible": True,
        "reason": None,
        "sbp_path": sbp_path,
        "D_path": D_path,
        "sbp_now": sbp_now,
        "D_now": D_now,
    }


def predicted_nadir(path, offsets) -> float:
    path = np.asarray(path, dtype=float)
    off = np.asarray(offsets, dtype=int)
    if len(off) == 0:
        return float("nan")
    if off.min() < 0 or off.max() >= len(path):
        return float("nan")
    return float(path[off].min())


def first_sustained_cut(d: dict, initial_min: int = 15, drop: float = 0.20,
                        sustain: int = 15) -> float | None:
    """First minute of a sustained >20% reduction from the initial UF rate."""
    et = np.asarray(d.get("et", []), dtype=float)
    mt = np.asarray(d.get("mt", []), dtype=float)
    if len(mt) == 0:
        return None
    t_end = min(float(et.max()) if len(et) else float(mt.max()),
                float(mt.max()))
    grid, uf, coverage = T.causal_uf_grid(d, t_end)
    if not coverage or len(uf) < max(initial_min + sustain, 2):
        return None
    initial = float(np.median(uf[:initial_min]))
    if initial <= 0:
        return None
    threshold = (1.0 - drop) * initial
    for i in range(0, len(uf) - sustain + 1):
        if np.all(uf[i:i + sustain] <= threshold):
            return float(grid[i])
    return None


def slice_session_before(d: dict, t_end: float) -> dict:
    """Copy a session with cuffs and machine records strictly before t_end."""
    out = dict(d)
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    ed = np.asarray(d["ed"], dtype=float)
    m = et < float(t_end)
    out["et"], out["es"], out["ed"] = et[m], es[m], ed[m]
    if "mt" in d:
        mt = np.asarray(d["mt"], dtype=float)
        mm = mt < float(t_end)
        out["mt"] = mt[mm]
        out["muf"] = np.asarray(d["muf"], dtype=float)[mm]
        for key in ("mbf", "mco", "mdt", "cum_uf"):
            if key in d:
                out[key] = np.asarray(d[key], dtype=float)[mm]
    return out


def fit_sessions_batch_precut(store: dict, cut_times: dict,
                              progress_every: int = 25000) -> dict:
    """Fit prior sessions only before their first sustained >20% UF cut.

    Sessions with no cut are omitted; the caller uses the full-session fit for
    them. A cut with fewer than four usable pre-cut cuffs returns an unfit
    entry, which the caller resolves with the pre-cut population prior.
    """
    a_all = np.clip(1.0 - T.K_GRID / 60.0, 0.0, 0.999999)
    out: dict[str, dict] = {}
    n_done = 0
    for sid, d in store.items():
        cut = cut_times.get(sid)
        if cut is None:
            continue
        sliced = slice_session_before(d, cut)
        out[sid] = T._fit_one_causal(sliced, a_all, min_cuffs=4)
        n_done += 1
        if progress_every and n_done % progress_every == 0:
            print(f"    pre-cut fits {n_done:,} sessions", flush=True)
    return out


def gbdt_uf_features(future, reference: float, horizon: int) -> dict:
    """Deterministic transformations of the frozen future-UF oracle."""
    fut = np.asarray(future, dtype=float)
    h = int(horizon)
    prefix = fut[:h]
    ref = float(reference)
    return {
        "horizon_min": float(h),
        "uf_future_at_h": float(fut[h - 1]),
        "uf_cum_h": float(prefix.sum() / 60.0),
        "uf_mean_h": float(prefix.mean()),
        "uf_min_h": float(prefix.min()),
        "uf_max_h": float(prefix.max()),
        "uf_seg_1_15": float(fut[:15].mean()),
        "uf_seg_16_30": float(fut[15:30].mean()),
        "uf_seg_31_45": float(fut[30:45].mean()),
        "uf_seg_46_60": float(fut[45:60].mean()),
        "uf_zero_share_h": float((prefix <= 1e-9).mean()),
        "uf_reduction_ref_h": (float(1.0 - prefix.mean() / ref)
                               if np.isfinite(ref) and ref > 0 else float("nan")),
        "uf_slope_60": float(np.polyfit(np.arange(len(fut)), fut, 1)[0]),
    }


def nearest_cuff(et, target: float, tol: float = 10.0) -> float | None:
    et = np.asarray(et, dtype=float)
    if len(et) == 0:
        return None
    i = int(np.argmin(np.abs(et - float(target))))
    return float(et[i]) if abs(et[i] - float(target)) <= tol else None


def anchor_row(d: dict, sid: str, pid: str, t: float) -> dict:
    """One Task 01 anchor row with coverage, oracle, regime, and cuffs."""
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    ed = np.asarray(d["ed"], dtype=float)
    i = int(np.searchsorted(et, t, side="left"))
    if i >= len(et) or abs(float(et[i]) - float(t)) > 1e-9:
        return {}
    cov = L.outcome_coverage(et, t, onset=np.inf, session_end=float(et[-1]))
    cuffs, offsets = cuffs_in_window(et, t)
    m = (et > float(t)) & (et <= float(t) + HORIZON)
    cuff_sbp = es[m]
    t30 = nearest_cuff(et, float(t) + 30.0)
    t60 = nearest_cuff(et, float(t) + 60.0)
    # Secondary endpoints must be inside the 60-minute horizon; a cuff at
    # t+70 can establish coverage but is not a 60-minute endpoint.
    if t30 is not None and t30 > float(t) + HORIZON:
        t30 = None
    if t60 is not None and t60 > float(t) + HORIZON:
        t60 = None
    oracle = oracle_future_uf(d, t)
    regime = classify_regime(oracle.get("future"), oracle.get("reference"))
    return {
        "session_id": sid,
        "pid": pid,
        "t_anchor": float(t),
        "sbp_anchor": float(es[i]),
        "dbp_anchor": float(ed[i]),
        "cuffs": cuffs,
        "offsets": offsets,
        "cuff_sbp": cuff_sbp,
        "observed_nadir": observed_nadir(et, es, t),
        "t30": t30,
        "t60": t60,
        "off30": (float(t30) - float(t)) if t30 is not None else None,
        "off60": (float(t60) - float(t)) if t60 is not None else None,
        "obs30": (float(es[et == t30][0]) if t30 is not None else float("nan")),
        "obs60": (float(es[et == t60][0]) if t60 is not None else float("nan")),
        "coverage_complete": bool(cov["coverage_complete"]),
        "max_gap_min": float(cov["max_gap_min"]),
        "future": oracle.get("future"),
        "reference_uf": oracle.get("reference"),
        "oracle_observable": bool(oracle.get("observable", False)),
        "oracle_reason": oracle.get("reason"),
        "regime": regime,
        "n_prior_sessions": int(d.get("n_prior", 0) or 0),
    }
