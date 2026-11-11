"""Task 00 tests: outcome-window observability and online eligibility."""
from __future__ import annotations

import numpy as np
import pandas as pd
import unittest

from src.labels import (
    build_anchors,
    build_online_cuffs,
    outcome_coverage,
    session_flow,
)


def _session(sid, pid, times, sbp):
    return pd.DataFrame({
        "session_id": sid, "pid": pid,
        "t_min": np.asarray(times, dtype=float),
        "sbp": np.asarray(sbp, dtype=float),
        "dbp": np.asarray(sbp, dtype=float) - 40.0,
    })


class OutcomeCoverageTest(unittest.TestCase):
    def test_short_next_cuff_then_long_gap_is_not_a_negative(self):
        et = np.array([0, 15, 30, 40, 70, 130], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=np.inf, session_end=et[-1])
        self.assertFalse(cov["coverage_complete"])
        self.assertTrue(np.isnan(cov["label"]))

    def test_cuff_outside_window_does_not_establish_coverage(self):
        et = np.array([0, 15, 30, 70, 130], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=np.inf, session_end=et[-1])
        self.assertFalse(cov["first_half"])
        self.assertFalse(cov["coverage_complete"])
        self.assertTrue(np.isnan(cov["label"]))

    def test_full_coverage_is_a_valid_negative(self):
        et = np.array([0, 15, 30, 50, 80, 100, 120, 150], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=np.inf, session_end=et[-1])
        self.assertTrue(cov["coverage_complete"])
        self.assertEqual(cov["label"], 0)
        self.assertTrue(cov["primary_eligible"])

    def test_session_ending_before_horizon_is_censored(self):
        et = np.array([0, 15, 30, 50, 80], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=np.inf, session_end=et[-1])
        self.assertFalse(cov["session_observed_past_end"])
        self.assertFalse(cov["coverage_complete"])
        self.assertTrue(np.isnan(cov["label"]))

    def test_observed_positive_does_not_need_full_negative_coverage(self):
        et = np.array([0, 15, 30, 70, 80, 120], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=80.0, session_end=et[-1])
        self.assertFalse(cov["coverage_complete"])
        self.assertEqual(cov["label"], 1)
        self.assertFalse(cov["primary_eligible"])

    def test_imminent_onset_is_not_a_supervised_label(self):
        et = np.array([0, 15, 30, 40, 80, 100, 120], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=40.0, session_end=et[-1])
        self.assertTrue(cov["imminent"])
        self.assertTrue(np.isnan(cov["label"]))
        self.assertFalse(cov["primary_eligible"])

    def test_gap_above_threshold_breaks_coverage(self):
        et = np.array([0, 15, 30, 45, 85, 100, 120], dtype=float)
        cov = outcome_coverage(et, 30.0, onset=np.inf, session_end=et[-1])
        self.assertGreater(cov["max_gap_min"], 35)
        self.assertFalse(cov["coverage_complete"])


class AnchorConstructionTest(unittest.TestCase):
    def setUp(self):
        # S3: event at 15; the minute-0 cuff is exactly 15 min earlier and
        # therefore still a warning. S4: event at 15 with no earlier cuff in
        # [-45, 0], so it has no warning window at all.
        frames = [
            _session("S0", "P0", [0, 15, 30, 50, 80, 100, 120, 150],
                     [130, 128, 126, 124, 122, 120, 118, 116]),
            _session("S1", "P1", [0, 15, 30, 40, 70, 130],
                     [130, 128, 126, 124, 122, 120]),
            _session("S2", "P2", [0, 15, 30, 50, 80, 100, 120],
                     [130, 128, 126, 124, 88, 110, 115]),
            _session("S3", "P3", [0, 15, 30, 40, 80, 100, 120],
                     [130, 85, 88, 90, 110, 112, 114]),
            _session("S4", "P4", [15, 40, 60, 80, 100, 120],
                     [85, 88, 90, 110, 112, 114]),
        ]
        self.ev = pd.concat(frames, ignore_index=True)

    def test_build_anchors_applies_coverage_and_keeps_positive(self):
        anch = build_anchors(self.ev, verbose=False)
        by = anch.groupby("session_id").agg(
            n=("label", "size"), pos=("label", "sum")).to_dict("index")
        self.assertGreaterEqual(by["S0"]["n"], 1)
        self.assertEqual(by["S0"]["pos"], 0)
        self.assertNotIn("S1", by)  # incomplete follow-up is not a negative
        self.assertGreaterEqual(by["S2"]["pos"], 1)

    def test_online_cuffs_are_independent_of_future_coverage(self):
        online = build_online_cuffs(self.ev, verbose=False)
        sids = set(online.session_id)
        self.assertIn("S1", sids)  # still scoreable live despite bad follow-up
        self.assertIn("S3", sids)
        s3 = online[online.session_id == "S3"]
        self.assertTrue(s3.is_post_onset.any())  # post-onset cuff retained

    def test_session_flow_counts_event_sessions_and_warning_windows(self):
        flow = session_flow(self.ev)
        self.assertEqual(flow["sessions"], 5)
        self.assertEqual(flow["event_sessions"], 3)
        # S2 has a cuff at 50, 30 min before onset 80; S3's minute-0 cuff is
        # 15 min before onset 15; S4 has no cuff in [-45, 0].
        self.assertEqual(flow["event_sessions_with_warning_window"], 2)
        self.assertEqual(flow["event_sessions_no_warning_window"], 1)
        self.assertEqual(
            flow["supervised_anchors"],
            flow["supervised_positive_anchors"] + flow["supervised_negative_anchors"],
        )
        self.assertGreater(flow["excluded_incomplete_coverage"], 0)
        self.assertGreater(flow["excluded_post_onset"], 0)


if __name__ == "__main__":
    unittest.main()
