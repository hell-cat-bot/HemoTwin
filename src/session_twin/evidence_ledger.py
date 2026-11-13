"""Pre-registered gate scoreboard from the PhysioTwin-v4.1 benchmark report."""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_REPORT = (Path(__file__).resolve().parents[2] / "evidence"
                  / "benchmark_report.json")

GATE_NAMES = {
    "G1": "Taper recovery vs retired twin",
    "G2": "Observational non-inferiority",
    "G3": "Actual-UF vs hold discrimination",
    "G4": "Monotone counterfactual physics",
    "G5": "Regime-conditioned conformal coverage",
    "G6": "Future invariance and cold start",
}


def load_report(path=None) -> dict | None:
    p = Path(path) if path else DEFAULT_REPORT
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def build_scoreboard(report: dict) -> list[dict]:
    rows = []
    gates = report.get("gates", {})
    for gid, name in GATE_NAMES.items():
        g = gates.get(gid, {})
        metric = ""
        if gid == "G1":
            metric = (f"MAE {g.get('v4', {}).get('mae', float('nan')):.3f} "
                      f"vs v3 {g.get('v3', {}).get('mae', float('nan')):.3f} "
                      f"(ratio {g.get('mae_ratio_v4_over_v3', float('nan')):.3f})")
        elif gid == "G2":
            f2 = g.get("fold2", {})
            metric = (f"fold-2 fair MAE "
                      f"{f2.get('v4', {}).get('mae', float('nan')):.3f} vs base "
                      f"{f2.get('base', {}).get('mae', float('nan')):.3f}; "
                      f"plan-written pass={g.get('pass_as_plan_written', False)}")
        elif gid == "G3":
            b = g.get("bootstrap", {})
            metric = (f"actual {g.get('actual', {}).get('mae', float('nan')):.3f} "
                      f"vs hold {g.get('hold', {}).get('mae', float('nan')):.3f}; "
                      f"delta CI {b.get('ci95', '—')}")
        elif gid == "G4":
            metric = (f"{g.get('violations', '—')} violations / "
                      f"{g.get('n_pairwise_minute_checks', '—')} checks; "
                      f"continuity {g.get('continuity_max_abs_error', '—')}")
        elif gid == "G5":
            regs = g.get("regimes", {})
            metric = "; ".join(
                f"{k} {v.get('coverage_fold2', float('nan')):.3f}"
                for k, v in regs.items())
        elif gid == "G6":
            metric = (f"cold start {g.get('cold_start_n', '—')}; future "
                      f"invariance {g.get('future_invariance_bitwise_equal', '—')}"
                      f"/{g.get('future_invariance_n', '—')}")
        rows.append({
            "gate": gid,
            "name": name,
            "pass": bool(g.get("pass", False)),
            "metric": metric,
        })
    return rows


def render_markdown(rows: list[dict], report: dict | None = None) -> str:
    lines = ["| Gate | Check | Result | Metric |",
             "| --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['gate']} | {r['name']} | "
                     f"{'PASS' if r['pass'] else 'FAIL'} | {r['metric']} |")
    if report:
        lines.append("")
        lines.append(f"Mechanism status: **{report.get('mechanism_status', '—')}**; "
                     f"gamma* = {report.get('gamma_orth', '—')}.")
    return "\n".join(lines)
