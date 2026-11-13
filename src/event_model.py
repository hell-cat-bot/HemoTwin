"""Task 02 event model and online alarm replay.

The event model predicts the first observed SBP<90 crossing in (t+15,t+60].
The online policy scores every observed cuff with sufficient causal history and
runs a frozen, non-resetting 60-minute refractory state machine. Current
SBP<90 is rescue, never a forecast alert. No quantitative treatment
recommendation is produced here.
"""
from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from .config import CONFIG
from .labels import outcome_coverage

SEEDS = (42, 43, 44)
REFRACTORY_MIN = 60


def cap_negatives(df: pd.DataFrame, k: int | None = None,
                  seed: int = 42) -> pd.DataFrame:
    k = CONFIG["MAX_NEG_ANCHORS_PER_SESSION_TRAIN"] if k is None else k
    if k is None:
        return df
    rng = np.random.default_rng(seed)
    keep = []
    for _, g in df.groupby("session_id", observed=True):
        pos = g[g.label == 1]
        neg = g[g.label == 0]
        if len(neg) > k:
            neg = neg.iloc[rng.choice(len(neg), k, replace=False)]
        keep.append(pos)
        keep.append(neg)
    return pd.concat(keep).sort_values(["session_id", "t_min"]).reset_index(drop=True)


def train_boosters(fit_df: pd.DataFrame, early_df: pd.DataFrame,
                   feats: list[str], seeds=SEEDS) -> tuple[list, list]:
    if len(early_df) == 0:
        raise ValueError("early-stop frame is empty")
    ytr = fit_df.label.to_numpy(int)
    yva = early_df.label.to_numpy(int)
    spw = min((ytr == 0).sum() / max((ytr == 1).sum(), 1),
              CONFIG["SCALE_POS_WEIGHT_CAP"])
    boosters, iters = [], []
    for seed in seeds:
        params = dict(
            objective="binary",
            learning_rate=CONFIG["LEARNING_RATE"],
            num_leaves=CONFIG["NUM_LEAVES"],
            min_child_samples=CONFIG["MIN_CHILD_SAMPLES"],
            feature_fraction=CONFIG["FEATURE_FRACTION"],
            bagging_fraction=CONFIG["BAGGING_FRACTION"],
            bagging_freq=1,
            scale_pos_weight=spw,
            metric=["average_precision", "auc"],
            verbosity=-1,
            seed=seed,
        )
        dtr = lgb.Dataset(fit_df[feats], label=ytr)
        dva = lgb.Dataset(early_df[feats], label=yva, reference=dtr)
        booster = lgb.train(
            params, dtr, num_boost_round=CONFIG["MAX_ROUNDS"],
            valid_sets=[dva],
            callbacks=[lgb.early_stopping(CONFIG["EARLY_STOPPING"], verbose=False),
                       lgb.log_evaluation(0)])
        boosters.append(booster)
        iters.append(max(int(booster.best_iteration), 1))
    return boosters, iters


def raw_predict(boosters, df: pd.DataFrame, feats: list[str]) -> np.ndarray:
    return np.mean([b.predict(df[feats], num_iteration=b.best_iteration)
                    for b in boosters], axis=0)


def fit_isotonic(raw, y) -> IsotonicRegression:
    return IsotonicRegression(out_of_bounds="clip").fit(
        np.asarray(raw, float), np.asarray(y, int))


def predict_calibrated(boosters, iso, df: pd.DataFrame,
                       feats: list[str]) -> np.ndarray:
    return np.clip(iso.predict(raw_predict(boosters, df, feats)), 0.0, 1.0)


def save_model(boosters, iso, feats: list[str], threshold,
               path_prefix: str | Path, best_iters=None) -> None:
    prefix = Path(path_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for i, b in enumerate(boosters):
        p = prefix.with_name(f"{prefix.name}_m{i}.txt")
        b.save_model(str(p))
        files.append(p.name)
    knots = {"x": iso.X_thresholds_.tolist(),
             "y": iso.y_thresholds_.tolist()}
    prefix.with_name(f"{prefix.name}_isotonic.json").write_text(
        json.dumps(knots))
    meta = {"feats": feats, "members": len(boosters), "files": files,
            "threshold": threshold, "best_iters": best_iters,
            "label": "first observed SBP<90 in (t+15,t+60]"}
    prefix.with_name(f"{prefix.name}_meta.json").write_text(
        json.dumps(meta, indent=2))


def load_model(path_prefix: str | Path):
    prefix = Path(path_prefix)
    meta = json.loads(prefix.with_name(f"{prefix.name}_meta.json").read_text())
    boosters = [lgb.Booster(model_file=str(prefix.with_name(f)))
                for f in meta["files"]]
    knots = json.loads(prefix.with_name(
        f"{prefix.name}_isotonic.json").read_text())
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(np.asarray(knots["x"], float), np.asarray(knots["y"], float))
    return boosters, iso, meta["feats"], meta["threshold"], meta


def _outcome(session: dict, t_alert: float, score: float) -> dict:
    onset = float(session["onset"])
    et = np.asarray(session["et"], dtype=float)
    useful = bool(np.isfinite(onset) and onset > t_alert
                  and onset <= t_alert + 60.0)
    timely = bool(np.isfinite(onset) and onset >= t_alert + 15.0
                  and onset <= t_alert + 60.0)
    cov = outcome_coverage(et, t_alert, onset, horizon_lo=0, horizon_hi=60,
                           session_end=float(session["session_end"]))
    confirmed_false = bool((not useful) and cov["coverage_complete"])
    indeterminate = bool((not useful) and not cov["coverage_complete"])
    return {
        "t_alert": float(t_alert),
        "score": float(score),
        "lead_time_min": float(onset - t_alert) if timely else None,
        "timely": timely,
        "useful": useful,
        "confirmed_false": confirmed_false,
        "indeterminate": indeterminate,
        "coverage_complete": bool(cov["coverage_complete"]),
    }


def run_session(session: dict, threshold, refractory: float = REFRACTORY_MIN) -> dict:
    """Frozen online state machine for one session."""
    alerts = []
    states = []
    last_alert = -np.inf
    post_event = False
    online = sorted(session.get("online", []), key=lambda x: x["t"])
    for row in online:
        t = float(row["t"])
        sbp = float(row.get("sbp", np.nan))
        score = float(row.get("score", np.nan))
        onset = float(session["onset"])
        if post_event or (np.isfinite(onset) and t >= onset):
            state = "rescue" if np.isfinite(sbp) and sbp < 90.0 else "post_event"
            post_event = True
            states.append((t, state))
            continue
        if np.isfinite(sbp) and sbp < 90.0:
            states.append((t, "rescue"))
            post_event = True
            continue
        if not np.isfinite(score) or not np.isfinite(sbp):
            states.append((t, "unscorable"))
            continue
        if threshold is None:
            states.append((t, "no_alert"))
            continue
        if not (score >= float(threshold)):
            states.append((t, "below_threshold"))
            continue
        if t < last_alert + refractory:
            states.append((t, "suppressed"))
            continue
        last_alert = t
        alerts.append(_outcome(session, t, score))
        states.append((t, "alert"))
    n_unscorable = sum(1 for _, s in states if s == "unscorable")
    n_online = len(states)
    return {
        "session_id": session["session_id"],
        "pid": session["pid"],
        "session_end": float(session["session_end"]),
        "event": bool(np.isfinite(float(session["onset"]))),
        "no_warning_window": bool(session.get("no_warning_window", False)),
        "n_online": n_online,
        "n_scored": n_online - n_unscorable,
        "n_unscorable": n_unscorable,
        "alerts": alerts,
        "states": states,
        "n_alerts": len(alerts),
        "detected_timely": bool(any(a["timely"] for a in alerts)),
        "detected_useful": bool(any(a["useful"] for a in alerts)),
        "n_useful": sum(1 for a in alerts if a["useful"]),
        "n_timely": sum(1 for a in alerts if a["timely"]),
        "n_false": sum(1 for a in alerts if a["confirmed_false"]),
        "n_indeterminate": sum(1 for a in alerts if a["indeterminate"]),
        "post_event": post_event,
    }


def summarize_replay(sessions: list[dict], threshold, policy: str = "policy",
                     fold: int | None = None) -> dict:
    rows = [run_session(s, threshold) for s in sessions]
    n_sessions = len(rows)
    event_rows = [r for r in rows if r["event"]]
    n_event = len(event_rows)
    n_detected = sum(1 for r in event_rows if r["detected_timely"])
    n_useful_detected = sum(1 for r in event_rows if r["detected_useful"])
    n_alerts = sum(r["n_alerts"] for r in rows)
    n_useful = sum(r["n_useful"] for r in rows)
    n_timely = sum(r["n_timely"] for r in rows)
    n_false = sum(r["n_false"] for r in rows)
    n_indet = sum(r["n_indeterminate"] for r in rows)
    non_useful = n_false + n_indet
    n_online = sum(r["n_online"] for r in rows)
    n_unscorable = sum(r["n_unscorable"] for r in rows)
    lead = [a["lead_time_min"] for r in rows for a in r["alerts"]
            if a["lead_time_min"] is not None]
    alert_sessions = sum(1 for r in rows if r["n_alerts"] > 0)
    repeat = sum(1 for r in rows if r["n_alerts"] > 1)
    session_hours = sum(max(float(s["session_end"]), 0.0) for s in sessions) / 60.0
    for r in rows:
        r["policy"] = policy
        r["fold"] = fold
        r["threshold"] = threshold
    return {
        "policy": policy, "fold": fold, "threshold": threshold,
        "n_sessions": n_sessions,
        "n_event_sessions": n_event,
        "n_event_sessions_no_warning": sum(1 for r in event_rows
                                            if r["no_warning_window"]),
        "timely_detected": n_detected,
        "detection": n_detected / max(n_event, 1),
        "useful_detected": n_useful_detected,
        "useful_detection": n_useful_detected / max(n_event, 1),
        "n_alerts": n_alerts,
        "n_useful": n_useful,
        "n_timely": n_timely,
        "n_confirmed_false": n_false,
        "n_indeterminate": n_indet,
        "non_useful_episodes": non_useful,
        "burden": non_useful / max(n_sessions, 1),
        "confirmed_false_per_session": n_false / max(n_sessions, 1),
        "indeterminate_per_session": n_indet / max(n_sessions, 1),
        "alerts_per_session": n_alerts / max(n_sessions, 1),
        "repeat_alert_rate": repeat / max(alert_sessions, 1),
        "unscorable_share": n_unscorable / max(n_online, 1),
        "useful_ppv": n_useful / max(n_alerts, 1),
        "timely_ppv": n_timely / max(n_alerts, 1),
        "timely_among_useful": n_timely / max(n_useful, 1),
        "lead_time_median": float(np.median(lead)) if lead else None,
        "lead_time_iqr": ([float(np.percentile(lead, 25)),
                           float(np.percentile(lead, 75))] if lead else None),
        "false_alerts_per_session_hour": non_useful / max(session_hours, 1e-9),
        "simulated_non_useful_per_8chair_8h_shift": (
            non_useful / max(session_hours, 1e-9) * 8 * 8),
        "rows": rows,
    }


def threshold_grid(scores) -> list:
    s = np.asarray(scores, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return [None]
    qs = np.unique(np.quantile(s, np.linspace(0.0, 1.0, 101)))
    return [float(x) for x in qs] + [None]


def select_threshold(sessions: list[dict], policy: str,
                     budget: float = 0.25) -> dict:
    scores = [row.get("score", np.nan) for s in sessions for row in s["online"]]
    candidates = threshold_grid(scores)
    best = None
    trials = []
    for cand in candidates:
        summ = summarize_replay(sessions, cand, policy)
        feasible = bool(summ["burden"] <= budget)
        trials.append({
            "threshold": cand,
            "detection": summ["detection"],
            "burden": summ["burden"],
            "n_alerts": summ["n_alerts"],
            "timely_detected": summ["timely_detected"],
            "feasible": feasible,
        })
        if not feasible:
            continue
        key = (summ["detection"], -summ["burden"],
               cand if cand is not None else -np.inf)
        if best is None or key > best[0]:
            best = (key, cand, summ)
    if best is None or best[2]["detection"] <= 0.0:
        fallback = summarize_replay(sessions, None, policy)
        return {**fallback, "selection": "no_alert_fallback",
                "candidates": len(candidates), "trials": trials}
    _, cand, summ = best
    return {**summ, "selection": "budgeted", "candidates": len(candidates),
            "trials": trials}


def bootstrap_policies(session_tables: dict[str, list[dict]],
                       n_boot: int = 1000, seed: int = 20261108) -> dict:
    """Paired patient-clustered bootstrap for detection and burden."""
    policies = list(session_tables)
    tabs = {p: {r["session_id"]: r for r in session_tables[p]} for p in policies}
    base = tabs[policies[0]]
    by_pid: dict[str, list[str]] = {}
    for sid, r in base.items():
        by_pid.setdefault(r["pid"], []).append(sid)
    rng = np.random.default_rng(seed)
    diffs = {p: [] for p in policies[1:]}
    burdens = {p: [] for p in policies[1:]}
    detection = {p: [] for p in policies}
    burden = {p: [] for p in policies}
    for _ in range(n_boot):
        pids = rng.choice(list(by_pid), size=len(by_pid), replace=True)
        sids = [sid for p in pids for sid in by_pid[p]]
        vals = {}
        for pol in policies:
            tab = tabs[pol]
            rows = [tab[s] for s in sids]
            ev = sum(1 for r in rows if r["event"])
            det = sum(1 for r in rows if r["event"] and r["detected_timely"])
            nus = sum(r["n_false"] + r["n_indeterminate"] for r in rows)
            vals[pol] = (det / max(ev, 1), nus / max(len(rows), 1))
            detection[pol].append(vals[pol][0])
            burden[pol].append(vals[pol][1])
        for p in policies[1:]:
            diffs[p].append(vals[p][0] - vals[policies[0]][0])
            burdens[p].append(vals[p][1] - vals[policies[0]][1])
    out = {}
    for p in policies:
        out[p] = {
            "detection_ci": [float(np.percentile(detection[p], 2.5)),
                             float(np.percentile(detection[p], 97.5))],
            "burden_ci": [float(np.percentile(burden[p], 2.5)),
                          float(np.percentile(burden[p], 97.5))],
        }
        if p in diffs:
            out[p]["detection_diff_vs_" + policies[0]] = [
                float(np.percentile(diffs[p], 2.5)),
                float(np.percentile(diffs[p], 97.5))]
            out[p]["burden_diff_vs_" + policies[0]] = [
                float(np.percentile(burdens[p], 2.5)),
                float(np.percentile(burdens[p], 97.5))]
    return out
