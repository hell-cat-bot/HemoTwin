"""Task 02 workflow tests: real manual/CSV inference and safety states."""
from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from src import manual_console as C
from src.paths import MODELS

TASK02 = MODELS / "event_model"
FULL_MODEL = TASK02 / "models" / "fold_0" / "universal"
SMOKE_MODEL = TASK02 / "smoke" / "models" / "fold_0" / "universal"
MODEL = FULL_MODEL if FULL_MODEL.with_name("universal_meta.json").exists() else SMOKE_MODEL
THRESH = (TASK02 / "thresholds.json" if (TASK02 / "thresholds.json").exists()
          else TASK02 / "smoke" / "thresholds.json")
READY = MODEL.with_name("universal_meta.json").exists()

START = {"session_id": "manual_test", "pre_weight": 68.0, "dry_weight": 65.0,
         "age": 60, "sex": "M", "dm": 1, "vintage_years": 3, "month": 3}
CUFFS = [
    {"t": 0, "sbp": 140, "dbp": 80, "uf": 1.3},
    {"t": 30, "sbp": 132, "dbp": 76, "uf": 1.3},
    {"t": 60, "sbp": 124, "dbp": 72, "uf": 1.3},
    {"t": 90, "sbp": 116, "dbp": 68, "uf": 1.3},
]


@unittest.skipUnless(READY, "fold-0 universal model not built yet")
class ManualConsoleTest(unittest.TestCase):
    def _score(self, cuffs=None, as_of=None, current_time=None, start=None):
        return C.score_session(start or START, cuffs or CUFFS,
                               model_dir=MODEL, threshold_file=THRESH,
                               as_of_min=as_of, current_time_min=current_time)

    def test_real_inference_and_units(self):
        r = self._score()
        self.assertTrue(r["scorable"])
        self.assertIsInstance(r["risk"], float)
        self.assertGreaterEqual(r["risk"], 0.0)
        self.assertLessEqual(r["risk"], 1.0)
        self.assertEqual(r["n_scored"], 2)
        self.assertAlmostEqual(r["uf_ml_kg_h"], 20.0, places=6)
        self.assertTrue(r["uf_over13"])

    def test_current_hypotension_routes_to_rescue(self):
        cuffs = CUFFS + [{"t": 120, "sbp": 85, "dbp": 50, "uf": 0.0}]
        r = self._score(cuffs=cuffs)
        self.assertEqual(r["alert_state"], "rescue")
        self.assertIn("below 90", r["guideline"])

    def test_missing_current_bp_blocks_scoring(self):
        cuffs = CUFFS + [{"t": 120, "sbp": None, "dbp": None, "uf": 1.0}]
        r = self._score(cuffs=cuffs)
        self.assertFalse(r["scorable"])
        self.assertIn("missing", r["reason"])

    def test_stale_current_bp_blocks_scoring(self):
        r = self._score(current_time=200.0)
        self.assertFalse(r["scorable"])
        self.assertIn("stale", r["reason"])

    def test_future_records_do_not_change_earlier_score(self):
        a = self._score(as_of=60)
        future = CUFFS + [{"t": 120, "sbp": 70, "dbp": 40, "uf": 0.0}]
        b = self._score(cuffs=future, as_of=60)
        self.assertEqual(a["risk"], b["risk"])
        self.assertEqual(a["alert_state"], b["alert_state"])

    def test_new_cuff_changes_output_through_real_inference(self):
        a = self._score(as_of=60)
        b = self._score(as_of=90)
        self.assertNotEqual(a["n_scored"], b["n_scored"])
        self.assertTrue(np.isfinite(a["risk"]) and np.isfinite(b["risk"]))

    def test_csv_and_manual_are_equivalent(self):
        csv = ("elapsed_min,sbp,dbp,uf_Lh\n"
               "0,140,80,1.3\n30,132,76,1.3\n60,124,72,1.3\n90,116,68,1.3\n")
        cuffs = C.parse_csv(csv)
        a = C.score_session(START, CUFFS, model_dir=MODEL, threshold_file=THRESH)
        b = C.score_session(START, cuffs, model_dir=MODEL, threshold_file=THRESH)
        self.assertEqual(a["risk"], b["risk"])
        self.assertEqual(a["alert_state"], b["alert_state"])
        self.assertEqual(a["n_scored"], b["n_scored"])

    def test_invalid_uf_rejected(self):
        cuffs = CUFFS + [{"t": 120, "sbp": 110, "dbp": 70, "uf": 9.0}]
        r = self._score(cuffs=cuffs)
        self.assertFalse(r["scorable"])
        self.assertIn("invalid UF", r["reason"])


if __name__ == "__main__":
    unittest.main()
