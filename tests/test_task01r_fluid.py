"""Task 01R fluid-accounting golden and property tests."""
from __future__ import annotations

import math
import unittest

from src.session_twin.fluid import calculate_fluid


class FluidTest(unittest.TestCase):
    def test_golden_case(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.2, q_left=0.5,
                            additional_fluid_L=0.1, next_prescription_L=2.0,
                            next_duration_h=4.0, weight_kg=65.0)
        self.assertEqual(r["remaining_uf_status"], "ok")
        self.assertAlmostEqual(r["remaining_uf_mL"], 1800.0)
        self.assertAlmostEqual(r["fluid_left_mL"], 900.0)
        self.assertAlmostEqual(r["carry_forward_mL"], 1000.0)
        self.assertAlmostEqual(r["next_session_volume_mL"], 3000.0)
        self.assertAlmostEqual(r["baseline_intensity_mL_kg_h"], 2000.0 / (65.0 * 4.0))
        self.assertAlmostEqual(r["scenario_intensity_mL_kg_h"], 3000.0 / (65.0 * 4.0))
        self.assertEqual(r["intensity_status"], "ok")

    def test_missing_weight_keeps_volume(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.0, q_left=0.25,
                            next_prescription_L=2.0, next_duration_h=4.0,
                            weight_kg=None)
        self.assertEqual(r["carry_forward_mL"], 500.0)
        self.assertEqual(r["next_session_volume_mL"], 2500.0)
        self.assertEqual(r["intensity_status"], "missing_weight")
        self.assertIsNone(r["baseline_intensity_mL_kg_h"])

    def test_missing_duration_keeps_volume(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.0, q_left=0.0,
                            next_prescription_L=2.0, next_duration_h=None,
                            weight_kg=65.0)
        self.assertEqual(r["next_session_volume_mL"], 2000.0)
        self.assertEqual(r["intensity_status"], "missing_duration")
        self.assertIsNone(r["scenario_intensity_mL_kg_h"])

    def test_missing_next_prescription_keeps_carry(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.0, q_left=0.5,
                            next_prescription_L=None, next_duration_h=4.0,
                            weight_kg=65.0)
        self.assertEqual(r["carry_forward_mL"], 1000.0)
        self.assertEqual(r["next_session_volume_status"], "missing")
        self.assertIsNone(r["next_session_volume_mL"])

    def test_more_fluid_left_cannot_reduce_carry(self):
        a = calculate_fluid(uf_goal_L=4.0, uf_removed_L=1.0, q_left=0.25,
                            next_prescription_L=2.0, next_duration_h=4.0,
                            weight_kg=70.0)
        b = calculate_fluid(uf_goal_L=4.0, uf_removed_L=1.0, q_left=0.50,
                            next_prescription_L=2.0, next_duration_h=4.0,
                            weight_kg=70.0)
        self.assertLessEqual(a["carry_forward_mL"], b["carry_forward_mL"])

    def test_removed_above_goal_is_zero_remaining(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=3.4, q_left=0.5,
                            next_prescription_L=2.0, next_duration_h=4.0,
                            weight_kg=65.0)
        self.assertEqual(r["remaining_uf_mL"], 0.0)
        self.assertEqual(r["carry_forward_mL"], 0.0)

    def test_invalid_q_rejected(self):
        with self.assertRaises(ValueError):
            calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.0, q_left=1.2)

    def test_all_outputs_finite(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.0, q_left=0.3,
                            additional_fluid_L=0.2, next_prescription_L=2.5,
                            next_duration_h=3.5, weight_kg=62.0)
        for key in ("remaining_uf_mL", "fluid_left_mL", "carry_forward_mL",
                    "next_session_volume_mL", "baseline_intensity_mL_kg_h",
                    "scenario_intensity_mL_kg_h"):
            self.assertTrue(math.isfinite(r[key]), key)

    def test_reference_threshold_flags_without_changing_prescription(self):
        r = calculate_fluid(uf_goal_L=3.0, uf_removed_L=1.0, q_left=1.0,
                            next_prescription_L=4.0, next_duration_h=4.0,
                            weight_kg=65.0)
        self.assertTrue(r["scenario_over_reference"])
        self.assertEqual(r["reference_intensity_mL_kg_h"], 13.0)
        self.assertEqual(r["next_session_volume_mL"], 6000.0)


if __name__ == "__main__":
    unittest.main()
