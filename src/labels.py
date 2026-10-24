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


def build_anchors(ev: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """One row per eligible prediction anchor.

    label = 1 iff the FIRST SBP<threshold event of the session starts in
    (t + HORIZON_LO, t + HORIZON_HI].
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
        for i in range(len(g)):
            ti = t[i]
            if ti < CONFIG["MIN_ANCHOR_MIN"] or ti > CONFIG["MAX_ANCHOR_MIN"]:
                continue
            if ti >= onset:                      # at or after onset: stop
                break
            nxt = t[i + 1] if i + 1 < len(t) else np.inf
            if nxt > ti + CONFIG["MAX_NEXT_MEAS_GAP_MIN"]:
                continue                         # outcome unknowable
            rel = onset - ti
            if rel <= lo:                        # imminent: ambiguous
                continue
            out.append((sid, pid, ti, sbp[i], dbp[i],
                        onset if np.isfinite(onset) else np.nan,
                        1 if rel <= hi else 0))

    anch = pd.DataFrame(out, columns=["session_id", "pid", "t_min", "sbp_now",
                                      "dbp_now", "onset_min", "label"])
    if verbose:
        n = len(anch)
        p = int(anch.label.sum())
        print(f"Anchors: {n:,} | positive: {p:,} ({100*p/max(n,1):.2f}%) | "
              f"sessions with >=1 anchor: {anch.session_id.nunique():,}")
    return anch


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
