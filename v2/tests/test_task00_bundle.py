"""Task 00 tests: rescue routing, MET fallback, and cascade units."""
from __future__ import annotations

import types
import unittest

import numpy as np

from src import bundle as B
from src import twin as T


def _alert(score: float, sbp_now: float = 120.0):
    return types.SimpleNamespace(score=score, sbp_now=sbp_now, label=0,
                                 onset_min=np.nan)


class ActionRoutingTest(unittest.TestCase):
    def test_current_hypotension_is_rescue_even_with_low_score(self):
        txt = B._action({"nadir": 110.0, "time_to_nadir_min": 30.0}, None,
                        _alert(0.01, sbp_now=85.0))
        self.assertIn("Current SBP is below 90", txt)
        self.assertIn("does not depend on the forecast score", txt)
        self.assertNotIn("Routine monitoring", txt)

    def test_low_score_cannot_suppress_projected_crash(self):
        txt = B._action({"nadir": 82.0, "time_to_nadir_min": 25.0}, None,
                        _alert(0.01, sbp_now=120.0))
        self.assertNotIn("Routine monitoring", txt)
        self.assertIn("projects a nadir of 82", txt)
        self.assertIn("recommendations are retired", txt)
        self.assertNotIn("250", txt)
        self.assertNotIn("give", txt.lower())

    def test_no_silent_point_estimate_fallback(self):
        sweep = [
            {"taper_frac": 0.0, "nadir": 80.0},
            {"taper_frac": 0.50, "nadir": 95.0},
        ]
        band = {"lo": -12.0, "hi": 12.0}
        self.assertIsNone(T.min_effective_taper(sweep, band, target=90.0))
        txt = B._action({"nadir": 80.0, "time_to_nadir_min": 30.0}, None,
                        _alert(0.5, sbp_now=118.0))
        self.assertIn("No simulated taper clears", txt)
        self.assertNotIn("taper UF by", txt)

    def test_met_is_not_a_quantitative_recommendation(self):
        met = {"taper_frac": 0.25, "nadir": 93.0, "fluid_left_L": 0.4}
        txt = B._action({"nadir": 80.0, "time_to_nadir_min": 30.0}, met,
                        _alert(0.5, sbp_now=118.0))
        self.assertIn("not a validated quantitative recommendation", txt)
        self.assertNotIn("taper UF by 25%", txt)

    def test_hold_above_target_continues(self):
        txt = B._action({"nadir": 105.0, "time_to_nadir_min": 20.0}, None,
                        _alert(0.9, sbp_now=125.0))
        self.assertIn("Continue the current prescription", txt)

    def test_infeasible_forecast_is_explicit(self):
        txt = B._action({"nadir": float("nan"), "time_to_nadir_min": None},
                        None, _alert(0.9, sbp_now=125.0))
        self.assertIn("Forecast unavailable", txt)
        self.assertNotIn("Routine monitoring", txt)


class CascadeUnitTest(unittest.TestCase):
    def test_corrected_ml_kg_h(self):
        v = B.next_session_intensity(2.6, 0.0, 180.0, 65.0)
        self.assertAlmostEqual(v, 13.3333333, places=5)
        self.assertGreater(v, 13.0)

    def test_missing_inputs_return_none(self):
        self.assertIsNone(B.next_session_intensity(np.nan, 0.0, 180.0, 65.0))
        self.assertIsNone(B.next_session_intensity(2.6, 0.0, 0.0, 65.0))
        self.assertIsNone(B.next_session_intensity(2.6, 0.0, 180.0, 10.0))

    def test_disabled_cooling_and_pause_cards(self):
        self.assertNotIn("cool10", B.WHATIF_POLICIES)
        self.assertNotIn("pause", B.WHATIF_POLICIES)
        self.assertIn("hold", B.WHATIF_POLICIES)
        self.assertIn("taper25", B.WHATIF_POLICIES)


if __name__ == "__main__":
    unittest.main()
