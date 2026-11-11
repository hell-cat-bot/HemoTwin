"""Tests for FHIR export, hash-chained audit, handoff, pod triage, ledger."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.session_twin.audit_chain import (
    append_chained_event, verify_audit_chain,
)
from src.session_twin.evidence_ledger import (
    build_scoreboard, load_report, render_markdown,
)
from src.session_twin.fhir_export import (
    build_fhir_bundle, validate_fhir_r4_bundle_schema,
)
from src.session_twin.handoff_summary import build_handoff_card
from src.session_twin.pod_triage import (
    budget_projection, build_pod_board, triage_status,
)


class FhirTest(unittest.TestCase):
    def test_valid_bundle(self):
        bundle = build_fhir_bundle(
            patient_id="p1", session_id="s1", age=64, sex="F",
            observations={"sbp": 112, "dbp": 58, "weight": 68.4, "uf": 0.8},
            latent_state={"plasma_deficit_l": 0.7,
                          "refill_rate_l_h": 0.3,
                          "baro_exhaustion_pct": 22.0},
            risk={"score": 0.2, "state": "NO_ALERT", "rationale": "shadow"},
            detected_issue="Stale cuff in demo session")
        ok, errors = validate_fhir_r4_bundle_schema(bundle)
        self.assertTrue(ok, errors)
        text = json.dumps(bundle)
        for code in ("8480-6", "8462-4", "29463-7", "33050-6", "302497006"):
            self.assertIn(code, text)
        self.assertIn("https://hemotwin.local/codes", text)

    def test_missing_subject_fails(self):
        bundle = build_fhir_bundle(patient_id="p1", session_id="s1",
                                   observations={"sbp": 112})
        for entry in bundle["entry"]:
            if entry["resource"]["resourceType"] == "Observation":
                entry["resource"].pop("subject", None)
        ok, errors = validate_fhir_r4_bundle_schema(bundle)
        self.assertFalse(ok)
        self.assertTrue(any("subject" in e for e in errors))

    def test_missing_value_fails(self):
        bundle = build_fhir_bundle(patient_id="p1", session_id="s1",
                                   observations={"sbp": 112})
        for entry in bundle["entry"]:
            if entry["resource"]["resourceType"] == "Observation":
                entry["resource"].pop("valueQuantity", None)
        ok, errors = validate_fhir_r4_bundle_schema(bundle)
        self.assertFalse(ok)


class AuditChainTest(unittest.TestCase):
    def test_chain_verifies_and_tamper_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.jsonl"
            for i in range(3):
                append_chained_event(path, {"event": "view", "i": i},
                                     timestamp=f"2026-11-09T0{i}:00:00+00:00")
            result = verify_audit_chain(path)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["n_events"], 3)
            lines = path.read_text(encoding="utf-8").splitlines()
            rec = json.loads(lines[1])
            rec["i"] = 99
            lines[1] = json.dumps(rec, sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = verify_audit_chain(path)
            self.assertFalse(result["ok"])

    def test_empty_chain(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.jsonl"
            result = verify_audit_chain(path)
            self.assertTrue(result["ok"])
            self.assertEqual(result["n_events"], 0)


class HandoffTest(unittest.TestCase):
    def test_bilingual_card(self):
        card = build_handoff_card(
            session_id="s1", sbp_now=112, projected_nadir=104,
            band=(94, 116), fluid_left_l=0.4, next_intensity=13.5,
            status="REVIEW_NOW")
        for key in ("english", "hindi", "disclaimer_en", "disclaimer_hi"):
            self.assertTrue(card[key])
        self.assertIn("REVIEW_NOW", card["english"])
        self.assertIn("प्रिस्क्रिप्शन", card["disclaimer_hi"])


class PodTriageTest(unittest.TestCase):
    def test_status_rules(self):
        self.assertEqual(triage_status(85, 80, 10), "URGENT_CLINICAL_REVIEW")
        self.assertEqual(triage_status(110, 88, 10), "REVIEW_NOW")
        self.assertEqual(triage_status(110, 95, 10), "NO_ALERT")
        self.assertEqual(triage_status(110, 95, 40),
                         "INSUFFICIENT_INFORMATION")
        # high shadow score with stable vitals stays NO_ALERT
        self.assertEqual(triage_status(110, 95, 10, risk_shadow=0.999),
                         "NO_ALERT")

    def test_board_and_budget(self):
        rows = [
            {"session_id": "a", "sbp_now": 110, "projected_nadir": 95,
             "cuff_age_min": 10},
            {"session_id": "b", "sbp_now": 84, "projected_nadir": 80,
             "cuff_age_min": 10},
            {"session_id": "c", "sbp_now": 110, "projected_nadir": 88,
             "cuff_age_min": 10},
        ]
        board = build_pod_board(rows, n_chairs=12, fa_per_session=0.26)
        self.assertEqual(board["n_chairs"], 12)
        self.assertEqual(board["occupied"], 3)
        self.assertEqual(board["board"][0]["session_id"], "b")
        self.assertEqual(board["board"][0]["status"],
                         "URGENT_CLINICAL_REVIEW")
        self.assertAlmostEqual(
            budget_projection(0.26)["expected_false_alerts_per_shift"], 3.12)
        self.assertAlmostEqual(
            budget_projection(0.62)["expected_false_alerts_per_shift"], 7.44)


class EvidenceLedgerTest(unittest.TestCase):
    def test_scoreboard_from_real_report(self):
        report = load_report()
        self.assertIsNotNone(report)
        rows = build_scoreboard(report)
        self.assertEqual(len(rows), 6)
        self.assertEqual({r["gate"] for r in rows}, {"G1", "G2", "G3",
                                                     "G4", "G5", "G6"})
        md = render_markdown(rows, report)
        self.assertIn("G1", md)
        self.assertIn("REJECTED_ON_DEV", md)

    def test_synthetic_report(self):
        report = {"gates": {"G1": {"pass": True,
                                   "v4": {"mae": 11.0},
                                   "v3": {"mae": 15.0},
                                   "mae_ratio_v4_over_v3": 0.73},
                            "G2": {"pass": True,
                                   "fold2": {"v4": {"mae": 10.9},
                                             "base": {"mae": 10.9}},
                                   "pass_as_plan_written": False}},
                  "mechanism_status": "REJECTED_ON_DEV", "gamma_orth": 0.0}
        rows = build_scoreboard(report)
        self.assertEqual(len(rows), 6)
        self.assertFalse(rows[2]["pass"])
        self.assertTrue(rows[1]["metric"].endswith("False"))


if __name__ == "__main__":
    unittest.main()
