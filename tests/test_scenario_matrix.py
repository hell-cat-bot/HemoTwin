"""Tests for the coupled scenario matrix and 4-block state vector."""
from __future__ import annotations

import unittest

import numpy as np

from src.session_twin.scenario_matrix import (
    GOVERNANCE_LABEL, build_scenario_matrix,
)
from src.session_twin.state_vector import (
    build_causal_state_vector, flatten_state_vector,
)


def _row(**kw):
    base = {
        "sbp_anchor": 120.0, "uf_at_anchor": 0.8, "uf_Lh": 0.8,
        "uf_goal_L": 2.5, "cum_uf_L": 1.5, "dry_weight": 70.0,
        "pre_weight": 72.0, "dm": 0.0, "age": 60.0, "sex_M": 0.0,
        "vintage_years": 3.0, "n_prior_sessions": 5, "k_pat": 0.30,
        "beta_pat": 15.0, "dia_temp": 36.5, "D0": 0.6, "R0": 0.3,
        "C0": 0.1, "OH0": 1.0,
        "uf_seg_1_15": 0.8, "uf_seg_16_30": 0.8, "uf_seg_31_45": 0.8,
        "uf_seg_46_60": 0.8, "sbp_now": 120.0, "dbp_now": 60.0,
        "map_now": 80.0, "sbp_mean_15": 121.0, "sbp_min_15": 118.0,
        "sbp_slope_15": -0.1, "sbp_mean_30": 122.0, "sbp_min_30": 117.0,
        "sbp_slope_30": -0.2, "sbp_mean_60": 123.0, "sbp_min_60": 116.0,
        "sbp_slope_60": -0.15, "sbp_drop_from_max": 5.0,
        "sbp_std_30": 2.0, "pulse_pressure": 60.0, "map_slope_30": -0.1,
        "uf_slope_15": 0.0, "uf_slope_30": 0.0, "uf_var_30": 0.01,
        "cum_uf_L": 1.5, "frac_uf_done": 0.6, "elapsed_min": 120.0,
        "gap_since_last": 10.0, "n_bp_so_far": 5,
    }
    base.update(kw)
    return base


class ScenarioMatrixTest(unittest.TestCase):
    def test_structure_and_governance(self):
        out = build_scenario_matrix(_row())
        self.assertEqual(len(out["scenarios"]), 5)
        self.assertEqual(out["governance_label"], GOVERNANCE_LABEL)
        self.assertIn("inverse_13_cap", out)
        for s in out["scenarios"]:
            for k in ("projected_nadir_mmhg", "nadir_band_90",
                      "peak_plasma_deficit_l", "fluid_left_behind_l",
                      "next_session_uf_intensity_ml_kg_h",
                      "clears_90_mmhg_nadir_floor"):
                self.assertIn(k, s)
            self.assertTrue(np.isfinite(s["projected_nadir_mmhg"]))

    def test_taper_lifts_nadir_and_carries_fluid(self):
        out = build_scenario_matrix(_row())
        by = {s["policy"]: s for s in out["scenarios"]}
        self.assertGreaterEqual(
            by["TAPER_50_PCT"]["projected_nadir_mmhg"],
            by["HOLD_CURRENT_UF"]["projected_nadir_mmhg"])
        self.assertGreater(
            by["TAPER_50_PCT"]["fluid_left_behind_l"],
            by["HOLD_CURRENT_UF"]["fluid_left_behind_l"])
        self.assertGreater(
            by["TAPER_50_PCT"]["expected_nadir_stabilization_vs_hold_mmhg"],
            0.0)

    def test_hold_has_zero_lift(self):
        out = build_scenario_matrix(_row())
        hold = [s for s in out["scenarios"] if s["policy"] == "HOLD_CURRENT_UF"][0]
        self.assertAlmostEqual(
            hold["expected_nadir_stabilization_vs_hold_mmhg"], 0.0, places=9)

    def test_inverse_13_cap(self):
        out = build_scenario_matrix(_row())
        cap = out["inverse_13_cap"]
        self.assertIsNotNone(cap)
        self.assertGreaterEqual(cap["uf_rate_l_h"], 0.0)
        self.assertTrue(np.isfinite(cap["projected_nadir_mmhg"]))

    def test_conformal_band(self):
        out = build_scenario_matrix(_row(), conformal=(-15.0, 25.0))
        for s in out["scenarios"]:
            lo, hi = s["nadir_band_90"]
            self.assertAlmostEqual(lo, s["projected_nadir_mmhg"] - 15.0)
            self.assertAlmostEqual(hi, s["projected_nadir_mmhg"] + 25.0)


class StateVectorTest(unittest.TestCase):
    def test_four_blocks(self):
        sv = build_causal_state_vector(_row())
        self.assertEqual(set(sv), {
            "static_ehr_state", "inter_session_memory_state",
            "intra_session_dynamic_state",
            "latent_starling_baroreflex_state"})
        self.assertAlmostEqual(
            sv["latent_starling_baroreflex_state"]["refill_deficit_l_h"],
            0.5, places=9)
        flat = flatten_state_vector(sv)
        self.assertIn("latent_starling_baroreflex_state.plasma_deficit_l",
                      flat)

    def test_cold_start_weight_zero(self):
        sv = build_causal_state_vector(_row(n_prior_sessions=0))
        self.assertEqual(sv["inter_session_memory_state"]["shrinkage_weight"],
                         0.0)
        sv2 = build_causal_state_vector(_row(n_prior_sessions=30))
        self.assertGreater(
            sv2["inter_session_memory_state"]["shrinkage_weight"], 0.7)

    def test_blocks_are_finite(self):
        sv = build_causal_state_vector(_row())
        for block, values in sv.items():
            for key, value in values.items():
                if isinstance(value, (int, float)):
                    self.assertTrue(np.isfinite(value), f"{block}.{key}")


if __name__ == "__main__":
    unittest.main()
