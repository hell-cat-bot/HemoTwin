"""Task 03 tests: cuff-level score cache (smoke artifact).

The cache (artifacts/review_20261108/cuff_scores_smoke.parquet, full:
cuff_scores.parquet) must satisfy the invariants alarm-policy research relies
on:

1. fixed schema [fold, policy, session_id, pid, t_cuff, sbp, dbp, score_raw,
   score_cal, elapsed_min, session_event, event_time_min];
2. calibrated scores are probabilities in [0, 1] and raw scores are finite
   wherever features were complete (features are complete for every cached
   row by construction -- build_cuff_scores.py only emits fully scored cuffs);
3. one row per (policy, session, cuff) unique key;
4. event bookkeeping follows the Task 02 definitions: a cuff observed with
   sbp < 90 always belongs to an event session whose first crossing (the
   onset task02's replay rescues on) is at or before that cuff; any cuff
   whose onset falls inside the Task 02 label window (t+15, t+60] is likewise
   an event session; and event-free sessions carry no event time;
5. the patient's fold is the frozen Task 00 outer fold.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import ARTIFACTS

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ARTIFACTS / "review_20261108" / "cuff_scores_smoke.parquet"
FULL = ARTIFACTS / "review_20261108" / "cuff_scores.parquet"
SPLITS = ARTIFACTS / "review_20261107" / "task00" / "splits.json"
EVENTS = ARTIFACTS / "review_20261107" / "task01" / "events_task01.parquet"
CACHE_READY = (SMOKE.exists() or FULL.exists()) and SPLITS.exists() and EVENTS.exists()

COLUMNS = ["fold", "policy", "session_id", "pid", "t_cuff", "sbp", "dbp",
           "score_raw", "score_cal", "elapsed_min", "session_event",
           "event_time_min"]
POLICIES = ("full", "universal", "minimal")


def _load_frame() -> pd.DataFrame:
    path = SMOKE if SMOKE.exists() else FULL
    if not path.exists():
        raise FileNotFoundError(
            "no score cache found; run scripts/build_cuff_scores.py smoke")
    return pd.read_parquet(path)


def _pid_fold_map() -> dict[str, int]:
    manifest = json.loads(SPLITS.read_text())["manifest"]
    m: dict[str, int] = {}
    for f in range(int(manifest["n_outer_folds"])):
        for p in manifest["folds"][f]["test_patients"]:
            m[str(p)] = f
    return m


@unittest.skipUnless(CACHE_READY, "cuff-score cache not bundled")
class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = _load_frame()

    def test_exact_columns(self):
        self.assertEqual(list(self.df.columns), COLUMNS)

    def test_policies_present(self):
        self.assertEqual(set(self.df.policy.unique()), set(POLICIES))

    def test_score_cal_in_unit_interval(self):
        c = self.df.score_cal.to_numpy(float)
        self.assertTrue(np.isfinite(c).all())
        self.assertGreaterEqual(float(np.min(c)), 0.0)
        self.assertLessEqual(float(np.max(c)), 1.0)

    def test_score_raw_finite_where_features_complete(self):
        # every cached row had complete features at build time, so the raw
        # ensemble score must be finite (LightGBM handles NaN inputs, isotonic
        # clipping bounds the calibrated output)
        r = self.df.score_raw.to_numpy(float)
        self.assertTrue(np.isfinite(r).all())

    def test_one_row_per_policy_session_cuff(self):
        dup = self.df.duplicated(["policy", "session_id", "t_cuff"])
        self.assertEqual(int(dup.sum()), 0)


@unittest.skipUnless(CACHE_READY, "cuff-score cache not bundled")
class EventBookkeepingTest(unittest.TestCase):
    """Task 02 label logic: the session event is the FIRST observed
    SBP<90 crossing; a scored cuff with sbp<90 therefore sits at/after the
    onset, and a cuff whose onset lies in (t+15, t+60] belongs to an event
    session (task02's label==1 window)."""

    @classmethod
    def setUpClass(cls):
        cls.df = _load_frame()

    def test_low_sbp_cuff_implies_session_event(self):
        low = self.df[self.df.sbp < 90.0]
        self.assertGreater(len(low), 0)
        self.assertTrue((low.session_event == 1).all())
        ok = (low.event_time_min.to_numpy(float)
              <= low.t_cuff.to_numpy(float) + 1e-9)
        self.assertTrue(ok.all())

    def test_onset_inside_label_window_implies_session_event(self):
        rel = (self.df.event_time_min.to_numpy(float)
               - self.df.t_cuff.to_numpy(float))
        window = ((self.df.session_event == 1) & np.isfinite(rel)
                  & (rel > 15.0) & (rel <= 60.0))
        self.assertGreater(int(window.sum()), 0)
        self.assertTrue((self.df.session_event[window] == 1).all())

    def test_event_free_sessions_have_no_event_time(self):
        no_ev = self.df[self.df.session_event == 0]
        if len(no_ev):
            self.assertTrue(np.isnan(no_ev.event_time_min.to_numpy(float)).all())

    def test_event_sessions_have_finite_event_time(self):
        ev = self.df[self.df.session_event == 1]
        self.assertTrue(np.isfinite(ev.event_time_min.to_numpy(float)).all())

    def test_session_event_is_constant_within_session_and_policy(self):
        g = self.df.groupby(["policy", "session_id"], observed=True)
        self.assertEqual(int(g.session_event.nunique().max()), 1)
        # event_time_min likewise constant per session (NaN allowed together)
        t = g.event_time_min.nunique(dropna=False)
        self.assertEqual(int(t.max()), 1)

    def test_onset_matches_events_task01_recomputation(self):
        if not EVENTS.exists():
            self.skipTest("events_task01.parquet not available")
        ev = pd.read_parquet(EVENTS, columns=["session_id", "t_min", "sbp"])
        sample_sids = (self.df.session_id.drop_duplicates()
                       .sample(min(50, self.df.session_id.nunique()),
                               random_state=7))
        ev = ev[ev.session_id.isin(set(sample_sids))]
        onset = {}
        for sid, g in ev.groupby("session_id", observed=True):
            t = g.sort_values("t_min").t_min.to_numpy(float)
            s = g.sort_values("t_min").sbp.to_numpy(float)
            below = np.flatnonzero(s < 90.0)
            onset[sid] = float(t[below[0]]) if len(below) else np.nan
        rows = self.df[self.df.session_id.isin(set(sample_sids))]
        for sid, g in rows.groupby("session_id", observed=True):
            exp = onset.get(sid, np.nan)
            got = float(g.event_time_min.iloc[0])
            flag_exp = 0 if not np.isfinite(exp) else 1
            self.assertEqual(int(g.session_event.iloc[0]), flag_exp, sid)
            if np.isfinite(exp):
                self.assertAlmostEqual(got, exp, places=6, msg=sid)
            else:
                self.assertTrue(np.isnan(got), sid)


@unittest.skipUnless(CACHE_READY, "cuff-score cache not bundled")
class FoldAssignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = _load_frame()

    def test_fold_matches_frozen_manifest(self):
        pf = _pid_fold_map()
        self.assertGreater(len(pf), 0)
        sample = self.df[["pid", "fold"]].drop_duplicates()
        for r in sample.itertuples(index=False):
            self.assertEqual(int(r.fold), pf[str(r.pid)],
                             f"pid {r.pid} in fold {r.fold}, manifest says "
                             f"{pf.get(str(r.pid))}")


if __name__ == "__main__":
    unittest.main()
