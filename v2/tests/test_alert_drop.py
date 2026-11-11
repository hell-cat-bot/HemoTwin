"""twin-v3b: patient-relative drop-from-baseline alert channel.

Pins: the drop channel participates in the SHARED refractory budget (no
bypass — the alert-v1 union-bypass bug class, regression-pinned), unions
with the absolute rescue rule, and stays inert without a usable baseline.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.alert_policy import episode_flags_matrix  # noqa: E402


def _flags(times, sbp, drop_min, baseline, sbp_rule_min=None,
           refractory=60.0, scores=None, thresholds=(0.5,),
           drop_zone_max=None):
    scores = scores if scores is not None else np.full(len(times), -1e9)
    return episode_flags_matrix(
        np.asarray(times, float), np.asarray(scores, float),
        np.asarray(sbp, float), np.asarray(thresholds, float),
        refractory, sbp_rule_min, None, drop_min, baseline, drop_zone_max)


class TestDropChannel(unittest.TestCase):
    def test_fires_on_drop_beyond_min(self):
        # baseline = first cuff (150); drop to 120 at t=30 (30 >= 25) fires;
        # at t=90 the drop is only 20 and the refractory from t=30 has just
        # elapsed (60 >= 60) but 20 < 25 -> no fire
        f = _flags([0.0, 30.0, 90.0], [150.0, 120.0, 130.0],
                   drop_min=25.0, baseline=150.0)
        self.assertEqual(f[0].tolist(), [False, True, False])
        # a further large drop after the refractory elapses fires again
        f2 = _flags([0.0, 30.0, 95.0], [150.0, 120.0, 110.0],
                    drop_min=25.0, baseline=150.0)
        self.assertEqual(f2[0].tolist(), [False, True, True])

    def test_no_fire_on_small_drop(self):
        f = _flags([0.0, 30.0, 60.0], [150.0, 140.0, 135.0],
                   drop_min=25.0, baseline=150.0)
        self.assertFalse(f[0].any())

    def test_shared_refractory_no_bypass(self):
        # absolute rule opens an episode at t=0 (sbp < 98.88); the drop rule
        # must NOT open another during the refractory window even with a
        # large further drop (regression for the alert-v1 bypass bug class)
        f = _flags([0.0, 30.0], [90.0, 60.0], drop_min=10.0, baseline=150.0,
                   sbp_rule_min=98.88)
        self.assertEqual(f[0].tolist(), [True, False])

    def test_union_with_absolute_rule(self):
        # neither rule alone at t=0; both false; then drop rule fires later
        f = _flags([0.0, 45.0, 120.0], [150.0, 140.0, 110.0],
                   drop_min=25.0, baseline=150.0, sbp_rule_min=98.88)
        self.assertEqual(f[0].tolist(), [False, False, True])

    def test_nan_baseline_inert(self):
        f = _flags([0.0, 30.0], [150.0, 100.0], drop_min=25.0,
                   baseline=np.nan)
        self.assertFalse(f[0].any())

    def test_zone_gate_blocks_high_sbp_drops(self):
        # drop 40 from baseline 150 -> sbp 110: NOT below zone max 110 -> no
        # fire; a deeper drop to 100 IS in the zone -> fires
        f = _flags([0.0, 30.0, 90.0], [150.0, 110.0, 100.0],
                   drop_min=25.0, baseline=150.0, drop_zone_max=110.0)
        self.assertEqual(f[0].tolist(), [False, False, True])

    def test_zone_gate_none_is_unconstrained(self):
        # zone None keeps the twin-v3b unconstrained behavior (fires at 110)
        f = _flags([0.0, 30.0], [150.0, 110.0],
                   drop_min=25.0, baseline=150.0, drop_zone_max=None)
        self.assertEqual(f[0].tolist(), [False, True])

    def test_zone_gated_channel_still_respects_refractory(self):
        # absolute rule opens at t=0 (sbp 90); zone-gated drop during the
        # refractory must NOT open another episode
        f = _flags([0.0, 30.0], [90.0, 70.0], drop_min=10.0, baseline=150.0,
                   sbp_rule_min=98.88, drop_zone_max=110.0)
        self.assertEqual(f[0].tolist(), [True, False])

    def test_none_drop_min_is_legacy_behavior(self):
        times = [0.0, 30.0]
        sbp = [150.0, 90.0]
        scores = np.zeros(2)
        legacy = episode_flags_matrix(
            np.asarray(times, float), scores, np.asarray(sbp, float),
            np.asarray([0.5]), 60.0, 98.88, None, None, None)
        self.assertEqual(legacy[0].tolist(), [False, True])

    def test_per_threshold_independence(self):
        # two grid entries behave independently (own refractory per row)
        times = [0.0, 50.0, 120.0]
        sbp = [150.0, 130.0, 110.0]
        f = _flags(times, sbp, drop_min=np.array([15.0, 45.0]),
                   baseline=150.0, thresholds=(0.5, 0.5))
        # drop_min 15: fires at 50 (20>=15) and again at 120 (40>=15, refr ok)
        self.assertEqual(f[0].tolist(), [False, True, True])
        # drop_min 45: never (max drop 40)
        self.assertFalse(f[1].any())


if __name__ == "__main__":
    unittest.main()
