"""Task 00 tests: twin units, state propagation, cooling, and fold priors."""
from __future__ import annotations

import copy
import unittest

import numpy as np

from src import twin as T


def _session() -> dict:
    et = np.array([0, 30, 60, 90], dtype=float)
    es = np.array([140, 132, 124, 116], dtype=float)
    mt = np.array([0, 30, 60, 90], dtype=float)
    muf = np.array([1.0, 1.0, 0.8, 0.8], dtype=float)
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


PARAMS = {"k_refill": 0.30, "beta_bp": 19.6, "beta_T": T.POP_BETA_T}


class TwinUnitTest(unittest.TestCase):
    def test_refill_derivative_is_per_minute(self):
        dD = T.deficit_derivative(2.0, 0.0, 0.30)
        self.assertAlmostEqual(dD, -0.01, places=12)

    def test_pause_decays_existing_deficit(self):
        path = T.deficit_path(np.zeros(60), 0.30, phi=0.0, d0=2.0)
        self.assertEqual(path[0], 2.0)
        self.assertLess(path[1], path[0])
        self.assertAlmostEqual(path[1], 1.99, places=12)
        self.assertTrue(np.all(np.diff(path) < 0))

    def test_locf_not_linear_interpolation(self):
        d = _session()
        d["mt"] = np.array([0.0, 30.0])
        d["muf"] = np.array([2.0, 0.0])
        grid, uf, coverage = T.causal_uf_grid(d, 15.0)
        self.assertTrue(coverage)
        self.assertEqual(float(uf[15]), 2.0)  # LOCF, not 1.0
        grid, uf, coverage = T.causal_uf_grid(d, 30.0)
        self.assertEqual(float(uf[30]), 0.0)

    def test_uf_log_must_cover_session_start(self):
        d = _session()
        d["mt"] = np.array([10.0, 30.0, 60.0, 90.0])
        _, _, coverage = T.causal_uf_grid(d, 90.0)
        self.assertFalse(coverage)


class PolicySimulationTest(unittest.TestCase):
    def setUp(self):
        self.d = _session()

    def test_pause_does_not_leave_deficit_flat(self):
        r = T.simulate_policy(self.d, 90.0, PARAMS,
                              {"uf_mult": 0.0, "pause_min": 60, "bolus_L": 0.0})
        self.assertTrue(r["feasible"])
        self.assertEqual(len(r["D_path"]), 61)
        self.assertLess(r["D_path"][1], r["D_path"][0])
        self.assertLess(r["D_path"][-1], r["D_path"][0])
        self.assertTrue(np.allclose(r["uf_path"], 0.0))

    def test_pause_never_auto_resumes_at_goal_rate(self):
        r = T.simulate_policy(self.d, 90.0, PARAMS,
                              {"uf_mult": 0.0, "pause_min": 10, "bolus_L": 0.0})
        self.assertTrue(np.allclose(r["uf_path"][10:], 0.0))
        self.assertEqual(r["uf_rate_Lh"], 0.0)

    def test_explicit_resume_rate_is_honoured(self):
        r = T.simulate_policy(self.d, 90.0, PARAMS,
                              {"uf_mult": 0.0, "pause_min": 10,
                               "resume_rate": 1.0, "bolus_L": 0.0})
        self.assertTrue(np.allclose(r["uf_path"][10:], 1.0))

    def test_cooling_raises_not_lowers_sbp(self):
        hold = T.simulate_policy(self.d, 90.0, PARAMS, T.POLICIES["hold"])
        cool = T.simulate_policy(self.d, 90.0, PARAMS, T.POLICIES["cool10"])
        self.assertGreaterEqual(cool["nadir"], hold["nadir"])
        self.assertGreater(cool["nadir"], hold["nadir"])

    def test_future_records_do_not_change_the_forecast(self):
        before = T.simulate_policy(self.d, 90.0, PARAMS, T.POLICIES["hold"])
        d2 = copy.deepcopy(self.d)
        d2["et"] = np.concatenate([d2["et"], [110.0, 140.0]])
        d2["es"] = np.concatenate([d2["es"], [80.0, 70.0]])
        d2["ed"] = d2["es"] - 40.0
        d2["mt"] = np.concatenate([d2["mt"], [110.0, 140.0]])
        d2["muf"] = np.concatenate([d2["muf"], [3.0, 0.0]])
        d2["cum_uf"] = np.concatenate([d2["cum_uf"], [5.0, 5.0]])
        after = T.simulate_policy(d2, 90.0, PARAMS, T.POLICIES["hold"])
        self.assertEqual(before["nadir"], after["nadir"])
        self.assertEqual(before["path"], after["path"])

    def test_forecast_path_is_the_shared_hold_simulation(self):
        r = T.simulate_policy(self.d, 90.0, PARAMS, T.POLICIES["hold"])
        path = T.forecast_path(self.d, 90.0, PARAMS, minutes=60)
        self.assertEqual(path, r["path"])


class FoldPriorTest(unittest.TestCase):
    def test_fit_population_for_fold_excludes_outer_patients(self):
        store = {}
        for pid in ("p1", "p2", "p3"):
            store[f"{pid}_2020-01-01"] = {"et": np.arange(6.0)}
        fits = {
            "p1_2020-01-01": {"k": 0.30, "beta": 10.0},
            "p2_2020-01-01": {"k": 0.50, "beta": 20.0},
            "p3_2020-01-01": {"k": 1.40, "beta": 80.0},
        }
        pop = T.fit_population_for_fold(store, {"p1", "p2"}, fits=fits)
        self.assertEqual(pop["n"], 2)
        self.assertAlmostEqual(pop["k_refill"], 0.40)
        self.assertAlmostEqual(pop["beta_bp"], 15.0)

    def test_twin_state_table_uses_supplied_population_prior(self):
        store = {
            "p1_2020-01-01": {"et": np.arange(6.0)},
            "p1_2020-01-02": {"et": np.arange(6.0)},
        }
        fits = {
            "p1_2020-01-01": {"k": 1.0, "beta": 10.0},
            "p1_2020-01-02": {"k": 1.0, "beta": 10.0},
        }
        pop = {"k_refill": 0.40, "beta_bp": 12.0}
        tab = T.twin_state_table(store, pop=pop, fits=fits).set_index("session_id")
        self.assertAlmostEqual(tab.loc["p1_2020-01-01", "k_pat"], 0.40)
        w = 1.0 / 6.0
        self.assertAlmostEqual(tab.loc["p1_2020-01-02", "k_pat"],
                               w * 1.0 + (1 - w) * 0.40)


if __name__ == "__main__":
    unittest.main()
