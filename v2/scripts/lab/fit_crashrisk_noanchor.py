"""Fit the strictly pre-session crashrisk variant used by the Chair board.

Feature audit:
- ``sbp_anchor`` is the task01 anchor BP, not session-start.
- ``uf_ml_kg_h`` is the current UF rate at that anchor (``features.py`` uses
  ``uf_now``), not the planned pre-session rate.

Both are excluded here. The resulting variant is history + static patient
fields + planned UF goal only. It is a feature-audit correction of the
pre-registered secondary variant A; the primary B model is not used.

The shape model is evaluated as an ablation for the model card, but it is not
shipped: without the anchor BP and anchor UF rate it is AUROC 0.705 versus
baseline 0.701, too weak for a per-chair watch window.

Run from v2:

    python scripts/lab/fit_crashrisk_noanchor.py \
        --crashrisk-dir "D:/.../Digitwin/HemoTwin - Copy/crashrisk"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models" / "crashrisk"
EVIDENCE = ROOT / "evidence" / "crashrisk"
EXCLUDED = ("sbp_anchor", "uf_ml_kg_h")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    n = len(y)
    k = max(int(0.25 * n), 1)
    top = np.argsort(-p)[:k]
    return {
        "n": int(n),
        "n_event": int(y.sum()),
        "base_rate": float(y.mean()),
        "auroc": float(_auroc(y, p)),
        "recall_at_25": float(y[top].sum() / y.sum()),
        "ppv_at_25": float(y[top].mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "base_rate_brier": float(y.mean() * (1.0 - y.mean())),
        "ece10": float(ece10(p, y)),
        "top25_threshold": float(np.sort(p)[-k]),
    }


def _fit(train: pd.DataFrame, train_y: np.ndarray, eval_df: pd.DataFrame,
         eval_y: np.ndarray, feats: list[str]) -> dict:
    x_tr, x_ev = design_matrix(train, eval_df, feats)
    model = lgb.LGBMClassifier(**LGB_PARAMS)
    model.fit(x_tr, train_y)
    oof = np.zeros(len(train))
    folds = patient_cv_folds(train["pid_int"].to_numpy())
    for f in range(5):
        held = folds == f
        m = lgb.LGBMClassifier(**LGB_PARAMS)
        m.fit(x_tr.iloc[~held], train_y[~held])
        oof[held] = m.predict_proba(x_tr.iloc[held])[:, 1]
    a, b = fit_platt(oof, train_y)
    prob = platt_apply(model.predict_proba(x_ev)[:, 1], a, b)
    return {
        "model": model,
        "a": a,
        "b": b,
        "features": list(x_tr.columns),
        "medians": {c: float(train[c].median()) for c in feats},
        "prob": prob,
        "metrics": _metrics(eval_y, prob),
    }


def _band_stats(y: np.ndarray, p: np.ndarray) -> dict:
    out = {}
    for name, lo, hi in (("low", -1.0, 0.20), ("moderate", 0.20, 0.35),
                         ("high", 0.35, 2.0)):
        mask = (p >= lo) & (p < hi)
        out[name] = {
            "n": int(mask.sum()),
            "share": float(mask.mean()),
            "events": int(y[mask].sum()),
            "event_rate": float(y[mask].mean()) if mask.any() else None,
        }
    total = int(y.sum())
    out["low"]["share_of_events"] = float(out["low"]["events"] / total)
    out["high"]["share_of_events"] = float(out["high"]["events"] / total)
    out["thresholds"] = {"moderate": 0.20, "high": 0.35}
    return out


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=1, sort_keys=False),
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crashrisk-dir", required=True)
    args = parser.parse_args()
    source = Path(args.crashrisk_dir).resolve()
    sys.path.insert(0, str(source / "scripts"))
    sys.path.insert(0, str(source / "src"))
    global LGB_PARAMS, design_matrix, fit_platt, platt_apply, patient_cv_folds
    global ece10, _auroc, FEATURES_A
    from bench_sessionrisk import (  # noqa: E402
        LGB_PARAMS, _auroc, design_matrix, ece10, fit_platt,
        patient_cv_folds, platt_apply)
    from assemble import FEATURES_A  # noqa: E402

    feats = [c for c in FEATURES_A if c not in EXCLUDED]
    df = pd.read_parquet(source / "evidence" / "sessions_table.parquet")
    f2 = df[df["fold"] == 2].copy()
    dev = df[df["fold"].isin([0, 1])]
    tune = dev[dev["pid_int"] % 2 == 1].copy()

    risk = _fit(tune, tune["session_event"].to_numpy(int), f2,
                f2["session_event"].to_numpy(int), feats)
    risk_path = MODELS / "session_risk_booster_A2.txt"
    risk["model"].booster_.save_model(str(risk_path))
    bands = _band_stats(f2["session_event"].to_numpy(int), risk["prob"])
    official = json.loads((source / "evidence" / "confirm_fold2_risk.json")
                          .read_text(encoding="utf-8"))
    official_a = official["results"]["A_no_anchor"]

    risk_meta = {
        "date": "2026-11-11",
        "segment": "session-risk-v1 variant A2 (pre-session-safe)",
        "pre_registered": "secondary feature-audit correction",
        "anchor_used": False,
        "uf_rate_used": False,
        "excluded_features": list(EXCLUDED),
        "trained_on": "TUNE = pid-odd sessions of folds 0+1 "
                      "(patient-disjoint; fold 2 never used in any fit)",
        "n_train": int(len(tune)),
        "n_train_events": int(tune["session_event"].sum()),
        "base_features": feats,
        "features": risk["features"],
        "imputation": "TUNE medians + missing indicators",
        "medians": risk["medians"],
        "platt": {"a": risk["a"], "b": risk["b"]},
        "lgb_params": {k: _jsonable(v) for k, v in LGB_PARAMS.items()},
        "confirm_numbers": {
            "official_A_anchor_time_uf": {
                k: float(v) for k, v in official_a.items()},
            "recomputed_A2": risk["metrics"],
        },
        "bands": bands,
        "band_note": "Band edges are display conventions, not the "
                     "pre-registered 25% referral rule.",
        "claim": "Observational pre-session risk from history, static patient "
                 "fields, and the planned UF goal only. No blood pressure or "
                 "current UF rate is used. Display-only, staff-facing. Not a "
                 "treatment recommendation, not an alarm, not a "
                 "chair-allocation order. A low band means NOT elevated, never "
                 "safe. Planned-UF features encode clinician decisions made at "
                 "session start.",
    }
    risk_meta["artifacts"] = {"booster_sha256": _sha(risk_path)}
    _write_json(MODELS / "session_risk_meta_A2.json", risk_meta)

    # Shape is evaluated as an ablation for the model card, not shipped.
    crash = df[(df["session_event"] == 1) & df["onset_min"].notna()].copy()
    cdev = crash[crash["fold"].isin([0, 1])]
    ctune = cdev[cdev["pid_int"] % 2 == 1].copy()
    cf2 = crash[crash["fold"] == 2].copy()
    ctune["early"] = (ctune["onset_min"] < 90).astype(int)
    cf2["early"] = (cf2["onset_min"] < 90).astype(int)
    shape = _fit(ctune, ctune["early"].to_numpy(int), cf2,
                 cf2["early"].to_numpy(int), feats)
    baseline = _auroc(
        cf2["early"].to_numpy(int),
        cf2["hist_early_crash10"].fillna(
            cf2["hist_early_crash10"].median()).to_numpy(float))
    anchor_meta = json.loads((source / "models" / "session_shape_meta.json")
                             .read_text(encoding="utf-8"))

    ev = f2[f2["session_event"] == 1]
    evidence = {
        "date": "2026-11-11",
        "segment": "chairs pre-session re-read",
        "fold": 2,
        "risk": {
            "variant": "A2_pre_session_safe",
            "pre_registered": "secondary feature-audit correction",
            "official_A_anchor_time_uf": {
                k: float(v) for k, v in official_a.items()},
            "recomputed_A2": risk["metrics"],
            "bands": bands,
        },
        "shape": {
            "status": "not_shipped_pre_session",
            "reason": "The pre-registered shape model uses anchor SBP and "
                      "anchor UF rate. The no-anchor/no-UF ablation is barely "
                      "above its clinical-prior baseline, so no pre-session "
                      "shape prediction is shown.",
            "anchor_model": anchor_meta["confirm_numbers"],
            "anchor_baseline_auroc": 0.7005842476139506,
            "pre_session_ablation": {
                **shape["metrics"],
                "baseline_auroc": float(baseline),
                "base_rate": float(cf2["early"].mean()),
            },
            "display": "Recorded onset only after the reveal; never a "
                       "prediction.",
        },
        "feature_audit": {
            "fold2_events": int(len(ev)),
            "sbp_anchor_below_90": int((ev["sbp_anchor"] < 90).sum()),
            "sbp_anchor_share": float((ev["sbp_anchor"] < 90).mean()),
            "uf_rate_is_anchor_time": True,
            "excluded_features": list(EXCLUDED),
            "note": "sbp_anchor is the task01 anchor BP; uf_ml_kg_h is the "
                    "current UF rate at that anchor. Neither is a pre-session "
                    "feature. Variant A2 excludes both.",
        },
        "notes": "Shape is shown only as a recorded outcome. The anchor-based "
                 "shape model remains a separate research output, not a "
                 "pre-session claim.",
    }
    _write_json(EVIDENCE / "confirm_fold2_presession.json", evidence)

    print(f"risk A2: {risk['metrics']}")
    print(f"shape ablation: {shape['metrics']} baseline {baseline:.4f}")
    print(f"bands: {json.dumps(bands, indent=1)}")
    print(f"wrote {MODELS} and {EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
