"""twin-v3 second-generation patient-memory features (segment twin-v3).

Pins three properties:
1. equivalence — the refactored v1 wrapper returns the frozen v1 values;
2. causality — v3 history columns for session s use only STRICTLY EARLIER
   sessions plus s's own session-start facts;
3. QC plausibility — out-of-range raw session facts become NaN, never clamped.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import (  # noqa: E402
    V3_HIST_COLUMNS,
    session_history_features,
    session_history_features_old,
    session_history_features_v3,
)


def _events():
    rows = []
    # (sid, pid, date, [(t, sbp)], pre_w, post_w, uf_L, temp)
    sessions = [
        ("1_2024-01-01", 1, "2024-01-01",
         [(0, 150), (30, 140), (60, 120), (120, 110), (240, 118)],
         70.0, 68.0, 2.5, 36.5),
        ("1_2024-01-03", 1, "2024-01-03",
         [(0, 148), (30, 100), (60, 95), (90, 102)],
         69.0, 67.0, 3.0, 35.5),
        ("1_2024-01-06", 1, "2024-01-06",
         [(0, 152), (45, 130), (100, 100)],
         71.0, 68.5, 2.0, 36.0),
        ("1_2024-01-08", 1, "2024-01-08",
         [(0, 140), (50, 120)],
         70.5, 69.0, 2.2, 36.0),
        # QC probes: out-of-range pre-weight / UF / temp
        ("2_2024-01-01", 2, "2024-01-01",
         [(0, 150), (60, 130)],
         300.0, 68.0, 50.0, 45.0),
        ("2_2024-01-03", 2, "2024-01-03",
         [(0, 150), (60, 130)],
         70.0, 68.0, 2.0, 36.0),
    ]
    for sid, pid, date, cuffs, pre, post, uf, temp in sessions:
        for t, sbp in cuffs:
            rows.append({"session_id": sid, "pid": pid, "date": date,
                         "t_min": float(t), "sbp": float(sbp),
                         "dbp": 70.0, "pre_weight": pre, "post_weight": post,
                         "uf_measured_L": uf, "dia_temp_presc": temp})
    return pd.DataFrame(rows)


def _eq(a, b) -> bool:
    """NaN-aware scalar equality."""
    a, b = float(a), float(b)
    return bool(np.isnan(a) and np.isnan(b)) or a == b


class TestV1Equivalence(unittest.TestCase):
    def test_wrapper_matches_frozen_implementation(self):
        ev = _events()
        a = session_history_features(ev).sort_values(
            "session_id").reset_index(drop=True)
        b = session_history_features_old(ev).sort_values(
            "session_id").reset_index(drop=True)
        self.assertEqual(list(a.columns), list(b.columns))
        for c in b.columns:
            np.testing.assert_allclose(
                pd.to_numeric(a[c], errors="coerce").to_numpy(float),
                pd.to_numeric(b[c], errors="coerce").to_numpy(float),
                equal_nan=True, err_msg=f"column {c} diverges")


class TestV3Causality(unittest.TestCase):
    def setUp(self):
        self.v3 = session_history_features_v3(_events()).set_index(
            "session_id")

    def test_columns_exact(self):
        self.assertEqual(list(self.v3.columns), V3_HIST_COLUMNS)

    def test_first_session_history_is_nan(self):
        r = self.v3.loc["1_2024-01-01"]
        self.assertTrue(np.isnan(r["hist_mean_nadir10"]))
        self.assertTrue(np.isnan(r["hist_prev_uf"]))
        self.assertTrue(np.isnan(r["hist_typical_drop10"]))
        self.assertEqual(r["hist_n_sessions"], 0)
        # own session-start facts ARE present (causal, known pre-session)
        self.assertTrue(np.isnan(r["idwg_kg"]))  # no prior post weight
        self.assertTrue(np.isnan(r["idi_days"]))
        self.assertAlmostEqual(r["dia_temp_c"], 36.5)

    def test_prior_session_math(self):
        r = self.v3.loc["1_2024-01-08"]
        self.assertAlmostEqual(r["idi_days"], 2.0)
        self.assertAlmostEqual(r["idwg_kg"], 70.5 - 68.5)   # prior post 68.5
        self.assertAlmostEqual(r["hist_idwg_mean10"], (1.0 + 4.0) / 2.0)
        self.assertAlmostEqual(r["hist_prev_uf"], 2.0)
        self.assertAlmostEqual(r["hist_uf_mean3"], (3.0 + 2.0 + 2.5) / 3.0)
        self.assertAlmostEqual(r["hist_typical_drop10"],
                               (40.0 + 53.0 + 52.0) / 3.0)
        self.assertAlmostEqual(r["hist_n_sessions"], 3)
        self.assertAlmostEqual(r["dia_temp_c"], 36.0)
        self.assertAlmostEqual(r["hist_dia_temp_mean10"],
                               (36.5 + 35.5 + 36.0) / 3.0)
        self.assertAlmostEqual(r["hist_dur_mean10"], (240 + 90 + 100) / 3.0)

    def test_sensitivity_needs_min_periods(self):
        # 3 prior sessions < min_periods=4 for the UF->nadir slope
        r = self.v3.loc["1_2024-01-08"]
        self.assertTrue(np.isnan(r["hist_uf_nadir_sens10"]))

    def test_own_outcome_does_not_leak_into_history_columns(self):
        ev = _events()
        mask = (ev.session_id == "1_2024-01-08") & (ev.t_min == 50)
        ev.loc[mask, "sbp"] = 85.0  # crash this session
        v3 = session_history_features_v3(ev).set_index("session_id")
        for c in ("hist_mean_nadir10", "hist_prev_nadir", "hist_prev_uf",
                  "hist_typical_drop10", "hist_nadir_std10",
                  "hist_uf_nadir_sens10", "hist_idwg_mean10"):
            self.assertTrue(_eq(v3.loc["1_2024-01-08", c],
                                self.v3.loc["1_2024-01-08", c]), c)

    def test_qc_plausibility_guards(self):
        # patient 2, session 1: pre 300 kg / uf 50 L / temp 45 C -> NaN
        r = self.v3.loc["2_2024-01-01"]
        self.assertTrue(np.isnan(r["idwg_kg"]))       # pre_w out of range
        self.assertTrue(np.isnan(r["dia_temp_c"]))
        r2 = self.v3.loc["2_2024-01-03"]
        self.assertTrue(np.isnan(r2["hist_prev_uf"]))  # prior uf out of range
        self.assertTrue(np.isnan(r2["hist_dia_temp_mean10"]))

    def test_patient_isolation(self):
        r = self.v3.loc["2_2024-01-03"]
        # patient 2's history must never see patient 1's sessions
        self.assertEqual(r["hist_n_sessions"], 1)
        self.assertAlmostEqual(r["hist_mean_nadir10"], 130.0)


if __name__ == "__main__":
    unittest.main()
