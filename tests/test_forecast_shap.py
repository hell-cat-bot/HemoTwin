"""Tests for exact TreeSHAP attribution."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import forecast_serve as FS
from src.paths import ARTIFACTS


TABLE = str(ARTIFACTS / "physiotwin_v4" / "anchor_table.parquet")


def _features():
    try:
        row = pd.read_parquet(TABLE).iloc[0].to_dict()
    except Exception:
        row = {}
    return row


class ShapTest(unittest.TestCase):
    def test_available_and_consistent(self):
        out = FS.explain_forecast_drivers(_features())
        if not out.get("available"):
            self.skipTest(f"model bundle unavailable: {out.get('reason')}")
        self.assertTrue(np.isfinite(out["prediction_mmHg"]))
        self.assertEqual(out["n_seeds"], 3)
        # block totals must exhaust the sum of feature contributions
        total = out["prediction_mmHg"] - out["base_value_mmHg"]
        block_sum = sum(out["block_totals_mmHg"].values())
        self.assertAlmostEqual(block_sum, total, places=6)
        self.assertIn("STATIC_EHR", out["primary_block_totals_mmHg"])
        self.assertIn("PATIENT_HISTORY_MEMORY",
                      out["primary_block_totals_mmHg"])
        self.assertIn("DYNAMIC_INTRA_SESSION",
                      out["primary_block_totals_mmHg"])
        for item in out["top_downward"]:
            self.assertLess(item["contribution_mmHg"], 0.0)
        for item in out["top_stabilizing"]:
            self.assertGreater(item["contribution_mmHg"], 0.0)

    def test_missing_features_do_not_crash(self):
        out = FS.explain_forecast_drivers({"sbp_now": 120.0})
        if out.get("available"):
            self.assertTrue(np.isfinite(out["prediction_mmHg"]))
        else:
            self.assertIn("reason", out)

    def test_fallback(self):
        with patch.object(FS, "load_bundle", return_value=None):
            out = FS.explain_forecast_drivers({"sbp_now": 120.0})
        self.assertFalse(out["available"])
        self.assertIn("reason", out)

    def test_pre_anchor_attribution(self):
        out = FS.explain_pre_anchor_drivers(_features(), top_k=3)
        if not out.get("available"):
            self.skipTest(f"v4 model unavailable: {out.get('reason')}")
        self.assertTrue(np.isfinite(out["prediction_mmHg"]))
        self.assertEqual(out["n_seeds"], 3)
        self.assertIn("STATIC_EHR", out["primary_block_totals_mmHg"])
        self.assertLessEqual(len(out["top_downward"]), 3)
        total = out["prediction_mmHg"] - out["base_value_mmHg"]
        self.assertAlmostEqual(
            sum(out["block_totals_mmHg"].values()), total, places=5)


if __name__ == "__main__":
    unittest.main()
