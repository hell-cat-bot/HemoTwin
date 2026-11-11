"""Unit tests for the G7 non-reactive step-down scanner and estimator."""
from __future__ import annotations

import unittest

import numpy as np

from src.physiotwin_v4 import PhysioParamsV4
from src.session_twin import g7_identification as G


def _event(**kw):
    base = dict(
        session_id="s1", pid="p1", fold=0, t_anchor=90.0, t_e=50.0,
        u_prev=0.6, u_new=0.3, dose_l_h=0.3, dose_units=1.2,
        held_until=80.0, sbp_now=120.0, sbp_min=116.0, slope=0.0,
        last_change=-1.0, n_cuffs=3, cum_uf_l=1.0, oh0_l=1.0,
        deltas={30: 3.0}, pre_change=0.5)
    base.update(kw)
    return G.Event(**base)


def _control(**kw):
    base = dict(
        session_id="s2", pid="p1", fold=0, t_c=52.0, sbp_now=118.0,
        sbp_min=114.0, slope=0.0, last_change=-1.0, n_cuffs=3,
        cum_uf_l=0.9, oh0_l=1.0, deltas={30: 1.0}, pre_change=0.4)
    base.update(kw)
    return G.Control(**base)


class G7ScannerTest(unittest.TestCase):
    def test_uf_step_hold_ignores_small_changes(self):
        steps = G.uf_steps([0, 10, 20, 40], [0.6, 0.4, 0.42, 0.5], 60)
        first = next(s for s in steps if s["t"] == 10.0)
        self.assertEqual(first["held_until"], 40.0)

    def test_pre_stability_pass_and_fail(self):
        ok = G.pre_stability(np.array([0, 15, 30]),
                             np.array([120, 119, 118]), 30.0)
        self.assertTrue(ok["ok"])
        bad = G.pre_stability(np.array([0, 15, 30]),
                              np.array([120, 112, 104]), 30.0)
        self.assertFalse(bad["ok"])

    def test_nearest_cuff_tolerance(self):
        et = np.array([10, 30, 50])
        es = np.array([100, 110, 120])
        self.assertEqual(G.nearest_cuff(et, es, 30, 2), (30.0, 110.0))
        self.assertIsNone(G.nearest_cuff(et, es, 40, 5))

    def test_mde_shrinks_with_n(self):
        rng = np.random.default_rng(0)
        y = rng.normal(0, 10, 200)
        pids = np.repeat(np.arange(20), 10)
        a = G.mde_power(y, pids, 100)
        b = G.mde_power(y, pids, 400)
        self.assertLess(b["mde80"], a["mde80"])

    def test_match_pairs_same_patient_other_session(self):
        ev = _event()
        pairs = G.match_pairs(
            [ev],
            {"p1": [_control(), _control(session_id="s1"),
                    _control(pid="p2")]},
            30)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["n_controls"], 1)
        self.assertAlmostEqual(pairs[0]["outcome"], 2.0)

    def test_fit_fe_dr_recovers_slope(self):
        pairs = []
        for i in range(10):
            dose = 0.5 + i * 0.1
            pairs.append({"pid": f"p{i % 5}", "dose_units": dose,
                          "outcome": 2.0 * dose, "d_sbp_now": 0.0,
                          "d_cum_uf": 0.0, "d_oh0": 0.0})
        fit = G.fit_fe_dr(pairs, "dose_units", "outcome")
        self.assertAlmostEqual(fit["slope"], 2.0, places=6)

    def test_temporal_order(self):
        d = {"et": np.array([0, 30, 60, 90, 120]),
             "es": np.array([120, 118, 116, 88, 95]),
             "mt": np.array([0, 60, 90]),
             "muf": np.array([0.6, 0.6, 0.3]),
             "pre": 60.0, "dry": 58.0}
        out = G.temporal_order_diagnostic(d, 60.0, 116.0)
        self.assertEqual(out["class"], "intermediate_after_drop")

    def test_event_dh_positive_for_step_down(self):
        d = {"et": np.array([0, 15, 30]),
             "es": np.array([120, 119, 118]),
             "mt": np.array([0, 30]),
             "muf": np.array([0.6, 0.3]),
             "pre": 60.0, "dry": 58.0}
        ev = _event(t_e=30.0)
        dh = G.event_dh(d, ev, PhysioParamsV4(w_dry_kg=60.0, oh0_l=1.0))
        self.assertGreater(dh[30], 0.0)


if __name__ == "__main__":
    unittest.main()
