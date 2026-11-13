"""Build per-cuff inspection values for the Case Lab chart.

The frozen demo bundle stores one SBP value per cuff. The click inspector also
needs the recorded DBP, the machine UF programme, and the latent twin state at
that cuff. This script reads the raw HEMOBP VIP table and the frozen machine
store, integrates the pre-anchor Starling-baroreflex ODE to every cuff minute,
and writes a compact evidence sidecar. The demo bundle itself is not modified.

Run from the V2 folder with the V2 interpreter:
    C:/Python314/python.exe scripts/lab/enrich_case_inspection.py
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2))

from src.paths import ARTIFACTS, DATA  # noqa: E402
from src.physiotwin_v4 import (  # noqa: E402
    estimate_patient_posterior_params, integrate_pre_anchor, session_uf_grid,
)

DEMO = V2 / "evidence" / "demo_twin.json"
STORE = ARTIFACTS / "cache" / "bench_store_v1.pkl"
VIP = DATA / "raw" / "vip.csv"
OUT = V2 / "evidence" / "case_inspection.json"


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _cum_uf(grid: np.ndarray, minute: int, anchor_min: int,
            anchor_cum: float | None) -> float:
    """Integrate the machine programme and align it to the anchor record."""
    raw = float(np.sum(grid[:minute]) / 60.0)
    raw_anchor = float(np.sum(grid[:anchor_min]) / 60.0)
    if anchor_cum is None:
        return raw
    if minute <= anchor_min:
        if raw_anchor > 1e-9:
            return max(0.0, raw * anchor_cum / raw_anchor)
        return 0.0
    return max(0.0, anchor_cum + (raw - raw_anchor))


def _vip_lookup(vip: pd.DataFrame, sid: str) -> pd.DataFrame:
    pid, day = sid.split("_", 1)
    return vip[(vip["pid"].astype(str) == pid)
               & (vip["datatime"].astype(str).str.startswith(day))]


def _dbp_at(rows: pd.DataFrame, t: float, sbp: float) -> float | None:
    hit = rows[(rows["time"].astype(float) == float(t))
               & (rows["sbp"].astype(float) == float(sbp))]
    hit = hit[hit["dbp"].notna()]
    return None if hit.empty else float(hit.iloc[0]["dbp"])


def main() -> int:
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    store = pickle.load(STORE.open("rb"))
    vip = pd.read_csv(VIP, usecols=["pid", "datatime", "sbp", "dbp", "time"],
                      dtype={"datatime": str})
    cases: dict[str, dict] = {}
    for case in demo["cases"]:
        if case.get("synthetic_demo") or not case.get("cuffs"):
            continue
        sid = case["session_id"]
        d = store.get(sid)
        if d is None:
            print(f"skip {sid}: not in the frozen store")
            continue
        anchor_min = int(round(float(case["t_anchor"])))
        anchor_cum = _num((case.get("features") or {}).get("cum_uf_L"))
        max_min = max(int(round(float(c["t"]))) for c in case["cuffs"])
        row = dict(case.get("features") or {})
        row.update(case.get("state") or {})
        params = estimate_patient_posterior_params(row)
        grid = session_uf_grid(d, max_min)
        states = integrate_pre_anchor(
            grid, max_min, params,
            record_minutes=[int(round(float(c["t"]))) for c in case["cuffs"]])
        anchor_state = states.get(anchor_min)
        stored = case.get("state") or {}
        if anchor_state is not None:
            deltas = [
                abs(anchor_state.d_deficit_l - float(stored.get("D0", 0.0))),
                abs(anchor_state.r_refill_l_h - float(stored.get("R0", 0.0))),
                abs(anchor_state.c_baro_exhaustion - float(stored.get("C0", 0.0))),
                abs(anchor_state.oh_remaining_l - float(stored.get("OH0", 0.0))),
            ]
            if max(deltas) > 1e-6:
                raise SystemExit(
                    f"{sid}: reconstructed anchor state differs by {max(deltas):.3g}")
        rows = _vip_lookup(vip, sid)
        hold_series = ((case.get("calibrated") or {}).get("scenarios")
                       or [{}])[0].get("nadir_series_mmhg") or []
        cuffs = []
        for cuff in case["cuffs"]:
            t = float(cuff["t"])
            minute = int(round(t))
            st = states.get(minute)
            if st is None:
                raise SystemExit(f"{sid}: no twin state at minute {minute}")
            rel = float(cuff["rel"])
            projection = None
            if 0.0 <= rel <= 60.0:
                idx = int(round(rel))
                if idx < len(hold_series):
                    projection = _num(hold_series[idx])
            cuffs.append({
                "t": t,
                "rel": rel,
                "phase": cuff["phase"],
                "sbp": _num(cuff["sbp"]),
                "dbp": _dbp_at(rows, t, float(cuff["sbp"])),
                "uf_lh": float(grid[minute]),
                "cum_uf_l": _cum_uf(grid, minute, anchor_min, anchor_cum),
                "twin": {
                    "D": float(st.d_deficit_l),
                    "R": float(st.r_refill_l_h),
                    "C": float(st.c_baro_exhaustion),
                    "OH": float(st.oh_remaining_l),
                },
                "projection_sbp": projection,
            })
        cases[case["id"]] = {
            "session_id": sid,
            "anchor_min": float(case["t_anchor"]),
            "cuffs": cuffs,
        }
        missing = sum(1 for c in cuffs if c["dbp"] is None)
        print(f"{case['name']}: {len(cuffs)} cuffs · {missing} without DBP")

    payload = {
        "version": 1,
        "generated": date.today().isoformat(),
        "source": {
            "vip": "data/raw/vip.csv",
            "machine": "artifacts/cache/bench_store_v1.pkl",
            "state": "Starling-baroreflex ODE integrated from recorded UF",
        },
        "cases": cases,
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
