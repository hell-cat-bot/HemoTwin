"""Label construction and honest evaluation splits.

The anti-cheating rules are enforced here, not in the model:

1. Splits are by PATIENT. A patient never appears in two splits.
2. We predict only the FIRST hypotensive episode of a session.
3. Onsets closer than HORIZON_LO are DROPPED, not labelled — we cannot act on
   them, so counting them as wins or losses would be dishonest.
4. An anchor keeps a label only if a BP measurement exists in the label window.
   We never fabricate negatives for an unobserved outcome.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG


def outcome_coverage(et, t: float, onset: float = np.inf,
                     horizon_lo: int | None = None, horizon_hi: int | None = None,
                     gap_min: int | None = None, edge_tol: int | None = None,
                     half_min: int | None = None,
                     session_end: float | None = None) -> dict:
    """Explicit coverage of the outcome window (t+15, t+60].

    A negative is only valid when the window is fully observed:
      * at least one cuff in (t, t+30],
      * at least one cuff in (t+30, t+60],
      * a cuff within +/-10 minutes of t+60,
      * no gap between consecutive observations (including from t) >35 min,
      * the observed session continues to at least t+60.

    A short next-cuff gap followed by a long later gap therefore cannot
    manufacture a negative. A cuff outside the label window does not by itself
    establish coverage. Sessions ending before t+60 are censored, not scored
    on a shortened horizon.
    """
    horizon_lo = CONFIG["HORIZON_LO"] if horizon_lo is None else horizon_lo
    horizon_hi = CONFIG["HORIZON_HI"] if horizon_hi is None else horizon_hi
    gap_min = CONFIG["OUTCOME_GAP_MIN"] if gap_min is None else gap_min
    edge_tol = CONFIG["OUTCOME_EDGE_TOL_MIN"] if edge_tol is None else edge_tol
    half_min = CONFIG["OUTCOME_HALF_MIN"] if half_min is None else half_min
    et = np.asarray(et, dtype=float)
    et = et[np.isfinite(et)]
    session_end = float(et[-1]) if session_end is None and len(et) else session_end
    window_end = float(t) + horizon_hi

    cuffs = et[(et >= t) & (et <= window_end + edge_tol)]
    first_half = bool(np.any((cuffs > t) & (cuffs <= t + half_min)))
    second_half = bool(np.any((cuffs > t + half_min) & (cuffs <= window_end)))
    edge = bool(np.any((cuffs >= window_end - edge_tol) &
                       (cuffs <= window_end + edge_tol)))
    nodes = np.concatenate([[float(t)], cuffs]) if len(cuffs) else np.array([float(t)])
    gaps = np.diff(nodes)
    max_gap = float(gaps.max()) if len(gaps) else np.inf
    session_observed_past_end = bool(session_end is not None and
                                     np.isfinite(session_end) and
                                     session_end >= window_end)
    complete = bool(first_half and second_half and edge and
                    max_gap <= gap_min and session_observed_past_end)

    event_observed = bool(np.isfinite(onset) and onset > t + horizon_lo
                          and onset <= window_end)
    imminent = bool(np.isfinite(onset) and onset > t
                    and onset <= t + horizon_lo)
    post_onset = bool(np.isfinite(onset) and onset <= t)

    if event_observed:
        label = 1
    elif complete and not post_onset and not imminent:
        label = 0
    else:
        label = np.nan
    return {
        "label": label,
        "event_observed": event_observed,
        "imminent": imminent,
        "post_onset": post_onset,
        "coverage_complete": complete,
        "primary_eligible": bool(complete and not post_onset and not imminent),
        "first_half": first_half,
        "second_half": second_half,
        "edge": edge,
        "session_observed_past_end": session_observed_past_end,
        "max_gap_min": max_gap,
        "n_window_cuffs": int(len(cuffs)),
    }


def build_anchors(ev: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """One row per supervised prediction anchor with an observable outcome.

    label = 1 iff the FIRST SBP<threshold event of the session starts in
    (t + HORIZON_LO, t + HORIZON_HI]. A negative requires full outcome-window
    coverage; otherwise the anchor is dropped rather than labelled 0.
    """
    thr = CONFIG["IDH_SBP_THRESHOLD"]
    lo, hi = CONFIG["HORIZON_LO"], CONFIG["HORIZON_HI"]
    ev = ev.sort_values(["session_id", "t_min"])

    out = []
    for sid, g in ev.groupby("session_id", sort=False, observed=True):
        t = g.t_min.to_numpy(float)
        sbp = g.sbp.to_numpy(float)
        dbp = g.dbp.to_numpy(float)
        pid = g.pid.iloc[0]
        below = np.flatnonzero(sbp < thr)
        onset = t[below[0]] if len(below) else np.inf
        session_end = float(t[-1]) if len(t) else np.nan
        for i in range(len(g)):
            ti = t[i]
            n_earlier = int(np.sum(t < ti))
            if ti < CONFIG["MIN_ANCHOR_MIN"]:
                continue
            if ti > CONFIG["MAX_ANCHOR_MIN"]:
                break
            if n_earlier < 2:
                continue
            if ti >= onset:                      # at or after onset: stop
                break
            rel = onset - ti
            if rel <= lo:                        # imminent: ambiguous
                continue
            cov = outcome_coverage(t, ti, onset, lo, hi, session_end=session_end)
            if not np.isfinite(cov["label"]):
                continue
            out.append((sid, pid, ti, sbp[i], dbp[i],
                        onset if np.isfinite(onset) else np.nan,
                        int(cov["label"]), bool(cov["coverage_complete"]),
                        bool(cov["primary_eligible"]), n_earlier,
                        float(cov["max_gap_min"])))

    anch = pd.DataFrame(out, columns=[
        "session_id", "pid", "t_min", "sbp_now", "dbp_now", "onset_min",
        "label", "coverage_complete", "primary_eligible", "n_earlier",
        "max_gap_min",
    ])
    if verbose:
        n = len(anch)
        p = int(anch.label.sum()) if n else 0
        print(f"Anchors: {n:,} | positive: {p:,} ({100*p/max(n,1):.2f}%) | "
              f"sessions with >=1 anchor: {anch.session_id.nunique():,}")
    return anch


def build_online_cuffs(ev: pd.DataFrame, min_history: int = 2,
                       verbose: bool = True) -> pd.DataFrame:
    """Every observed cuff that an online system could score.

    Eligibility uses only current/past data: at least `min_history` earlier
    cuffs and time at/after MIN_ANCHOR_MIN. It is independent of scores and
    future coverage. Post-onset cuffs remain in this frame because a live
    system still has to handle them (as rescue, not forecast, in Task 02).
    `onset_min` is an offline outcome column and must not be used for scoring.
    """
    rows = []
    for sid, g in ev.groupby("session_id", sort=False, observed=True):
        g = g.sort_values("t_min")
        t = g.t_min.to_numpy(float)
        sbp = g.sbp.to_numpy(float)
        dbp = g.dbp.to_numpy(float)
        pid = g.pid.iloc[0]
        below = np.flatnonzero(sbp < CONFIG["IDH_SBP_THRESHOLD"])
        onset = t[below[0]] if len(below) else np.inf
        for i in range(len(g)):
            ti = t[i]
            n_earlier = int(np.sum(t < ti))
            if ti < CONFIG["MIN_ANCHOR_MIN"] or n_earlier < min_history:
                continue
            cov = outcome_coverage(t, ti, onset, session_end=float(t[-1]))
            rows.append((sid, pid, ti, sbp[i], dbp[i],
                         onset if np.isfinite(onset) else np.nan,
                         bool(np.isfinite(onset) and ti >= onset),
                         bool(np.isfinite(onset) and ti < onset and
                              onset - ti <= CONFIG["HORIZON_LO"]),
                         n_earlier, cov["label"], cov["coverage_complete"]))
    out = pd.DataFrame(rows, columns=[
        "session_id", "pid", "t_min", "sbp_now", "dbp_now", "onset_min",
        "is_post_onset", "imminent", "n_earlier", "label", "coverage_complete",
    ])
    if verbose:
        print(f"Online-eligible cuffs: {len(out):,} | sessions: "
              f"{out.session_id.nunique():,}")
    return out


def session_flow(ev: pd.DataFrame, pids=None, verbose: bool = False) -> dict:
    """Auditable session and anchor flow with every exclusion reason."""
    if pids is not None:
        keep = {str(p) for p in pids}
        ev = ev[ev.pid.astype(str).isin(keep)]
    lo, hi = CONFIG["HORIZON_LO"], CONFIG["HORIZON_HI"]
    min_anchor = CONFIG["MIN_ANCHOR_MIN"]
    max_anchor = CONFIG["MAX_ANCHOR_MIN"]
    counts = {
        "patients": int(ev.pid.nunique()),
        "sessions": int(ev.session_id.nunique()),
        "represented_sessions": 0,
        "cuff_readings": int(len(ev)),
        "online_eligible_cuffs": 0,
        "online_scored_sessions": 0,
        "supervised_sessions": 0,
        "supervised_anchors": 0,
        "supervised_primary_eligible_anchors": 0,
        "supervised_positive_anchors": 0,
        "supervised_positive_primary_eligible": 0,
        "supervised_negative_anchors": 0,
        "supervised_negative_primary_eligible": 0,
        "event_sessions": 0,
        "event_sessions_with_warning_window": 0,
        "event_sessions_no_warning_window": 0,
        "excluded_before_min_anchor": 0,
        "excluded_after_max_anchor": 0,
        "excluded_insufficient_history": 0,
        "excluded_post_onset": 0,
        "excluded_imminent": 0,
        "excluded_incomplete_coverage": 0,
        "excluded_incomplete_session_censored": 0,
        "excluded_incomplete_gap": 0,
        "excluded_incomplete_window": 0,
        "sessions_without_online_cuffs": 0,
    }
    for sid, g in ev.groupby("session_id", sort=False, observed=True):
        g = g.sort_values("t_min")
        t = g.t_min.to_numpy(float)
        sbp = g.sbp.to_numpy(float)
        below = np.flatnonzero(sbp < CONFIG["IDH_SBP_THRESHOLD"])
        onset = t[below[0]] if len(below) else np.inf
        has_event = bool(np.isfinite(onset))
        if np.any((t >= min_anchor) & (t <= max_anchor)):
            counts["represented_sessions"] += 1
        if has_event:
            counts["event_sessions"] += 1
            has_warn = bool(np.any((t >= onset - hi) & (t <= onset - lo)))
            if has_warn:
                counts["event_sessions_with_warning_window"] += 1
            else:
                counts["event_sessions_no_warning_window"] += 1
        online = 0
        sup = sup_primary = pos = pos_primary = neg = neg_primary = 0
        for i in range(len(g)):
            ti = t[i]
            n_earlier = int(np.sum(t < ti))
            if ti < min_anchor:
                counts["excluded_before_min_anchor"] += 1
                continue
            if n_earlier < 2:
                counts["excluded_insufficient_history"] += 1
                continue
            online += 1
            if ti > max_anchor:
                # Still online-scoreable; excluded only from the supervised
                # anchor frame (whose range is a training convention).
                counts["excluded_after_max_anchor"] += 1
                continue
            if ti >= onset:
                counts["excluded_post_onset"] += 1
                continue
            rel = onset - ti
            if rel <= lo:
                counts["excluded_imminent"] += 1
                continue
            cov = outcome_coverage(t, ti, onset, session_end=float(t[-1]))
            if not np.isfinite(cov["label"]):
                counts["excluded_incomplete_coverage"] += 1
                if not cov["session_observed_past_end"]:
                    counts["excluded_incomplete_session_censored"] += 1
                elif cov["max_gap_min"] > CONFIG["OUTCOME_GAP_MIN"]:
                    counts["excluded_incomplete_gap"] += 1
                else:
                    counts["excluded_incomplete_window"] += 1
                continue
            sup += 1
            if cov["primary_eligible"]:
                sup_primary += 1
            if cov["label"] == 1:
                pos += 1
                if cov["primary_eligible"]:
                    pos_primary += 1
            else:
                neg += 1
                if cov["primary_eligible"]:
                    neg_primary += 1
        counts["online_eligible_cuffs"] += online
        if online:
            counts["online_scored_sessions"] += 1
        else:
            counts["sessions_without_online_cuffs"] += 1
        if sup:
            counts["supervised_sessions"] += 1
        counts["supervised_anchors"] += sup
        counts["supervised_primary_eligible_anchors"] += sup_primary
        counts["supervised_positive_anchors"] += pos
        counts["supervised_positive_primary_eligible"] += pos_primary
        counts["supervised_negative_anchors"] += neg
        counts["supervised_negative_primary_eligible"] += neg_primary
    if verbose:
        print(counts)
    return counts


def patient_level_split(anch: pd.DataFrame, seed: int | None = None):
    seed = CONFIG["SEED"] if seed is None else seed
    rng = np.random.default_rng(seed)
    # materialise as a plain object array: shuffling an Arrow-backed string
    # array is not guaranteed to preserve the permutation
    pids = np.asarray(anch.pid.unique(), dtype=object)
    rng.shuffle(pids)
    n_test = int(len(pids) * CONFIG["TEST_FRACTION"])
    n_val = int(len(pids) * CONFIG["VAL_FRACTION"])
    test_p = set(pids[:n_test])
    val_p = set(pids[n_test:n_test + n_val])
    train_p = set(pids[n_test + n_val:])

    tr = anch[anch.pid.isin(train_p)].copy()
    va = anch[anch.pid.isin(val_p)].copy()
    te = anch[anch.pid.isin(test_p)].copy()

    assert not (train_p & val_p) and not (train_p & test_p) and not (val_p & test_p)
    for name, df in (("train", tr), ("val", va), ("test", te)):
        print(f"  {name:5s}: {len(df):8,d} anchors | {df.pid.nunique():4d} patients | "
              f"{df.session_id.nunique():7,d} sessions | pos {100*df.label.mean():.2f}%")
    return tr, va, te


def cap_train_negatives(tr: pd.DataFrame, seed: int | None = None) -> pd.DataFrame:
    """Downsample NEGATIVE anchors per session (train only).

    Bounds compute and softens imbalance. Positives are never dropped.
    Validation and test keep their natural prevalence so metrics stay honest.
    """
    k = CONFIG["MAX_NEG_ANCHORS_PER_SESSION_TRAIN"]
    if k is None:
        return tr
    seed = CONFIG["SEED"] if seed is None else seed
    rng = np.random.default_rng(seed)
    keep = []
    for _, g in tr.groupby("session_id", observed=True):
        pos = g[g.label == 1]
        neg = g[g.label == 0]
        if len(neg) > k:
            neg = neg.iloc[rng.choice(len(neg), k, replace=False)]
        keep.append(pos)
        keep.append(neg)
    out = pd.concat(keep).sort_values(["session_id", "t_min"])
    print(f"Train anchors after negative capping: {len(out):,} "
          f"(positive rate {100*out.label.mean():.2f}%)")
    return out


# ---------------------------------------------------------------------------
# Event-level evaluation
# ---------------------------------------------------------------------------
def event_level_detection(anch: pd.DataFrame, score: np.ndarray,
                          threshold: float,
                          warn_lo: int = CONFIG["HORIZON_LO"],
                          warn_hi: int = CONFIG["HORIZON_HI"]) -> dict:
    """Session-level detection, evaluated on the SAME window the model is trained on.

    A session counts as detected only if an anchor inside
    [onset - warn_hi, onset - warn_lo] fires. This is the fix for the
    mismatch in the v1 notebook, where labels were (15, 30] but the event
    metric credited fires anywhere in [onset-75, onset-15].
    """
    a = anch.copy()
    a["score"] = score
    a = a.sort_values(["session_id", "t_min"])

    det = missed = no_anchor = 0
    non_max = []

    for sid, g in a.groupby("session_id", observed=True):
        onset = g.onset_min.iloc[0]
        if not np.isfinite(onset):
            non_max.append(g.score.max())
            continue
        t = g.t_min.to_numpy()
        s = g.score.to_numpy()
        m = (t >= onset - warn_hi) & (t <= onset - warn_lo)
        if not m.any():
            no_anchor += 1
        elif (s[m] >= threshold).any():
            det += 1
        else:
            missed += 1

    fa = float(np.mean(np.array(non_max) >= threshold)) if non_max else float("nan")

    total = det + missed + no_anchor
    return {
        "detected": det,
        "missed": missed,
        "no_anchor_window": no_anchor,
        "n_idh_sessions": total,
        "detection_rate_evaluable": det / max(det + missed, 1),
        "detection_rate_all_sessions": det / max(total, 1),
        "false_alarm_session_rate": fa,
        "warn_lo": warn_lo, "warn_hi": warn_hi,
    }


def session_level_ppv(anch: pd.DataFrame, score: np.ndarray,
                      threshold: float) -> dict:
    """Of the sessions we flag, how many actually had an IDH event?

    This is the number a nurse experiences; anchor-level PPV is not.
    """
    a = anch.copy()
    a["score"] = score
    flagged = a.groupby("session_id", observed=True)["score"].max().ge(threshold)
    had = a.groupby("session_id", observed=True)["onset_min"].first().notna()
    n_flag = int(flagged.sum())
    tp = int((flagged & had).sum())
    return {
        "sessions_flagged": n_flag,
        "flagged_and_true": tp,
        "session_ppv": tp / max(n_flag, 1),
        "flagged_share": n_flag / max(len(flagged), 1),
    }
