"""Metrics, with the ones the literature usually omits."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score, roc_curve)


def bootstrap_ci(y_true, score, groups, n_boot: int = 300, seed: int = 0,
                 metric=roc_auc_score):
    """Patient-clustered bootstrap. Resamples patients, not rows."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    score = np.asarray(score)
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    idx_by_group = {g: np.flatnonzero(groups == g) for g in uniq}
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_group[g] for g in pick])
        y = y_true[idx]
        if y.min() == y.max():
            continue
        vals.append(metric(y, score[idx]))
    if not vals:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def sens_at_spec(y_true, score, spec: float = 0.90) -> float:
    fpr, tpr, _ = roc_curve(y_true, score)
    ok = fpr <= (1 - spec)
    return float(tpr[ok].max()) if ok.any() else float("nan")


def ece(y_true, prob, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    prob = np.asarray(prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(prob, edges) - 1, 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.sum() == 0:
            continue
        total += (m.sum() / len(prob)) * abs(y_true[m].mean() - prob[m].mean())
    return float(total)


def reliability_table(y_true, prob, n_bins: int = 10):
    y_true = np.asarray(y_true, dtype=float)
    prob = np.asarray(prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(prob, edges) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        if m.sum() == 0:
            continue
        rows.append({
            "bin_mid": float((edges[b] + edges[b + 1]) / 2),
            "predicted": float(prob[m].mean()),
            "observed": float(y_true[m].mean()),
            "n": int(m.sum()),
        })
    return rows


def calibration_slope_intercept(y_true, prob) -> tuple[float, float]:
    """Fit logit(y) = a + b * logit(p). Perfect calibration: a=0, b=1."""
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(prob, dtype=float), 1e-6, 1 - 1e-6)
    x = np.log(p / (1 - p))
    # weighted least squares on the logit scale
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def full_report(y_true, score, pid) -> dict:
    y_true = np.asarray(y_true)
    score = np.asarray(score)
    lo, hi = bootstrap_ci(y_true, score, pid)
    ap = float(average_precision_score(y_true, score))
    rep = {
        "auroc": float(roc_auc_score(y_true, score)),
        "auroc_ci": [lo, hi],
        "auprc": ap,
        "prevalence": float(y_true.mean()),
        "lift": float(ap / max(y_true.mean(), 1e-9)),
        "sens_at_spec90": sens_at_spec(y_true, score, 0.90),
    }
    # Brier only makes sense for calibrated probabilities.
    if score.min() >= 0.0 and score.max() <= 1.0:
        rep["brier"] = float(brier_score_loss(y_true, np.clip(score, 0, 1)))
    return rep
