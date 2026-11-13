"""Verify the v1 claim boundary, frozen gates, demo integrity, and G7 verdict.

Runs without HEMOBP data or model binaries: it checks the committed weights,
the compact evidence record, the benchmark report, the G7 report, and the
built demo bundle, so CI can enforce the claim boundary.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WEIGHTS = ROOT / "src" / "session_twin" / "physiotwin_v4_weights.json"
EVIDENCE = ROOT / "docs" / "physiotwin_v4_evidence.json"
OUT = ROOT / "evidence"
REPORT = OUT / "benchmark_report.json"
G7 = OUT / "g7_report.json"
PROTOCOL = OUT / "g7_protocol.md"
DEMO = OUT / "demo_twin.json"
APP = ROOT / "app" / "views" / "case_lab.py"
README = ROOT / "README.md"
EVIDENCE_MD = ROOT / "docs" / "EVIDENCE_STATUS.md"

_checks: list[bool] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _checks.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}"
          + (f" — {detail}" if detail and not ok else ""))


def _text(path: Path) -> str:
    return (path.read_text(encoding="utf-8", errors="replace")
            if path.exists() else "")


def main() -> int:
    if not WEIGHTS.exists():
        print(f"FAIL  missing {WEIGHTS}")
        return 1
    weights = json.loads(WEIGHTS.read_text(encoding="utf-8"))
    evidence = (json.loads(EVIDENCE.read_text(encoding="utf-8"))
                if EVIDENCE.exists() else {})

    try:
        gamma = float(weights.get("gamma_orth", 999.0))
    except (TypeError, ValueError):
        gamma = 999.0
    check("calibrated gamma is 0", gamma == 0.0, f"gamma={gamma}")
    check("mechanism sign is not claimed",
          weights.get("mechanism_sign_supported") is False)
    gate_summary = weights.get("gate_summary") or {}
    check("G3 recorded as failed", gate_summary.get("G3") is False)
    check("G2 plan-written baseline recorded as failed",
          weights.get("g2_as_plan_written_pass") is False)
    boundary = str(weights.get("claim_boundary", "")).lower()
    check("claim boundary rejects the validated-twin claim",
          "not a validated counterfactual twin" in boundary)
    check("evidence records gamma=0",
          float(evidence.get("gamma_orth", 999.0)) == 0.0)
    check("evidence records G3 fail",
          (evidence.get("gates") or {}).get("G3", {}).get("pass") is False)
    check("evidence records the plan-faithful G2 fail",
          evidence.get("g2_as_plan_written_pass") is False)

    try:
        from src.session_twin.scenario_matrix import GOVERNANCE_LABEL
        check("scenario governance label is non-prescription",
              "NOT AN AUTONOMOUS PRESCRIPTION" in GOVERNANCE_LABEL)
    except Exception as exc:  # noqa: BLE001
        check("scenario governance label import", False, str(exc))
    try:
        from src.session_twin.handoff_summary import DISCLAIMER_EN
        check("handoff disclaimer is non-prescription",
              "Not a prescription" in DISCLAIMER_EN)
    except Exception as exc:  # noqa: BLE001
        check("handoff disclaimer import", False, str(exc))

    # 11 — frozen G1-G6 values and booleans.
    frozen_ok = False
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        gates = report["gates"]
        frozen_ok = (
            abs(gates["G1"]["v4"]["mae"] - 11.594909211884882) < 1e-6
            and abs(gates["G1"]["v3"]["mae"] - 15.550072636002879) < 1e-6
            and abs(gates["G5"]["regimes"]["HOLD"]["coverage_fold2"]
                    - 0.8915608663181479) < 1e-6
            and abs(gates["G5"]["regimes"]["TAPER"]["coverage_fold2"]
                    - 0.9010695187165776) < 1e-6
            and gates["G3"]["pass"] is False
            and gates["G2"]["pass_as_plan_written"] is False
            and report.get("all_pass") is False
            and float(report.get("gamma_orth", 999.0)) == 0.0
            and {k: bool(v.get("pass")) for k, v in gates.items()}
            == weights.get("gate_summary")
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        frozen_ok = False
    check("G1-G6 frozen integrity", frozen_ok,
          "benchmark report missing or frozen values changed")

    # 12 — banned claims and precise scoreboard wording.
    banned = ("partial identification", "manski", "balke-pearl", "ceiling",
              "envelope", "100% guaranteed")
    hits: list[str] = []
    for path in (APP, EVIDENCE_MD, README):
        text = _text(path).lower()
        hits += [f"{path.name}:{word}" for word in banned if word in text]
        hits += [f"{path.name}:{m}" for m in
                 re.findall(r"\b[1-6]/6 gates passed\b", text)]
    demo = (json.loads(DEMO.read_text(encoding="utf-8"))
            if DEMO.exists() else {})
    wording = str(demo.get("scoreboard_wording", ""))
    lint_ok = (not hits and "5 of 6 gate booleans" in wording
               and "G7 verdict" in wording)
    check("no unsubstantiated bound/gate language", lint_ok,
          "; ".join(hits) or "scoreboard wording missing")

    # 13 — cohort disclosure (app carries the full scale + failed-transport
    # numbers; the README stays lean with the headline cohort only),
    # 87.2% denominator, and demo-case integrity.
    app_text = _text(APP)
    readme_text = _text(README)
    cohort_ok = (
        all(s in app_text for s in ("205,482", "303,122", "0.474"))
        and "205,482" in readme_text)
    denom_ok = (
        ("87.2%" not in app_text or "32,565" in app_text)
        and ("87.2%" not in readme_text or "32,565" in readme_text))
    demo_ok = False
    try:
        by_name = {c.get("name"): c for c in demo.get("cases", [])}
        crash = by_name["true_crash"]
        showcase = by_name["g1_taper_showcase"]
        stale = by_name["stale_cuff"]
        demo_ok = (
            crash["base_nadir"] < 90.0
            and crash["observed_nadir"] < 90.0
            and abs(showcase["pred_v3"] - showcase["observed_nadir"]) >= 14.0
            and abs(showcase["base_nadir"] - showcase["observed_nadir"]) <= 5.0
            and stale.get("synthetic_demo") is True
            and float(stale.get("cuff_age_min", 0)) > 35.0)
    except (KeyError, TypeError, ValueError):
        demo_ok = False
    check("cohort/Spain/denominator/demo integrity",
          cohort_ok and denom_ok and demo_ok,
          f"cohort={cohort_ok} denominator={denom_ok} demo={demo_ok}")

    # 14 — G7 protocol hash, verdict, and operational gain.
    g7_ok = False
    try:
        protocol_hash = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
        g7 = json.loads(G7.read_text(encoding="utf-8"))
        verdict = str(g7.get("verdict"))
        allowed = {"PRODUCT_GRADE_PASS", "MECHANISM_PASS",
                   "STATISTICAL_ASSOCIATION_ONLY", "INCONCLUSIVE", "FAIL"}
        stage = g7.get("stage0") or {}
        gamma_ok = (
            verdict == "PRODUCT_GRADE_PASS"
            or (float(weights.get("gamma_orth", 999.0)) == 0.0
                and float(demo.get("gamma_orth", 999.0)) == 0.0))
        fan_ok = "value=False" in app_text
        g7_ok = (
            g7.get("protocol_sha256") == protocol_hash
            and verdict in allowed
            and gamma_ok
            and fan_ok
            and "n4_matched_events" in stage
            and "estimates" in g7
            and "p6a_fold2_trajectory" in g7
            and "p6b_fold2_anchor_fan" in g7)
    except (OSError, KeyError, TypeError, ValueError,
            json.JSONDecodeError):
        g7_ok = False
    check("G7 protocol hash/verdict/operational gain", g7_ok,
          "protocol, report, gamma, or fan default inconsistent")

    passed = sum(_checks)
    print(f"\n{passed}/{len(_checks)} claim-boundary checks passed")
    return 0 if passed == len(_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
