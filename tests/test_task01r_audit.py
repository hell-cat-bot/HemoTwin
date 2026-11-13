"""Task 01R append-only evidence-log tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.session_twin.audit import append_event, read_events
from src.session_twin.engine import recommend
from src.session_twin.protocol import load_protocol


def _recommendation():
    s = {
        "session_id": "s1", "t_min": 90.0, "sbp": 116.0, "dbp": 68.0,
        "sbp_drop_from_session_baseline": 24.0, "symptom_any": False,
        "symptoms": [], "clinician_concern": False, "position": "seated",
        "uf_rate_Lh": 1.3, "uf_goal_L": 3.0, "uf_removed_L": 1.2,
        "role": "RN", "risk_shadow": {"available": False},
    }
    return recommend(s, load_protocol())


class AuditTest(unittest.TestCase):
    def test_events_append_without_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.jsonl"
            rec = _recommendation()
            a = append_event(path, recommendation=rec, event_type="displayed",
                             role="RN", timestamp="2026-11-07T10:00:00Z")
            b = append_event(path, recommendation=rec, event_type="confirmed",
                             role="RN", action="repeat_bp",
                             reason="rechecked", timestamp="2026-11-07T10:01:00Z")
            events = read_events(path)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event_type"], "displayed")
            self.assertEqual(events[1]["action"], "repeat_bp")
            self.assertNotEqual(a["event_hash"], b["event_hash"])

    def test_event_binds_snapshot_and_protocol_versions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.jsonl"
            rec = _recommendation()
            event = append_event(path, recommendation=rec, event_type="displayed",
                                 role="RN", timestamp="2026-11-07T10:00:00Z")
            self.assertEqual(event["snapshot_hash"], rec["snapshot_hash"])
            self.assertEqual(event["protocol_version"], rec["protocol_version"])
            self.assertEqual(event["claim_label"], rec["claim_label"])

    def test_invalid_event_type_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                append_event(Path(td) / "a.jsonl", recommendation=_recommendation(),
                             event_type="prescribed", role="RN")

    def test_append_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "audit.jsonl"
            append_event(path, recommendation=_recommendation(),
                         event_type="displayed", role="RN")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
