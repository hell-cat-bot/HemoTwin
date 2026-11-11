"""Build dark-theme chart images for the V2 deck from the frozen evidence."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "deck" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

BG = "#07111F"
TEXT = "#E8F0F8"
MUTED = "#93A4B8"
GRID = "#1B2B3F"
CYAN = "#22D3EE"
TEAL = "#2DD4BF"
VIOLET = "#A78BFA"
AMBER = "#FBBF24"
CORAL = "#FB7185"
GOOD = "#34D399"


def _load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _style(ax) -> None:
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=12)
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.7)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def fan_chart() -> None:
    demo = _load("demo_twin.json")
    case = next(c for c in demo["cases"] if c["name"] == "g1_taper_showcase")
    hold = case["calibrated"]["scenarios"][0]
    before = [c for c in case["cuffs"] if c["phase"] == "before"]
    after = [c for c in case["cuffs"] if c["phase"] == "after"]

    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=200)
    fig.patch.set_facecolor(BG)
    _style(ax)

    y = hold["nadir_series_mmhg"]
    x = list(range(len(y)))
    nadir = hold["projected_nadir_mmhg"]
    lo = hold["nadir_band_90"][0] - nadir
    hi = hold["nadir_band_90"][1] - nadir
    ax.fill_between(x, [v + lo for v in y], [v + hi for v in y],
                    color=CYAN, alpha=0.13, linewidth=0)
    ax.plot(x, y, color=CYAN, linewidth=3, label="Calibrated projection · gain 0")

    if before:
        ax.plot([c["rel"] for c in before], [c["sbp"] for c in before],
                color=TEXT, linewidth=2.2, marker="o", markersize=4.5,
                markerfacecolor="white", markeredgecolor=BG,
                label="Observed cuffs · before anchor")
    if after:
        ax.scatter([c["rel"] for c in after], [c["sbp"] for c in after],
                   color=AMBER, marker="D", s=46, zorder=5,
                   label="Observed cuffs · ground truth")

    ax.scatter([60], [case["pred_v3"]], color=VIOLET, marker="x", s=95,
               linewidths=2.4, zorder=6,
               label=f"Retired v3 twin · {case['pred_v3']:.0f} mmHg")
    ax.axhline(90, color=CORAL, linestyle=(0, (2, 3)), linewidth=1.2, alpha=0.8)
    ax.text(61, 90.8, "90 mmHg floor", color=CORAL, fontsize=10, ha="right")
    ax.axvline(0, color="#5B7088", linestyle="--", linewidth=1)
    ax.text(1, 176, "anchor", color=MUTED, fontsize=10)

    ax.set_xlim(-102, 64)
    ax.set_ylim(88, 178)
    ax.set_xlabel("Minutes from anchor", fontsize=11)
    ax.set_ylabel("Systolic BP (mmHg)", fontsize=11)
    ax.legend(loc="lower left", frameon=False, fontsize=9, labelcolor=TEXT,
              ncol=2, bbox_to_anchor=(0, -0.31))
    fig.tight_layout()
    fig.savefig(OUT / "fan_chart_dark.png", facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def g7_forest() -> None:
    g7 = _load("g7_report.json")
    est = g7["estimates"]
    p6a = (g7.get("p6a_fold2_trajectory") or {}).get("30") or {}
    rows = [
        ("Early-UF effect", est["tau30_per_0.25_l_h"]["slope"],
         est["tau30_bootstrap"]["ci95"]),
        ("Twin gain", est["gamma_struct"]["slope"],
         est["gamma_struct_bootstrap"]["ci95"]),
        ("Pre-trend check", est["tau_pre"]["slope"],
         est["tau_pre_bootstrap"]["ci95"]),
        ("Sham-time check", est["sham"]["mean"], est["sham"]["ci95"]),
        ("Trajectory check", p6a.get("delta_mae"), p6a.get("ci95")),
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.9), dpi=200)
    fig.patch.set_facecolor(BG)
    _style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.7)
    ax.grid(axis="y", visible=False)

    for i, (label, value, ci) in enumerate(rows):
        if value is None:
            continue
        lo, hi = float(ci[0]), float(ci[1])
        crosses = lo <= 0 <= hi
        color = "#7C8DA3" if crosses else (CORAL if value > 0 else GOOD)
        ax.plot([lo, hi], [i, i], color=color, linewidth=3, solid_capstyle="round")
        ax.scatter([value], [i], color=color, s=55, zorder=5,
                   edgecolor=BG, linewidth=1.2)
        ax.text(hi + 0.15, i, f"{value:+.2f}  [{lo:+.2f}, {hi:+.2f}]",
                va="center", color=TEXT, fontsize=9.5)

    ax.axvline(0, color=TEXT, linewidth=1, alpha=0.5)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(-4.2, 4.6)
    ax.set_xlabel("Estimate (95% bootstrap CI)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "g7_forest_dark.png", facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def cohort_funnel() -> None:
    g7 = _load("g7_report.json")
    stage0 = g7["stage0"]
    # 205,482 is the QC-eligible cohort count; the G7 report starts at the
    # census (205,113) and carries the downstream event counts.
    values = [
        205482,
        int(sum(stage0["n_sessions"].values())),
        int(stage0["n1_any_step_sessions"]),
        int(stage0["n3_stability_events"]),
        int(stage0["n4_matched_events"]),
    ]
    labels = [
        "QC-eligible sessions",
        "G7 census sessions",
        "Dev sessions with a UF step",
        "Stable pre-anchor events",
        "Matched within-patient events",
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.4), dpi=200)
    fig.patch.set_facecolor(BG)
    _style(ax)
    ax.grid(axis="x", visible=False)
    colors = [CYAN, TEAL, "#38BDF8", AMBER, VIOLET]
    y = list(range(len(labels)))
    ax.barh(y, values, color=colors, alpha=0.85, height=0.55)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    for i, v in enumerate(values):
        ax.text(v * 1.12, i, f"{v:,}", va="center", color=TEXT, fontsize=11)
    ax.set_xlim(400, 420000)
    ax.set_xlabel("Sessions / events (log scale)", fontsize=11)
    ax.tick_params(axis="x", colors=MUTED)
    fig.tight_layout()
    fig.savefig(OUT / "cohort_funnel.png", facecolor=BG, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fan_chart()
    g7_forest()
    cohort_funnel()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
