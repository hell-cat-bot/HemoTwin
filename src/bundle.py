"""Build the frozen demo bundle consumed by the dashboard.

Kept separate from training so the bundle can be rebuilt from saved artifacts
in ~2 minutes without refitting the model.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import twin as T
from .config import CONFIG

DRIVER_COPY = {
    "sbp_now": ("Current systolic BP", "mmHg"),
    "dbp_now": ("Current diastolic BP", "mmHg"),
    "map_now": ("Current mean arterial pressure", "mmHg"),
    "sbp_slope_15": ("Systolic trend, last 15 min", "mmHg/min"),
    "sbp_slope_30": ("Systolic trend, last 30 min", "mmHg/min"),
    "sbp_slope_60": ("Systolic trend, last 60 min", "mmHg/min"),
    "sbp_min_30": ("Lowest systolic, last 30 min", "mmHg"),
    "sbp_min_60": ("Lowest systolic, last 60 min", "mmHg"),
    "sbp_drop_from_max": ("Drop from session maximum", "mmHg"),
    "uf_Lh": ("Ultrafiltration rate", "L/h"),
    "uf_ml_kg_h": ("Ultrafiltration intensity", "mL/kg/h"),
    "cum_uf_L": ("Fluid removed so far", "L"),
    "frac_uf_done": ("Fraction of UF goal completed", ""),
    "uf_gap_Lh": ("Gap to prescribed UF rate", "L/h"),
    "uf_required_Lh": ("UF rate needed to hit goal", "L/h"),
    "hist_idh_rate10": ("IDH rate, last 10 sessions", ""),
    "hist_mean_nadir3": ("Mean nadir, last 3 sessions", "mmHg"),
    "hist_last_idh": ("Previous session crashed", ""),
    "vintage_years": ("Dialysis vintage", "years"),
    "dm": ("Diabetes", ""),
    "elapsed_frac": ("Session progress", ""),
    "minutes_to_end": ("Minutes to session end", "min"),
    "age": ("Age", "years"),
    "dry_weight": ("Dry weight", "kg"),
    "pre_weight": ("Pre-session weight", "kg"),
    "conductivity": ("Dialysate conductivity", "mS/cm"),
    "dia_temp": ("Dialysate temperature", "°C"),
    "blood_flow": ("Blood flow", "mL/min"),
}


def _drivers(booster, row: pd.DataFrame, feats: list[str], k: int = 4) -> list[dict]:
    contrib = booster.predict(row[feats], pred_contrib=True)
    if contrib.ndim == 3:
        contrib = contrib[:, :-1, 1]
    vals = contrib[0, :-1]
    order = np.argsort(-np.abs(vals))[:k]
    out = []
    for i in order:
        name = feats[i]
        label, unit = DRIVER_COPY.get(name, (name.replace("_", " "), ""))
        out.append({
            "feature": name,
            "label": label,
            "unit": unit,
            "value": _num(row.iloc[0][name]),
            "contribution": round(float(vals[i]), 4),
            "direction": "raises" if vals[i] > 0 else "lowers",
        })
    return out


def _num(x):
    try:
        v = float(x)
        return None if not np.isfinite(v) else round(v, 3)
    except Exception:  # noqa: BLE001
        return None


def _action(hold: dict, alert) -> str:
    if alert.score < 0.15:
        return "Routine monitoring. Reassess at the next cuff."
    if hold["nadir"] >= 90:
        return ("Continue the current prescription. No projected fall below 90 mmHg "
                "in the next hour; recheck at the next cuff.")
    return (f"Holding the current rate projects a nadir of {hold['nadir']:.0f} mmHg "
            f"within {hold['time_to_nadir_min']:.0f} min. Taper now. If systolic "
            "reaches 90, stop ultrafiltration and give 250 mL; escalate to the "
            "remote nephrologist.")


def build_bundle(tables, Fte, p_cal, booster, feats, pop, band, vol,
                 rep, evd, ppv, base1, base2, cal, n_sessions: int = 8,
                 threshold: float | None = None) -> dict:
    store = tables["session_store"]
    te = Fte.copy()
    te["score"] = p_cal
    thr = threshold if threshold is not None else cal["threshold"]

    sess = (te.groupby("session_id", observed=True)
              .agg(maxscore=("score", "max"), onset=("onset_min", "first"),
                   pid=("pid", "first"), n=("score", "size"))
              .reset_index())
    sess = sess[sess.n >= 3].sort_values("maxscore", ascending=False)
    # the demo needs a known ultrafiltration goal, otherwise the "fluid left
    # behind" half of the counterfactual is undefined
    ok = [sid for sid in sess.session_id
          if sid in store and np.isfinite(store[sid].get("goal", np.nan))]
    sess = sess[sess.session_id.isin(set(ok))]

    idh = sess[sess.onset.notna()].head(24)
    clean = sess[sess.onset.isna()].head(6)
    picked = pd.concat([idh, clean]).drop_duplicates("session_id")

    by_pid: dict[str, list[str]] = {}
    for pid, g in te.groupby("pid", observed=True):
        by_pid[pid] = sorted(g.session_id.unique())

    chairs = []
    for _, s in picked.iterrows():
        sid = s.session_id
        d = store.get(sid)
        if d is None:
            continue
        rows = te[te.session_id == sid].sort_values("t_min")

        # The console is re-evaluated at every cuff, so the demo shows the
        # reading at the decision point: the one nearest 30 minutes before
        # onset for a crashing session. For a stable session, peak risk.
        alert = rows.loc[rows.score.idxmax()]
        if np.isfinite(alert.onset_min):
            cand = rows[(rows.t_min >= alert.onset_min - 60) &
                        (rows.t_min <= alert.onset_min - 15)]
            if len(cand):
                ref = alert.onset_min - 30
                cand = cand.assign(_d=(cand.t_min - ref).abs()).sort_values("_d")
                alert = cand.iloc[0]
        t_now = float(alert.t_min)
        alert_row = rows.loc[[alert.name], feats].astype(float)

        cur_date = sid.split("_")[-1]
        prior = [x for x in by_pid[s.pid]
                 if x != sid and x.split("_")[-1] < cur_date]
        params = T.fit_patient(store, s.pid, prior, pop)

        cf = T.counterfactual(d, t_now, params)
        for c in cf:
            c["lo"] = round(c["nadir"] + band.get("lo", -12), 1)
            c["hi"] = round(c["nadir"] + band.get("hi", 12), 1)
        hold = next(c for c in cf if c["policy"] == "hold")
        taper = next(c for c in cf if c["policy"] == "taper25")

        chairs.append({
            "session_id": sid,
            "pid": str(s.pid),
            "age": _num(d.get("age")),
            "sex": d.get("sex"),
            "dm": _num(d.get("dm")),
            "vintage_years": _num(d.get("vintage")),
            "dry_weight": _num(d.get("dry")),
            "pre_weight": _num(d.get("pre")),
            "uf_goal_L": _num(d.get("goal")),
            "dia_temp_presc": _num(d.get("temp_presc")),
            "t_now_min": round(t_now, 1),
            "elapsed_min": round(float(d["et"].max()), 1),
            "sbp_now": round(float(np.interp(t_now, d["et"], d["es"])), 1),
            "dbp_now": round(float(np.interp(t_now, d["et"], d["ed"])), 1),
            "risk": round(float(alert.score), 4),
            "risk_band": [round(max(float(alert.score) - 0.05, 0.0), 3),
                          round(min(float(alert.score) + 0.05, 1.0), 3)],
            "label": int(alert.label),
            "session_idh": bool(np.isfinite(alert.onset_min)),
            "onset_min": (None if not np.isfinite(alert.onset_min)
                          else round(float(alert.onset_min), 1)),
            "detected": bool(float(alert.score) >= thr),
            "trajectory": [
                {"t": round(float(t), 1), "sbp": round(float(sv), 1),
                 "dbp": round(float(dv), 1), "uf": round(float(u), 2),
                 "cum_uf": round(float(c), 2)}
                for t, sv, dv, u, c in zip(
                    d["et"], d["es"], d["ed"],
                    np.interp(d["et"], d["mt"], d["muf"]),
                    np.interp(d["et"], d["mt"], d["cum_uf"]))
                if t <= t_now
            ],
            "forecast": T.forecast_path(d, t_now, params),
            "twin": {
                "k_refill": round(float(params["k_refill"]), 3),
                "beta_bp": round(float(params["beta_bp"]), 2),
                "n_prior_sessions": int(params["n_prior_sessions"]),
                "v_removed_L": round(float(np.interp(t_now, d["mt"], d["cum_uf"])), 2),
                "v_target_L": _num(d.get("goal")),
            },
            "whatif": cf,
            "delta_nadir": round(taper["nadir"] - hold["nadir"], 1),
            "drivers": _drivers(booster, alert_row, feats),
            "action": _action(hold, alert),
        })

    idh_c = sorted([c for c in chairs if c["session_idh"]],
                   key=lambda c: (-c["delta_nadir"], -c["risk"]))
    cln_c = sorted([c for c in chairs if not c["session_idh"]],
                   key=lambda c: -c["risk"])
    keep = idh_c[:max(n_sessions - 3, 4)] + cln_c[:3]
    chairs = keep[:n_sessions]
    chairs.sort(key=lambda c: -c["risk"])
    for i, c in enumerate(chairs, start=1):
        c["chair"] = i

    return {
        "meta": {
            "product": "HemoTwin",
            "hook": "Predict the crash. Price the fix.",
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "dataset": "HEMOBP (Lin et al., Sci Data 2019), CC BY 4.0",
            "threshold": thr,
            "horizon_min": [CONFIG["HORIZON_LO"], CONFIG["HORIZON_HI"]],
            "bp_projection_min": 60,
            "n_sessions_demo": len(chairs),
        },
        "metrics": {
            "test": rep,
            "event_level": evd,
            "session_ppv": ppv,
            "baselines": {"r1": base1, "r2": base2},
            "calibration": {"ece_raw_holdout": cal["ece_raw_holdout"],
                            "ece_cal_holdout": cal["ece_cal_holdout"],
                            "reliability": cal["reliability"],
                            "threshold": thr},
            "twin": {"population": pop, "band": band, "volume": vol},
        },
        "chairs": chairs,
    }
