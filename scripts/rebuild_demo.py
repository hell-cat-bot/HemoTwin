"""Rebuild demo/demo_bundle.json from saved artifacts, without retraining.

    python scripts/rebuild_demo.py

Needs: artifacts/cache/te.parquet, artifacts/predictions_test.parquet,
       artifacts/hemotwin_event_model.txt, artifacts/hemotwin_meta.json,
       artifacts/train_report.json, and the raw data (for trajectories).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import data  # noqa: E402
from src.bundle import build_bundle  # noqa: E402
from src.config import ARTIFACTS, DEMO  # noqa: E402


def main() -> None:
    print("Loading data + session store ...")
    tables = data.load_tables()
    tables["session_store"] = data.build_session_store(tables)

    Fte = pd.read_parquet(ARTIFACTS / "cache" / "te.parquet")
    preds = pd.read_parquet(ARTIFACTS / "predictions_test.parquet")
    assert len(preds) == len(Fte), "prediction/feature row mismatch"
    Fte["score"] = preds["score"].to_numpy()

    meta = json.loads((ARTIFACTS / "hemotwin_meta.json").read_text())
    rep = json.loads((ARTIFACTS / "train_report.json").read_text())
    booster = lgb.Booster(model_file=str(ARTIFACTS / "hemotwin_event_model.txt"))

    bundle = build_bundle(
        tables, Fte, Fte["score"].to_numpy(), booster, meta["features"],
        rep["twin"]["population"], rep["twin"]["band"], rep["twin"]["volume"],
        rep["test"], rep["event_level"], rep["session_ppv"],
        rep["baselines"]["r1"], rep["baselines"]["r2"],
        meta["calibration"], n_sessions=8,
        threshold=rep["test"]["threshold"],
    )
    out = DEMO / "demo_bundle.json"
    out.write_text(json.dumps(bundle, indent=2))
    print(f"wrote {len(bundle['chairs'])} sessions -> {out}")

    # Re-derive the threshold sweep / decision curve from the same test
    # predictions and embed it, so the committed bundle always carries the
    # operating-point trade-off.
    try:
        from scripts.threshold_sweep import build_report, embed_in_bundle
        sweep_report = build_report(preds)
        embed_in_bundle(sweep_report, out)
    except Exception as exc:  # noqa: BLE001
        print(f"warning: threshold sweep not embedded ({exc})")

    for c in bundle["chairs"]:
        w = {p["policy"]: p for p in c["whatif"]}
        left = w["taper25"]["fluid_left_L"]
        print(f"  chair {c['chair']}: risk {c['risk']:.2f} "
              f"{'IDH' if c['session_idh'] else 'no-IDH'} "
              f"hold {w['hold']['nadir']:.0f} taper {w['taper25']['nadir']:.0f} "
              f"pause {w['pause']['nadir']:.0f} | delta {c['delta_nadir']:+.1f} "
              f"| fluid left {left}")


if __name__ == "__main__":
    main()
