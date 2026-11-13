"""Package-level verification for the self-contained V2 submission."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "LICENSE",
    "requirements.txt",
    "app/hemotwin.py",
    "app/manual_app.py",
    "app/views/case_lab_page.py",
    "app/views/chair_board_page.py",
    "app/views/chair_board.py",
    "app/views/evidence_page.py",
    "app/views/replay_page.py",
    "assets/replay/replay.html",
    "app/views/case_lab.py",
    "app/views/evidence_handoff.py",
    "config/protocols/idh_review_research_v1.json",
    "evidence/benchmark_report.json",
    "evidence/g7_report.json",
    "evidence/g7_protocol.md",
    "evidence/g7_protocol.sha256",
    "evidence/demo_twin.json",
    "evidence/case_inspection.json",
    "evidence/chair_risk.json",
    "evidence/crashrisk/confirm_fold2_presession.json",
    "evidence/crashrisk/confirm_fold2_risk.json",
    "evidence/crashrisk/confirm_fold2_shape.json",
    "models/crashrisk/session_risk_booster_A2.txt",
    "models/crashrisk/session_risk_meta_A2.json",
    "docs/CRASHRISK.md",
    "docs/crashrisk_pre_registration.md",
    "models/physiotwin_v4/train_meta.json",
    "models/physiotwin_v4/models/base_seed42.txt",
    "models/forecast_v2/fold_0/FEATURES.md",
    "models/forecast_v2/fold_0/nadir_seed42.txt",
    "models/event_model/models/fold_0/universal_meta.json",
    "models/event_model/thresholds.json",
    "app/static/sim/embed.html",
    "demo/live_session_demo.csv",
    "docs/architecture.svg",
    "docs/EVIDENCE_STATUS.md",
    "docs/DESIGN.md",
    "deck/HemoTwin_Signal.pptx",
    "deck/HemoTwin_Story.pptx",
    "report/HemoTwin_System_Brief.pdf",
]

BANNED = ("guaranteed", "envelope", "ceiling", "partial identification",
          "100% safe", "no side effects")


def main() -> int:
    failures: list[str] = []
    print("HemoTwin V2 package verification")
    print("=" * 60)

    for rel in REQUIRED:
        ok = (ROOT / rel).exists()
        print(f"{'PASS' if ok else 'FAIL'}  exists  {rel}")
        if not ok:
            failures.append(rel)

    # No raw data or lab artifacts.
    for bad in ("data/raw", "artifacts"):
        path = ROOT / bad
        ok = not path.exists()
        print(f"{'PASS' if ok else 'FAIL'}  no {bad}/ in package")
        if not ok:
            failures.append(bad)

    # Package size (repo content only; .git is not part of the package).
    total = sum(p.stat().st_size for p in ROOT.rglob("*")
                if p.is_file() and ".git" not in p.parts)
    mb = total / (1024 * 1024)
    ok = mb < 60
    print(f"{'PASS' if ok else 'FAIL'}  package size {mb:.1f} MB (<60 MB)")
    if not ok:
        failures.append("package-size")

    # README numbers/claims.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for token in ("205,482", "303,122", "0.474", "10.99", "9.60",
                  "+0.13", "G7", "FAIL"):
        ok = token in readme
        print(f"{'PASS' if ok else 'FAIL'}  README contains {token}")
        if not ok:
            failures.append(f"readme:{token}")
    low = readme.lower()
    for word in BANNED:
        ok = word not in low
        print(f"{'PASS' if ok else 'FAIL'}  README avoids '{word}'")
        if not ok:
            failures.append(f"readme-ban:{word}")

    # App must not contain invented risk scores.
    for rel in ("app/views/case_lab.py", "app/manual_app.py"):
        source = (ROOT / rel).read_text(encoding="utf-8")
        ok = "0.99 if" not in source and "score\": 0.2" not in source
        print(f"{'PASS' if ok else 'FAIL'}  no invented score in {rel}")
        if not ok:
            failures.append(f"fake-score:{rel}")

    # Presentation artifacts are present and non-trivial.
    for rel, min_kb in (("deck/HemoTwin_Signal.pptx", 500),
                        ("deck/HemoTwin_Story.pptx", 500),
                        ("report/HemoTwin_System_Brief.pdf", 100)):
        path = ROOT / rel
        ok = path.exists() and path.stat().st_size > min_kb * 1024
        size = path.stat().st_size // 1024 if path.exists() else 0
        print(f"{'PASS' if ok else 'FAIL'}  {rel} ({size} KB, min {min_kb})")
        if not ok:
            failures.append(f"artifact:{rel}")

    # Evidence/chart data consistency: the charts are generated from these files.
    try:
        demo = json.loads((ROOT / "evidence" / "demo_twin.json").read_text(encoding="utf-8"))
        g7 = json.loads((ROOT / "evidence" / "g7_report.json").read_text(encoding="utf-8"))
        report = json.loads((ROOT / "evidence" / "benchmark_report.json").read_text(encoding="utf-8"))
        data_errors = []
        for case in demo["cases"]:
            hold = (case.get("calibrated") or {}).get("scenarios", [{}])[0]
            series = hold.get("nadir_series_mmhg") or []
            if len(series) != 61:
                data_errors.append(f"{case['name']}: series length {len(series)}")
            if not series:
                data_errors.append(f"{case['name']}: empty series")
                continue
            # The chart's +60 min value is the endpoint of the calibrated
            # trajectory. The synthetic stale-cuff guardrail reuses a demo
            # trajectory but withholds the projection, so it is exempt.
            if not case.get("synthetic_demo"):
                if abs(float(series[-1]) - float(case["base_nadir"])) > 1e-6:
                    data_errors.append(f"{case['name']}: series end != base_nadir")
                band = hold.get("nadir_band_90") or [None, None]
                if band[0] is None or not (float(band[0]) <= float(case["base_nadir"]) <= float(band[1])):
                    data_errors.append(f"{case['name']}: forecast outside band")
            else:
                band = hold.get("nadir_band_90") or [None, None]
                if band[0] is None or not (float(band[0]) <= float(series[-1]) <= float(band[1])):
                    data_errors.append(f"{case['name']}: synthetic series outside band")
        stage0 = g7["stage0"]
        census = sum(stage0["n_sessions"].values())
        if census != 205_113:
            data_errors.append(f"G7 census {census}")
        if stage0["n4_matched_events"] != 581 or stage0["n4_patients"] != 158:
            data_errors.append("G7 matched-event counts changed")
        if str(g7.get("verdict")) != "FAIL":
            data_errors.append(f"G7 verdict {g7.get('verdict')}")
        fold2 = report["gates"]["G2"]["fold2"]
        if abs(float(fold2["v4"]["mae"]) - 10.985512866875297) > 1e-6:
            data_errors.append("fair fold-2 MAE changed")
        if abs(float(fold2["oracle_forecast_v2"]["mae"]) - 9.600822913300828) > 1e-6:
            data_errors.append("oracle fold-2 MAE changed")
        ok = not data_errors
        print(f"{'PASS' if ok else 'FAIL'}  chart/evidence data consistency"
              + (f" ({data_errors[:3]})" if data_errors else ""))
        if not ok:
            failures.append("chart-data")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  chart/evidence data consistency: {exc}")
        failures.append("chart-data")

    # Markdown local links resolve.
    broken = []
    for md in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        text = md.read_text(encoding="utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = target.split("#")[0].strip()
            if not target:
                continue
            path = (md.parent / target).resolve()
            if not path.exists():
                path = (ROOT / target).resolve()
            if not path.exists():
                broken.append(f"{md.name} -> {target}")
    ok = not broken
    print(f"{'PASS' if ok else 'FAIL'}  local Markdown links resolve"
          + (f" (broken: {broken[:5]})" if broken else ""))
    if not ok:
        failures.append("links")

    # Audit chain.
    try:
        sys.path.insert(0, str(ROOT))
        from src.session_twin.audit_chain import verify_audit_chain
        chain = verify_audit_chain(ROOT / "demo" / "audit.jsonl")
        ok = bool(chain.get("ok")) and chain.get("n_events", 0) >= 7
        print(f"{'PASS' if ok else 'FAIL'}  demo audit chain verifies "
              f"({chain.get('n_events')} events)")
        if not ok:
            failures.append("audit-chain")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  audit chain: {exc}")
        failures.append("audit-chain")

    print("=" * 60)
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        for item in failures:
            print(" -", item)
        return 1
    print("All package checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
