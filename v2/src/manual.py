"""Task 02: ordinary-machine (manual availability) features.

The universal tier must be trainable and usable from routine cuff/flowsheet
entry alone. UF rate and cumulative UF are reconstructed only from cuff-entry
values; the high-frequency machine integral is reserved for the full tier and
its ablation. No twin-state or machine channel enters this module.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import WINDOWS

# Features that require no current UF-rate dynamics (minimal sensitivity tier).
MINIMAL_KEEP_PREFIXES = (
    "sbp_", "dbp_", "map_", "pulse_pressure", "n_bp_",
    "gap_since_last", "cuff_gap", "age", "sex_M", "dm", "vintage_years",
    "dry_weight", "pre_weight", "uf_goal_L", "cum_uf_L", "frac_uf_done",
    "elapsed_min", "month", "hist_",
)
MINIMAL_DROP = {"uf_Lh", "uf_ml_kg_h", "uf_change_prev", "uf_delta_30",
                "uf_delta_60"}


def _ok(x) -> bool:
    try:
        return bool(np.isfinite(float(x)))
    except Exception:  # noqa: BLE001
        return False


def _f(x) -> float:
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except Exception:  # noqa: BLE001
        return np.nan


def build_manual_store(base_store: dict) -> dict:
    """Attach cuff-entry UF and a cuff-only cumulative to each session.

    `cuff_uf[i]` is the last programmed UF at the observed cuff time (what a
    nurse would read and chart). `cuff_cum[i]` is the trapezoidal integral of
    the cuff-entry rates; it never uses the high-frequency telemetry.
    """
    out = {}
    for sid, d in base_store.items():
        et = np.asarray(d["et"], dtype=float)
        n = len(et)
        cuff_uf = np.full(n, np.nan)
        cuff_cum = np.full(n, np.nan)
        cuff_gap = np.full(n, np.nan)
        cuff_change = np.full(n, np.nan)
        mt = np.asarray(d.get("mt", []), dtype=float)
        muf = np.asarray(d.get("muf", []), dtype=float)
        for i, t in enumerate(et):
            if len(mt):
                idx = int(np.searchsorted(mt, t, side="right") - 1)
                if idx >= 0:
                    cuff_uf[i] = float(muf[idx])
            if i == 0:
                cuff_cum[i] = 0.0 if np.isfinite(cuff_uf[i]) else np.nan
            else:
                dt = float(t - et[i - 1])
                prev = cuff_uf[i - 1]
                cur = cuff_uf[i]
                if not np.isfinite(cuff_cum[i - 1]):
                    cuff_cum[i] = np.nan
                elif np.isfinite(prev) and np.isfinite(cur):
                    cuff_cum[i] = cuff_cum[i - 1] + (prev + cur) / 2.0 * dt / 60.0
                elif np.isfinite(prev):
                    cuff_cum[i] = cuff_cum[i - 1] + prev * dt / 60.0
                else:
                    cuff_cum[i] = np.nan
                cuff_gap[i] = dt
                if np.isfinite(prev) and np.isfinite(cur):
                    cuff_change[i] = cur - prev
        out[sid] = {**d,
                    "cuff_uf": cuff_uf,
                    "cuff_cum": cuff_cum,
                    "cuff_gap": cuff_gap,
                    "cuff_uf_change": cuff_change}
    return out


def universal_features(d: dict, t: float, session_id: str) -> dict:
    """Manual-availability features at an observed cuff time t."""
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    ed = np.asarray(d["ed"], dtype=float)
    cuff_uf = np.asarray(d.get("cuff_uf", np.full(len(et), np.nan)), dtype=float)
    cuff_cum = np.asarray(d.get("cuff_cum", np.full(len(et), np.nan)), dtype=float)
    cuff_gap = np.asarray(d.get("cuff_gap", np.full(len(et), np.nan)), dtype=float)
    cuff_change = np.asarray(d.get("cuff_uf_change", np.full(len(et), np.nan)),
                             dtype=float)
    past = et <= float(t)
    et_p, es_p, ed_p = et[past], es[past], ed[past]
    if len(et_p) == 0:
        return {}
    i = int(np.searchsorted(et, float(t), side="right") - 1)
    if i < 0:
        return {}
    sbp_now = float(es_p[-1])
    dbp_now = float(ed_p[-1])
    r = {"sbp_now": sbp_now, "dbp_now": dbp_now,
         "map_now": float(dbp_now + (sbp_now - dbp_now) / 3.0)}

    for w in WINDOWS:
        m = et_p > float(t) - w
        if m.sum() >= 2:
            r[f"sbp_mean_{w}"] = float(es_p[m].mean())
            r[f"sbp_min_{w}"] = float(es_p[m].min())
            span = float(et_p[m].max() - et_p[m].min())
            r[f"sbp_slope_{w}"] = float((es_p[m][-1] - es_p[m][0]) /
                                        max(span, 1e-9))
        else:
            r[f"sbp_mean_{w}"] = sbp_now
            r[f"sbp_min_{w}"] = sbp_now
            r[f"sbp_slope_{w}"] = 0.0

    r["sbp_drop_from_max"] = float(es_p.max() - sbp_now)
    r["n_bp_so_far"] = int(len(et_p))
    r["pulse_pressure"] = sbp_now - dbp_now
    m30bp = et_p > float(t) - 30
    m60bp = et_p > float(t) - 60
    r["sbp_std_30"] = float(es_p[m30bp].std()) if m30bp.sum() >= 3 else np.nan
    r["sbp_std_60"] = float(es_p[m60bp].std()) if m60bp.sum() >= 3 else np.nan
    sbp_then = _last(et_p, es_p, float(t) - 30)
    dbp_then = _last(et_p, ed_p, float(t) - 30)
    map_then = (dbp_then + (sbp_then - dbp_then) / 3.0
                if _ok(sbp_then) and _ok(dbp_then) else np.nan)
    r["map_slope_30"] = ((r["map_now"] - map_then) / 30.0
                         if _ok(map_then) else np.nan)
    r["gap_since_last"] = float(t) - float(et_p[-1])
    r["n_bp_60"] = int(m60bp.sum())

    uf_now = float(cuff_uf[i]) if i < len(cuff_uf) else np.nan
    cum_now = float(cuff_cum[i]) if i < len(cuff_cum) else np.nan
    dry = _f(d.get("dry"))
    pre = _f(d.get("pre"))
    goal = _f(d.get("goal"))
    r.update({
        "uf_Lh": uf_now,
        "cum_uf_L": cum_now,
        "uf_ml_kg_h": (uf_now * 1000.0 / dry
                       if _ok(uf_now) and _ok(dry) and dry > 20 else np.nan),
        "uf_goal_L": goal,
        "frac_uf_done": (cum_now / goal
                         if _ok(goal) and goal > 0.3 and _ok(cum_now) else np.nan),
        "uf_change_prev": (float(cuff_change[i]) if i < len(cuff_change)
                           else np.nan),
        "cuff_gap": (float(cuff_gap[i]) if i < len(cuff_gap) else np.nan),
        "age": _f(d.get("age")),
        "sex_M": float(str(d.get("sex")) == "M"),
        "dm": _f(d.get("dm")),
        "vintage_years": _f(d.get("vintage")),
        "dry_weight": dry,
        "pre_weight": pre,
        "elapsed_min": float(t),
    })
    for w in (30, 60):
        j = int(np.searchsorted(et, float(t) - w, side="right") - 1)
        r[f"uf_delta_{w}"] = ((uf_now - float(cuff_uf[j]))
                              if j >= 0 and _ok(uf_now) and _ok(cuff_uf[j])
                              else np.nan)
    try:
        r["month"] = int(d.get("month")) if d.get("month") is not None \
            else int(str(session_id)[-5:-3])
    except Exception:  # noqa: BLE001
        r["month"] = np.nan
    return r


def minimal_feature_columns(columns) -> list[str]:
    out = []
    for c in columns:
        if c in MINIMAL_DROP:
            continue
        if c.startswith(MINIMAL_KEEP_PREFIXES):
            out.append(c)
    return out


def universal_feature_columns(df: pd.DataFrame) -> list[str]:
    """Every universal feature except identifiers/metadata."""
    drop = {"session_id", "pid", "label", "t_min", "onset_min", "t_anchor",
            "coverage_complete", "primary_eligible", "n_earlier"}
    return [c for c in df.columns if c not in drop]


def _last(ts, vals, t: float) -> float:
    ts = np.asarray(ts, dtype=float)
    vals = np.asarray(vals, dtype=float)
    if len(ts) == 0:
        return float("nan")
    i = int(np.searchsorted(ts, float(t), side="right") - 1)
    return float(vals[i]) if i >= 0 else float("nan")
