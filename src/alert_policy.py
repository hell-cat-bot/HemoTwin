"""Alarm-policy module for segment alert-v1.

The code under test: turning per-cuff shadow scores into alarm episodes.
Frozen baseline semantics follow the Task 02 protocol: non-resetting
60-minute refractory (later cuffs inside the refractory window do NOT extend
the episode), threshold crossing on the chosen score series. Substrate:
artifacts/review_20261108/cuff_scores.parquet (5,494,035 rows, fidelity-proven
against the frozen Task 02 replay by scripts/build_cuff_scores.py).

Governance mirrors forecast-v1: folds 0+1 = development (patient-parity
TUNE/EVAL split; threshold selected on TUNE only), fold 2 confirmatory.
The current-SBP rule (score = 1 if sbp < 90 else 0) is the comparator to
beat: 20.2% pooled timely detection at 0.171 burden (Task 02 outer).
"""
from __future__ import annotations

from dataclasses import dataclass


# Module-owned default policy (the code under test). The frozen benchmark
# resolves its --sbp-rule-min default from here, so iterations change this
# module, not the harness.
#
# Budget-allocation schedule: each score threshold thr on the grid is paired
# with a rescue-rule threshold sbp_min(thr) = LO + (HI - LO) * (1 - thr), so
# the family sweeps from rule-dominant (low thr) to model-dominant (high
# thr) while the selector picks the pair meeting the burden cap.
DEFAULT_SBP_RULE_MIN = None
DEFAULT_SBP_RULE_SCHEDULE = (90.0, 102.0)
# Score-channel gate: when set, the model score may only fire alerts at or
# above this raw-score floor (used to close the model channel entirely —
# gate above the score range — or to test its marginal value at the top of
# the score distribution).
DEFAULT_SCORE_GATE = 1e9
# twin-v3b (segment 6): the alert-v1 ADOPTED absolute rescue threshold, kept
# fixed while the patient-relative drop channel is swept (one focused change:
# the drop channel is ADDED to this rule, the absolute threshold does not
# re-tune). Provenance: alert-v1 fold-2 confirm operating point
# (artifacts/review_20261108/confirm_alert_fold2.json: thr 0.26 schedule pair).
DEFAULT_SBP_RULE_MIN_FIXED = 98.88
# twin-v3c (segment 7): zone-gated drop channel — the drop rule may only fire
# when SBP is BELOW this ceiling (near the absolute-rule zone), so episodes
# fire EARLIER rather than MORE OFTEN. Mechanism: the union opens the episode
# at the earlier of the two triggers, converting late absolute-rule alerts
# into timely ones without adding episodes in the high-SBP range (where the
# unconstrained channel's burden came from).
DEFAULT_DROP_ZONE_MAX = 110.0


def sbp_rule_schedule(grid):
    import numpy as np
    lo, hi = DEFAULT_SBP_RULE_SCHEDULE
    grid = np.asarray(grid, dtype=float)
    return lo + (hi - lo) * (1.0 - grid)


@dataclass
class PolicyConfig:
    threshold: float
    refractory_min: float = 60.0
    score_field: str = "score_raw"  # or "score_cal", "current_sbp", "hybrid"


def episode_flags(times, scores, cfg: PolicyConfig):
    """Fire an episode when score >= threshold and refractory has elapsed.

    Non-resetting: the episode closes refractory_min after it OPENS; high
    scores during the window do not extend it. Returns a boolean array.
    """
    fired = []
    last_open = -1e18
    for t, s in zip(times, scores):
        if s >= cfg.threshold and t - last_open >= cfg.refractory_min:
            fired.append(True)
            last_open = t
        else:
            fired.append(False)
    return fired


def episode_counts(times, scores, ev, onset, thresholds, refractory_min=60.0,
                   sbp=None, sbp_rule_min=90.0):
    """One pass over a session scores ALL grid thresholds at once.

    Returns per-threshold counts dict of numpy arrays:
    useful / confirmed_false / indeterminate / timely.
    Semantics (task02 protocol): an alert is useful if event onset falls in
    (t, t+60]; among those, timely if onset-t in [15, 60]; confirmed-false
    when the session has no event; indeterminate otherwise. Conservative
    burden = confirmed_false + indeterminate.

    Hybrid union rule (iteration 2): when `sbp` is supplied, an episode also
    fires whenever current SBP < sbp_rule_min — the rescue-state rule — with
    the model score gate sharing the same refractory budget.
    """
    import numpy as np
    thr = np.asarray(thresholds, dtype=float)
    last_open = np.full(len(thr), -1e18)
    useful = np.zeros(len(thr), dtype=np.int64)
    cfalse = np.zeros(len(thr), dtype=np.int64)
    indet = np.zeros(len(thr), dtype=np.int64)
    timely = np.zeros(len(thr), dtype=np.int64)
    times = np.asarray(times, dtype=float)
    scores = np.asarray(scores, dtype=float)
    sbp_arr = None if sbp is None else np.asarray(sbp, dtype=float)
    for j in range(len(times)):
        t = times[j]
        can = (t - last_open) >= refractory_min
        hit = can & (scores[j] >= thr)
        if sbp_arr is not None:
            hit = hit | (sbp_arr[j] < sbp_rule_min)
        if not hit.any():
            continue
        if ev == 1 and np.isfinite(onset):
            lead = onset - t
            if 0 < lead <= 60:
                useful[hit] += 1
                if 15 <= lead <= 60:
                    timely[hit] += 1
            else:
                indet[hit] += 1
        elif ev == 0:
            cfalse[hit] += 1
        else:
            indet[hit] += 1
        last_open[hit] = t
    return {"useful": useful, "confirmed_false": cfalse,
            "indeterminate": indet, "timely": timely}


def score_series(df, cfg: PolicyConfig):
    if cfg.score_field == "current_sbp":
        return (df["sbp"] < 90).astype(float)
    return df[cfg.score_field]


def episode_flags_matrix(times, scores, sbp, thresholds, refractory_min=60.0,
                         sbp_rule_min: float | None = None,
                         score_gate: float | None = None,
                         drop_min: float | None = None,
                         baseline: float | None = None,
                         drop_zone_max: float | None = None):
    """Boolean flags matrix (n_thresholds, n_cuffs) — one pass per session.

    Episode fires at cuff j for threshold k when score >= thr[k] (or, when
    sbp_rule_min is set, current SBP < sbp_rule_min — the rescue-zone rule;
    or, when drop_min and baseline are set, the patient-relative rule
    baseline - SBP >= drop_min, optionally gated to SBP < drop_zone_max —
    the twin-v3c zone-limited channel) and the non-resetting refractory has
    elapsed since that threshold's last episode open. ALL channels share the
    SAME refractory budget (regression-pinned).
    """
    import numpy as np
    thr = np.asarray(thresholds, dtype=float)
    times = np.asarray(times, dtype=float)
    scores = np.asarray(scores, dtype=float)
    flags = np.zeros((len(thr), len(times)), dtype=bool)
    last_open = np.full(len(thr), -1e18)
    drop_rule = (drop_min is not None) and (baseline is not None) \
        and np.isfinite(baseline)
    for j in range(len(times)):
        can = (times[j] - last_open) >= refractory_min
        model_ok = True if score_gate is None else scores[j] >= score_gate
        base = (scores[j] >= thr) & model_ok
        if sbp_rule_min is not None:
            # every channel lives INSIDE the shared refractory gate `can`
            # (regression-pinned: the alert-v1 bypass bug class)
            base = base | (sbp[j] < sbp_rule_min)
        if drop_rule:
            term = (baseline - sbp[j]) >= drop_min
            if drop_zone_max is not None:
                term = term & (sbp[j] < drop_zone_max)
            base = base | term
        hit = can & base
        flags[hit, j] = True
        last_open[hit] = times[j]
    return flags
