"""Task 00 tests: causal anchor features and unit correctness."""
from __future__ import annotations

import copy
import math
import unittest

import numpy as np
import pandas as pd

from src import features as F
from src import twin as T


def _session(uf_now: float = 1.3) -> dict:
    et = np.array([0, 30, 60, 90, 120, 150], dtype=float)
    es = np.array([140, 132, 124, 116, 108, 100], dtype=float)
    mt = np.array([0, 30, 60, 90, 120, 150], dtype=float)
    muf = np.array([uf_now, uf_now, uf_now, uf_now, 0.5, 0.0], dtype=float)
    cum = np.concatenate(
        [[0.0], np.cumsum(np.diff(mt) / 60.0 * (muf[1:] + muf[:-1]) / 2.0)])
    return {
        "et": et, "es": es, "ed": es - 40.0,
        "mt": mt, "muf": muf, "cum_uf": cum,
        "mbf": np.full_like(mt, 300.0),
        "mco": np.full_like(mt, 14.0),
        "mdt": np.full_like(mt, 36.5),
        "dry": 65.0, "pre": 68.0, "goal": 3.0,
        "age": 60.0, "sex": "M", "dm": 1.0, "vintage": 3.0,
        "temp_presc": 36.5, "measured_uf": 2.5,
    }


def _dicts_equal(testcase, a, b):
    testcase.assertEqual(set(a), set(b))
    for key in a:
        x, y = a[key], b[key]
        if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
            continue
        if isinstance(x, float) and isinstance(y, float):
            testcase.assertTrue(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12),
                                msg=f"{key}: {x} != {y}")
        else:
            testcase.assertEqual(x, y, msg=key)


class CausalFeatureTest(unittest.TestCase):
    def test_future_values_do_not_change_anchor_features(self):
        d = _session()
        before = F.causal_anchor_features(d, 90.0, "p1_2020-01-01", 0.30, 19.6)
        d2 = copy.deepcopy(d)
        d2["es"][4:] = [70.0, 60.0]
        d2["ed"][4:] = [30.0, 20.0]
        d2["mt"][4:] = [100.0, 110.0]
        d2["muf"][4:] = [3.0, 0.0]
        d2["mbf"][4:] = [100.0, 50.0]
        d2["mco"][4:] = [10.0, 9.0]
        d2["mdt"][4:] = [34.0, 33.0]
        d2["cum_uf"][4:] = [5.0, 5.0]
        after = F.causal_anchor_features(d2, 90.0, "p1_2020-01-01", 0.30, 19.6)
        _dicts_equal(self, before, after)

    def test_duration_derived_features_are_absent(self):
        d = _session()
        r = F.causal_anchor_features(d, 90.0, "p1_2020-01-01", 0.30, 19.6)
        for name in ("elapsed_frac", "minutes_to_end",
                     "uf_required_Lh", "uf_gap_Lh"):
            self.assertNotIn(name, r)

    def test_worked_uf_intensity_example(self):
        d = _session(uf_now=1.3)
        r = F.causal_anchor_features(d, 90.0, "p1_2020-01-01", 0.30, 19.6)
        self.assertAlmostEqual(r["uf_ml_kg_h"], 20.0, places=9)
        self.assertEqual(r["uf_over13"], 1.0)

    def test_refill_feature_has_per_minute_k_units(self):
        d = _session()
        k, beta = 0.30, 19.6
        r = F.causal_anchor_features(d, 90.0, "p1_2020-01-01", k, beta)
        D_now = T.twin_state_at(d, 90.0, k)["D_now"]
        uf_now = r["uf_Lh"]
        # refill = phi*UF + k*D in L/h; the k*D term must be per minute, not
        # per hour. With k=0.3, phi=0.3: refill = 0.3*UF + 0.3*D.
        expected = T.POP_PHI * uf_now + k * D_now
        self.assertAlmostEqual(r["twin_refill_Lh"], expected, places=9)

    def test_twin_pred_nadir_is_the_shared_forecast(self):
        d = _session()
        k, beta = 0.30, 19.6
        r = F.causal_anchor_features(d, 90.0, "p1_2020-01-01", k, beta)
        params = {"k_refill": k, "beta_bp": beta, "beta_T": T.POP_BETA_T}
        fc = T.simulate_policy(d, 90.0, params, T.POLICIES["hold"], horizon=60)
        self.assertTrue(fc["feasible"])
        self.assertEqual(r["twin_pred_nadir"], fc["nadir"])


class FeatureFrameTest(unittest.TestCase):
    def test_frame_drops_metadata_from_model_columns(self):
        d = _session()
        sid = "p1_2020-01-01"
        tables = {
            "events": pd.DataFrame({
                "session_id": [sid], "pid": ["p1"], "t_min": [90.0],
                "sbp": [116.0], "dbp": [76.0],
            }),
            "session_store": {sid: d},
        }
        anch = pd.DataFrame([{
            "session_id": sid, "pid": "p1", "t_min": 90.0,
            "sbp_now": 116.0, "dbp_now": 76.0, "onset_min": np.nan,
            "label": 0, "coverage_complete": True, "primary_eligible": True,
            "n_earlier": 3,
        }])
        twin_state = pd.DataFrame([{
            "session_id": sid, "k_pat": 0.30, "beta_pat": 19.6, "n_prior": 1,
        }])
        frame = F.make_tabular_features(tables, anch, twin_state)
        self.assertEqual(len(frame), 1)
        feats = F.feature_columns(frame)
        for name in ("session_id", "pid", "label", "t_min", "onset_min",
                     "coverage_complete", "primary_eligible", "n_earlier"):
            self.assertNotIn(name, feats)
        self.assertNotIn("elapsed_frac", feats)
        self.assertNotIn("minutes_to_end", feats)
        self.assertIn("twin_pred_nadir", feats)


if __name__ == "__main__":
    unittest.main()
