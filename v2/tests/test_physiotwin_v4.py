"""Unit tests for the PhysioTwin-v4.1 core (v1 product)."""
from __future__ import annotations

import unittest

import numpy as np

from src.physiotwin_v4 import (
    PhysioParamsV4, StarlingBaroreflexState, counterfactual_batch,
    estimate_patient_posterior_params, integrate_pre_anchor, params_to_batch,
    phi_shape, policy_schedule, rk4_step_starling_baroreflex,
    segments_to_minutes, session_uf_grid, simulate_branch_batch,
    summarize_branch,
)


def _params(**kw):
    base = dict(w_dry_kg=70.0, oh0_l=2.0, v_b0_l=5.25, beta_vol_mmHg_per_l=12.0,
                beta_baro_mmHg=14.0, k_refill=1.0, theta_crit=0.06)
    base.update(kw)
    return PhysioParamsV4(**base)


def _state0(d=0.5, r=0.3, c=0.1, oh=1.0):
    return {"D": np.array([d]), "R": np.array([r]),
            "C": np.array([c]), "OH": np.array([oh])}


def _batch(state0, uf):
    uf = np.asarray(uf, dtype=float).reshape(1, -1)
    p = _params()
    return counterfactual_batch(state0, params_to_batch([p]),
                                np.array([120.0]), np.array([112.0]),
                                uf, uf)


class PhiShapeTest(unittest.TestCase):
    def test_endpoints_and_monotonicity(self):
        dt = np.arange(61, dtype=float)
        phi = phi_shape(dt)
        self.assertAlmostEqual(float(phi[0]), 0.0, places=12)
        self.assertAlmostEqual(float(phi[-1]), 1.0, places=12)
        self.assertTrue(np.all(np.diff(phi) >= 0.0))
        expected = (1 - np.exp(-1.0)) / (1 - np.exp(-60.0 / 22.0))
        self.assertAlmostEqual(float(phi_shape(np.array([22.0]))[0]),
                               expected, places=6)


class AnchorIdentityTest(unittest.TestCase):
    def test_continuity_at_zero(self):
        out = _batch(_state0(), np.full(60, 0.6))
        self.assertAlmostEqual(float(out["sbp"][0, 0]), 120.0, places=12)

    def test_expected_care_reduces_to_baseline(self):
        out = _batch(_state0(), np.full(60, 0.6))
        self.assertAlmostEqual(float(out["sbp"][0, -1]), 112.0, places=9)
        self.assertTrue(np.allclose(out["sbp"][0], out["B"][0]))

    def test_mu_above_anchor_uses_endpoint(self):
        # The plan's min-over-[15,60] identity is false when mu > anchor;
        # the implementation reports B(60) as the projected nadir.
        st = _state0()
        uf = np.full(60, 0.6).reshape(1, -1)
        out = counterfactual_batch(st, params_to_batch([_params()]),
                                   np.array([120.0]), np.array([130.0]),
                                   uf, uf)
        self.assertAlmostEqual(float(out["sbp"][0, -1]), 130.0, places=9)
        self.assertLess(float(np.min(out["sbp"][0, 15:])), 130.0)

    def test_refill_lag_is_continuous_across_uf_change(self):
        p = _params()
        st = StarlingBaroreflexState(0.0, 0.0, 0.0, p.oh0_l)
        for _ in range(120):
            st = rk4_step_starling_baroreflex(st, 0.6, p)
        before = st.r_refill_l_h
        st = rk4_step_starling_baroreflex(st, 0.3, p)
        self.assertLess(abs(st.r_refill_l_h - before), 0.02)
        self.assertGreater(st.r_refill_l_h, 0.0)

    def test_batch_matches_scalar_step(self):
        p = _params()
        st = StarlingBaroreflexState(0.5, 0.3, 0.1, 1.0)
        scalar = rk4_step_starling_baroreflex(st, 0.6, p)
        batch = simulate_branch_batch(
            {"D": np.array([0.5]), "R": np.array([0.3]),
             "C": np.array([0.1]), "OH": np.array([1.0])},
            np.full((1, 1), 0.6), params_to_batch([p]))
        for key, val in (("D", scalar.d_deficit_l),
                         ("R", scalar.r_refill_l_h),
                         ("C", scalar.c_baro_exhaustion),
                         ("OH", scalar.oh_remaining_l)):
            self.assertAlmostEqual(float(batch[key][0, 1]), val, places=12)


class MonotonicityTest(unittest.TestCase):
    def test_lower_uf_never_lowers_sbp(self):
        st = _state0()
        p = _params()
        exp = np.full(60, 0.4).reshape(1, -1)
        low = np.full(60, 0.2).reshape(1, -1)
        high = np.full(60, 0.6).reshape(1, -1)
        a = counterfactual_batch(st, params_to_batch([p]),
                                 np.array([120.0]), np.array([112.0]), exp, low)
        b = counterfactual_batch(st, params_to_batch([p]),
                                 np.array([120.0]), np.array([112.0]), exp, high)
        self.assertTrue(np.all(a["sbp"] >= b["sbp"] - 1e-9))

    def test_policy_schedules(self):
        hold = policy_schedule("HOLD", 0.8)
        self.assertTrue(np.allclose(hold, 0.8))
        self.assertTrue(np.allclose(policy_schedule("TAPER_50", 0.8), 0.4))
        self.assertTrue(np.allclose(policy_schedule("TAPER_75", 0.8), 0.6))
        floor = policy_schedule("MIN_KEEP_OPEN_010_LH", 0.8)
        self.assertTrue(np.allclose(floor, 0.1))
        pause = policy_schedule("PAUSE_30M_THEN_RESUME", 0.8)
        self.assertTrue(np.allclose(pause[:30], 0.0))
        self.assertTrue(np.allclose(pause[30:], 0.8))

    def test_segments_to_minutes(self):
        out = segments_to_minutes([0.1, 0.2, 0.3, 0.4])
        self.assertEqual(out.shape, (60,))
        self.assertAlmostEqual(float(out[:15].mean()), 0.1)
        self.assertAlmostEqual(float(out[45:].mean()), 0.4)


class ParameterTest(unittest.TestCase):
    def test_cold_start_is_covariate_prior(self):
        p = estimate_patient_posterior_params({
            "n_prior": 0, "dm": 0, "age": 50, "dry_weight": 70.0,
            "pre_weight": 72.0, "k_pat": 0.9, "beta_pat": 23.0})
        self.assertAlmostEqual(p.k_refill, 1.0, places=9)
        self.assertAlmostEqual(p.beta_vol_mmHg_per_l, 10.0, places=9)
        self.assertAlmostEqual(p.theta_crit, 0.065, places=9)
        self.assertAlmostEqual(p.oh0_l, 2.0, places=9)
        self.assertAlmostEqual(p.v_b0_l, 5.25, places=9)

    def test_shrinkage_increases_with_history(self):
        base = {"dm": 0, "age": 50, "dry_weight": 70.0, "pre_weight": 72.0,
                "k_pat": 0.9, "beta_pat": 23.0}
        p2 = estimate_patient_posterior_params({**base, "n_prior": 2})
        p30 = estimate_patient_posterior_params({**base, "n_prior": 30})
        self.assertGreater(p30.k_refill, p2.k_refill)
        self.assertGreater(p30.beta_vol_mmHg_per_l, p2.beta_vol_mmHg_per_l)

    def test_frail_prior_lowers_threshold(self):
        p = estimate_patient_posterior_params({
            "n_prior": 0, "dm": 1, "age": 70, "dry_weight": 70.0})
        self.assertAlmostEqual(p.theta_crit, 0.045, places=9)
        self.assertGreaterEqual(p.beta_baro_mmHg, 6.0)

    def test_bounds(self):
        for n in (0, 2, 30, 300):
            p = estimate_patient_posterior_params({
                "n_prior": n, "dm": 1, "age": 80, "dry_weight": 70.0,
                "pre_weight": 76.0, "k_pat": 5.0, "beta_pat": 50.0})
            self.assertGreaterEqual(p.beta_vol_mmHg_per_l, 4.5)
            self.assertLessEqual(p.beta_vol_mmHg_per_l, 24.0)
            self.assertGreaterEqual(p.beta_baro_mmHg, 6.0)
            self.assertLessEqual(p.beta_baro_mmHg, 28.0)
            self.assertTrue(np.isfinite(p.k_refill))


class CausalityTest(unittest.TestCase):
    def test_future_machine_records_are_ignored(self):
        d = {"mt": np.array([0.0, 10.0, 20.0, 30.0]),
             "muf": np.array([0.5, 0.6, 0.7, 0.9])}
        g = session_uf_grid(d, 15)
        d2 = {"mt": np.array([0.0, 10.0, 20.0, 30.0, 40.0]),
              "muf": np.array([0.5, 0.6, 0.7, 0.9, 9.9])}
        g2 = session_uf_grid(d2, 15)
        self.assertTrue(np.array_equal(g, g2))
        self.assertAlmostEqual(float(g[0]), 0.5)
        self.assertAlmostEqual(float(g[10]), 0.6)
        self.assertAlmostEqual(float(g[15]), 0.6)

    def test_pre_anchor_integration_is_causal(self):
        grid = np.linspace(0.5, 0.5, 121)
        p = _params()
        rec = integrate_pre_anchor(grid, 120, p, record_minutes=[60, 120])
        self.assertIn(60, rec)
        self.assertIn(120, rec)
        self.assertGreaterEqual(rec[120].d_deficit_l, rec[60].d_deficit_l)

    def test_summary_keys(self):
        out = _batch(_state0(), np.full(60, 0.6))
        s = summarize_branch(out, "HOLD")
        for k in ("projected_nadir_mmhg", "trajectory_min_mmhg",
                  "peak_deficit_l", "delayed_refill_rate_end_l_h",
                  "peak_baro_exhaustion_pct", "nadir_series_mmhg"):
            self.assertIn(k, s)
        self.assertEqual(len(s["nadir_series_mmhg"]), 61)
        self.assertTrue(np.isfinite(s["projected_nadir_mmhg"]))


if __name__ == "__main__":
    unittest.main()
