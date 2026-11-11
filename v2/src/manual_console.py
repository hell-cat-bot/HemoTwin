"""Manual/CSV inference backend for the ordinary-machine risk console.

This is the real inference path: the corrected universal feature builder, the
fold-0 LightGBM ensemble, isotonic calibrator, and the frozen alarm state
machine. It never uses a precomputed score and never produces a quantitative
treatment recommendation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import event_model as E
from . import manual as M
from .paths import MODELS

ROOT = Path(__file__).resolve().parents[1]
TASK02 = MODELS / "event_model"
STALE_MIN = 60.0

DRIVER_LABELS = {
    "sbp_now": "Current systolic BP", "dbp_now": "Current diastolic BP",
    "map_now": "Current MAP", "sbp_slope_15": "SBP trend 15 min",
    "sbp_slope_30": "SBP trend 30 min", "sbp_slope_60": "SBP trend 60 min",
    "sbp_min_30": "Lowest SBP 30 min", "sbp_min_60": "Lowest SBP 60 min",
    "sbp_drop_from_max": "Drop from session maximum",
    "uf_Lh": "Current UF rate", "uf_ml_kg_h": "UF intensity",
    "cum_uf_L": "Fluid removed so far", "uf_goal_L": "UF goal",
    "frac_uf_done": "Fraction of goal removed", "uf_change_prev": "UF change",
    "uf_delta_30": "UF change 30 min", "uf_delta_60": "UF change 60 min",
    "cuff_gap": "Cuff gap", "gap_since_last": "Minutes since last cuff",
    "elapsed_min": "Elapsed minutes", "pulse_pressure": "Pulse pressure",
    "sbp_std_30": "SBP variability 30 min", "sbp_std_60": "SBP variability 60 min",
    "map_slope_30": "MAP trend 30 min", "hist_idh_rate10": "IDH rate, last 10 sessions",
    "hist_mean_nadir3": "Mean nadir, last 3 sessions",
    "hist_prev_nadir": "Previous nadir", "age": "Age",
    "dry_weight": "Dry weight", "pre_weight": "Pre-weight",
    "vintage_years": "Dialysis vintage", "dm": "Diabetes",
}


def model_paths(model_dir: str | Path | None = None,
                threshold_file: str | Path | None = None):
    if model_dir is None:
        candidates = [TASK02 / "models" / "fold_0" / "universal",
                      TASK02 / "smoke" / "models" / "fold_0" / "universal"]
        model_dir = next((p for p in candidates
                          if p.with_name(p.name + "_meta.json").exists()), candidates[0])
    model_dir = Path(model_dir)
    if threshold_file is None:
        candidates = [TASK02 / "thresholds.json",
                      TASK02 / "smoke" / "thresholds.json"]
        threshold_file = next((p for p in candidates if p.exists()), candidates[0])
    threshold = None
    if Path(threshold_file).exists():
        data = json.loads(Path(threshold_file).read_text())
        threshold = data.get("fold_0_universal", {}).get("threshold")
    return model_dir, threshold


def _num(x, default=np.nan):
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except Exception:  # noqa: BLE001
        return default


def validate_session(start: dict, cuffs: list[dict],
                     as_of_min: float | None = None,
                     current_time_min: float | None = None) -> tuple[dict | None, list[str], str | None]:
    """Validate and normalise a manual session; return (session, warnings, error)."""
    warnings = []
    sid = str(start.get("session_id") or "manual_session")
    pre = _num(start.get("pre_weight"))
    dry = _num(start.get("dry_weight"))
    if not np.isfinite(pre) or not (20 <= pre <= 300):
        return None, warnings, "pre-weight must be 20-300 kg"
    if not np.isfinite(dry) or not (20 <= dry <= 200):
        return None, warnings, "dry/target weight must be 20-200 kg"
    if pre < dry:
        warnings.append("pre-weight is below dry weight; UF goal is zero")
    goal = max(pre - dry, 0.0)
    if goal <= 0.3:
        warnings.append("weight-derived UF goal <= 0.3 L; goal features are missing")
        goal = np.nan
    age = _num(start.get("age"))
    if not np.isfinite(age) or not (18 <= age <= 120):
        return None, warnings, "age must be 18-120"
    sex = str(start.get("sex", "")).upper()
    if sex not in ("M", "F"):
        return None, warnings, "sex must be M or F"
    dm = _num(start.get("dm"), 0.0)
    if dm not in (0.0, 1.0):
        return None, warnings, "diabetes must be 0 or 1"
    vintage = _num(start.get("vintage_years"), 0.0)
    if not np.isfinite(vintage) or vintage < 0:
        return None, warnings, "vintage must be >= 0"

    rows = []
    raw_times = [_num(c.get("t")) for c in cuffs]
    raw_times = [t for t in raw_times if np.isfinite(t) and t >= 0]
    target = float(as_of_min) if as_of_min is not None else (
        max(raw_times) if raw_times else np.nan)
    cum_entered = []
    for i, c in enumerate(cuffs):
        t = _num(c.get("t"))
        sbp = _num(c.get("sbp"))
        dbp = _num(c.get("dbp"))
        uf = _num(c.get("uf"))
        cum = _num(c.get("cumulative_uf"))
        if not np.isfinite(t) or t < 0:
            return None, warnings, f"cuff {i + 1}: elapsed time is missing/invalid"
        if not np.isfinite(sbp) or not np.isfinite(dbp):
            if np.isfinite(target) and t >= target - 1e-9:
                return None, warnings, "current BP is missing; scoring is blocked"
            warnings.append(f"cuff at {t:.0f} min has missing BP and was skipped")
            continue
        if not (40 <= sbp <= 250) or not (20 <= dbp <= 150) or sbp <= dbp:
            return None, warnings, f"cuff at {t:.0f} min has impossible BP"
        if not np.isfinite(uf) or not (0 <= uf <= 6):
            return None, warnings, f"cuff at {t:.0f} min has invalid UF (0-6 L/h)"
        if np.isfinite(cum):
            cum_entered.append((float(t), float(cum)))
        rows.append({"t": float(t), "sbp": float(sbp), "dbp": float(dbp),
                     "uf": float(uf), "cumulative_uf": cum})
    if len(cum_entered) >= 2:
        vals = [v for _, v in sorted(cum_entered)]
        if any(vals[i] < vals[i - 1] - 1e-9 for i in range(1, len(vals))):
            warnings.append("entered cumulative UF is not monotonic; the model "
                            "uses the cuff-only reconstruction")
    if not rows:
        return None, warnings, "no valid cuff entries"
    rows.sort(key=lambda r: r["t"])
    times = np.array([r["t"] for r in rows], dtype=float)
    if len(np.unique(times)) != len(times):
        return None, warnings, "duplicate cuff times"
    if as_of_min is None:
        as_of_min = float(times[-1])
    as_of_min = float(as_of_min)
    rows = [r for r in rows if r["t"] <= as_of_min + 1e-9]
    if not rows:
        return None, warnings, "no cuff at or before the scoring time"
    times = np.array([r["t"] for r in rows], dtype=float)
    if current_time_min is not None and current_time_min > times[-1] + STALE_MIN:
        return None, warnings, (f"stale current BP: last cuff is "
                                f"{current_time_min - times[-1]:.0f} min old")
    if len(rows) < 3:
        warnings.append("fewer than three cuffs; the model needs two earlier cuffs")
    # Cuff-only cumulative from entered rates.
    uf = np.array([r["uf"] for r in rows], dtype=float)
    cum = np.zeros(len(rows))
    for i in range(1, len(rows)):
        dt = times[i] - times[i - 1]
        cum[i] = cum[i - 1] + (uf[i - 1] + uf[i]) / 2.0 * dt / 60.0
    gaps = np.diff(times, prepend=np.nan)
    change = np.diff(uf, prepend=np.nan)
    d = {
        "session_id": sid, "pid": sid,
        "et": times,
        "es": np.array([r["sbp"] for r in rows], dtype=float),
        "ed": np.array([r["dbp"] for r in rows], dtype=float),
        "cuff_uf": uf, "cuff_cum": cum,
        "cuff_gap": gaps, "cuff_uf_change": change,
        "dry": dry, "pre": pre, "goal": goal,
        "age": age, "sex": sex, "dm": dm, "vintage": vintage,
        "month": int(start.get("month") or 1),
        "as_of_min": as_of_min,
    }
    return d, warnings, None


def _frame(feats: list[str], d: dict, t: float) -> pd.DataFrame:
    row = M.universal_features(d, t, d["session_id"])
    if not row:
        return pd.DataFrame()
    for c in feats:
        row.setdefault(c, np.nan)
    return pd.DataFrame([row])[feats]


def _drivers(booster, frame: pd.DataFrame, feats: list[str], k: int = 3) -> list[dict]:
    try:
        contrib = booster.predict(frame[feats], pred_contrib=True)
        if contrib.ndim == 3:
            contrib = contrib[:, :-1, 1]
        vals = contrib[0, :-1]
        order = np.argsort(-np.abs(vals))[:k]
        out = []
        for i in order:
            name = feats[int(i)]
            out.append({"feature": name,
                        "label": DRIVER_LABELS.get(name, name.replace("_", " ")),
                        "value": float(frame.iloc[0][name])
                        if np.isfinite(_num(frame.iloc[0][name])) else None,
                        "contribution": round(float(vals[int(i)]), 4)})
        return out
    except Exception:  # noqa: BLE001
        return []


def score_session(start: dict, cuffs: list[dict],
                  model_dir: str | Path | None = None,
                  threshold_file: str | Path | None = None,
                  as_of_min: float | None = None,
                  current_time_min: float | None = None,
                  history: dict | None = None) -> dict:
    model_dir, threshold = model_paths(model_dir, threshold_file)
    d, warnings, err = validate_session(start, cuffs, as_of_min, current_time_min)
    if err:
        return {"scorable": False, "reason": err, "warnings": warnings,
                "alert_state": "unscorable", "risk": None, "threshold": threshold}
    boosters, iso, feats, _meta_thr, meta = E.load_model(model_dir)
    as_of = d["as_of_min"]
    # The first two cuffs cannot satisfy the two-earlier-cuff scoring rule.
    online = []
    for t in d["et"]:
        if t < 30.0 or int(np.sum(d["et"] < t)) < 2:
            continue
        frame = _frame(feats, d, float(t))
        if frame.empty:
            continue
        if history:
            for c, v in history.items():
                if c in feats:
                    frame[c] = v
        raw = float(E.raw_predict(boosters, frame, feats)[0])
        cal = float(np.clip(iso.predict([raw])[0], 0.0, 1.0))
        online.append({"t": float(t),
                       "sbp": float(d["es"][np.where(d["et"] == t)[0][0]]),
                       "score": raw, "risk": cal, "frame": frame})
    if not online:
        return {"scorable": False,
                "reason": "fewer than three cuffs; no model-scorable cuff",
                "warnings": warnings, "alert_state": "unscorable",
                "risk": None, "threshold": threshold}
    session = {"session_id": d["session_id"], "pid": d["pid"], "et": d["et"],
               "onset": float("inf"), "session_end": float(d["et"][-1]),
               "online": [{"t": o["t"], "sbp": o["sbp"], "score": o["score"]}
                          for o in online]}
    state = E.run_session(session, threshold)
    latest = online[-1]
    last_state = state["states"][-1][1] if state["states"] else "unscorable"
    current_sbp = latest["sbp"]
    if np.isfinite(current_sbp) and current_sbp < 90.0:
        alert_state = "rescue"
    elif last_state == "rescue":
        alert_state = "rescue"
    elif state["post_event"]:
        alert_state = "post_event"
    else:
        alert_state = last_state
    uf_ml = M.universal_features(d, as_of, d["session_id"]).get("uf_ml_kg_h", np.nan)
    if alert_state == "rescue":
        guideline = ("Current SBP is below 90 mmHg: follow the locally approved "
                     "hypotension/rescue protocol now, recheck BP, and escalate. "
                     "This rescue state does not depend on the forecast score. "
                     "No default fluid dose is supplied by this prototype.")
    elif alert_state == "alert":
        guideline = ("Risk is above the frozen alert threshold. Follow local "
                     "protocol: consider stopping or tapering UF per unit "
                     "protocol. No validated quantitative prescription is "
                     "provided; recheck at the next cuff.")
    elif alert_state == "suppressed":
        guideline = ("An alert was already emitted within the 60-minute "
                     "refractory window. Recheck at the next cuff.")
    elif alert_state == "post_event":
        guideline = ("Post-event/recovery: no new forecast alert. Follow local "
                     "hypotension protocol and recheck at the next cuff.")
    elif alert_state == "below_threshold":
        guideline = "Below the alert threshold. Continue and recheck at the next cuff."
    elif alert_state == "no_alert":
        guideline = "No alert threshold is active. Follow routine cuff monitoring."
    else:
        guideline = "Scoring unavailable. Recheck the data and follow local protocols."
    return {
        "scorable": True, "reason": None, "warnings": warnings,
        "risk": float(latest["risk"]), "threshold": threshold,
        "alert_state": alert_state, "current_sbp": float(current_sbp),
        "as_of_min": float(as_of), "n_scored": len(online),
        "uf_ml_kg_h": float(uf_ml) if np.isfinite(uf_ml) else None,
        "uf_over13": bool(np.isfinite(uf_ml) and uf_ml > 13.0),
        "stale_min": (float(current_time_min - as_of)
                      if current_time_min is not None else 0.0),
        "drivers": _drivers(boosters[0], latest["frame"], feats),
        "guideline": guideline,
        "model": str(model_dir),
        "provenance": "fold-0 universal model; retrospective evaluation artifact",
    }


def parse_csv(text: str) -> list[dict]:
    """Parse the cuff CSV. Required columns: elapsed_min, sbp, dbp, uf_Lh."""
    df = pd.read_csv(pd.io.common.StringIO(text))
    required = {"elapsed_min", "sbp", "dbp", "uf_Lh"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")
    out = []
    for _, r in df.iterrows():
        out.append({"t": r["elapsed_min"], "sbp": r["sbp"], "dbp": r["dbp"],
                    "uf": r["uf_Lh"],
                    "cumulative_uf": r.get("cumulative_uf", np.nan)})
    return out


def save_note(session_id: str, action: str, role: str, next_cuff: str,
              result: dict, out_dir: str | Path | None = None) -> Path:
    out_dir = Path(out_dir or ROOT / "demo" / "manual_logs")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"manual_{session_id}.jsonl"
    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "role": role,
        "action": action,
        "next_cuff": next_cuff,
        "risk": result.get("risk"),
        "alert_state": result.get("alert_state"),
        "threshold": result.get("threshold"),
        "as_of_min": result.get("as_of_min"),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return path
