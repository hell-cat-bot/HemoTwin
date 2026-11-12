"""V2 console smoke tests: shell, case lab, live session, replay, evidence."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "hemotwin.py"
MANUAL = ROOT / "app" / "manual_app.py"
REPLAY = ROOT / "app" / "views" / "replay_page.py"
REPLAY_ASSET = ROOT / "assets" / "replay" / "replay.html"
EVIDENCE = ROOT / "app" / "views" / "evidence_page.py"


def _markdown_blob(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


class HomePageTest(unittest.TestCase):
    def test_home_lands_on_the_3d_bay_without_exception(self):
        at = AppTest.from_file(str(APP), default_timeout=120).run()
        self.assertEqual(list(at.exception), [])
        self.assertIn("Five views, one twin", _markdown_blob(at))
        sim = ROOT / "app" / "static" / "sim" / "index.html"
        self.assertTrue(sim.exists())
        bundle = " ".join(
            p.read_text(encoding="utf-8")
            for p in (sim.parent / "assets").glob("*.js"))
        self.assertIn("./models/dialysis_bay.glb", bundle)
        home = (ROOT / "app" / "views" / "home_page.py").read_text(
            encoding="utf-8")
        self.assertIn("/app/static/sim/embed.html", home)
        embed = sim.parent / "embed.html"
        self.assertIn("index.html?embed=1",
                      embed.read_text(encoding="utf-8"))
        nav = (ROOT / "app" / "hemotwin.py").read_text(encoding="utf-8")
        self.assertLess(nav.index("views/home_page.py"),
                        nav.index("views/case_lab_page.py"))


class ShellAndCaseLabTest(unittest.TestCase):
    def test_case_lab_loads_without_exception(self):
        at = AppTest.from_file(str(APP), default_timeout=120).run()
        at.switch_page("views/case_lab_page.py").run()
        self.assertEqual(list(at.exception), [])
        self.assertEqual(at.session_state["case_id"].split(".")[0], "2")
        self.assertEqual(at.session_state["case_select"], "Taper")
        self.assertTrue(any("See the pressure falling" in m.value for m in at.markdown))

    def test_case_lab_inspector_and_policy_section(self):
        at = AppTest.from_file(str(APP), default_timeout=120).run()
        at.switch_page("views/case_lab_page.py").run()
        self.assertEqual(list(at.exception), [])
        blob = " ".join(
            [str(m.value) for m in at.markdown]
            + [str(c.value) for c in at.caption])
        self.assertNotIn("Twin test", blob)
        self.assertNotIn("FAILED", blob)
        self.assertIn("What each policy changes", blob)
        self.assertIn("Click any cuff point", blob)
        labels = [m.label for m in at.metric]
        self.assertIn("SBP · mmHg", labels)
        self.assertIn("DBP · mmHg", labels)
        self.assertIn("Latent twin state", blob)

    def test_stale_cuff_blocks_and_true_crash_reviews(self):
        at = AppTest.from_file(str(APP), default_timeout=120).run()
        at.switch_page("views/case_lab_page.py").run()
        stale = next(b for b in at.button if b.label.startswith("Stale cuff"))
        stale.click().run()
        self.assertEqual(list(at.exception), [])
        self.assertIn("DEMO-STALE-CUFF", at.session_state["case_id"])
        self.assertIn("INSUFFICIENT", _markdown_blob(at))

        crash = next(b for b in at.button if b.label.startswith("True crash"))
        crash.click().run()
        self.assertEqual(list(at.exception), [])
        self.assertIn("REVIEW NOW", _markdown_blob(at))


class LiveSessionTest(unittest.TestCase):
    def test_live_session_evaluates_example_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = str(Path(tmp) / "live_audit.jsonl")
            with mock.patch.dict(os.environ, {"HEMOTWIN_AUDIT_PATH": audit}):
                at = AppTest.from_file(str(MANUAL), default_timeout=120).run()
                load = next(b for b in at.button if "Load example" in b.label)
                load.click().run()
                self.assertEqual(list(at.exception), [])
                evaluate = next(b for b in at.button if "Evaluate" in b.label)
                evaluate.click().run()
                self.assertEqual(list(at.exception), [])
                forecast = at.session_state["forecast_result"]
                self.assertEqual(forecast["mode"], "manual_limited")
                self.assertEqual(at.session_state["recommendation"]["state"],
                                 "NO_ALERT")
                self.assertTrue(Path(audit).exists())


class EvidencePageTest(unittest.TestCase):
    def test_evidence_renders_g7_and_boundary(self):
        at = AppTest.from_file(str(EVIDENCE), default_timeout=120).run()
        self.assertEqual(list(at.exception), [])
        blob = _markdown_blob(at)
        self.assertIn("The evidence", blob)
        self.assertIn("is the product", blob)
        self.assertIn("G7", blob)
        self.assertIn("FAIL", blob)
        self.assertIn("We refuse to claim", blob)


class ReplayPageTest(unittest.TestCase):
    def test_replay_page_renders_inside_console(self):
        at = AppTest.from_file(str(REPLAY), default_timeout=120).run()
        self.assertEqual(list(at.exception), [])
        blob = _markdown_blob(at)
        self.assertIn("Session replay", blob)
        self.assertIn("Prediction, then the record", blob)

    def test_replay_asset_and_nav_are_present(self):
        self.assertTrue(REPLAY_ASSET.exists())
        html = REPLAY_ASSET.read_text(encoding="utf-8")
        self.assertIn("const DATA", html)
        self.assertIn("12776336", html)
        self.assertNotIn("__REPLAY_DATA__", html)
        nav = (ROOT / "app" / "hemotwin.py").read_text(encoding="utf-8")
        self.assertIn("views/replay_page.py", nav)
        self.assertIn("Session replay", nav)


if __name__ == "__main__":
    unittest.main()
