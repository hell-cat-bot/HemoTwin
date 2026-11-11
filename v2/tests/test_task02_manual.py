"""Task 02 tests: manual store and universal/minimal features."""
from __future__ import annotations

import copy
import unittest

import numpy as np

from src import manual as M


def _session() -> dict:
    et = np.array([0.0, 30.0, 60.0, 90.0, 120.0])
    es = np.array([140.0, 132.0, 124.0, 116.0, 108.0])
    mt = np.arange(0.0, 121.0, 1.0)
    muf = np.where(mt < 60.0, 1.0, 0.5)
    return {
        "et": et, "es": es, "ed": es - 40.0,
        "mt": mt, "muf": muf,
        "dry": 65.0, "pre": 68.0, "goal": 3.0,
        "age": 60.0, "sex": "M", "dm": 1.0, "vintage": 3.0,
    }


class ManualStoreTest(unittest.TestCase):
    def test_cuff_entry_uf_and_cumulative(self):
        store = M.build_manual_store({"s": _session()})
        d = store["s"]
        np.testing.assert_allclose(d["cuff_uf"], [1.0, 1.0, 0.5, 0.5, 0.5])
        # 0 + (1+1)/2*30/60 + (1+0.5)/2*30/60 + (0.5+0.5)/2*30/60
        np.testing.assert_allclose(d["cuff_cum"][:4],
                                   [0.0, 0.5, 0.875, 1.125], atol=1e-12)
        np.testing.assert_allclose(d["cuff_gap"][1:], [30, 30, 30, 30])
        np.testing.assert_allclose(d["cuff_uf_change"][1:],
                                   [0.0, -0.5, 0.0, 0.0])

    def test_universal_features(self):
        store = M.build_manual_store({"s": _session()})
        r = M.universal_features(store["s"], 60.0, "p1_2020-03-01")
        self.assertAlmostEqual(r["uf_Lh"], 0.5)
        self.assertAlmostEqual(r["cum_uf_L"], 0.875)
        self.assertAlmostEqual(r["uf_ml_kg_h"], 0.5 * 1000.0 / 65.0)
        self.assertAlmostEqual(r["uf_delta_30"], -0.5)
        self.assertAlmostEqual(r["uf_delta_60"], -0.5)
        self.assertEqual(r["elapsed_min"], 60.0)
        self.assertEqual(r["month"], 3)
        self.assertEqual(r["cuff_gap"], 30.0)
        for forbidden in ("blood_flow", "conductivity", "dia_temp",
                          "k_pat", "beta_pat", "twin_D_now", "twin_pre_nadir"):
            self.assertNotIn(forbidden, r)

    def test_universal_future_invariance(self):
        d = _session()
        store = M.build_manual_store({"s": d})
        before = M.universal_features(store["s"], 60.0, "p1_2020-03-01")
        d2 = copy.deepcopy(store["s"])
        d2["et"][3:] = [110.0, 150.0]
        d2["es"][3:] = [70.0, 65.0]
        d2["ed"][3:] = [30.0, 25.0]
        d2["cuff_uf"][3:] = [0.0, 0.0]
        d2["cuff_cum"][3:] = [9.0, 9.0]
        after = M.universal_features(d2, 60.0, "p1_2020-03-01")
        for k in before:
            a, b = before[k], after[k]
            if isinstance(a, float) and np.isnan(a) and np.isnan(b):
                continue
            if isinstance(a, float):
                self.assertAlmostEqual(a, b, places=12, msg=k)
            else:
                self.assertEqual(a, b, msg=k)

    def test_minimal_columns_exclude_rate_dynamics(self):
        cols = ["uf_Lh", "uf_ml_kg_h", "uf_change_prev", "uf_delta_30",
                "uf_delta_60", "cum_uf_L", "sbp_now", "cuff_gap",
                "hist_prev_nadir", "uf_goal_L"]
        keep = set(M.minimal_feature_columns(cols))
        self.assertNotIn("uf_Lh", keep)
        self.assertNotIn("uf_ml_kg_h", keep)
        self.assertNotIn("uf_change_prev", keep)
        self.assertNotIn("uf_delta_30", keep)
        self.assertNotIn("uf_delta_60", keep)
        self.assertIn("cum_uf_L", keep)
        self.assertIn("sbp_now", keep)
        self.assertIn("cuff_gap", keep)
        self.assertIn("hist_prev_nadir", keep)
        self.assertIn("uf_goal_L", keep)


if __name__ == "__main__":
    unittest.main()
