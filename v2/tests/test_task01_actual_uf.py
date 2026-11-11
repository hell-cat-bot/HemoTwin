"""Task 01 tests: machine-only UF, oracle, regimes, and baselines."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from src import actual_uf as A
from src import data


def _session(uf_seq=None) -> dict:
    et = np.arange(0.0, 181.0, 30.0)
    es = 140.0 - 0.20 * et
    mt = np.arange(0.0, 181.0, 1.0)
    if uf_seq is None:
        uf_seq = np.where(mt <= 60.0, 1.0, 0.5)
    muf = np.asarray(uf_seq, dtype=float)
    cum = np.concatenate(
        [[0.0], np.cumsum(np.diff(mt) / 60.0 * (muf[1:] + muf[:-1]) / 2.0)])
    return {
        "et": et, "es": es, "ed": es - 40.0,
        "mt": mt, "muf": muf, "cum_uf": cum,
        "mbf": np.full_like(mt, 300.0),
        "mco": np.full_like(mt, 14.0),
        "mdt": np.full_like(mt, 36.5),
        "dry": 65.0, "pre": 68.0, "goal": 3.0,
        "age": 60.0, "sex": "M", "dm": 0.0, "vintage": 3.0,
        "temp_presc": 36.5, "measured_uf": 2.0,
    }


def _dense_session() -> dict:
    et = np.arange(0.0, 121.0, 15.0)
    es = 140.0 - 0.20 * et
    mt = np.arange(0.0, 121.0, 1.0)
    muf = np.where(mt < 60.0, 1.0, 0.5)
    cum = np.concatenate(
        [[0.0], np.cumsum(np.diff(mt) / 60.0 * (muf[1:] + muf[:-1]) / 2.0)])
    d = _session()
    d.update({"et": et, "es": es, "ed": es - 40.0, "mt": mt, "muf": muf,
              "cum_uf": cum, "mbf": np.full_like(mt, 300.0),
              "mco": np.full_like(mt, 14.0), "mdt": np.full_like(mt, 36.5)})
    return d


class OracleAndRegimeTest(unittest.TestCase):
    def test_observable_future_vector_and_reference(self):
        d = _session()
        o = A.oracle_future_uf(d, 60.0)
        self.assertTrue(o["observable"])
        self.assertEqual(len(o["future"]), 60)
        self.assertAlmostEqual(o["reference"], 1.0)
        self.assertAlmostEqual(float(o["future"][0]), 0.5)  # minute 61

    def test_unobservable_when_machine_log_ends_early(self):
        d = _session()
        d["mt"] = d["mt"][d["mt"] <= 100.0]
        d["muf"] = d["muf"][:len(d["mt"])]
        o = A.oracle_future_uf(d, 60.0)
        self.assertFalse(o["observable"])
        self.assertIn("ends before", o["reason"])

    def test_unobservable_when_log_starts_late(self):
        d = _session()
        d["mt"] = d["mt"] + 10.0
        o = A.oracle_future_uf(d, 60.0)
        self.assertFalse(o["observable"])

    def test_regime_precedence(self):
        ref = 1.0
        self.assertEqual(A.classify_regime(np.zeros(60), ref), "pause")
        self.assertEqual(A.classify_regime(np.full(60, 0.4), ref), "aggressive")
        self.assertEqual(A.classify_regime(np.full(60, 0.7), ref), "moderate")
        self.assertEqual(A.classify_regime(np.full(60, 1.0), ref), "hold")
        mixed = np.full(60, 0.5)
        mixed[:15] = 1.0
        self.assertEqual(A.classify_regime(mixed, ref), "mixed")
        self.assertEqual(A.classify_regime(np.zeros(60), 0.0), "zero_reference")
        self.assertEqual(A.classify_regime(None, ref), "unobservable")
        self.assertEqual(A.classify_regime(np.full(60, np.nan), ref),
                         "unobservable")

    def test_actual_uf_forecast_starts_from_d_now(self):
        d = _session()
        fut = np.zeros(60)
        r = A.actual_uf_forecast(d, 60.0, {"k_refill": 0.3, "beta_bp": 19.6}, fut)
        self.assertTrue(r["feasible"])
        self.assertEqual(len(r["sbp_path"]), 61)
        self.assertEqual(r["D_path"][0], r["D_now"])
        self.assertLess(r["D_path"][1], r["D_path"][0])
        self.assertGreater(r["sbp_path"][1], r["sbp_path"][0])  # refill raises SBP

    def test_linear_baseline_is_bounded(self):
        et = np.array([0.0, 30.0, 60.0])
        es = np.array([140.0, 130.0, 120.0])
        nadir = A.linear_nadir(et, es, 60.0, [10, 20])
        self.assertAlmostEqual(nadir, 120.0 - (10.0 / 30.0) * 20.0, places=9)
        self.assertTrue(np.isnan(A.linear_nadir(
            np.array([0.0]), np.array([140.0]), 0.0, [10])))

    def test_first_sustained_cut(self):
        d = _session(uf_seq=np.where(np.arange(181.0) < 30.0, 1.0, 0.5))
        self.assertEqual(A.first_sustained_cut(d), 30.0)
        d2 = _session(uf_seq=np.full(181, 1.0))
        self.assertIsNone(A.first_sustained_cut(d2))

    def test_precut_fit_uses_only_cuffs_before_cut(self):
        d = _dense_session()
        cut = A.first_sustained_cut(d)
        self.assertEqual(cut, 60.0)
        sliced = A.slice_session_before(d, cut)
        self.assertLess(float(sliced["et"].max()), 60.0)
        self.assertLess(float(sliced["mt"].max()), 60.0)
        fits = A.fit_sessions_batch_precut({"s": d}, {"s": cut})
        self.assertIn("s", fits)
        self.assertTrue(fits["s"]["feasible"])
        self.assertEqual(fits["s"]["n_cuffs"], 4)

    def test_gbdt_uf_features(self):
        f = A.gbdt_uf_features(np.full(60, 1.0), 1.0, 30)
        self.assertEqual(f["horizon_min"], 30.0)
        self.assertAlmostEqual(f["uf_cum_h"], 0.5)
        self.assertAlmostEqual(f["uf_mean_h"], 1.0)
        self.assertAlmostEqual(f["uf_zero_share_h"], 0.0)
        self.assertAlmostEqual(f["uf_reduction_ref_h"], 0.0)
        self.assertAlmostEqual(f["uf_slope_60"], 0.0)

    def test_anchor_row(self):
        d = _session()
        row = A.anchor_row(d, "p1_2020-01-01", "p1", 60.0)
        self.assertTrue(row["coverage_complete"])
        self.assertTrue(row["oracle_observable"])
        self.assertEqual(list(row["offsets"]), [30, 60])
        self.assertAlmostEqual(row["observed_nadir"], 140.0 - 0.2 * 120.0)
        # At t=60 the reference is 1.0 and the first 15 future minutes are
        # 0.5 -> aggressive taper.
        self.assertEqual(row["regime"], "aggressive")


class MachineOnlyLoadTest(unittest.TestCase):
    def test_no_bp_filter_and_invalid_uf_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "vip.csv"
            pd.DataFrame({
                "pid": [1, 1, 1, 2],
                "datatime": ["2020-01-01 10:00", "2020-01-01 10:01",
                             "2020-01-01 10:02", "2020-01-01 10:03"],
                "time": [0, 1, 2, 0],
                "uf": [1.0, -0.5, 10.0, 0.0],
                "blood_flow": [300, 300, 300, 300],
                "conductivity": [14, 14, 14, 14],
                "dia_temp_value": [36.5, 36.5, 36.5, 36.5],
                "sbp": [80, 300, 120, 120],       # invalid SBP must not matter
            }).to_csv(path, index=False)
            with mock.patch.object(data, "RAW", Path(td)):
                vip = data.load_machine_only(verbose=False)
            self.assertEqual(len(vip), 2)
            self.assertEqual(set(vip.pid), {"1", "2"})
            self.assertEqual(float(vip.uf.min()), 0.0)


if __name__ == "__main__":
    unittest.main()
