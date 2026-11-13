"""Forecast-v2 fold-0 serving layer: modes, honesty gates, and card wiring.

Covers the feature-computability rule (see src/forecast_serve.py):
- playback sessions with a fold-0 substrate anchor -> playback_full, features
  exactly as task03 built them (verified against the stored substrate
  prediction);
- playback sessions without a well-posed conditional anchor -> abstain;
- fresh manual sessions -> manual_limited with the out-of-distribution label
  threshold, or abstain when the minimum set cannot be computed;
- absent model artifacts degrade to an unavailable note;
- the app card is display-only and carries the fixed claim caption.
"""
from __future__ import annotations

import atexit
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "manual_app.py"
PLAYBACK = ROOT / "demo" / "fold0_playback.json"
SUBSTRATE = ROOT / "models" / "predictions_outer_v2.parquet"
PLAYBACK_READY = PLAYBACK.exists() and SUBSTRATE.exists()
REAL_AUDIT_PATH = ROOT / "demo" / "task01r_audit.jsonl"

FIXED_CAPTION = ("Observational conditional forecast under the observed UF "
                 "trajectory — not a validated what-if effect, not a "
                 "treatment recommendation, not a safety layer.")

from src import forecast_serve as FS  # noqa: E402

MANUAL_START = {"session_id": "manual_demo", "pre_weight": 68.0,
                "dry_weight": 65.0, "age": 60, "sex": "M", "dm": 0,
                "vintage_years": 3.0, "month": 11}
EXAMPLE_CUFFS = [
    {"t": 0, "sbp": 140, "dbp": 80, "uf": 1.3},
    {"t": 30, "sbp": 132, "dbp": 76, "uf": 1.3},
    {"t": 60, "sbp": 124, "dbp": 72, "uf": 1.3},
    {"t": 90, "sbp": 116, "dbp": 68, "uf": 1.3},
]

# Scratch audit target for the AppTest-based integration test. The redirect is
# scoped INSIDE the test (mock.patch.dict) — never at module level — so this
# module cannot clobber the env var that tests/test_task01r_app_smoke.py sets
# for its own AppTest runs, and the real demo log is never touched.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="hemotwin_forecast_serve_"))
TEMP_AUDIT_PATH = _TMP_DIR / "task01r_audit.jsonl"


def tearDownModule() -> None:
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


atexit.register(lambda: shutil.rmtree(_TMP_DIR, ignore_errors=True))


def _audit_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()])


@unittest.skipUnless(PLAYBACK_READY, "playback substrate not bundled")
class PlaybackFullForecastTest(unittest.TestCase):
    """A fold-0 playback session serves the exact task03 feature path."""

    @classmethod
    def setUpClass(cls):
        sessions = json.loads(PLAYBACK.read_text())["sessions"]
        cls.pb_session = next(s for s in sessions
                              if s["session_id"] == "1025914_2014-10-27")
        cls.result = FS.forecast({"start": cls.pb_session["start"],
                                  "cuffs": cls.pb_session["cuffs"],
                                  "source": "playback"})

    def test_model_files_exist_and_forecast_is_finite(self):
        for seed in FS.SEEDS:
            for stem in FS.MODEL_STEMS.values():
                self.assertTrue(
                    (FS.MODELS_DIR / stem.format(seed)).exists(),
                    stem.format(seed))
        self.assertEqual(self.result["mode"], "playback_full")
        for key in ("nadir_mean", "p30", "p60"):
            self.assertIsNotNone(self.result[key], key)
            self.assertTrue(self.result[key] == self.result[key])  # not NaN
            self.assertTrue(abs(float(self.result[key])) < 500.0)

    def test_matches_the_stored_fold0_substrate_prediction(self):
        """The serving path reproduces the substrate's own pred_gbdt exactly.

        This is the proof that the 72 features are computed exactly as
        scripts/task03_refit_nadir.py built them for this anchor.
        """
        import pandas as pd
        row = pd.read_parquet(SUBSTRATE, columns=[
            "fold", "session_id", "t_anchor", "pred_gbdt", "pred_gbdt_30",
            "pred_gbdt_60"])
        row = row[(row["fold"] == 0)
                  & (row["session_id"] == self.pb_session["session_id"])]
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(self.result["nadir_mean"],
                               float(row["pred_gbdt"].iloc[0]), places=9)
        self.assertAlmostEqual(self.result["p30"],
                               float(row["pred_gbdt_30"].iloc[0]), places=9)
        self.assertAlmostEqual(self.result["p60"],
                               float(row["pred_gbdt_60"].iloc[0]), places=9)
        self.assertAlmostEqual(self.result["anchor_min"],
                               float(row["t_anchor"].iloc[0]), places=9)

    def test_band_brackets_the_mean(self):
        lo, hi = self.result["nadir_band"]
        mean = self.result["nadir_mean"]
        self.assertLess(lo, mean)
        self.assertLess(mean, hi)
        # The band is a residual band around the mean (lo < 0 < hi offsets).
        self.assertLess(lo, mean)  # redundant by construction; explicit intent
        self.assertLess(float(FS.load_bundle()["band"][0]), 0.0)
        self.assertGreater(float(FS.load_bundle()["band"][1]), 0.0)

    def test_playback_feature_coverage_is_high(self):
        # Only the sparse-window variance features may be missing, exactly as
        # in the refit row (never imputed).
        self.assertGreaterEqual(self.result["features_available"], 69)
        self.assertEqual(set(self.result["features_missing"]),
                         {"uf_var_30", "sbp_std_30", "sbp_std_60"})


@unittest.skipUnless(PLAYBACK_READY, "playback substrate not bundled")
class PlaybackWithoutAnchorAbstains(unittest.TestCase):
    """No well-posed conditional point -> abstain, never invent the condition."""

    def test_session_without_fold0_anchor_abstains(self):
        sessions = json.loads(PLAYBACK.read_text())["sessions"]
        s2 = next(s for s in sessions
                  if s["session_id"] == "10434576_2013-06-01")
        result = FS.forecast({"start": s2["start"], "cuffs": s2["cuffs"],
                              "source": "playback"})
        self.assertIsNone(result["mode"])
        self.assertIsNone(result["nadir_mean"])
        self.assertIn("anchor", result["reason"])


class ManualLimitedForecastTest(unittest.TestCase):
    """Fresh manual entry serves only as a labelled limited-history forecast."""

    @classmethod
    def setUpClass(cls):
        cls.result = FS.forecast({"start": MANUAL_START,
                                  "cuffs": EXAMPLE_CUFFS,
                                  "source": "manual"})

    def test_limited_mode_with_ood_label_threshold(self):
        self.assertEqual(self.result["mode"], "manual_limited")
        self.assertIsNotNone(self.result["nadir_mean"])
        self.assertGreaterEqual(len(self.result["features_missing"]),
                                FS.MANUAL_OOD_MIN_MISSING)

    def test_structurally_missing_blocks_are_listed(self):
        missing = set(self.result["features_missing"])
        for name in FS.HIST_FEATURES:          # no prior sessions
            self.assertIn(name, missing)
        for name in FS.UF_BLOCK_FEATURES:      # no observed future trajectory
            self.assertIn(name, missing)
        for name in FS.TWIN_FEATURES:          # no twin parameters
            self.assertIn(name, missing)

    def test_band_brackets_the_mean(self):
        lo, hi = self.result["nadir_band"]
        self.assertLess(lo, self.result["nadir_mean"])
        self.assertLess(self.result["nadir_mean"], hi)

    def test_single_cuff_does_not_crash_or_return_nan(self):
        result = FS.forecast({"start": MANUAL_START,
                              "cuffs": EXAMPLE_CUFFS[:1],
                              "source": "manual"})
        self.assertEqual(result["mode"], "manual_limited")
        self.assertIsNotNone(result["nadir_mean"])
        self.assertTrue(result["nadir_mean"] == result["nadir_mean"])
        self.assertGreaterEqual(len(result["features_missing"]),
                                FS.MANUAL_OOD_MIN_MISSING)


class ManualAbstainTest(unittest.TestCase):
    """The minimum set (current BP/UF block, cadence windows) is mandatory."""

    def test_invalid_cuffs_abstain_with_reason(self):
        result = FS.forecast({
            "start": MANUAL_START,
            "cuffs": [{"t": 0, "sbp": 300, "dbp": 80, "uf": 1.3}],
            "source": "manual"})
        self.assertIsNone(result["mode"])
        self.assertIn("minimum feature set not computable", result["reason"])

    def test_empty_cuffs_abstain(self):
        result = FS.forecast({"start": MANUAL_START, "cuffs": [],
                              "source": "manual"})
        self.assertIsNone(result["mode"])
        self.assertIsNotNone(result["reason"])


class AbsentModelDegradesTest(unittest.TestCase):
    """A stale/absent model degrades to an unavailable note, never a crash."""

    def test_missing_bundle_returns_unavailable(self):
        with mock.patch.object(FS, "load_bundle", return_value=None):
            result = FS.forecast({"start": MANUAL_START,
                                  "cuffs": EXAMPLE_CUFFS,
                                  "source": "manual"})
        self.assertIsNone(result["mode"])
        self.assertIn("unavailable", result["reason"])

    def test_corrupt_booster_degrades(self):
        with mock.patch.object(FS, "_load_booster", return_value=None):
            FS.load_bundle.cache_clear()
            try:
                result = FS.forecast({"start": MANUAL_START,
                                      "cuffs": EXAMPLE_CUFFS,
                                      "source": "manual"})
            finally:
                FS.load_bundle.cache_clear()
        self.assertIsNone(result["mode"])
        self.assertIn("unavailable", result["reason"])


class CardCaptionInAppSourceTest(unittest.TestCase):
    """Grep-level assertion: the card and its fixed claim caption are wired."""

    def test_fixed_caption_and_display_only_lines_in_app_source(self):
        import ast
        source = APP.read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Collect every string constant rendered by any call in the app.
        rendered = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                parts = [n.value for n in ast.walk(node)
                         if isinstance(n, ast.Constant)
                         and isinstance(n.value, str)]
                if parts:
                    rendered.append("".join(parts))
        blob = "\n".join(rendered)
        self.assertIn("WHAT HAPPENS NEXT", blob)
        self.assertIn(FIXED_CAPTION, blob)
        self.assertIn("Display only: the forecast never gates, suppresses, "
                      "or alters the protocol pathway.", blob)
        self.assertIn("LIMITED-HISTORY FORECAST", blob)
        self.assertIn("OUT-OF-DISTRIBUTION", blob)
        # Raw source greps (no rendering): the caption is written in this app.
        self.assertIn("Observational conditional forecast under the observed UF",
                      source)
        self.assertIn("treatment recommendation, not a safety layer.", source)

    def test_card_is_not_wired_into_protocol_state(self):
        # The card only reads stored display results; the protocol engine
        # (src/session_twin/engine.py) must not reference the forecast.
        engine = (ROOT / "src" / "session_twin" / "engine.py").read_text(
            encoding="utf-8")
        self.assertNotIn("forecast", engine.lower())


class CardIntegrationTest(unittest.TestCase):
    """The card renders after evaluation and never blocks the pathway."""

    def test_example_cuffs_show_manual_limited_card(self):
        from streamlit.testing.v1 import AppTest
        before = _audit_lines(TEMP_AUDIT_PATH)
        real_before = _audit_lines(REAL_AUDIT_PATH)
        with mock.patch.dict(os.environ,
                             {"HEMOTWIN_AUDIT_PATH": str(TEMP_AUDIT_PATH)}):
            at = AppTest.from_file(str(APP), default_timeout=60).run()
            next(b for b in at.button
                 if b.label == "Load example cuffs").click().run()
            next(b for b in at.button
                 if b.label == "Evaluate assessment").click().run()
        self.assertEqual(list(at.exception), [])
        fc = at.session_state["forecast_result"]
        self.assertIsNotNone(fc)
        self.assertEqual(fc["mode"], "manual_limited")
        captions = [" ".join(c.value.split()) for c in at.caption]
        self.assertTrue(any(FIXED_CAPTION in c for c in captions), captions)
        self.assertTrue(any("never gates, suppresses, or alters" in c
                            for c in captions), captions)
        # Display-only: the protocol state is unchanged by the card.
        self.assertEqual(at.session_state["recommendation"]["state"],
                         "NO_ALERT")
        # Evidence behaviour is unchanged by the card.
        self.assertEqual(_audit_lines(TEMP_AUDIT_PATH), before + 1)
        self.assertEqual(_audit_lines(REAL_AUDIT_PATH), real_before)

    @unittest.skipUnless(PLAYBACK_READY, "playback substrate not bundled")
    def test_playback_load_serves_playback_full_card(self):
        from streamlit.testing.v1 import AppTest
        with mock.patch.dict(os.environ,
                             {"HEMOTWIN_AUDIT_PATH": str(TEMP_AUDIT_PATH)}):
            at = AppTest.from_file(str(APP), default_timeout=120).run()
            next(b for b in at.button
                 if b.label == "Load retrospective playback").click().run()
            next(b for b in at.button
                 if b.label == "Evaluate assessment").click().run()
        self.assertEqual(list(at.exception), [])
        fc = at.session_state["forecast_result"]
        self.assertIsNotNone(fc)
        self.assertEqual(fc["mode"], "playback_full")
        self.assertAlmostEqual(fc["nadir_mean"], 92.63198955267416, places=9)
        self.assertAlmostEqual(fc["anchor_min"], 97.0, places=9)
        captions = [" ".join(c.value.split()) for c in at.caption]
        self.assertTrue(any("retrospective playback" in c and "anchor minute 97"
                            in c for c in captions), captions)
        self.assertTrue(any(FIXED_CAPTION in c for c in captions), captions)


if __name__ == "__main__":
    unittest.main()
