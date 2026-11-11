"""Task 01R protocol schema and pathway tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.session_twin.protocol import (ProtocolError, load_protocol,
                                      pathway_ids, validate_protocol)


class ProtocolTest(unittest.TestCase):
    def test_default_protocol_loads_and_is_research(self):
        p = load_protocol()
        self.assertEqual(p["protocol_id"], "hemotwin.idh-review")
        self.assertEqual(p["version"], "1.0.0")
        self.assertEqual(p["status"], "research")
        self.assertIn("not approved", p["label"].lower())
        self.assertIn("urgent", p["pathways"])
        self.assertIn("insufficient", p["pathways"])

    def test_pathway_preserves_declared_order(self):
        p = load_protocol()
        self.assertEqual(pathway_ids(p, "urgent")[0], "assess_patient")
        self.assertEqual(pathway_ids(p, "urgent")[-1], "recheck_document")

    def test_unknown_step_is_rejected(self):
        path = Path(__file__).resolve().parents[1] / "config" / "protocols" \
            / "idh_review_research_v1.json"
        p = json.loads(path.read_text(encoding="utf-8"))
        p["pathways"]["urgent"].append("does_not_exist")
        with self.assertRaises(ProtocolError):
            validate_protocol(p)

    def test_duplicate_step_ids_are_rejected(self):
        path = Path(__file__).resolve().parents[1] / "config" / "protocols" \
            / "idh_review_research_v1.json"
        p = json.loads(path.read_text(encoding="utf-8"))
        p["steps"].append(dict(p["steps"][0]))
        with self.assertRaises(ProtocolError):
            validate_protocol(p)

    def test_malformed_json_has_clear_error(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ProtocolError):
                load_protocol(bad)


if __name__ == "__main__":
    unittest.main()
