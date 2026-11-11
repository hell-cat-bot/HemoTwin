"""Task 00 tests: causal, fold-aware weight fallbacks."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.data import build_session_store, resolve_weights


def _ev(rows):
    return pd.DataFrame(rows, columns=[
        "pid", "session_id", "date", "dry_weight_sess", "pre_weight_sess"])


class WeightFallbackTest(unittest.TestCase):
    def setUp(self):
        self.ev = _ev([
            ("A", "A_2020-01-01", "2020-01-01", 60.0, 63.0),
            ("A", "A_2020-01-03", "2020-01-03", np.nan, np.nan),
            ("B", "B_2020-01-02", "2020-01-02", 80.0, 84.0),
            ("B", "B_2020-01-04", "2020-01-04", np.nan, np.nan),
            ("C", "C_2020-01-05", "2020-01-05", np.nan, np.nan),
            ("D", "D_2020-01-06", "2020-01-06", 120.0, 125.0),
        ])
        self.weights = resolve_weights(self.ev, fit_pids={"A", "C"})
        self.w = self.weights.set_index("session_id")

    def test_session_level_values_win(self):
        r = self.w.loc["A_2020-01-01"]
        self.assertEqual(r.weight_source, "session")
        self.assertEqual(r.dry_weight, 60.0)
        self.assertEqual(r.uf_goal_L, 3.0)

    def test_same_patient_prior_session_is_used(self):
        r = self.w.loc["A_2020-01-03"]
        self.assertEqual(r.weight_source, "prior_patient")
        self.assertEqual(r.dry_weight, 60.0)
        self.assertEqual(r.pre_weight, 63.0)

    def test_prior_session_works_for_outer_test_patient(self):
        # B is not a fit patient; its own earlier session is still a causal
        # personalization source, never a population prior.
        r = self.w.loc["B_2020-01-04"]
        self.assertEqual(r.weight_source, "prior_patient")
        self.assertEqual(r.dry_weight, 80.0)

    def test_fit_population_excludes_non_fit_patients(self):
        r = self.w.loc["C_2020-01-05"]
        self.assertEqual(r.weight_source, "fit_population")
        self.assertEqual(r.dry_weight, 60.0)  # D's 120 must not enter the median
        self.assertEqual(r.pre_weight, 63.0)

    def test_missing_when_no_fit_population_and_no_history(self):
        w = resolve_weights(self.ev, fit_pids=set()).set_index("session_id")
        r = w.loc["C_2020-01-05"]
        self.assertEqual(r.weight_source, "missing")
        self.assertTrue(np.isnan(r.dry_weight))
        self.assertTrue(np.isnan(r.uf_goal_L))

    def test_goal_is_weight_derived(self):
        r = self.w.loc["B_2020-01-04"]
        self.assertEqual(r.uf_goal_L, 4.0)

    def test_store_uses_resolved_weights(self):
        tables = {
            "events": pd.DataFrame([{
                "session_id": "A_2020-01-03", "pid": "A", "t_min": 30.0,
                "sbp": 120.0, "dbp": 70.0, "age": 60.0, "sex": "M", "dm": 0,
                "vintage_years": 2.0, "dry_weight": np.nan,
                "pre_weight": np.nan, "uf_goal_L": np.nan,
                "dia_temp_presc": 36.5, "uf_measured_L": np.nan,
                "uf_goal_source": "unresolved",
            }]),
            "telemetry": pd.DataFrame([{
                "session_id": "A_2020-01-03", "time": 0.0, "uf": 1.0,
                "blood_flow": 300.0, "conductivity": 14.0,
                "dia_temp_value": 36.5,
            }]),
        }
        store = build_session_store(tables, weights=self.weights)
        d = store["A_2020-01-03"]
        self.assertEqual(d["dry"], 60.0)
        self.assertEqual(d["pre"], 63.0)
        self.assertEqual(d["goal"], 3.0)
        self.assertEqual(d["weight_source"], "prior_patient")


if __name__ == "__main__":
    unittest.main()
