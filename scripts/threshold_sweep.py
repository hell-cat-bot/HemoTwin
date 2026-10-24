"""Threshold sweep and decision-curve analysis on the held-out test split.

    python scripts/threshold_sweep.py

Answers the question a reviewer always asks: "why 0.0410?" The operating
threshold is a clinical-staffing trade-off, so we show the whole trade-off
curve instead of asserting one number.

Reads the saved test predictions (artifacts/predictions_test.parquet), so it
needs no retraining and no raw data. Writes artifacts/threshold_sweep.json.

Three families of metric, all at the level a nurse experiences:

  1. Detection    - IDH sessions flagged before onset, inside the same
                    [onset-60, onset-15] window the model was trained on.
  2. Alarm burden - share of uncomplicated sessions that raise an alarm.
  3. Net benefit  - decision-curve analysis at the session level. For a
                    threshold probability of benefit pt, the value of
                    alarming a session is
                        NB = TP/n - FP/n * (pt / (1 - pt))
                    compared against "alarm on everyone" and "never alarm".
                    A threshold is worth choosing only where our curve sits
                    above both baselines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import ARTIFACTS, CONFIG  # noqa: E402

PRED = ARTIFACTS / "predictions_test.parquet"
OUT = ARTIFACTS / "threshold_sweep.json"

WARN_LO = CONFIG["HORIZON_LO"]
WARN_HI = CONFIG["HORIZON_HI"]
FROZEN = 0.040957015409570155

# Decision-curve threshold probabilities of benefit.
PTS = (0.05, 0.10, 0.20)
PT_KEYS = {pt: f"{pt:.2f}" for pt in PTS}


def session_table(preds: pd.DataFrame) -> pd.DataFrame:
    """One row per session: was it an IDH session, and what is its max score.

    Also records whether the session had at least one anchor inside the
    warnable window, so we can separate "model missed it" from "the cuff
    cadence left no usable anchor".
    """
    p = preds.sort_values(["session_id", "t_min"])
    rows = []
    for sid, g in p.groupby("session_id", observed=True):
        onset = g.onset_min.iloc[0]
        has_event = bool(np.isfinite(onset))
        if has_event:
            t = g.t_min.to_numpy()
            m = (t >= onset - WARN_HI) & (t <= onset - WARN_LO)
            has_anchor = bool(m.any())
            max_in_window = float(g.score.to_numpy()[m].max()) if m.any() else np.nan
        else:
            has_anchor = True          # no event to be early for
            max_in_window = np.nan
        rows.append({
            "session_id": sid,
            "has_event": has_event,
            "has_anchor": has_anchor,
            "max_score": float(g.score.max()),
            "max_in_window": max_in_window,
        })
    return pd.DataFrame(rows)


def sweep(sess: pd.DataFrame, thresholds: np.ndarray) -> list[dict]:
    ev = sess[sess.has_event]
    noev = sess[~sess.has_event]
    n_ev, n_noev = len(ev), len(noev)
    n_all = len(sess)

    # "Alarm on everyone" and "never alarm" reference lines.
    # Treat-all flags every session: TP = all IDH sessions, FP = all non-IDH.
    nb_treat_all = {PT_KEYS[pt]: (n_ev / n_all) - (n_noev / n_all) * (pt / (1 - pt))
                    for pt in PTS}
    nb_treat_none = {PT_KEYS[pt]: 0.0 for pt in PTS}

    out = []
    for thr in thresholds:
        # Detection: an alarm must fire inside the warnable window.
        win = ev[ev.has_anchor]
        detected = int((win.max_in_window >= thr).sum())
        missed = int(len(win) - detected)
        no_anchor = int((~ev.has_anchor).sum())
        n_idh = int(len(ev))

        # Alarm burden: any alarm at all in a session that did not crash.
        fa_sessions = int((noev.max_score >= thr).sum())

        # Flagged sessions overall and how many of them truly crashed.
        flagged = sess[sess.max_score >= thr]
        n_flag = int(len(flagged))
        tp = int(flagged.has_event.sum())
        ppv = tp / n_flag if n_flag else 0.0

        # Decision curve: value of alarming, per session.
        fp = fa_sessions
        nb = {PT_KEYS[pt]: (detected / n_all) - (fp / n_all) * (pt / (1 - pt))
              for pt in PTS}

        out.append({
            "threshold": float(thr),
            "is_frozen": bool(abs(thr - FROZEN) < 1e-9),
            "detection_rate_all_sessions": detected / n_idh if n_idh else 0.0,
            "detection_rate_evaluable": detected / (detected + missed)
            if (detected + missed) else 0.0,
            "n_idh_sessions": n_idh,
            "detected": detected,
            "missed": missed,
            "no_anchor_window": no_anchor,
            "false_alarm_session_rate": fa_sessions / n_noev if n_noev else 0.0,
            "n_false_alarm_sessions": fa_sessions,
            "sessions_flagged": n_flag,
            "flagged_share": n_flag / n_all if n_all else 0.0,
            "session_ppv": ppv,
            "net_benefit": nb,
        })
    return out


def build_report(preds: pd.DataFrame) -> dict:
    """Compute the full sweep + decision-curve report from test predictions."""
    sess = session_table(preds)
    n_ev = int(sess.has_event.sum())

    thresholds = np.array([
        0.005, 0.010, 0.015, 0.020, 0.025, 0.030, 0.035,
        0.040957015409570155,   # the frozen operating point
        0.050, 0.060, 0.080, 0.100, 0.150, 0.200, 0.300,
    ])
    rows = sweep(sess, thresholds)

    n_all = len(sess)
    n_noev = int((~sess.has_event).sum())
    baselines = {
        "treat_all": {PT_KEYS[pt]: (n_ev / n_all) - (n_noev / n_all) * (pt / (1 - pt))
                      for pt in PTS},
        "treat_none": {PT_KEYS[pt]: 0.0 for pt in PTS},
        "n_sessions": n_all,
        "n_idh_sessions": n_ev,
    }

    # Which thresholds beat "never alarm" at pt = 0.10?
    useful = [r["threshold"] for r in rows
              if r["net_benefit"]["0.10"] > baselines["treat_none"]["0.10"] + 1e-9]
    frozen = next(r for r in rows if r["is_frozen"])

    # Where does the model beat "alarm on everyone"? This is the strongest
    # defensible claim: not "we detect more", but "we are worth listening to
    # in the cost regime a real ward operates in".
    beats_treat_all = {}
    for pt in PTS:
        k = PT_KEYS[pt]
        win = [r["threshold"] for r in rows
               if r["net_benefit"][k] > baselines["treat_all"][k] + 1e-9]
        beats_treat_all[k] = [min(win), max(win)] if win else None

    # The threshold that maximises net benefit at pt = 0.10.
    best = max(rows, key=lambda r: r["net_benefit"]["0.10"])

    # False alarms per 1,000 sessions, the unit a ward manager thinks in.
    for r in rows:
        r["false_alarms_per_1000_sessions"] = (
            r["n_false_alarm_sessions"] / n_all * 1000 if n_all else 0.0)

    return {
        "source": "artifacts/predictions_test.parquet (held-out test split)",
        "split": "patient-disjoint",
        "warn_window_min": [WARN_LO, WARN_HI],
        "frozen_threshold": FROZEN,
        "n_sessions": n_all,
        "n_idh_sessions": n_ev,
        "prevalence_session_level": n_ev / n_all if n_all else 0.0,
        "baselines": baselines,
        "sweep": rows,
        "useful_threshold_range": [min(useful), max(useful)] if useful else None,
        "beats_treat_all_range": beats_treat_all,
        "net_benefit_optimal_threshold": best["threshold"],
        "frozen_row": frozen,
    }


def embed_in_bundle(report: dict, bundle_path: Path | None = None) -> None:
    """Fold the sweep into the committed demo bundle.

    artifacts/ is git-ignored, so without this the dashboard could not show
    the operating-point trade-off for a reviewer who only cloned the repo.
    """
    bundle_path = bundle_path or (ROOT / "demo" / "demo_bundle.json")
    if not bundle_path.exists():
        print("note: demo/demo_bundle.json not found; skipped embedding",
              file=sys.stderr)
        return
    bundle = json.loads(bundle_path.read_text())
    bundle["threshold_sweep"] = report
    bundle_path.write_text(json.dumps(bundle, indent=2))
    print(f"embedded sweep -> {bundle_path}")


def main() -> None:
    if not PRED.exists():
        print(f"missing {PRED} - run scripts/train.py first", file=sys.stderr)
        raise SystemExit(1)

    print(f"Loading {PRED.name} ...")
    preds = pd.read_parquet(PRED)
    print(f"  {len(preds):,} anchors · {preds.session_id.nunique():,} sessions")

    sess = session_table(preds)
    n_ev = int(sess.has_event.sum())
    print(f"  {n_ev:,} IDH sessions · {int((~sess.has_event).sum()):,} non-IDH sessions")

    report = build_report(preds)
    rows = report["sweep"]
    baselines = report["baselines"]
    frozen = report["frozen_row"]
    beats_treat_all = report["beats_treat_all_range"]
    best = max(rows, key=lambda r: r["net_benefit"]["0.10"])

    OUT.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {OUT}")

    # Fold into the committed demo bundle so the dashboard can show the
    # operating-point trade-off offline, with no artifacts/ directory.
    embed_in_bundle(report)

    print(f"\n{'thr':>8} {'det(all)':>9} {'det(eval)':>10} "
          f"{'FA/sess':>9} {'PPV':>7} {'NB@.10':>8}")
    print("-" * 56)
    for r in rows:
        star = "  <- frozen" if r["is_frozen"] else ""
        print(f"{r['threshold']:8.4f} "
              f"{100*r['detection_rate_all_sessions']:8.1f}% "
              f"{100*r['detection_rate_evaluable']:9.1f}% "
              f"{100*r['false_alarm_session_rate']:8.1f}% "
              f"{100*r['session_ppv']:6.1f}% "
              f"{r['net_benefit']['0.10']:8.4f}{star}")

    print("\nBaselines (net benefit, session level):")
    for pt in PTS:
        k = PT_KEYS[pt]
        print(f"  pt={k}: never-alarm {baselines['treat_none'][k]:+.4f} | "
              f"alarm-everyone {baselines['treat_all'][k]:+.4f} | "
              f"frozen {frozen['net_benefit'][k]:+.4f}")
    print(f"\nThreshold range beating 'alarm on everyone': {beats_treat_all}")
    print(f"Net-benefit-optimal threshold at pt=0.10: {best['threshold']:.4f} "
          f"(NB {best['net_benefit']['0.10']:.4f})")


if __name__ == "__main__":
    main()
