"""Feature construction: causal, multi-scale, machine-derived.

Every feature is computable at time t from data available at time t.
Windows look backwards only. Patient history uses strictly earlier sessions
(shift-by-one at the session level).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG

WINDOWS = (15, 30, 60, 120)


def session_history_features(ev: pd.DataFrame) -> pd.DataFrame:
    """Per-session history from EARLIER sessions of the same patient only."""
    ev2 = ev.copy()
    ev2["sess_date"] = ev2.session_id.str[-10:]
    sess = (ev2.groupby(["pid", "session_id"], observed=True)
                .agg(sess_date=("sess_date", "first"),
                     nadir_sbp=("sbp", "min"),
                     first_sbp=("sbp", "first"),
                     n_events=("sbp", "size"),
                     dur_min=("t_min", "max"))
                .reset_index())
    sess["is_idh"] = (sess.nadir_sbp < CONFIG["IDH_SBP_THRESHOLD"]).astype(int)
    sess = sess.sort_values(["pid", "sess_date", "session_id"])

    g = sess.groupby("pid", observed=True)
    sess["hist_idh_rate10"] = g.is_idh.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_mean_nadir3"] = g.nadir_sbp.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    sess["hist_mean_first_sbp3"] = g.first_sbp.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    sess["hist_last_idh"] = g.is_idh.shift(1).fillna(0)
    sess["hist_n_sessions"] = g.cumcount()

    return sess[["session_id", "hist_idh_rate10", "hist_mean_nadir3",
                 "hist_mean_first_sbp3", "hist_last_idh", "hist_n_sessions"]]


def make_tabular_features(tables: dict, anch: pd.DataFrame) -> pd.DataFrame:
    hist = session_history_features(tables["events"])
    store = tables.get("session_store") or {}

    anch = anch.sort_values(["session_id", "t_min"])
    rows = []
    for sid, ag in anch.groupby("session_id", observed=True):
        d = store.get(sid)
        if d is None:
            continue
        et, es = d["et"], d["es"]
        mt, muf, mbf, mco, mdt = d["mt"], d["muf"], d["mbf"], d["mco"], d["mdt"]
        cum_uf = d["cum_uf"]
        dry, pre, goal = d["dry"], d["pre"], d["goal"]
        dur = float(et.max()) if len(et) else np.nan

        for _, a in ag.iterrows():
            t = float(a.t_min)
            r = {
                "session_id": sid, "pid": a.pid, "label": a.label,
                "t_min": t, "onset_min": a.onset_min,
                "sbp_now": float(a.sbp_now), "dbp_now": float(a.dbp_now),
                "map_now": float(a.dbp_now + (a.sbp_now - a.dbp_now) / 3.0),
            }

            last = et <= t
            for w in WINDOWS:
                m = (et > t - w) & last
                if m.sum() >= 2:
                    r[f"sbp_mean_{w}"] = float(es[m].mean())
                    r[f"sbp_min_{w}"] = float(es[m].min())
                    span = et[m].max() - et[m].min()
                    r[f"sbp_slope_{w}"] = float((es[m][-1] - es[m][0]) / max(span, 1e-9))
                else:
                    r[f"sbp_mean_{w}"] = float(a.sbp_now)
                    r[f"sbp_min_{w}"] = float(a.sbp_now)
                    r[f"sbp_slope_{w}"] = 0.0

            r["sbp_drop_from_max"] = float(es[last].max() - a.sbp_now) if last.any() else 0.0
            r["n_bp_so_far"] = int(last.sum())

            k = int(np.searchsorted(mt, t, side="right") - 1)
            if k >= 0:
                r["uf_Lh"] = float(muf[k])
                r["blood_flow"] = float(mbf[k])
                r["conductivity"] = float(mco[k])
                r["dia_temp"] = float(mdt[k])
                r["cum_uf_L"] = float(cum_uf[k])
            else:
                for c in ("uf_Lh", "blood_flow", "conductivity", "dia_temp", "cum_uf_L"):
                    r[c] = np.nan

            r["uf_ml_kg_h"] = (r["uf_Lh"] * 1000.0 / 60.0 / dry
                               if _ok(dry) and dry > 20 and _ok(r["uf_Lh"]) else np.nan)
            r["uf_goal_L"] = goal
            r["frac_uf_done"] = (r["cum_uf_L"] / goal
                                 if _ok(goal) and goal > 0.3 and _ok(r["cum_uf_L"]) else np.nan)

            # how much extra rate is needed to still hit the prescribed goal
            remaining_h = max((dur - t) / 60.0, 1e-3) if _ok(dur) else np.nan
            if _ok(goal) and _ok(r["cum_uf_L"]) and _ok(remaining_h):
                r["uf_required_Lh"] = max(goal - r["cum_uf_L"], 0.0) / remaining_h
                r["uf_gap_Lh"] = r["uf_required_Lh"] - (r["uf_Lh"] if _ok(r["uf_Lh"]) else 0.0)
            else:
                r["uf_required_Lh"] = np.nan
                r["uf_gap_Lh"] = np.nan

            r["age"] = d["age"]
            r["sex_M"] = float(d["sex"] == "M")
            r["dm"] = d["dm"]
            r["vintage_years"] = d["vintage"]
            r["dry_weight"] = dry
            r["pre_weight"] = pre
            r["elapsed_frac"] = t / max(dur, 1e-9) if _ok(dur) else np.nan
            r["minutes_to_end"] = (dur - t) if _ok(dur) else np.nan
            rows.append(r)

    feat = pd.DataFrame(rows).merge(hist, on="session_id", how="left")
    return feat


def feature_columns(df: pd.DataFrame) -> list[str]:
    drop = {"session_id", "pid", "label", "t_min", "onset_min"}
    return [c for c in df.columns if c not in drop]


def rule_baselines(anch: pd.DataFrame):
    """Two zero-training clinical rules the model must beat.

    R1: 'current SBP is low'          -> score = -SBP
    R2: 'extrapolate the recent slope' -> score = -(SBP + slope * HORIZON_HI)
    """
    t = anch.t_min.to_numpy(float)
    s = anch.sbp_now.to_numpy(float)
    within = anch.groupby("session_id", sort=False, observed=True).cumcount().to_numpy()
    j = np.arange(len(anch))
    gstart = j - within
    k = np.maximum(gstart, j - 2)
    dt = t[j] - t[k]
    slope = np.where(dt > 0, (s[j] - s[k]) / np.maximum(dt, 1e-9), 0.0)
    return -s, -(s + slope * CONFIG["HORIZON_HI"])


def _ok(x) -> bool:
    try:
        return bool(np.isfinite(float(x)))
    except Exception:  # noqa: BLE001
        return False
