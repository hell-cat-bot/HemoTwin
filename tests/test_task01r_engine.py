"""Task 01R state precedence, claim-boundary, and role tests."""
from __future__ import annotations

import copy
import unittest

from src.session_twin.engine import recommend, snapshot_hash
from src.session_twin.protocol import load_protocol


def _snapshot(**overrides):
    s = {
        "session_id": "manual_test",
        "t_min": 90.0,
        "sbp": 116.0,
        "dbp": 68.0,
        "sbp_drop_from_session_baseline": 24.0,
        "symptom_any": False,
        "symptoms": [],
        "clinician_concern": False,
        "position": "seated",
        "uf_rate_Lh": 1.3,
        "uf_goal_L": 3.0,
        "uf_removed_L": 1.2,
        "role": "RN",
        "risk_shadow": {
            "available": True, "score": 0.42, "threshold": 0.98,
            "as_of_min": 90.0, "model_version": "task02-fold0-universal",
        },
    }
    s.update(overrides)
    return s


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.protocol = load_protocol()

    def test_low_sbp_is_urgent_even_with_zero_risk(self):
        s = _snapshot(sbp=85.0, risk_shadow={"available": True, "score": 0.0,
                                             "threshold": 0.98, "as_of_min": 90.0})
        r = recommend(s, self.protocol)
        self.assertEqual(r["state"], "URGENT_CLINICAL_REVIEW")
        self.assertIn("sbp_below_90", r["state_reason_ids"])

    def test_clinician_concern_is_urgent_without_bp(self):
        r = recommend(_snapshot(sbp=None, clinician_concern=True), self.protocol)
        self.assertEqual(r["state"], "URGENT_CLINICAL_REVIEW")

    def test_symptoms_with_low_bp_are_urgent(self):
        r = recommend(_snapshot(sbp=96.0, symptom_any=True,
                                symptoms=["dizziness"]), self.protocol)
        self.assertEqual(r["state"], "URGENT_CLINICAL_REVIEW")
        self.assertIn("symptomatic_low_bp", r["state_reason_ids"])

    def test_high_risk_alone_never_triggers_review(self):
        s = _snapshot(sbp=140.0, sbp_drop_from_session_baseline=0.0,
                      risk_shadow={"available": True, "score": 0.9999,
                                   "threshold": 0.98, "as_of_min": 90.0})
        r = recommend(s, self.protocol)
        self.assertEqual(r["state"], "NO_ALERT")
        self.assertEqual(r["risk_shadow"]["authority"], "display_only")

    def test_configured_relative_drop_triggers_review(self):
        r = recommend(_snapshot(sbp=108.0, sbp_drop_from_session_baseline=24.0),
                      self.protocol)
        self.assertEqual(r["state"], "REVIEW_NOW")
        self.assertIn("large_relative_drop", r["state_reason_ids"])

    def test_missing_current_bp_abstains(self):
        r = recommend(_snapshot(sbp=None), self.protocol)
        self.assertEqual(r["state"], "INSUFFICIENT_INFORMATION")
        self.assertIn("current_sbp", r["data_quality"])

    def test_missing_trend_abstains_when_review_rule_needs_it(self):
        r = recommend(_snapshot(sbp=120.0, sbp_drop_from_session_baseline=None),
                      self.protocol)
        self.assertEqual(r["state"], "INSUFFICIENT_INFORMATION")

    def test_unknown_urgent_input_abstains(self):
        r = recommend(_snapshot(sbp=120.0, sbp_drop_from_session_baseline=0.0,
                                symptom_any=None, clinician_concern=False),
                      self.protocol)
        self.assertEqual(r["state"], "INSUFFICIENT_INFORMATION")
        self.assertIn("symptom_any", r["data_quality"])

    def test_role_suppression_is_visible_not_hidden(self):
        r = recommend(_snapshot(sbp=85.0, role="TECH"), self.protocol)
        steps = {s["id"]: s for s in r["pathway"]}
        self.assertTrue(steps["assess_patient"]["available"])
        self.assertFalse(steps["red_flags"]["available"])
        self.assertEqual(steps["red_flags"]["reason_code"], "role_not_permitted")

    def test_missing_uf_suppresses_only_uf_step(self):
        r = recommend(_snapshot(sbp=85.0, uf_rate_Lh=None), self.protocol)
        steps = {s["id"]: s for s in r["pathway"]}
        self.assertEqual(r["state"], "URGENT_CLINICAL_REVIEW")
        self.assertFalse(steps["uf_review"]["available"])
        self.assertEqual(steps["uf_review"]["reason_code"],
                         "missing_input:uf_rate_Lh")

    def test_stale_shadow_is_marked_but_changes_nothing(self):
        s = _snapshot(sbp=108.0,
                      risk_shadow={"available": True, "score": 0.99,
                                   "threshold": 0.98, "as_of_min": 0.0})
        r = recommend(s, self.protocol)
        self.assertEqual(r["risk_shadow"]["status"], "stale")
        self.assertEqual(r["state"], "REVIEW_NOW")

    def test_snapshot_hash_is_deterministic_and_sensitive(self):
        a = _snapshot()
        b = copy.deepcopy(a)
        self.assertEqual(snapshot_hash(a), snapshot_hash(b))
        b["sbp"] = 117.0
        self.assertNotEqual(snapshot_hash(a), snapshot_hash(b))


if __name__ == "__main__":
    unittest.main()
