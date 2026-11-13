"""Build the five-chair pre-session risk sidecar for the Chair board.

The board uses the A2 pre-session-safe risk bundle: history, static patient
fields, and planned UF goal only. Anchor BP and anchor-time UF rate are
excluded. Crash shape is recorded only after the reveal; it is not predicted.

Run from v2 after ``fit_crashrisk_noanchor.py``:

    python scripts/lab/build_chair_risk.py \
        --crashrisk-dir "D:/.../Digitwin/HemoTwin - Copy/crashrisk"
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models" / "crashrisk"
EVIDENCE = ROOT / "evidence"
OUT = EVIDENCE / "chair_risk.json"
DEMO = EVIDENCE / "demo_twin.json"
ORDER = ["stable_hold", "taper", "pause", "true_crash", "g1_taper_showcase"]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _score(meta: dict, booster: lgb.Booster, row: pd.Series) -> float:
    base = meta["base_features"]
    feats = meta["features"]
    med = meta["medians"]
    values = {}
    for c in base:
        raw = row.get(c)
        values[c] = float(raw) if pd.notna(raw) else np.nan
    x = {}
    for c in base:
        x[c] = values[c] if pd.notna(values[c]) else float(med[c])
    for c in base:
        miss = f"{c}_miss"
        if miss in feats:
            x[miss] = int(pd.isna(values[c]))
    for c in feats:
        x.setdefault(c, 0)
    frame = pd.DataFrame([x]).reindex(columns=feats, fill_value=0)
    raw = float(booster.predict(frame)[0])
    return float(1.0 / (1.0 + math.exp(
        -(float(meta["platt"]["a"]) * raw + float(meta["platt"]["b"])))))


def _risk_band(p: float) -> str:
    return "high" if p >= 0.35 else ("moderate" if p >= 0.20 else "low")


def _observed(case: dict, row: pd.Series) -> dict:
    cuffs = [c for c in (case.get("cuffs") or []) if c.get("sbp") is not None]
    post = [c for c in cuffs if float(c.get("rel") or 0) >= 0]
    low = min(post, key=lambda c: float(c["sbp"])) if post else None
    end = max((float(c.get("t") or 0) for c in cuffs), default=None)
    event = bool(int(row.get("session_event") or 0))
    onset = row.get("onset_min")
    recorded_shape = "no_event"
    if event and pd.notna(onset) and end:
        onset_f = float(onset)
        if onset_f < 90.0:
            recorded_shape = "early"
        elif onset_f / float(end) < 0.75:
            recorded_shape = "mid_session"
        else:
            recorded_shape = "final_hour"
    return {
        "event": event,
        "onset_min": float(onset) if pd.notna(onset) else None,
        "lowest_sbp": float(low["sbp"]) if low else None,
        "lowest_t": float(low["t"]) if low else None,
        "post_anchor_nadir": (float(case["observed_nadir"])
                              if case.get("observed_nadir") is not None
                              else None),
        "session_end_min": end,
        "recorded_shape": recorded_shape,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crashrisk-dir", required=True)
    args = parser.parse_args()
    source = Path(args.crashrisk_dir).resolve()
    demo = _read_json(DEMO)
    table = pd.read_parquet(source / "evidence" / "sessions_table.parquet")
    by_name = {c["name"]: c for c in demo["cases"]}
    risk_meta = _read_json(MODELS / "session_risk_meta_A2.json")
    risk_booster = lgb.Booster(model_file=str(
        MODELS / "session_risk_booster_A2.txt"))
    evidence = _read_json(EVIDENCE / "crashrisk" /
                          "confirm_fold2_presession.json")

    rows = []
    for chair, name in enumerate(ORDER, start=1):
        case = by_name[name]
        sid = case["session_id"]
        found = table[table["session_id"] == sid]
        if found.empty:
            raise SystemExit(f"missing {sid} in sessions_table")
        row = found.iloc[0]
        risk = _score(risk_meta, risk_booster, row)
        band = _risk_band(risk)
        inputs = {
            c: (None if pd.isna(row.get(c)) else float(row.get(c)))
            for c in risk_meta["base_features"]
        }
        patient = {
            "age": inputs["age"],
            "sex_M": inputs["sex_M"],
            "dm": inputs["dm"],
            "vintage_years": inputs["vintage_years"],
            "dry_weight": inputs["dry_weight"],
            "pre_weight": inputs["pre_weight"],
            "uf_goal_L": inputs["uf_goal_L"],
            "hist_idh_rate10": inputs["hist_idh_rate10"],
            "hist_early_crash10": inputs["hist_early_crash10"],
            "hist_last_idh": inputs["hist_last_idh"],
            "n_prior_sessions": inputs["n_prior_sessions"],
        }
        rows.append({
            "chair": chair,
            "case_id": case["id"],
            "case_select": name.replace("_", " ").title(),
            "case_name": name,
            "session_id": sid,
            "fold": int(row["fold"]),
            "patient": patient,
            "risk_probability": round(risk, 4),
            "risk_band": band,
            "observed": _observed(case, row),
            "inputs": inputs,
        })

    high = [c for c in rows if c["risk_band"] == "high"]
    moderate = [c for c in rows if c["risk_band"] == "moderate"]
    low = [c for c in rows if c["risk_band"] == "low"]
    events = [c for c in rows if c["observed"]["event"]]
    payload = {
        "version": 2,
        "generated": date.today().isoformat(),
        "source": "crashrisk segment 11/12, Digitwin research workspace",
        "demo": {
            "name": "Five patient-disjoint fold-2 chairs",
            "fold": 2,
            "curated": True,
            "note": "Five patient-disjoint fold-2 chairs from the curated "
                    "Case Lab demo; the synthetic stale-cuff guardrail is "
                    "excluded. Curated examples, not a prevalence sample. "
                    "Crash shape is recorded, not predicted.",
            "summary": {
                "n_chairs": len(rows),
                "high": len(high),
                "moderate": len(moderate),
                "low": len(low),
                "crashes": len(events),
                "high_crashes": sum(1 for c in high if c["observed"]["event"]),
                "moderate_crashes": sum(1 for c in moderate
                                        if c["observed"]["event"]),
                "low_crashes": sum(1 for c in low if c["observed"]["event"]),
            },
        },
        "risk_model": {
            "name": risk_meta["segment"],
            "variant": "A2_pre_session_safe",
            "pre_registered": risk_meta["pre_registered"],
            "anchor_used": False,
            "uf_rate_used": False,
            "excluded_features": risk_meta["excluded_features"],
            "metrics": risk_meta["confirm_numbers"]["recomputed_A2"],
            "official_A_anchor_time_uf":
                risk_meta["confirm_numbers"]["official_A_anchor_time_uf"],
            "bands": risk_meta["bands"],
            "thresholds": {"moderate": 0.20, "high": 0.35},
            "band_note": risk_meta["band_note"],
            "claim": risk_meta["claim"],
            "booster_sha256": risk_meta["artifacts"]["booster_sha256"],
        },
        "shape_policy": {
            **evidence["shape"],
            "display": "Recorded onset only after the reveal; not a "
                       "pre-session prediction.",
        },
        "feature_audit": evidence["feature_audit"],
        "chairs": rows,
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {OUT} with {len(rows)} chairs")
    print(json.dumps(payload["demo"]["summary"], indent=1))
    for c in rows:
        print(f"  chair {c['chair']}: {c['case_name']:20} "
              f"{c['risk_band']:8} {c['risk_probability']:.3f} "
              f"event={c['observed']['event']} "
              f"shape={c['observed']['recorded_shape']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
