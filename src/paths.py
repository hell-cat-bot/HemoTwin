"""Single source of paths for the self-contained V2 package.

``data/`` and ``artifacts/`` are not part of the lean app package. They are
optional lab inputs used by provenance/rebuild scripts and heavy tests. Resolve
them from inside ``v2/`` first, then from the portable bundle root (the parent
folder in the full research workspace).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT.parent
MODELS = ROOT / "models"
EVIDENCE = ROOT / "evidence"
DEMO = ROOT / "demo"
ASSETS = ROOT / "assets"
CONFIG_DIR = ROOT / "config"


def _optional_tree(name: str) -> Path:
    local = ROOT / name
    return local if local.exists() else BUNDLE / name


DATA = _optional_tree("data")
ARTIFACTS = _optional_tree("artifacts")
