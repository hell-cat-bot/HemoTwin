"""Chair board data, claim boundary, and AppTest integration."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "hemotwin.py"
BOARD = ROOT / "evidence" / "chair_risk.json"
DEMO = ROOT / "evidence" / "demo_twin.json"


def _blob(at) -> str:
    return " ".join(
        [str(m.value) for m in at.markdown]
        + [str(c.value) for c in at.caption])


class ChairBoardDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = json.loads(BOARD.read_text(encoding="utf-8"))
        cls.demo = json.loads(DEMO.read_text(encoding="utf-8"))

    def test_sidecar_is_patient_disjoint_fold_two(self):
        chairs = self.board["chairs"]
        self.assertEqual(len(chairs), 5)
        ids = [c["session_id"] for c in chairs]
        pids = [s.split("_")[0] for s in ids]
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(len(set(pids)), 5)
        self.assertTrue(all(c["fold"] == 2 for c in chairs))
        self.assertEqual(self.board["demo"]["summary"]["high"], 1)
        self.assertEqual(self.board["demo"]["summary"]["moderate"], 0)
        self.assertEqual(self.board["demo"]["summary"]["low"], 4)
        self.assertEqual(self.board["demo"]["summary"]["high_crashes"], 1)
        self.assertEqual(self.board["demo"]["summary"]["moderate_crashes"], 0)
        self.assertEqual(self.board["demo"]["summary"]["low_crashes"], 0)

    def test_case_ids_and_labels_match_case_lab(self):
        by_name = {c["name"]: c for c in self.demo["cases"]}
        for chair in self.board["chairs"]:
            case = by_name[chair["case_name"]]
            self.assertEqual(chair["case_id"], case["id"])
            self.assertEqual(chair["case_select"],
                             case["name"].replace("_", " ").title())

    def test_expected_risk_scores_and_bands(self):
        expected = {
            "stable_hold": (0.0467, "low"),
            "taper": (0.0511, "low"),
            "pause": (0.1551, "low"),
            "true_crash": (0.7018, "high"),
            "g1_taper_showcase": (0.0964, "low"),
        }
        for chair in self.board["chairs"]:
            risk, band = expected[chair["case_name"]]
            self.assertAlmostEqual(chair["risk_probability"], risk, delta=0.002)
            self.assertEqual(chair["risk_band"], band)

    def test_no_presession_shape_prediction_is_shipped(self):
        model = self.board["risk_model"]
        self.assertEqual(model["variant"], "A2_pre_session_safe")
        self.assertFalse(model["anchor_used"])
        self.assertFalse(model["uf_rate_used"])
        self.assertEqual(set(model["excluded_features"]),
                         {"sbp_anchor", "uf_ml_kg_h"})
        policy = self.board["shape_policy"]
        self.assertEqual(policy["status"], "not_shipped_pre_session")
        self.assertLess(policy["pre_session_ablation"]["auroc"], 0.72)
        self.assertAlmostEqual(policy["anchor_model"]["fold2_auroc"],
                               0.7716, delta=0.001)
        for chair in self.board["chairs"]:
            self.assertNotIn("shape_probability", chair)
            self.assertNotIn("shape_band", chair)
            self.assertIn("recorded_shape", chair["observed"])
        pause = next(c for c in self.board["chairs"]
                     if c["case_name"] == "pause")
        crash = next(c for c in self.board["chairs"]
                     if c["case_name"] == "true_crash")
        self.assertFalse(pause["observed"]["event"])
        self.assertTrue(crash["observed"]["event"])
        self.assertEqual(crash["observed"]["recorded_shape"], "final_hour")
        self.assertEqual(crash["observed"]["lowest_sbp"], 78.0)

    def test_claim_boundary_is_explicit(self):
        risk = self.board["risk_model"]["claim"].lower()
        shape = self.board["shape_policy"]
        for phrase in ("display-only", "not a treatment recommendation",
                       "not an alarm", "not a chair-allocation order"):
            self.assertIn(phrase, risk)
        self.assertEqual(shape["status"], "not_shipped_pre_session")
        self.assertIn("recorded onset only", shape["display"].lower())
        self.assertIn("not a pre-session prediction", shape["display"].lower())
        audit = self.board["feature_audit"]
        self.assertEqual(audit["sbp_anchor_below_90"], 466)
        self.assertTrue(audit["uf_rate_is_anchor_time"])


class ChairBoardAppTest(unittest.TestCase):
    def test_board_select_reveal_and_case_link(self):
        at = AppTest.from_file(str(APP), default_timeout=120).run()
        at.switch_page("views/chair_board_page.py").run()
        self.assertEqual(list(at.exception), [])
        blob = _blob(at)
        self.assertIn("Five chairs, before the first cuff", blob)
        self.assertIn("1 high · 4 low", blob)
        self.assertIn("fold 2 · patient-disjoint", blob)
        labels = [b.label for b in at.button]
        for i in range(1, 6):
            self.assertIn(f"Inspect chair {i}", labels)
        next(b for b in at.button if b.label == "Inspect chair 4").click().run()
        self.assertEqual(list(at.exception), [])
        self.assertEqual(at.session_state["chair_selected"], 4)
        self.assertIn("Recorded crash shape", _blob(at))
        at.toggle[0].set_value(True).run()
        self.assertEqual(list(at.exception), [])
        blob = _blob(at)
        self.assertIn("Recorded crash at 112 min", blob)
        self.assertIn("FINAL-HOUR", blob)
        self.assertIn("1/1 high, 0/4 low", blob)
        next(b for b in at.button if b.label == "Session details").click().run()
        self.assertEqual(list(at.exception), [])
        self.assertEqual(at.session_state["chair_details"], 4)
        blob = _blob(at)
        self.assertIn("forecast and fluid arithmetic", blob)
        self.assertIn("Fluid arithmetic · what each policy changes", blob)
        self.assertIn("retired twin's mechanism sketch", blob)
        self.assertIn("Patient 4", blob)
        columns = list(at.dataframe[0].value.columns)
        self.assertIn("Next-session UF (mL/kg/h)", columns)
        self.assertNotIn("Δ SBP vs hold (mmHg)", columns)

    def test_case_select_stays_in_sync_after_page_switch(self):
        at = AppTest.from_file(str(APP), default_timeout=120).run()
        at.switch_page("views/case_lab_page.py").run()
        next(b for b in at.button if b.label.startswith("True crash")).click().run()
        at.switch_page("views/evidence_page.py").run()
        at.switch_page("views/case_lab_page.py").run()
        self.assertEqual(list(at.exception), [])
        self.assertEqual(at.session_state["case_select"], "True Crash")
        self.assertTrue(at.session_state["case_id"].startswith("4."))


if __name__ == "__main__":
    unittest.main()
