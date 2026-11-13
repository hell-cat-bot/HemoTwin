"""Task 02 tests: online state machine and threshold selection."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src import event_model as E


def _session(sid, et, sbp, onset, online, pid="p1") -> dict:
    et = np.asarray(et, float)
    no_warn = False
    if np.isfinite(onset):
        no_warn = not bool(np.any((et >= onset - 60) & (et <= onset - 15)))
    return {"session_id": sid, "pid": pid, "et": et,
            "onset": float(onset), "session_end": float(et[-1]),
            "no_warning_window": no_warn,
            "online": [{"t": float(t), "sbp": float(s), "score": float(sc)}
                       for t, s, sc in online]}


class StateMachineTest(unittest.TestCase):
    def test_timely_alert_and_non_resetting_refractory(self):
        s = _session(
            "a", [0, 30, 60, 80, 90, 100, 110, 120, 150, 180],
            [120, 118, 116, 114, 112, 88, 110, 112, 114, 116],
            onset=100,
            online=[(60, 116, 0.8), (80, 114, 0.9), (90, 112, 0.2),
                    (100, 88, 0.95), (110, 110, 0.9), (120, 112, 0.9)])
        r = E.run_session(s, 0.5)
        self.assertEqual(r["n_alerts"], 1)
        self.assertEqual(r["n_timely"], 1)
        self.assertEqual(r["n_useful"], 1)
        self.assertEqual(r["n_false"], 0)
        self.assertTrue(r["detected_timely"])
        self.assertEqual(r["alerts"][0]["lead_time_min"], 40.0)
        states = dict(r["states"])
        self.assertEqual(states[80.0], "suppressed")
        self.assertEqual(states[100.0], "rescue")
        self.assertEqual(states[110.0], "post_event")

    def test_second_episode_at_exact_refractory_and_outcome_components(self):
        s = _session(
            "b", [0, 30, 60, 90, 120, 150],
            [120, 120, 120, 120, 120, 120], onset=np.inf,
            online=[(60, 120, 0.9), (90, 120, 0.9),
                    (120, 120, 0.9), (150, 120, 0.9)])
        r = E.run_session(s, 0.5)
        self.assertEqual(r["n_alerts"], 2)
        self.assertEqual([a["t_alert"] for a in r["alerts"]], [60.0, 120.0])
        self.assertEqual(r["n_false"], 1)       # first episode is fully observed
        self.assertEqual(r["n_indeterminate"], 1)  # second lacks 60-min follow-up

    def test_confirmed_false_requires_full_followup(self):
        good = _session("c", [0, 30, 60, 80, 90, 120, 150, 180],
                        [120] * 8, np.inf, [(60, 120, 0.9)])
        self.assertEqual(E.run_session(good, 0.5)["n_false"], 1)
        bad = _session("d", [0, 30, 60, 80, 90, 130],
                       [120] * 6, np.inf, [(60, 120, 0.9)])
        r = E.run_session(bad, 0.5)
        self.assertEqual(r["n_false"], 0)
        self.assertEqual(r["n_indeterminate"], 1)

    def test_current_hypotension_is_rescue_not_forecast_alert(self):
        s = _session("e", [0, 30, 60, 90], [120, 118, 85, 110],
                     60, [(60, 85, 0.99)])
        r = E.run_session(s, 0.01)
        self.assertEqual(r["n_alerts"], 0)
        self.assertEqual(dict(r["states"])[60.0], "rescue")
        self.assertTrue(r["post_event"])

    def test_no_alert_candidate(self):
        s = _session("f", [0, 30, 60, 90], [120] * 4, np.inf,
                     [(60, 120, 0.9)])
        r = E.run_session(s, None)
        self.assertEqual(r["n_alerts"], 0)
        self.assertEqual(r["burden"], 0.0) if "burden" in r else None


class ThresholdSelectionTest(unittest.TestCase):
    def test_selects_useful_threshold_under_budget(self):
        s = _session("a", [0, 30, 60, 80, 90, 100, 110, 120, 150, 180],
                     [120, 118, 116, 114, 112, 88, 110, 112, 114, 116],
                     onset=100, online=[(60, 116, 0.9), (80, 114, 0.2)])
        out = E.select_threshold([s], "tier")
        self.assertEqual(out["selection"], "budgeted")
        self.assertEqual(out["threshold"], 0.9)
        self.assertEqual(out["timely_detected"], 1)
        self.assertEqual(out["burden"], 0.0)

    def test_negative_capping_keeps_positives(self):
        rows = []
        for i in range(10):
            rows.append({"session_id": "s", "pid": "p", "t_min": float(i),
                         "label": 0, "x": i})
        for i in range(2):
            rows.append({"session_id": "s", "pid": "p", "t_min": 20.0 + i,
                         "label": 1, "x": i})
        df = pd.DataFrame(rows)
        out = E.cap_negatives(df, k=3, seed=42)
        self.assertEqual(int(out.label.sum()), 2)
        self.assertEqual(int((out.label == 0).sum()), 3)


if __name__ == "__main__":
    unittest.main()
