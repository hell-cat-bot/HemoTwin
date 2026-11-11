"""Build the v1 PhysioTwin-v4.1 demo bundle for the console.

The demo cases are pinned to a curated, patient-disjoint fold-2 set. The
selection is deliberate: each forecast is close to the recorded nadir and the
pre-session A2 risk band matches the recorded outcome. It is an illustrative
demo set, not a prevalence or accuracy sample.

Run from V2 after the upstream v4 artifacts exist:

    python scripts/lab/build_v4_demo.py --artifacts-dir ../v1/artifacts
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.physiotwin_v4 import estimate_patient_posterior_params  # noqa: E402
from src.session_twin.audit_chain import (  # noqa: E402
    append_chained_event, verify_audit_chain,
)
from src.session_twin.evidence_ledger import (  # noqa: E402
    build_scoreboard, render_markdown,
)
from src.session_twin.scenario_matrix import build_scenario_matrix  # noqa: E402

WEIGHTS = ROOT / "src" / "session_twin" / "physiotwin_v4_weights.json"
CURATED = [
    ("stable_hold", "5275064_2016-09-26"),
    ("taper", "31128561_2017-02-14"),
    ("pause", "24891136_2016-03-23"),
    ("true_crash", "14975018_2015-12-02"),
    ("g1_taper_showcase", "20782271_2016-11-02"),
]


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _case(name: str, row, idx: int, store, weights, pre_features):
    """Build one frozen demo case from a fold-2 prediction row."""
    sid = str(row["session_id"])
    t = float(row["t_anchor"])
    d = store.get(sid)
    et = np.asarray(d["et"], dtype=float) if d else np.array([])
    es = np.asarray(d["es"], dtype=float) if d else np.array([])
    past = et <= t
    after = (et > t) & (et <= t + 60.0)
    cuffs = []
    for tt, ss in zip(et[past][-8:], es[past][-8:]):
        cuffs.append({"t": float(tt), "rel": float(tt) - t,
                      "sbp": float(ss), "phase": "before"})
    for tt, ss in zip(et[after], es[after]):
        cuffs.append({"t": float(tt), "rel": float(tt) - t,
                      "sbp": float(ss), "phase": "after"})
    params = estimate_patient_posterior_params(row)
    exp = row[["exp_uf_seg_1_15", "exp_uf_seg_16_30",
               "exp_uf_seg_31_45", "exp_uf_seg_46_60"]].to_numpy(float)
    regime = str(row["regime"])
    conf = weights["conformal"]["HOLD" if regime == "hold" else "TAPER"]
    common = dict(row=row, params=params,
                  base_nadir=float(row["base_pred"]),
                  expected_segments=exp,
                  conformal=(float(conf["q05"]), float(conf["q95"])))
    calibrated = build_scenario_matrix(gain=0.0, **common)
    illustration = build_scenario_matrix(gain=1.0, **common)
    uf_rate = _num(row.get("uf_at_anchor"))
    if uf_rate is None:
        uf_rate = _num(row.get("uf_Lh"))
    first_sbp = _num(es[past][0]) if len(es[past]) else _num(row["sbp_anchor"])
    return {
        "id": f"{idx}. {sid} @ {int(round(t))} min ({name})",
        "name": name,
        "session_id": sid,
        "t_anchor": t,
        "regime": regime,
        "observed_nadir": _num(row["observed_nadir"]),
        "base_nadir": _num(row["base_pred"]),
        "pred_v2_oracle": _num(row["pred_v2"]),
        "pred_v3": _num(row["pred_v3"]),
        "sbp_anchor": _num(row["sbp_anchor"]),
        "cuffs": cuffs,
        "features": {f: _num(row[f]) for f in pre_features},
        "state": {
            "D0": _num(row.get("D0")), "R0": _num(row.get("R0")),
            "C0": _num(row.get("C0")), "OH0": _num(row.get("OH0")),
            "n_prior_sessions": int(row.get("n_prior_sessions", 0)),
            "k_pat": _num(row.get("k_pat")),
            "beta_pat": _num(row.get("beta_pat")),
            "dry_weight": _num(row.get("dry_weight")),
            "pre_weight": _num(row.get("pre_weight")),
            "uf_at_anchor": uf_rate,
        },
        "uf_rate_lh": uf_rate,
        "uf_goal_l": _num(row.get("uf_goal_L")),
        "uf_removed_l": _num(row.get("cum_uf_L")),
        "first_sbp": first_sbp,
        "cuff_age_min": 10,
        "synthetic_demo": False,
        "params": {
            "k_refill": params.k_refill,
            "theta_crit": params.theta_crit,
            "beta_vol_mmHg_per_l": params.beta_vol_mmHg_per_l,
            "beta_baro_mmHg": params.beta_baro_mmHg,
            "w_dry_kg": params.w_dry_kg,
            "oh0_l": params.oh0_l,
        },
        "calibrated": calibrated,
        "illustration": illustration,
    }


def _synthetic_stale_case(stable: dict, idx: int) -> dict:
    case = json.loads(json.dumps(stable))
    case.update({
        "id": f"{idx}. DEMO-STALE-CUFF (synthetic stale-cuff guardrail)",
        "name": "stale_cuff",
        "session_id": "DEMO-STALE-CUFF",
        "t_anchor": 100.0,
        "regime": "synthetic",
        "observed_nadir": None,
        "pred_v2_oracle": None,
        "pred_v3": None,
        "sbp_anchor": 118.0,
        "base_nadir": 110.0,
        "cuffs": [],
        "cuff_age_min": 42,
        "synthetic_demo": True,
        "source_case": stable["session_id"],
        "uf_rate_lh": 0.5,
        "features": dict(stable["features"]),
        "state": dict(stable["state"]),
    })
    return case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", type=Path, required=True,
                        help="Directory containing physiotwin_v4/ and "
                             "review_20261107/task01/")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "evidence" / "demo_twin.json")
    parser.add_argument("--audit", type=Path,
                        default=ROOT / "demo" / "physiotwin_v4_audit.jsonl")
    args = parser.parse_args()

    artifacts = args.artifacts_dir.resolve()
    out = artifacts / "physiotwin_v4"
    weights = json.loads(WEIGHTS.read_text(encoding="utf-8"))
    report = json.loads((out / "benchmark_report.json").read_text(encoding="utf-8"))
    g7_path = out / "g7_report.json"
    g7 = json.loads(g7_path.read_text(encoding="utf-8")) if g7_path.exists() else {}
    meta = json.loads((out / "train_meta.json").read_text(encoding="utf-8"))
    pre_features = list(meta["features"])
    table = pd.read_parquet(out / "anchor_table.parquet")
    pred = pd.read_parquet(out / "fold2_predictions.parquet")
    df = pred.merge(table, on=["session_id", "t_anchor"], how="left",
                    suffixes=("", "_tab"))
    df = df[df["observed_nadir"].notna()].reset_index(drop=True)
    store = pickle.load(
        (artifacts / "review_20261107" / "task01" / "base_store.pkl").open("rb"))

    picked: list[tuple[str, object]] = []
    for name, session_id in CURATED:
        found = df[df["session_id"] == session_id]
        if found.empty:
            raise SystemExit(f"missing {session_id} ({name}) in fold-2 data")
        picked.append((name, found.iloc[0]))

    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text("", encoding="utf-8")

    cases = []
    for i, (name, row) in enumerate(picked):
        case = _case(name, row, i + 1, store, weights, pre_features)
        cases.append(case)
        append_chained_event(args.audit, {
            "event": "demo_case_loaded",
            "session_id": case["session_id"],
            "t_anchor": case["t_anchor"],
            "regime": case["regime"],
            "gamma_orth": weights["gamma_orth"],
            "claim": "research_display_only",
        })
    stable = next((c for c in cases if c["name"] == "stable_hold"), cases[0])
    cases.append(_synthetic_stale_case(stable, len(cases) + 1))
    append_chained_event(args.audit, {
        "event": "synthetic_demo_case_loaded",
        "session_id": "DEMO-STALE-CUFF",
        "synthetic_demo": True,
        "claim": "synthetic_ui_guardrail_only",
    })

    chain = verify_audit_chain(args.audit)
    scoreboard = build_scoreboard(report)
    gate_wording = (
        "5 of 6 gate booleans are true. G2 is a vacuous self-tie at gain 0; "
        "G4 is vacuous at gain 0 (the unit-gain consistency check passes 0 "
        "violations in 3,086,844). The substantive passes are G1, G5 and G6; "
        "G3 fails. all_pass is false.")
    if g7:
        gate_wording += (f" G7 verdict: {g7.get('verdict')} — "
                         f"{g7.get('claim', '')}")
    payload = {
        "version": "physiotwin-v4.1-v1",
        "generated": date.today().isoformat(),
        "gamma_orth": float(weights["gamma_orth"]),
        "mechanism_status": report["mechanism_status"],
        "gate_summary": weights["gate_summary"],
        "scoreboard_wording": gate_wording,
        "g2_as_plan_written_pass": weights["g2_as_plan_written_pass"],
        "plan_floor_gamma_0.25": report["plan_floor_gamma_0.25"],
        "sign_best_gamma_dev": report["sign_diagnostic"]["best_gamma"],
        "gate_markdown": render_markdown(scoreboard, report),
        "claim_boundary": weights["claim_boundary"],
        "g7": ({k: g7.get(k) for k in
                ("protocol_sha256", "stage0", "estimates",
                 "p6a_fold2_trajectory", "p6b_fold2_anchor_fan",
                 "temporal_order", "verdict", "claim")}
               if g7 else {"verdict": "MISSING"}),
        "audit_chain": chain,
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out} ({len(cases)} cases)")
    print("cases:", [c["name"] for c in cases])
    print(f"audit chain: {chain['ok']} ({chain['n_events']} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
