"""Pre-submission verification. Run this before pushing.

    python scripts/verify_submission.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
WARNS: list[str] = []


def check(cond: bool, msg: str, warn: bool = False) -> None:
    if cond:
        print(f"  PASS  {msg}")
    else:
        (WARNS if warn else FAILS).append(msg)
        print(f"  {'WARN' if warn else 'FAIL'}  {msg}")


def main() -> int:
    print("HemoTwin — submission verification\n")

    print("Repository structure")
    for p in ["README.md", "LICENSE", "requirements.txt", ".gitignore",
              "app/streamlit_app.py", "src/config.py", "src/data.py",
              "src/labels.py", "src/features.py", "src/model.py", "src/twin.py",
              "scripts/train.py", "docs/ARCHITECTURE.md", "docs/MODEL_CARD.md",
              "docs/FACTS.md", "deck/deck.html"]:
        check((ROOT / p).exists(), p)

    print("\nMandatory artefacts")
    check((ROOT / "deck" / "HemoTwin_Deck.pdf").exists(), "deck PDF", warn=True)
    check((ROOT / "docs" / "architecture.svg").exists(), "architecture diagram")
    check((ROOT / "docs" / "VIDEO_SCRIPT.md").exists(), "video script", warn=True)
    check((ROOT / "docs" / "QA.md").exists(), "judge Q&A", warn=True)

    print("\nREADME required sections")
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    for token, label in [("team", "team details"), ("problem statement", "problem statement"),
                         ("architecture", "architecture"), ("technical stack", "stack"),
                         ("limitation", "limitations"), ("licen", "licence")]:
        check(token in readme, label)

    print("\nDemo bundle")
    bundle_path = ROOT / "demo" / "demo_bundle.json"
    if not bundle_path.exists():
        check(False, "demo/demo_bundle.json exists (run scripts/train.py)")
        return _report()

    b = json.loads(bundle_path.read_text())
    chairs = b.get("chairs", [])
    check(len(chairs) >= 4, f"{len(chairs)} demo sessions")
    required = ["session_id", "risk", "trajectory", "forecast", "twin",
                "whatif", "drivers", "action"]
    for c in chairs:
        missing = [k for k in required if k not in c]
        check(not missing, f"{c.get('session_id')}: all fields ({', '.join(missing)})")
        pols = {p["policy"] for p in c.get("whatif", [])}
        check(pols == {"hold", "taper25", "pause"}, f"{c.get('session_id')}: 3 policies")
        hold = next((p for p in c["whatif"] if p["policy"] == "hold"), None)
        if hold:
            check(hold["lo"] <= hold["nadir"] <= hold["hi"],
                  f"{c.get('session_id')}: interval contains nadir")

    print("\nModel metrics present")
    m = b.get("metrics", {})
    for k in ["test", "event_level", "session_ppv", "baselines", "calibration", "twin"]:
        check(k in m, f"metrics.{k}")
    if "test" in m:
        check(0.80 <= m["test"]["auroc"] <= 0.99, f"AUROC plausible ({m['test']['auroc']:.3f})")
    if "event_level" in m:
        ev = m["event_level"]
        check(ev["detection_rate_all_sessions"] <= ev["detection_rate_evaluable"],
              "detection: all-session rate <= evaluable rate")

    print("\nCopy consistency")
    facts = (ROOT / "docs" / "FACTS.md").read_text(encoding="utf-8")
    check("75.7" in facts and "86.0" in facts, "FACTS has both detection denominators")
    deck = (ROOT / "deck" / "deck.html").read_text(encoding="utf-8")
    check("0.916" in deck, "deck quotes AUROC 0.916")
    check("15–60" in deck or "15-60" in deck, "deck states the 15-60 min horizon")

    return _report()


def _report() -> int:
    print("\n" + "=" * 60)
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(f"  - {f}")
    else:
        print("All blocking checks passed.")
    if WARNS:
        print(f"\n{len(WARNS)} warning(s):")
        for w in WARNS:
            print(f"  - {w}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
