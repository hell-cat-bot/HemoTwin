"""Build the frozen demo bundle consumed by the dashboard.

Kept separate from training so the bundle can be rebuilt from saved artifacts
in ~2 minutes without refitting the model.

v2 changes (docs/UPGRADE_LOG.md):
- One patient per chair. A chair board where the same person occupies six
  chairs reads as a data bug, not a ward; selection is now patient-disjoint.
- A realistic triage mix instead of eight identical verdicts: 1-2 red,
  2-3 amber, and a green majority, with at least one diabetic, one elderly
  and one long-vintage patient in the eight.
- Every policy card and the frontier come from the v2 counterfactual engine
  (programmed-profile hold, reconciled state), plus the taper sweep and the
  minimum effective taper.
- Uncertainty bands are conditional on the number of prior sessions and
  clamped to physiology (a 33 mmHg "nadir" is not a number anyone survives).
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
    # v3 research features
    "hist_mean_nadir10": ("Mean nadir, last 10 sessions", "mmHg"),
    "hist_prev_nadir": ("Previous session nadir", "mmHg"),
    "hist_early_crash10": ("Early-crash rate, last 10 sessions", ""),
    "uf_slope_15": ("UF rate trend, 15 min", "L/h per min"),
    "uf_slope_30": ("UF rate trend, 30 min", "L/h per min"),
    "uf_var_30": ("UF rate variability, 30 min", "L/h"),
    "uf_over13": ("UF intensity over KDOQI 13 mL/kg/h", ""),
    "cond_dev": ("Conductivity vs session norm", "mS/cm"),
    "temp_dev": ("Dialysate temp vs session norm", "°C"),
    "sbp_std_30": ("SBP variability, 30 min", "mmHg"),
    "sbp_std_60": ("SBP variability, 60 min", "mmHg"),
    "pulse_pressure": ("Pulse pressure", "mmHg"),
    "map_slope_30": ("MAP trend, 30 min", "mmHg/min"),
    "gap_since_last": ("Minutes since last cuff", "min"),
    "n_bp_60": ("Readings, last 60 min", ""),
    "month": ("Calendar month", ""),
    "k_pat": ("Refill rate (patient twin)", "/h"),
    "beta_pat": ("BP sensitivity (patient twin)", "mmHg/L"),
    "twin_D_now": ("Volume deficit state (twin)", "L"),
    "twin_refill_Lh": ("Implied plasma refill (twin)", "L/h"),
    "twin_refill_ratio": ("Refill-to-UF ratio (twin)", ""),
    "twin_pred_nadir": ("Hold-projected nadir (twin)", "mmHg"),
}

# Policies priced on the console. Quantitative cooling and pause cards are
# disabled pending intervention-specific evidence; they remain available to
# tests and research code under T.POLICIES.
WHATIF_POLICIES = {
    "hold":    T.POLICIES["hold"],
    "taper25": T.POLICIES["taper25"],
}

NADIR_FLOOR = 45.0    # mmHg; nothing below this is a survivable number.
                      # (The v1 band rendered "nadir 70 [33–92]"; the floor
                      # exists so no card can do that again. The v2 band is
                      # tight enough that its upper edge needs no clamp.)


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


def _band_for(band: dict) -> dict:
    """The shipped band, clamped so its edges stay physiologically possible."""
    s = band or {"lo": -12.0, "hi": 12.0}
    return {"lo": float(s.get("lo", -12.0)), "hi": float(s.get("hi", 12.0))}


def _alert_value(alert, name: str, default=np.nan) -> float:
    try:
        return float(getattr(alert, name))
    except Exception:  # noqa: BLE001
        try:
            return float(alert[name])
        except Exception:  # noqa: BLE001
            return default


def _action(hold: dict, met: dict | None, alert) -> str:
    """Guideline-based routing. Never a quantitative treatment dose.

    Current SBP<90 is a rescue state independent of the forecast score. A low
    classifier score cannot suppress a projected or current fall. The MET
    sweep remains research output; it is not a validated recommendation.
    """
    recovery = (" If an episode happens anyway: feet up, recheck BP every 5 min, "
                "and a standing BP before discharge — the walk out is a fall risk.")
    sbp_now = _alert_value(alert, "sbp_now")
    if np.isfinite(sbp_now) and sbp_now < 90.0:
        return ("Current SBP is below 90 mmHg: treat as ongoing hypotension. "
                "Follow the local hypotension rescue protocol per RN/standing "
                "order, recheck BP in 5 min, and escalate to the nephrologist. "
                "No default fluid dose is supplied by this prototype. This "
                "rescue state does not depend on the forecast score." + recovery)
    if not np.isfinite(_alert_value(hold, "nadir")):
        return ("Forecast unavailable: the UF log does not cover session start "
                "or patient twin parameters are missing. Reassess at the next "
                "cuff and follow local protocols; no quantitative action is "
                "recommended." + recovery)
    if hold["nadir"] >= 90.0:
        return ("Continue the current prescription. No projected fall below 90 mmHg "
                "in the next hour; recheck at the next cuff.")
    if met is None:
        met_txt = ("No simulated taper clears 90 mmHg at the conservative "
                   "criterion.")
    else:
        met_txt = ("A simulated taper clears 90 mmHg, but it is not a validated "
                   "quantitative recommendation.")
    return (f"Holding the current rate projects a nadir of {hold['nadir']:.0f} mmHg "
            f"within {hold['time_to_nadir_min']:.0f} min. {met_txt} Quantitative "
            "taper, pause, and cooling recommendations are retired — the Task 01 "
            "pre-registered validation failed. Follow the local hypotension "
            "rescue protocol per RN/standing order if hypotensive, and escalate "
            "to the nephrologist. No default fluid dose is supplied by this "
            "prototype." + recovery)


def next_session_intensity(goal_L: float, fluid_left_L: float,
                           duration_min: float, dry_kg: float) -> float | None:
    """Illustrative next-session UF intensity in mL/kg/h.

    Inputs must be causal: a planned duration, not the observed session end.
    Returns None when any input is unavailable.
    """
    vals = (goal_L, fluid_left_L, duration_min, dry_kg)
    if not all(np.isfinite(float(v)) for v in vals):
        return None
    if duration_min <= 0 or dry_kg <= 20:
        return None
    hours = float(duration_min) / 60.0
    return float((float(goal_L) + float(fluid_left_L)) * 1000.0
                 / hours / float(dry_kg))


def _chair_facts(d: dict, t_now: float) -> dict:
    """The three facts a nurse triages on, computed from data at/before now."""
    et = np.asarray(d["et"], dtype=float)
    es = np.asarray(d["es"], dtype=float)
    past = et <= float(t_now)
    m30 = past & (et >= float(t_now) - 30)
    slope30 = (float(es_slope(et, es, m30)) if m30.sum() >= 2 else 0.0)
    et_p = et[past]
    gaps = np.diff(et_p)
    cadence = float(np.median(gaps)) if len(gaps) else np.nan
    uf_now, _ = T.last_observation(d.get("mt", []), d.get("muf", []), t_now)
    return {
        "sbp_trend_30": round(slope30, 1),           # mmHg over the last 30 min
        "cuff_cadence_min": round(cadence, 0) if np.isfinite(cadence) else None,
        "uf_rate_now_Lh": round(float(uf_now), 2) if np.isfinite(uf_now) else None,
    }


def es_slope(et: np.ndarray, es: np.ndarray, mask: np.ndarray) -> float:
    """SBP change across the masked window (mmHg over the window, not per min)."""
    span = et[mask]
    if len(span) < 2:
        return 0.0
    return float(es[mask][-1] - es[mask][0])


def build_bundle(tables, Fte, p_cal, booster, feats, pop, band, vol,
                 rep, evd, ppv, base1, base2, cal, n_sessions: int = 8,
                 threshold: float | None = None,
                 twin_benchmark: dict | None = None) -> dict:
    store = tables["session_store"]
    te = Fte.copy()
    te["score"] = p_cal
    thr = threshold if threshold is not None else cal["threshold"]

    sess = (te.groupby("session_id", observed=True)
              .agg(maxscore=("score", "max"), onset=("onset_min", "first"),
                   pid=("pid", "first"), n=("score", "size"))
              .reset_index())
    sess = sess[sess.n >= 3].sort_values("maxscore", ascending=False)
    ok = [sid for sid in sess.session_id
          if sid in store and np.isfinite(store[sid].get("goal", np.nan))]
    sess = sess[sess.session_id.isin(set(ok))]

    # ---- pools: best session per patient WITHIN each pool, so a patient's ----
    # ---- crash session can headline the board while their quiet session  ----
    # ---- can still sit elsewhere on it (never both: picks are disjoint)  ----
    def best_per_pid(df: pd.DataFrame) -> pd.DataFrame:
        return (df.sort_values("maxscore", ascending=False)
                  .drop_duplicates("pid"))

    idh = best_per_pid(sess[sess.onset.notna()].copy())
    clean = best_per_pid(sess[sess.onset.isna()].copy())

    by_pid: dict[str, list[str]] = {}
    for pid, g in te.groupby("pid", observed=True):
        by_pid[pid] = sorted(g.session_id.unique())

    def build_chair(sid, s) -> dict | None:
        d = store.get(sid)
        if d is None:
            return None
        rows = te[te.session_id == sid].sort_values("t_min")
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

        recon = T.innovation(d, t_now, params)
        cf = T.counterfactual(d, t_now, params, policies=WHATIF_POLICIES,
                              planned_duration=d.get("planned_duration"))
        sweep = T.taper_sweep(d, t_now, params,
                              planned_duration=d.get("planned_duration"))

        # Cascade pricing is illustrative and only shown with a causal planned
        # duration. Observed session end is not a substitute.
        for c in cf:
            c["next_uf_ml_kg_h"] = next_session_intensity(
                d.get("goal", np.nan), c.get("fluid_left_L"),
                d.get("planned_duration", np.nan), d.get("dry", np.nan))
            c["cascade_basis"] = ("planned duration" if c["next_uf_ml_kg_h"] is not None
                                  else "not shown: planned duration unavailable")

        # Personal baseline (field truth #8: nurses trust a tool that knows
        # THEIR patient — typical nadir and the Keane-2021 early-crash share,
        # both from strictly earlier sessions only).
        prior_nadirs, prior_early = [], []
        for psid in prior:
            pd_ = store.get(psid)
            if pd_ is None or len(pd_["et"]) < 4:
                continue
            p_nadir = float(pd_["es"].min())
            prior_nadirs.append(p_nadir)
            j = int(np.argmin(pd_["es"]))
            if p_nadir < 90.0 and float(pd_["et"][j]) <= float(pd_["et"].max()) / 2.0:
                prior_early.append(1.0)
            elif p_nadir < 90.0:
                prior_early.append(0.0)
        hist_nadir_typical = (round(float(np.median(prior_nadirs)), 1)
                              if len(prior_nadirs) >= 2 else None)
        hist_early_share = (round(float(np.mean(prior_early)), 2)
                            if len(prior_early) >= 2 else None)

        band_c = _band_for(band)
        for c in cf:
            c["lo"] = round(max(c["nadir"] + band_c["lo"], NADIR_FLOOR), 1)
            c["hi"] = round(c["nadir"] + band_c["hi"], 1)
        hold = next(c for c in cf if c["policy"] == "hold")
        taper = next(c for c in cf if c["policy"] == "taper25")
        if not hold.get("feasible", False):
            return None       # no causal forecast; never show a fabricated one

        # cheapest taper whose band-lo clears 90. No point-estimate fallback:
        # if none clears, met stays None and the action says so explicitly.
        met = T.min_effective_taper(sweep, band_c, target=90.0, use_band=True)

        facts = _chair_facts(d, t_now)
        vintage = _num(d.get("vintage"))

        return {
            "session_id": sid,
            "pid": str(s.pid),
            "age": _num(d.get("age")),
            "sex": d.get("sex"),
            "dm": _num(d.get("dm")),
            "vintage_years": vintage,
            "dry_weight": _num(d.get("dry")),
            "pre_weight": _num(d.get("pre")),
            "uf_goal_L": _num(d.get("goal")),
            "dia_temp_presc": _num(d.get("temp_presc")),
            "t_now_min": round(t_now, 1),
            "elapsed_min": round(float(d["et"].max()), 1),
            "sbp_now": round(float(np.interp(t_now, d["et"], d["es"])), 1),
            "dbp_now": round(float(np.interp(t_now, d["et"], d["ed"])), 1),
            "risk": round(float(alert.score), 4),
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
            "forecast": T.forecast_path(d, t_now, params,
                                        planned_duration=d.get("planned_duration")),
            "twin": {
                "k_refill": round(float(params["k_refill"]), 3),
                "beta_bp": round(float(params["beta_bp"]), 2),
                "n_prior_sessions": int(params["n_prior_sessions"]),
                "v_removed_L": _num(T.last_observation(
                    d.get("mt", []), d.get("cum_uf", []), t_now)[0]),
                "v_target_L": _num(d.get("goal")),
                "innovation_mmHg": round(float(recon["innovation"]), 1),
                "n_cuffs": int(recon["n_used"]),
            },
            "whatif": cf,
            "sweep": sweep,
            "met": met,
            "delta_nadir": (round(float(taper["nadir"] - hold["nadir"]), 1)
                            if np.isfinite(taper["nadir"]) and
                            np.isfinite(hold["nadir"]) else None),
            "drivers": _drivers(booster, alert_row, feats),
            "action": _action(hold, met, alert),
            "hist_nadir_typical": hist_nadir_typical,
            "hist_early_share": hist_early_share,
            **facts,
        }

    chairs = []
    seen: set[str] = set()
    for s in idh.itertuples():
        c = build_chair(s.session_id, s)
        if c is None:
            continue
        chairs.append(c)
        seen.add(s.pid)
        if len(chairs) >= 30:
            break
    # clean sessions: take a SPREAD, not just the highest-scoring ones. The
    # top of the clean pool is by construction the alarming sessions; the
    # stable majority a ward actually shows lives at the low end.
    clean_rows = list(clean.itertuples())
    spread = clean_rows[:20] + clean_rows[-40:] if len(clean_rows) > 60 else clean_rows
    for s in spread:
        if s.pid in seen:
            continue
        c = build_chair(s.session_id, s)
        if c is None:
            continue
        chairs.append(c)
        seen.add(s.pid)
        if len(chairs) >= 70:
            break

    # ---- compose the ward: triage class from the two engines, not a raw ----
    # ---- probability cutoff. Calibrated scores at 2.8% prevalence rarely  ----
    # ---- exceed 0.5, so a fixed 0.6 "red" line never fires. What actually ----
    # ---- matters: did the alarm fire, and does the twin project a crash?  ----
    thr = threshold if threshold is not None else cal["threshold"]
    for c in chairs:
        hold = next(p for p in c["whatif"] if p["policy"] == "hold")
        c["hold_nadir"] = hold["nadir"]
        alarmed = bool(c["risk"] >= thr)
        crashes = bool(np.isfinite(hold["nadir"]) and hold["nadir"] < 90.0)
        current_low = bool(c.get("sbp_now") is not None and
                           float(c["sbp_now"]) < 90.0)
        if current_low:
            c["triage"] = "act_now"       # rescue state, score-independent
        elif alarmed and crashes:
            c["triage"] = "act_now"
        elif alarmed or crashes:
            c["triage"] = "watch"
        else:
            c["triage"] = "stable"

    rank = {"act_now": 0, "watch": 1, "stable": 2}

    def story(c):
        # crashing chairs: strongest alarm and the clearest taper effect first
        delta = c.get("delta_nadir")
        return (-rank[c["triage"]], -c["risk"],
                -(float(delta) if delta is not None else 0.0))

    picks: list[dict] = []
    used_pids: set[str] = set()
    used_risk: set[float] = set()

    def take(cands: list[dict], k: int) -> list[dict]:
        """Pick patient-disjoint chairs, avoiding repeated risk values (isotonic
        calibration saturates its top bin, and five identical 45% cards read
        as synthetic). The risk-dedupe is soft: it yields when filling fails."""
        out: list[dict] = []
        for c in cands:
            if c["pid"] in used_pids:
                continue
            r = round(c["risk"], 2)
            if r in used_risk and len(picks) + len(out) < n_sessions - 1:
                continue
            out.append(c)
            used_pids.add(c["pid"])
            used_risk.add(r)
            if len(out) >= k:
                break
        return out

    reds = take(sorted([c for c in chairs if c["triage"] == "act_now"], key=story), 2)
    if not reds:
        reds = take(sorted([c for c in chairs if c["session_idh"]], key=story), 2)
    picks += reds
    ambers = take(sorted([c for c in chairs if c["triage"] == "watch"], key=story), 3)
    picks += ambers
    n_green = max(n_sessions - len(picks), 3)
    green_cands = sorted([c for c in chairs
                          if c["triage"] == "stable" and not c["session_idh"]],
                         key=lambda c: c["risk"])
    if len(green_cands) < n_green:
        green_cands += sorted([c for c in chairs if c["triage"] == "stable"
                               and c not in green_cands],
                              key=lambda c: c["risk"])
    greens = take(green_cands, n_green)
    picks += greens

    # diversity: at least one diabetic, one elderly (>=70), one long vintage (>=8y)
    def has(pred):
        return any(pred(c) for c in picks)
    spares = sorted(chairs, key=story)
    for pred in ((lambda c: c.get("dm") == 1),
                 (lambda c: (c.get("age") or 0) >= 70),
                 (lambda c: (c.get("vintage_years") or 0) >= 8.0)):
        if not has(pred):
            for c in spares:
                if pred(c) and c["pid"] not in used_pids:
                    picks.append(c)
                    used_pids.add(c["pid"])
                    break

    chairs = picks[:n_sessions]
    if len(chairs) < 4:
        chairs = picks
    chairs.sort(key=lambda c: (rank[c["triage"]], -c["risk"]))
    for i, c in enumerate(chairs, start=1):
        c["chair"] = i

    return {
        "meta": {
            "product": "HemoTwin",
            "schema_version": "task00",
            "hook": "Predict the crash. Price the fix.",
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "dataset": "HEMOBP (Lin et al., Sci Data 2019), CC BY 4.0",
            "threshold": thr,
            "horizon_min": [CONFIG["HORIZON_LO"], CONFIG["HORIZON_HI"]],
            "bp_projection_min": 60,
            "n_sessions_demo": len(chairs),
            "band": band if band else {"lo": -12.0, "hi": 12.0},
            "policies": list(WHATIF_POLICIES),
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
            "twin_benchmark": twin_benchmark,
        },
        "chairs": chairs,
    }
