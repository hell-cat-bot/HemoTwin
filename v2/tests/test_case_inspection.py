"""Case Lab click-inspector data, chart traces, and selection mapping."""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ui import charts  # noqa: E402
from app.views import case_lab  # noqa: E402

DEMO = ROOT / "evidence" / "demo_twin.json"
INSPECTION = ROOT / "evidence" / "case_inspection.json"
THEME = ROOT / "app" / "ui" / "theme.py"
APP = ROOT / "app" / "views" / "case_lab.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _merged_cuffs(case: dict, inspection: dict) -> list[dict]:
    extra = inspection["cases"][case["id"]]["cuffs"]
    return [{**cuff, **entry, "index": i}
            for i, (cuff, entry) in enumerate(zip(case["cuffs"], extra))]


class InspectionDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = _load(DEMO)
        cls.inspection = _load(INSPECTION)
        cls.by_name = {c["name"]: c for c in cls.demo["cases"]}

    def test_sidecar_covers_every_real_case(self):
        real = [c for c in self.demo["cases"] if not c.get("synthetic_demo")]
        self.assertEqual(len(self.inspection["cases"]), len(real))
        for case in real:
            entry = self.inspection["cases"][case["id"]]
            self.assertEqual(entry["session_id"], case["session_id"])
            self.assertEqual(len(entry["cuffs"]), len(case["cuffs"]))

    def test_every_cuff_has_vitals_and_twin_state(self):
        for entry in self.inspection["cases"].values():
            for cuff in entry["cuffs"]:
                self.assertIsNotNone(cuff["dbp"], cuff)
                self.assertTrue(math.isfinite(float(cuff["uf_lh"])))
                self.assertTrue(math.isfinite(float(cuff["cum_uf_l"])))
                for key in ("D", "R", "C", "OH"):
                    self.assertTrue(math.isfinite(float(cuff["twin"][key])))
                if 0.0 <= float(cuff["rel"]) <= 60.0:
                    self.assertIsNotNone(cuff["projection_sbp"])
                else:
                    self.assertIsNone(cuff["projection_sbp"])

    def test_anchor_state_matches_the_frozen_demo_state(self):
        for name, keys in (("taper", ("D0", "R0", "C0", "OH0")),
                           ("true_crash", ("D0", "R0", "C0", "OH0"))):
            case = self.by_name[name]
            entry = self.inspection["cases"][case["id"]]
            anchor = min(entry["cuffs"], key=lambda c: abs(float(c["rel"])))
            self.assertAlmostEqual(anchor["twin"]["D"], case["state"]["D0"], 3)
            self.assertAlmostEqual(anchor["twin"]["R"], case["state"]["R0"], 3)
            self.assertAlmostEqual(anchor["twin"]["C"], case["state"]["C0"], 3)
            self.assertAlmostEqual(anchor["twin"]["OH"], case["state"]["OH0"], 3)

    def test_removed_volume_is_monotonic(self):
        for entry in self.inspection["cases"].values():
            values = [float(c["cum_uf_l"]) for c in entry["cuffs"]]
            self.assertEqual(values, sorted(values))


class ChartAndSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = _load(DEMO)
        cls.inspection = _load(INSPECTION)
        cls.by_name = {c["name"]: c for c in cls.demo["cases"]}

    def test_chart_no_longer_plots_the_retired_v3_marker(self):
        case = self.by_name["g1_taper_showcase"]
        fig = charts.fan_figure(case, show_illustration=False)
        names = [str(trace.name or "") for trace in fig.data]
        self.assertFalse(any("retired" in n.lower() for n in names))
        self.assertFalse(any("v3" in n.lower() for n in names))

    def test_after_cuff_hover_has_the_calibrated_value(self):
        case = self.by_name["taper"]
        cuffs = _merged_cuffs(case, self.inspection)
        fig = charts.fan_figure({**case, "cuffs": cuffs})
        after = next(t for t in fig.data
                     if t.name == "Observed · ground truth")
        self.assertEqual(len(after.customdata), 4)
        index, dbp, uf, calibrated = after.customdata[1]
        self.assertEqual(cuffs[index]["phase"], "after")
        self.assertIsNotNone(dbp)
        self.assertIsNotNone(uf)
        self.assertIsNotNone(calibrated)
        self.assertIn("calib", after.hovertemplate)

    def test_selection_uses_customdata_and_falls_back_to_x(self):
        case = self.by_name["taper"]
        cuffs = _merged_cuffs(case, self.inspection)
        anchor = case_lab._anchor_index(cuffs)
        self.assertEqual(anchor, 4)

        class Event:
            def __init__(self, points):
                self.selection = SimpleNamespace(points=points)

        self.assertEqual(
            case_lab._selection_index(Event([{"customdata": [6, "63", "0.34"]}]),
                                      cuffs), 6)
        self.assertEqual(
            case_lab._selection_index(Event([{"x": 37.0}]), cuffs), 8)
        self.assertIsNone(case_lab._selection_index(Event([]), cuffs))
        self.assertIsNone(
            case_lab._selection_index(Event([{"x": -20.0}]), cuffs))

    def test_sidebar_toolbar_is_not_hidden_by_css(self):
        source = THEME.read_text(encoding="utf-8")
        self.assertNotIn(
            '[data-testid="stToolbar"], [data-testid="stDecoration"]', source)
        self.assertIn('[data-testid="stExpandSidebarButton"]', source)
        app = APP.read_text(encoding="utf-8")
        self.assertNotIn('"Twin test: no effect"', app)
        self.assertNotIn('"label": "Twin test"', app)
        self.assertNotIn("What is the twin test?", app)


if __name__ == "__main__":
    unittest.main()
