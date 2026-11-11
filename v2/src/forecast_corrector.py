"""Corrector for the frozen Task 01 outer forecasts (segment forecast-v1).

Interface contract (exercised by scripts/bench_forecast.py):
    model = fit(df_tune)          # df_tune: anchors from TUNE patients only
    out = apply(df, model)        # {"nadir": array, "p30": array, "p60": array}

Governance: fit() may only use TUNE rows (patient-parity odd half of folds
0+1). Fold 2 never enters this module. Improvements are measured on the EVAL
half; fold-2 confirmation runs separately at segment milestones.

v2: multivariate least-squares calibration of the nadir on anchor-level
covariates — the affine fit (v1, KEEP) plus anchor SBP, the 30/60-minute point
forecasts (value-if-finite else nadir prediction, with finite indicators), UF
intensity, anchor time, prior-session count, demographics, UF reference, max
outcome-window gap, and regime one-hots. Closed form, deterministic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_REGIMES = ["hold", "mixed", "moderate", "aggressive", "zero_reference", "pause"]


def _col(df: pd.DataFrame, name: str, default=np.nan) -> np.ndarray:
    if name not in df.columns:
        return np.full(len(df), default, dtype=float)
    return pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)


def design(df: pd.DataFrame) -> np.ndarray:
    nadir = _col(df, "pred_gbdt")
    p30 = _col(df, "pred_gbdt_30")
    p60 = _col(df, "pred_gbdt_60")
    p30v = np.where(np.isfinite(p30), p30, nadir)
    p60v = np.where(np.isfinite(p60), p60, nadir)
    # multi-model stack: the ODE twin and causal baselines as additional
    # blend inputs (diversity: twin encodes physiology/history, persistence
    # encodes the raw level).
    twin = _col(df, "pred_twin_full")
    pers = _col(df, "pred_persistence")
    lin = _col(df, "pred_linear")
    feats = [
        nadir,
        twin,
        pers,
        lin,
        _col(df, "sbp_anchor"),
        p30v,
        p60v,
        (np.isfinite(p30)).astype(float),
        (np.isfinite(p60)).astype(float),
        _col(df, "t_anchor"),
        _col(df, "uf_ml_kg_h"),
        _col(df, "n_prior_sessions"),
        _col(df, "dm"),
        _col(df, "age"),
        _col(df, "vintage_years"),
        _col(df, "reference_uf"),
        _col(df, "max_gap_min"),
    ]
    for r in _REGIMES:
        feats.append((df["regime"] == r).to_numpy(dtype=float)
                     if "regime" in df.columns
                     else np.zeros(len(df)))
    X = np.column_stack(feats)
    X = np.where(np.isfinite(X), X, 0.0)
    # regime × nadir-prediction cross terms: per-regime intercept/slope for
    # the dominant covariate (Task 01: taper regimes over-predict more).
    n_base = X.shape[1]
    regime_block = X[:, n_base - len(_REGIMES):]
    nadir0 = X[:, 0]  # first feature column is pred_gbdt
    X = np.column_stack([X, regime_block * nadir0[:, None]])
    return np.column_stack([np.ones(len(df)), X])


def fit(df_tune: pd.DataFrame) -> dict:
    y = pd.to_numeric(df_tune["observed_nadir"], errors="coerce").to_numpy(dtype=float)
    X = design(df_tune)
    ok = np.isfinite(y)
    coef, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
    return {"coef": coef.tolist()}


def apply(df: pd.DataFrame, model: dict) -> dict:
    coef = np.asarray(model["coef"], dtype=float)
    nadir = design(df) @ coef
    p30 = pd.to_numeric(df.get("pred_gbdt_30"), errors="coerce").to_numpy(dtype=float)
    p60 = pd.to_numeric(df.get("pred_gbdt_60"), errors="coerce").to_numpy(dtype=float)
    return {"nadir": nadir, "p30": p30, "p60": p60}
