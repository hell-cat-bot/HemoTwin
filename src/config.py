"""Central configuration. One source of truth for paths and the label definition."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ARTIFACTS = ROOT / "artifacts"
DEMO = ROOT / "demo"

for _p in (RAW, ARTIFACTS, DEMO):
    _p.mkdir(parents=True, exist_ok=True)

# HEMOBP (Lin et al., Sci Data 2019) - CC BY 4.0
URLS = {
    "d1.csv": "https://ndownloader.figshare.com/files/15142151",
    "idp.csv": "https://ndownloader.figshare.com/files/15142154",
    "vip.csv": "https://ndownloader.figshare.com/files/15142157",
}

CONFIG = {
    "SEED": 42,

    # ---- Label: FIRST intradialytic hypotensive episode of the session ----
    "IDH_SBP_THRESHOLD": 90.0,   # mmHg, absolute nadir
    "HORIZON_LO": 15,            # minutes; onsets closer than this are dropped
    "HORIZON_HI": 60,            # minutes; label window is (t+15, t+60]

    # ---- Session quality ----
    "MIN_ANCHOR_MIN": 30,
    "MAX_ANCHOR_MIN": 225,
    # Must exceed the horizon, otherwise an anchor is dropped for "unknown
    # outcome" when the next cuff simply falls inside the label window.
    "MAX_NEXT_MEAS_GAP_MIN": 70,
    "MIN_EVENTS_PER_SESSION": 4,
    "MIN_SESSION_MINUTES": 120,
    "MAX_SESSION_MINUTES": 400,
    "SBP_VALID": (40, 250),
    "DBP_VALID": (20, 150),

    # ---- Splits ----
    "TEST_FRACTION": 0.15,
    "VAL_FRACTION": 0.15,
    "MAX_NEG_ANCHORS_PER_SESSION_TRAIN": 6,

    # ---- Model ----
    "NUM_LEAVES": 31,
    "LEARNING_RATE": 0.02,
    "MIN_CHILD_SAMPLES": 100,
    "FEATURE_FRACTION": 0.8,
    "BAGGING_FRACTION": 0.9,
    "MAX_ROUNDS": 1500,
    "EARLY_STOPPING": 150,
    "SCALE_POS_WEIGHT_CAP": 25.0,
    "TARGET_SENSITIVITY": 0.85,  # for the frozen operating point
}

TARGET = "first IDH event (nadir SBP < 90 mmHg) starting 15-60 minutes after t"
