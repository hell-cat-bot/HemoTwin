"""Event model: LightGBM + isotonic calibration fitted on a held-out half of validation.

Why a tree model: the only IDH predictor with published hospital deployment at
a comparable horizon (Zhang et al., NDT 2023) is a boosted-tree model on very
similar features. It trains on CPU in minutes, explains with TreeSHAP, and
exports as a single file.

Why calibration is split: fitting isotonic regression and then *reporting*
calibration on the same validation rows makes ECE look perfect by construction.
We fit on half of validation and report on the other half.
"""
from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from .config import ARTIFACTS, CONFIG
from .metrics import ece, full_report, reliability_table


def train(Ftr, Fva, Fte, feats: list[str]) -> tuple[lgb.Booster, IsotonicRegression, dict]:
    ytr = Ftr.label.values
    yva = Fva.label.values

    spw = min((ytr == 0).sum() / max((ytr == 1).sum(), 1),
              CONFIG["SCALE_POS_WEIGHT_CAP"])
    dtr = lgb.Dataset(Ftr[feats], label=ytr)
    dva = lgb.Dataset(Fva[feats], label=yva, reference=dtr)

    params = dict(
        objective="binary",
        learning_rate=CONFIG["LEARNING_RATE"],
        num_leaves=CONFIG["NUM_LEAVES"],
        min_child_samples=CONFIG["MIN_CHILD_SAMPLES"],
        feature_fraction=CONFIG["FEATURE_FRACTION"],
        bagging_fraction=CONFIG["BAGGING_FRACTION"],
        bagging_freq=1,
        scale_pos_weight=spw,
        metric=["average_precision", "auc"],
        verbosity=-1,
        seed=CONFIG["SEED"],
    )
    booster = lgb.train(
        params, dtr, num_boost_round=CONFIG["MAX_ROUNDS"], valid_sets=[dva],
        callbacks=[lgb.early_stopping(CONFIG["EARLY_STOPPING"], verbose=False),
                   lgb.log_evaluation(0)],
    )
    print(f"  best iteration: {booster.best_iteration}")

    pva = booster.predict(Fva[feats], num_iteration=booster.best_iteration)

    # ---- split validation: calibrate on A, report on B ----
    rng = np.random.default_rng(CONFIG["SEED"])
    order = rng.permutation(len(Fva))
    half = len(order) // 2
    cal_idx, hold_idx = order[:half], order[half:]

    iso = IsotonicRegression(out_of_bounds="clip").fit(pva[cal_idx], yva[cal_idx])
    p_hold_raw = pva[hold_idx]
    p_hold_cal = np.clip(iso.predict(p_hold_raw), 0, 1)

    print(f"  validation AUROC {roc_auc_score(yva, pva):.3f} | "
          f"AUPRC {average_precision_score(yva, pva):.3f}")
    print(f"  calibration (held-out half of val): "
          f"ECE {ece(yva[hold_idx], p_hold_raw):.4f} raw -> "
          f"{ece(yva[hold_idx], p_hold_cal):.4f} isotonic")

    # ---- frozen operating point, chosen on validation only ----
    # The threshold must live on the SAME scale as the scores we later compare
    # it against, i.e. the calibrated probabilities. Picking it on raw scores
    # and applying it to isotonic output flags nothing at all.
    pva_cal = np.clip(iso.predict(pva), 0, 1)
    thr = pick_threshold(yva, pva_cal, CONFIG["TARGET_SENSITIVITY"])
    val_sens = float((pva_cal[yva == 1] >= thr).mean())
    val_alarm = float((pva_cal >= thr).mean())
    print(f"  operating point: threshold {thr:.4f} | val sens {val_sens:.3f} | "
          f"val alarm rate {val_alarm:.3f}")

    cal = {
        "ece_raw_holdout": ece(yva[hold_idx], p_hold_raw),
        "ece_cal_holdout": ece(yva[hold_idx], p_hold_cal),
        "reliability": reliability_table(yva[hold_idx], p_hold_cal),
        "threshold": thr,
        "target_sensitivity": CONFIG["TARGET_SENSITIVITY"],
        "val_sens_at_thr": val_sens,
        "val_alarm_rate_at_thr": val_alarm,
    }
    return booster, iso, cal


def pick_threshold(y_true, prob, target_sens: float = 0.85) -> float:
    """Largest threshold that still achieves the target sensitivity on validation.

    Sensitivity is non-increasing in the threshold, so the feasible set is
    (0, t*]. We want t*: the most specific operating point that still meets the
    sensitivity requirement. Scanning ascending and returning the first hit
    would return ~0 and alarm on everything -- a mistake worth spelling out.
    """
    y_true = np.asarray(y_true).astype(bool)
    prob = np.asarray(prob)
    order = np.argsort(-prob)
    tp = np.cumsum(y_true[order])
    total = max(int(y_true.sum()), 1)
    sens = tp / total
    ok = np.flatnonzero(sens >= target_sens)
    if len(ok) == 0:
        return float(prob.min())
    idx = int(ok[0])          # largest threshold that still meets the target
    return float(prob[order[idx]])


def evaluate(booster, iso, Fte, feats: list[str], thr: float) -> dict:
    y = Fte.label.values
    p_raw = booster.predict(Fte[feats], num_iteration=booster.best_iteration)
    p_cal = np.clip(iso.predict(p_raw), 0, 1)

    rep = full_report(y, p_cal, Fte.pid.values)
    rep.update({
        "n": int(len(y)),
        "positives": int(y.sum()),
        "threshold": thr,
        "sens_at_thr": float((p_cal[y == 1] >= thr).mean()),
        "alarm_rate_at_thr": float((p_cal >= thr).mean()),
        "ppv_at_thr": float(y[p_cal >= thr].mean()) if (p_cal >= thr).any() else float("nan"),
        "calibration": {"ece": ece(y, p_cal)},
    })
    return rep, p_raw, p_cal


def save(booster, iso, feats, cal, rep, path_prefix="hemotwin"):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(ARTIFACTS / f"{path_prefix}_event_model.txt"))
    meta = {
        "features": feats,
        "best_iteration": booster.best_iteration,
        "calibration": cal,
        "test": rep,
        "label": "first IDH (nadir SBP<90) onset in (t+15, t+60]",
    }
    (ARTIFACTS / f"{path_prefix}_meta.json").write_text(json.dumps(meta, indent=2))
    # isotonic knots, exported so a C++/ONNX port can reproduce calibration
    knots = {"x": iso.X_thresholds_.tolist(), "y": iso.y_thresholds_.tolist()}
    (ARTIFACTS / f"{path_prefix}_isotonic.json").write_text(json.dumps(knots))
    print(f"  saved -> {ARTIFACTS}")
