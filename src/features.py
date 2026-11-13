"""Feature construction: causal, multi-scale, machine-derived.

Every feature is computable at time t from data available at time t. All
session arrays are sliced at the anchor before use; UF is last-observation-
carried-forward, never linearly interpolated from a future machine record.
Duration-derived features (elapsed_frac, minutes_to_end, required rate, goal
gap) are intentionally absent: HEMOBP has no validated causal scheduled-
duration field, and substituting the observed final cuff leaks the future.

Patient history uses strictly earlier sessions. Twin priors must be built
inside the relevant fold's fit patients (see src.splits and src.twin).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG
from . import twin as T

WINDOWS = (15, 30, 60, 120)

# Bump when the feature set changes: train.py keys its parquet cache on this.
FEATURE_VERSION = "v4_causal"


def _ols_slope(s: np.ndarray) -> float:
    """OLS slope of a rolling window (x = 0..n-1); NaN when degenerate."""
    n = len(s)
    if n < 2:
        return np.nan
    x = np.arange(n, dtype=float)
    dx = x - x.mean()
    den = float((dx * dx).sum())
    if den == 0.0:
        return np.nan
    return float((dx * (s - s.mean())).sum() / den)


# Optional session-static sources; absent columns degrade to NaN (the v1
# wrapper must keep working on BP-only frames such as events_slim.parquet).
_SESSION_OPTIONAL_SRC = {
    "date": "date",
    "pre_w": "pre_weight",
    "post_w": "post_weight",
    "uf_L": "uf_measured_L",
    "dia_temp": "dia_temp_presc",
}


def _session_frame(ev2: pd.DataFrame) -> pd.DataFrame:
    """One row per session: BP summary + session-static facts (first record)."""
    agg = dict(sess_date=("sess_date", "first"),
               nadir_sbp=("sbp", "min"),
               first_sbp=("sbp", "first"),
               n_events=("sbp", "size"),
               dur_min=("t_min", "max"))
    for dst, src in _SESSION_OPTIONAL_SRC.items():
        if src in ev2.columns:
            agg[dst] = (src, "first")
    sess = (ev2.groupby(["pid", "session_id"], observed=True)
                .agg(**agg)
                .reset_index())
    for dst in _SESSION_OPTIONAL_SRC:
        if dst not in sess.columns:
            sess[dst] = np.nan
    return sess


# Session-fact QC plausibility windows (raw-value sanity, not fitting).
_W_LO, _W_HI = 25.0, 250.0     # kg
_UF_LO, _UF_HI = 0.0, 10.0     # L removed
_T_LO, _T_HI = 33.0, 41.0      # degC dialysate prescription

# The 22 history columns v3 returns (session_id + v2's 9 + 12 new).
V3_HIST_COLUMNS = [
    "hist_idh_rate10", "hist_mean_nadir3", "hist_mean_nadir10",
    "hist_prev_nadir", "hist_mean_first_sbp3", "hist_early_crash10",
    "hist_last_idh", "hist_n_sessions",
    "idi_days", "idwg_kg", "hist_idwg_mean10",
    "hist_prev_uf", "hist_uf_mean3", "hist_uf_mean10",
    "hist_typical_drop10", "hist_nadir_std10", "hist_nadir_slope5",
    "hist_uf_nadir_sens10",
    "dia_temp_c", "hist_dia_temp_mean10", "hist_dur_mean10",
]


def session_history_features(ev: pd.DataFrame) -> pd.DataFrame:
    """Per-session history from EARLIER sessions of the same patient only."""
    ev2 = ev.copy()
    ev2["sess_date"] = ev2.session_id.str[-10:]
    sess = _session_frame(ev2)
    idx = ev2.groupby("session_id", observed=True).sbp.idxmin()
    nadir_t = ev2.loc[idx].set_index("session_id").t_min
    sess["nadir_t"] = sess.session_id.map(nadir_t)
    sess = sess.sort_values(["pid", "sess_date", "session_id"]).reset_index(
        drop=True)
    sess = _first_gen_history(sess)
    return sess[["session_id"] + V3_HIST_COLUMNS[:8]]


def _first_gen_history(sess: pd.DataFrame) -> pd.DataFrame:
    """The frozen v1 history block (identical definitions, shared frame)."""
    sess = sess.copy()
    sess["is_idh"] = (sess.nadir_sbp < CONFIG["IDH_SBP_THRESHOLD"]).astype(int)
    # Keane 2021: patients who crash in the FIRST HALF of their sessions are a
    # distinct, higher-mortality phenotype -- measurable from cuff history.
    sess["is_early_crash"] = ((sess.nadir_sbp < CONFIG["IDH_SBP_THRESHOLD"]) &
                              (sess.nadir_t <= sess.dur_min / 2.0)).astype(int)
    g = sess.groupby("pid", observed=True)
    sess["hist_idh_rate10"] = g.is_idh.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_mean_nadir3"] = g.nadir_sbp.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    # Zhang 2023 SHAP top-3: rolling last-10 aggregates dominate the predictor
    sess["hist_mean_nadir10"] = g.nadir_sbp.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_prev_nadir"] = g.nadir_sbp.shift(1)
    sess["hist_mean_first_sbp3"] = g.first_sbp.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    sess["hist_early_crash10"] = g.is_early_crash.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_last_idh"] = g.is_idh.shift(1).fillna(0)
    sess["hist_n_sessions"] = g.cumcount()
    return sess


def session_history_features_v3(ev: pd.DataFrame) -> pd.DataFrame:
    """Second-generation patient memory (twin-v3, pre-registered W1).

    Superset of session_history_features. Causality contract, per anchor of
    session s: only s's OWN session-start facts (date, pre-dialysis weight,
    prescribed dialysate temperature) and rows of sessions STRICTLY EARLIER
    than s (shift(1) everywhere). No outcome-window data, no fold-dependent
    imputation (LightGBM handles NaN natively).

    New signals over v1:
    - idi_days: interdialytic interval (days since this patient's previous
      session) — the long-interval session carries the largest fluid load.
    - idwg_kg: true interdialytic weight gain (this session's pre-dialysis
      weight minus the previous session's post-dialysis weight).
    - prior-session actual UF aggregates (uf_measured_L, last 3/10).
    - hist_uf_nadir_sens10: personal UF->nadir sensitivity, rolling OLS
      slope of nadir on UF over the last 10 prior sessions.
    - nadir variability (std 10) and trend (OLS slope 5) — trajectory, not
      just level.
    - hist_typical_drop10: personal typical first-to-nadir drop magnitude.
    - dia_temp_c: prescribed dialysate temperature (session-start
      prescription; same frozen-precedent category as the UF programme
      block: observed treatment trajectory, NOT a treatment-effect claim).
    """
    ev2 = ev.copy()
    ev2["sess_date"] = ev2.session_id.str[-10:]
    sess = _session_frame(ev2)
    idx = ev2.groupby("session_id", observed=True).sbp.idxmin()
    nadir_t = ev2.loc[idx].set_index("session_id").t_min
    sess["nadir_t"] = sess.session_id.map(nadir_t)

    # QC plausibility on raw session facts (outside -> NaN, never clamped)
    for c, lo, hi in (("pre_w", _W_LO, _W_HI), ("post_w", _W_LO, _W_HI),
                      ("uf_L", _UF_LO, _UF_HI), ("dia_temp", _T_LO, _T_HI)):
        v = pd.to_numeric(sess[c], errors="coerce")
        sess[c] = v.where(v.between(lo, hi))
    sess["date"] = pd.to_datetime(sess["date"], errors="coerce")

    sess = sess.sort_values(["pid", "sess_date", "session_id"]).reset_index(
        drop=True)
    sess = _first_gen_history(sess)

    def _extras(gr: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=gr.index)
        d = gr["date"]
        out["idi_days"] = (d - d.shift(1)).dt.total_seconds() / 86400.0
        out["idwg_kg"] = gr["pre_w"] - gr["post_w"].shift(1)
        out["hist_idwg_mean10"] = (out["idwg_kg"].shift(1)
                                   .rolling(10, min_periods=1).mean())
        out["hist_prev_uf"] = gr["uf_L"].shift(1)
        out["hist_uf_mean3"] = (gr["uf_L"].shift(1)
                                .rolling(3, min_periods=1).mean())
        out["hist_uf_mean10"] = (gr["uf_L"].shift(1)
                                 .rolling(10, min_periods=1).mean())
        drop = gr["first_sbp"] - gr["nadir_sbp"]
        out["hist_typical_drop10"] = (drop.shift(1)
                                      .rolling(10, min_periods=1).mean())
        out["hist_nadir_std10"] = (gr["nadir_sbp"].shift(1)
                                   .rolling(10, min_periods=2).std())
        out["hist_nadir_slope5"] = (gr["nadir_sbp"].shift(1)
                                    .rolling(5, min_periods=2)
                                    .apply(_ols_slope, raw=True))
        cov = gr["nadir_sbp"].rolling(10, min_periods=4).cov(gr["uf_L"])
        var = gr["uf_L"].rolling(10, min_periods=4).var()
        out["hist_uf_nadir_sens10"] = (cov / var).shift(1)
        out["dia_temp_c"] = gr["dia_temp"]
        out["hist_dia_temp_mean10"] = (gr["dia_temp"].shift(1)
                                       .rolling(10, min_periods=1).mean())
        out["hist_dur_mean10"] = (gr["dur_min"].shift(1)
                                  .rolling(10, min_periods=1).mean())
        return out

    extras = sess.groupby("pid", observed=True, sort=False,
                          group_keys=False).apply(_extras)
    sess = pd.concat([sess, extras], axis=1)
    return sess[["session_id"] + V3_HIST_COLUMNS]


def session_history_features_old(ev: pd.DataFrame) -> pd.DataFrame:
    """FROZEN v1 implementation kept verbatim for reference/tests.

    Superseded by session_history_features / _first_gen_history, which
    return identical values via the shared session frame.
    """
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
    # Keane 2021: patients who crash in the FIRST HALF of their sessions are a
    # distinct, higher-mortality phenotype -- measurable from cuff history.
    idx = ev2.groupby("session_id", observed=True).sbp.idxmin()
    nadir_t = ev2.loc[idx].set_index("session_id").t_min
    sess["nadir_t"] = sess.session_id.map(nadir_t)
    sess["is_early_crash"] = ((sess.nadir_sbp < CONFIG["IDH_SBP_THRESHOLD"]) &
                              (sess.nadir_t <= sess.dur_min / 2.0)).astype(int)
    sess = sess.sort_values(["pid", "sess_date", "session_id"])

    g = sess.groupby("pid", observed=True)
    sess["hist_idh_rate10"] = g.is_idh.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_mean_nadir3"] = g.nadir_sbp.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    # Zhang 2023 SHAP top-3: rolling last-10 aggregates dominate the predictor
    sess["hist_mean_nadir10"] = g.nadir_sbp.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_prev_nadir"] = g.nadir_sbp.shift(1)
    sess["hist_mean_first_sbp3"] = g.first_sbp.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    sess["hist_early_crash10"] = g.is_early_crash.transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    sess["hist_last_idh"] = g.is_idh.shift(1).fillna(0)
    sess["hist_n_sessions"] = g.cumcount()

    return sess[["session_id", "hist_idh_rate10", "hist_mean_nadir3",
                 "hist_mean_nadir10", "hist_prev_nadir",
                 "hist_mean_first_sbp3", "hist_early_crash10",
                 "hist_last_idh", "hist_n_sessions"]]


def causal_anchor_features(d: dict, t: float, session_id: str,
                           k_pat: float = np.nan,
                           beta_pat: float = np.nan,
                           include_hold: bool = True) -> dict:
    """All anchor features from data at or before t only.

    `d` is a session-store dict. The caller supplies the patient's twin
    parameters from strictly earlier sessions (or the fold population prior).
    `include_hold=False` keeps the causal twin state but omits the retired
    hold-policy projected nadir from the risk model.
    """
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    ed = np.asarray(d["ed"], dtype=float)
    past = et <= float(t)
    et_p, es_p, ed_p = et[past], es[past], ed[past]
    if len(et_p) == 0:
        return {}

    sbp_now = float(es_p[-1])
    dbp_now = float(ed_p[-1])
    r = {
        "sbp_now": sbp_now,
        "dbp_now": dbp_now,
        "map_now": float(dbp_now + (sbp_now - dbp_now) / 3.0),
    }

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

    mt = np.asarray(d.get("mt", []), dtype=float)
    muf = np.asarray(d.get("muf", []), dtype=float)
    mbf = np.asarray(d.get("mbf", np.full(len(mt), np.nan)), dtype=float)
    mco = np.asarray(d.get("mco", np.full(len(mt), np.nan)), dtype=float)
    mdt = np.asarray(d.get("mdt", np.full(len(mt), np.nan)), dtype=float)
    cum = np.asarray(d.get("cum_uf", np.full(len(mt), np.nan)), dtype=float)
    mp = mt <= float(t)
    mt_p, muf_p = mt[mp], muf[mp]
    uf_now, idx = T.last_observation(mt_p, muf_p, float(t))
    if idx >= 0:
        r["uf_Lh"] = float(uf_now)
        r["blood_flow"] = float(mbf[mp][idx])
        r["conductivity"] = float(mco[mp][idx])
        r["dia_temp"] = float(mdt[mp][idx])
        r["cum_uf_L"] = float(cum[mp][idx])
    else:
        for c in ("uf_Lh", "blood_flow", "conductivity", "dia_temp", "cum_uf_L"):
            r[c] = np.nan

    dry = _f(d.get("dry"))
    pre = _f(d.get("pre"))
    goal = _f(d.get("goal"))
    r["age"] = _f(d.get("age"))
    r["sex_M"] = float(str(d.get("sex")) == "M")
    r["dm"] = _f(d.get("dm"))
    r["vintage_years"] = _f(d.get("vintage"))
    r["dry_weight"] = dry
    r["pre_weight"] = pre
    r["uf_goal_L"] = goal
    r["elapsed_min"] = float(t)
    r["uf_ml_kg_h"] = (float(uf_now) * 1000.0 / dry
                       if _ok(uf_now) and _ok(dry) and dry > 20 else np.nan)
    r["frac_uf_done"] = (r["cum_uf_L"] / goal
                         if _ok(goal) and goal > 0.3 and _ok(r["cum_uf_L"])
                         else np.nan)

    # ---- v3 research features (all causal) -------------------------------
    for wmin in (15, 30):
        uf_then, _ = T.last_observation(mt_p, muf_p, float(t) - wmin)
        r[f"uf_slope_{wmin}"] = ((uf_now - uf_then) / wmin
                                 if _ok(uf_now) and _ok(uf_then) else np.nan)
    m30uf = (mt_p > float(t) - 30) & (mt_p <= float(t))
    r["uf_var_30"] = (float(muf_p[m30uf].std())
                      if m30uf.sum() >= 3 and _ok(uf_now) else np.nan)
    r["uf_over13"] = (float(r["uf_ml_kg_h"] > 13.0)
                      if _ok(r["uf_ml_kg_h"]) else np.nan)
    for name, arr in (("cond_dev", mco), ("temp_dev", mdt)):
        a = arr[mp]
        r[name] = (float(a[-1] - np.median(a)) if len(a) >= 3 else np.nan)

    # BP variability and cuff cadence (Agarwal 2008: the cuff is noisy)
    m30bp = (et_p > float(t) - 30)
    m60bp = (et_p > float(t) - 60)
    r["sbp_std_30"] = float(es_p[m30bp].std()) if m30bp.sum() >= 3 else np.nan
    r["sbp_std_60"] = float(es_p[m60bp].std()) if m60bp.sum() >= 3 else np.nan
    r["pulse_pressure"] = sbp_now - dbp_now
    sbp_then, _ = T.last_observation(et_p, es_p, float(t) - 30)
    dbp_then, _ = T.last_observation(et_p, ed_p, float(t) - 30)
    map_then = (dbp_then + (sbp_then - dbp_then) / 3.0
                if _ok(sbp_then) and _ok(dbp_then) else np.nan)
    r["map_slope_30"] = ((r["map_now"] - map_then) / 30.0
                         if _ok(map_then) else np.nan)
    r["gap_since_last"] = (float(t) - float(et_p[-1])) if len(et_p) else np.nan
    r["n_bp_60"] = int(m60bp.sum())
    try:
        r["month"] = int(str(session_id)[-5:-3])
    except Exception:  # noqa: BLE001
        r["month"] = np.nan

    # ---- twin-state block (the digital thread) ---------------------------
    r["k_pat"] = k_pat
    r["beta_pat"] = beta_pat
    twin_ok = _ok(k_pat) and _ok(beta_pat) and _ok(uf_now)
    if twin_ok:
        state = T.twin_state_at(d, t, k_pat)
        D_now = state["D_now"]
        if _ok(D_now):
            dD_dt = T.deficit_derivative(D_now, uf_now, k_pat, phi=T.POP_PHI)
            refill_lh = max(float(uf_now) / 60.0 - dD_dt, 0.0) * 60.0
            r["twin_D_now"] = float(D_now)
            r["twin_refill_Lh"] = float(refill_lh)
            r["twin_refill_ratio"] = float(np.clip(
                refill_lh / max(float(uf_now), 0.05), 0.0, 3.0))
        else:
            r["twin_D_now"] = np.nan
            r["twin_refill_Lh"] = np.nan
            r["twin_refill_ratio"] = np.nan
        params = {"k_refill": float(k_pat), "beta_bp": float(beta_pat),
                  "beta_T": T.POP_BETA_T}
        if include_hold:
            fc = T.simulate_policy(d, t, params, T.POLICIES["hold"], horizon=60)
            r["twin_pred_nadir"] = float(fc["nadir"]) if fc["feasible"] else np.nan
    else:
        for c in ("twin_D_now", "twin_refill_Lh", "twin_refill_ratio"):
            r[c] = np.nan
        if include_hold:
            r["twin_pred_nadir"] = np.nan
    return r


def make_tabular_features(tables: dict, anch: pd.DataFrame,
                          twin_state: pd.DataFrame | None = None) -> pd.DataFrame:
    hist = session_history_features(tables["events"])
    store = tables.get("session_store") or {}
    ts = None
    if twin_state is not None and len(twin_state):
        ts = twin_state.set_index("session_id")

    anch = anch.sort_values(["session_id", "t_min"])
    rows = []
    for sid, ag in anch.groupby("session_id", observed=True):
        d = store.get(sid)
        if d is None:
            continue
        k_pat = beta_pat = np.nan
        if ts is not None and sid in ts.index:
            trow = ts.loc[sid]
            if isinstance(trow, pd.DataFrame):      # duplicate index guard
                trow = trow.iloc[0]
            k_pat = float(trow.k_pat)
            beta_pat = float(trow.beta_pat)
        for _, a in ag.iterrows():
            r = causal_anchor_features(d, float(a.t_min), sid, k_pat, beta_pat)
            if not r:
                continue
            r.update({
                "session_id": sid,
                "pid": a.pid,
                "label": a.label,
                "t_min": float(a.t_min),
                "onset_min": a.onset_min,
                "coverage_complete": bool(a.coverage_complete),
                "primary_eligible": bool(a.primary_eligible),
                "n_earlier": int(a.n_earlier),
            })
            rows.append(r)

    feat = pd.DataFrame(rows).merge(hist, on="session_id", how="left")
    return feat


def feature_columns(df: pd.DataFrame) -> list[str]:
    drop = {
        "session_id", "pid", "label", "t_min", "onset_min",
        "coverage_complete", "primary_eligible", "n_earlier",
        "t_anchor", "regime", "n_prior_sessions",
    }
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


def _f(x) -> float:
    try:
        x = float(x)
        return x if np.isfinite(x) else np.nan
    except Exception:  # noqa: BLE001
        return np.nan
