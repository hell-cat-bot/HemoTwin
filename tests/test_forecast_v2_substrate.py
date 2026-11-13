"""Tests for the forecast-v2 substrate (task03 nadir-specialized GBDT refit).

Contract under test: artifacts/review_20261108/predictions_outer_v2.parquet
has EXACTLY the frozen Task 01 substrate schema and row alignment, with only
pred_gbdt / pred_gbdt_30 / pred_gbdt_60 replaced by the refit values (all
finite on every primary anchor). The frozen substrate itself is read-only.

These tests are skipped (with a clear reason) when the v2 artifact has not
been built yet, so the suite stays green on a fresh checkout.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import ARTIFACTS

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ARTIFACTS / "review_20261107" / "task01" / "predictions_outer.parquet"
V2 = ARTIFACTS / "review_20261108" / "predictions_outer_v2.parquet"
REPORT = ARTIFACTS / "review_20261108" / "task03_refit_report.json"
PRED_COLS = ("pred_gbdt", "pred_gbdt_30", "pred_gbdt_60")


@unittest.skipUnless(V2.exists() and FROZEN.exists(),
                     f"v2 substrate not built yet ({V2})")
class TestForecastV2Substrate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = pd.read_parquet(FROZEN)
        cls.v2 = pd.read_parquet(V2)

    def test_row_count_is_38143(self):
        self.assertEqual(len(self.v2), 38143)
        self.assertEqual(len(self.frozen), len(self.v2))

    def test_schema_identical_to_frozen(self):
        self.assertEqual(list(self.v2.columns), list(self.frozen.columns))
        for c in self.frozen.columns:
            self.assertEqual(
                self.v2[c].dtype, self.frozen[c].dtype,
                f"column {c}: dtype {self.v2[c].dtype} != frozen "
                f"{self.frozen[c].dtype}")

    def test_pred_columns_finite_on_all_primary_anchors(self):
        for c in PRED_COLS:
            arr = self.v2[c].to_numpy(dtype=float)
            self.assertEqual(int(arr.size), 38143)
            self.assertTrue(bool(np.isfinite(arr).all()),
                            f"{c} has non-finite values")

    def test_key_and_role_columns_unchanged_vs_frozen(self):
        for c in ("session_id", "pid", "fold", "t_anchor", "regime",
                  "observed_nadir", "observed_30", "observed_60",
                  "sbp_anchor"):
            self.assertTrue(self.v2[c].equals(self.frozen[c]),
                            f"column {c} differs from frozen substrate")

    def test_all_non_pred_columns_copied_verbatim(self):
        non_pred = [c for c in self.frozen.columns if c not in PRED_COLS]
        self.assertTrue(
            self.v2[non_pred].equals(self.frozen[non_pred]),
            "non-prediction columns were not copied verbatim")

    def test_pred_columns_actually_refit(self):
        # the refit must not be a verbatim copy of the frozen predictions
        self.assertFalse(
            self.v2["pred_gbdt"].equals(self.frozen["pred_gbdt"]),
            "pred_gbdt identical to the frozen GBDT — refit did not apply")

    def test_row_alignment_on_join_keys(self):
        self.assertTrue(
            (self.v2["session_id"] == self.frozen["session_id"]).all())
        self.assertTrue(
            (self.v2["t_anchor"] == self.frozen["t_anchor"]).all())
        self.assertEqual(self.v2["session_id"].nunique(), 38143)


@unittest.skipUnless(REPORT.exists(), f"refit report not written yet ({REPORT})")
class TestRefitReport(unittest.TestCase):
    def test_report_has_self_check_numbers(self):
        rep = json.loads(REPORT.read_text())
        self.assertIn("self_check", rep)
        sc = rep["self_check"]
        for k in ("mae_raw_refit_eval", "mae_raw_frozen_gbdt_eval",
                  "mae_corrected_frozen_eval"):
            self.assertIn(k, sc)
            self.assertIsInstance(sc[k], float)

    def test_report_records_excluded_columns(self):
        rep = json.loads(REPORT.read_text())
        self.assertIn("excluded_columns", rep)

    def test_no_fold2_metric_in_report(self):
        rep = json.loads(REPORT.read_text())
        self.assertNotIn("fold_2_mae", rep)
        self.assertNotIn("mae_fold_2", rep)


if __name__ == "__main__":
    unittest.main()
