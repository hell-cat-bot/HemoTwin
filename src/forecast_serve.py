"""Serving layer for the forecast-v2 fold-0 conditional nadir forecast.

Loads the fold-0 3-seed LightGBM dumps saved by scripts/task03_refit_nadir.py
(nadir/30/60 x seeds 42/43/44), averages the seeds, applies the dev-fold
empirical residual band from serving_band.json, and exposes:

    forecast(session_state) -> {
        "nadir_mean", "nadir_band": [lo, hi], "p30", "p60",
        "features_available", "features_missing": [names...],
        "mode": "playback_full" | "manual_limited" | None, ...}

CLAIM BOUNDARY (docs/EVIDENCE_STATUS.md, forecast-v2 entry): observational
forecasting of the later cuff-measured nadir under the observed UF
trajectory. NOT a counterfactual or treatment-effect claim, NOT a policy
engine (Task 01's kill stands), NOT a safety layer. This module is
display-only: its output must never gate, suppress, or alter the protocol
pathway (same authority semantics as the shadow risk score:
authority="display_only").

FEATURE-COMPUTABILITY RULE (the 72 FEATURES.md features, by block)
-----------------------------------------------------------------
The refit consumed 72 features built by three exact helpers:
src.features.causal_anchor_features (pre-anchor causal block + twin block),
src.features.session_history_features (strictly-earlier-session history
block), and src.actual_uf.gbdt_uf_features (observed future-UF block at the
target horizon). This module imports those helpers and calls them unchanged;
nothing is reimplemented and nothing is imputed.

(a) Retrospective playback (mode="playback_full"): the session_id resolves
    to a fold-0 row of predictions_outer_v2.parquet (the refit's own primary
    anchor set). All 72 features are computed EXACTLY as task03 did:
    causal_anchor_features on the frozen base_store.pkl session dict with the
    fold-0 twin parameters (fold_0_full_state.parquet), history from the
    frozen events table via session_history_features, and the future-UF
    block from the frozen machine log via actual_uf.oracle_future_uf at the
    substrate's t_anchor. The anchor is the substrate anchor -- the one point
    where the "observed UF trajectory" condition of the claim is genuinely
    observed and the features are the validated substrate's own inputs
    (verified bit-exact against the stored fold-0 pred_gbdt for the demo
    session). NaNs remain only where the refit row itself has NaNs (sparse
    30-minute windows: uf_var_30, sbp_std_30, sbp_std_60) -- 69/72 finite
    for the demo playback session. A playback session with no fold-0
    substrate anchor (its machine log ends before any eligible anchor +
    60 min, e.g. the second curated playback session) ABSTAINS: no
    well-posed conditional point exists, and inventing the UF condition
    would exceed the claim boundary.

(b) Fresh manual entry (mode="manual_limited"): one session, no prior
    sessions, no machine telemetry, no observed future. Session validation
    and the cuff-only reconstruction are reused from
    src.manual_console.validate_session (the same rule the shadow path
    uses); cuff times stand in for the machine log and cumulative UF is the
    established cuff-only trapezoid reconstruction. Structurally missing
    (NaN, never imputed): 6 twin parameters/state (k_pat, beta_pat,
    twin_D_now, twin_refill_Lh, twin_refill_ratio, twin_pred_nadir), 8
    history features, 13 observed future-UF features, 5 machine-telemetry
    features (blood_flow, conductivity, dia_temp, cond_dev, temp_dev) --
    i.e. at least 30 of 72 missing; ~40/72 computable. Because the
    missing-count threshold (>= MANUAL_OOD_MIN_MISSING = 10 of 72, per
    FEATURES.md) is always exceeded, every manual forecast is shown ONLY
    with the "limited-history forecast, out-of-distribution risk" label.
    The model never saw missing future-UF blocks (all training anchors had
    an observable oracle), so the manual prediction is genuinely
    out-of-distribution even though LightGBM routes NaNs natively.
    ABSTAIN (mode=None) when the minimum set cannot be computed: session
    validation fails (no current BP / no valid current UF block / invalid
    inputs), or the model artifacts are absent.

Missing features are NaN end to end -- never silently imputed.
"""
from __future__ import annotations

import json
import re
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import actual_uf as A
from . import features as F
from .manual_console import validate_session
from .paths import MODELS

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = MODELS / "forecast_v2" / "fold_0"
TASK01_DIR = MODELS / "task01"
SUBSTRATE_PARQUET = MODELS / "predictions_outer_v2.parquet"

SEEDS = (42, 43, 44)
MODEL_STEMS = {"nadir": "nadir_seed{}.txt", "30": "30_seed{}.txt",
               "60": "60_seed{}.txt"}
N_FEATURES = 72
DEV_SERVE_FOLD = 0  # fold-0 serving artifacts; only fold-0 substrate anchors are served

# A fresh manual session is shown with the out-of-distribution label when at
# least this many of the 72 FEATURES.md features are missing. Manual sessions
# structurally miss >= 30, so the label always applies there; the threshold
# exists so the rule is explicit and testable rather than implied.
MANUAL_OOD_MIN_MISSING = 10

# Feature blocks per FEATURES.md (verified against the parsed order at load).
HIST_FEATURES = ("hist_idh_rate10", "hist_mean_nadir3", "hist_mean_nadir10",
                 "hist_prev_nadir", "hist_mean_first_sbp3", "hist_early_crash10",
                 "hist_last_idh", "hist_n_sessions")
UF_BLOCK_FEATURES = ("horizon_min", "uf_future_at_h", "uf_cum_h", "uf_mean_h",
                     "uf_min_h", "uf_max_h", "uf_seg_1_15", "uf_seg_16_30",
                     "uf_seg_31_45", "uf_seg_46_60", "uf_zero_share_h",
                     "uf_reduction_ref_h", "uf_slope_60")
TWIN_FEATURES = ("k_pat", "beta_pat", "twin_D_now", "twin_refill_Lh",
                 "twin_refill_ratio", "twin_pred_nadir")
TELEMETRY_FEATURES = ("blood_flow", "conductivity", "dia_temp", "cond_dev",
                      "temp_dev")

# Fallback band, identical to serving_band.json (dev folds 0+1 TUNE half,
# residual quantiles [0.025, 0.975] of observed_nadir - pred_gbdt; EVAL-half
# coverage 0.958). Used only when the artifact file is absent so the module
# still degrades honestly on a slim checkout.
FALLBACK_BAND = (-28.922318874267432, 25.887775124267588)

MODEL_VERSION = "forecast-v2:task03/fold_0/3-seed-mean"

_MISSING_FEATURE_ORDER_FAILED = (
    "FEATURES.md feature contract missing or unreadable; refusing to serve "
    "with a guessed feature order")


def _parse_feature_order() -> list[str]:
    """Ordered 72-feature contract from the saved FEATURES.md."""
    md = (MODELS_DIR / "FEATURES.md").read_text(encoding="utf-8")
    seg = md.split("## Feature order (nadir / 60-minute models)")[1]
    seg = seg.split("## Feature order (30-minute model)")[0]
    names = [m.group(1) for m in
             (re.match(r"\d+\.\s+(\S+)\s*$", ln) for ln in seg.splitlines())
             if m]
    if len(names) != N_FEATURES or len(set(names)) != N_FEATURES:
        raise RuntimeError(_MISSING_FEATURE_ORDER_FAILED)
    return names


@lru_cache(maxsize=1)
def load_bundle() -> dict | None:
    """Load the 3-seed boosters, feature contract, calibration and band.

    Returns None when any artifact is missing/corrupt: the caller degrades to
    a "forecast unavailable" note (never blocks the protocol pathway).
    """
    try:
        order = _parse_feature_order()
        boosters = {}
        for stem, pattern in MODEL_STEMS.items():
            boosters[stem] = [
                _load_booster(MODELS_DIR / pattern.format(seed))
                for seed in SEEDS]
            if any(b is None for b in boosters[stem]):
                return None
            if any(b.num_feature() != N_FEATURES for b in boosters[stem]):
                return None
        for block in (HIST_FEATURES, UF_BLOCK_FEATURES, TWIN_FEATURES):
            if any(name not in order for name in block):
                raise RuntimeError(
                    "FEATURES.md order does not contain the expected blocks")
        band, band_source = FALLBACK_BAND, "builtin_fallback"
        band_path = MODELS_DIR / "serving_band.json"
        if band_path.exists():
            bj = json.loads(band_path.read_text(encoding="utf-8"))
            band = (float(bj["band_lo"]), float(bj["band_hi"]))
            band_source = str(band_path.name)
        calibration = {}
        calib_path = MODELS_DIR / "calibration.json"
        if calib_path.exists():
            calibration = json.loads(calib_path.read_text(encoding="utf-8"))
        return {"boosters": boosters, "features": order, "band": band,
                "band_source": band_source, "calibration": calibration}
    except Exception:  # noqa: BLE001 - absent/corrupt artifacts degrade, never crash
        return None


@lru_cache(maxsize=1)
def _load_booster(path: Path):
    import lightgbm as lgb
    try:
        return lgb.Booster(model_file=str(path))
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def _playback_context() -> dict | None:
    """Frozen fold-0 serving context: store, history table, twin state, anchors.

    Heavy (~10 s, cached for the process). Read-only over the frozen Task 01
    artifacts and the v2 substrate; nothing is written.
    """
    try:
        import pickle
        with (TASK01_DIR / "base_store.pkl").open("rb") as fh:
            store = pickle.load(fh)
        ev = pd.read_parquet(TASK01_DIR / "events_task01.parquet")
        hist = F.session_history_features(ev)
        state = pd.read_parquet(
            TASK01_DIR / "fold_0_full_state.parquet").set_index("session_id")
        v2 = pd.read_parquet(SUBSTRATE_PARQUET, columns=[
            "fold", "session_id", "t_anchor", "pred_gbdt", "pred_gbdt_30",
            "pred_gbdt_60"])
        v0 = v2[v2["fold"] == DEV_SERVE_FOLD]
        anchors = {str(r.session_id): float(r.t_anchor)
                   for r in v0.itertuples()}
        return {"store": store, "hist": hist, "state": state,
                "anchors": anchors}
    except Exception:  # noqa: BLE001
        return None


def _row_vector(values: dict, order: list[str]) -> np.ndarray:
    """72-vector in the saved feature order; absent/NaN features stay NaN."""
    out = np.full((1, len(order)), np.nan, dtype=float)
    for j, name in enumerate(order):
        v = values.get(name)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if np.isfinite(f):
            out[0, j] = f
    return out


def _ensemble_predict(bundle: dict, x: np.ndarray, stem: str) -> float:
    preds = [float(b.predict(x)[0]) for b in bundle["boosters"][stem]]
    return float(np.mean(preds))


def _finish(bundle: dict, values: dict, mode: str, anchor: float,
            reason: str | None = None, warnings_list: list[str] | None = None,
            horizon30_extra: dict | None = None) -> dict:
    """Predict all three endpoints and assemble the serving result."""
    order = bundle["features"]
    lo, hi = bundle["band"]
    x = _row_vector(values, order)
    if horizon30_extra:
        x30 = _row_vector({**values, **horizon30_extra}, order)
    else:
        x30 = x
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        nadir = _ensemble_predict(bundle, x, "nadir")
        p30 = _ensemble_predict(bundle, x30, "30")
        p60 = _ensemble_predict(bundle, x, "60")
    missing = [name for j, name in enumerate(order)
               if not np.isfinite(x[0, j])]
    result = {
        "mode": mode,
        "nadir_mean": nadir,
        "nadir_band": [nadir + lo, nadir + hi],
        "p30": p30,
        "p60": p60,
        "features_available": int(len(order) - len(missing)),
        "features_missing": missing,
        "n_features": len(order),
        "anchor_min": anchor,
        "reason": reason,
        "warnings": list(warnings_list or []),
        "band_source": bundle["band_source"],
        "model_version": MODEL_VERSION,
        "authority": "display_only",
        "calibration": (bundle["calibration"] or {}).get("calibration"),
    }
    if not all(np.isfinite(result[k]) for k in ("nadir_mean", "p30", "p60")):
        return {"mode": None, "reason": "model produced a non-finite forecast",
                "nadir_mean": None, "nadir_band": None, "p30": None, "p60": None,
                "features_available": len(order) - len(missing),
                "features_missing": missing, "n_features": len(order),
                "anchor_min": anchor, "warnings": list(warnings_list or []),
                "band_source": bundle["band_source"],
                "model_version": MODEL_VERSION,
                "authority": "display_only"}
    return result


def _abstain(reason: str, warnings_list: list[str] | None = None) -> dict:
    return {"mode": None, "reason": reason, "nadir_mean": None,
            "nadir_band": None, "p30": None, "p60": None,
            "features_available": None, "features_missing": None,
            "n_features": N_FEATURES, "anchor_min": None,
            "warnings": list(warnings_list or []),
            "band_source": None, "model_version": MODEL_VERSION,
            "authority": "display_only"}


def _playback_forecast(bundle: dict, start: dict) -> dict:
    ctx = _playback_context()
    if ctx is None:
        return _abstain("frozen fold-0 serving context unavailable")
    sid = str(start.get("session_id") or "").strip()
    anchor = ctx["anchors"].get(sid)
    if anchor is None:
        return _abstain(
            "no fold-0 substrate anchor for this session: the frozen machine "
            "log does not cover 60 minutes beyond any eligible anchor, so no "
            "well-posed conditional point under the observed UF trajectory "
            "exists for this playback session")
    d = ctx["store"].get(sid)
    if d is None:
        return _abstain("playback session not found in the frozen store")
    k_pat = beta_pat = np.nan
    strow = ctx["state"].loc[sid] if sid in ctx["state"].index else None
    if strow is not None:
        try:
            k_pat = float(strow["k_pat"])
            beta_pat = float(strow["beta_pat"])
        except (TypeError, ValueError, KeyError):
            pass
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        feat = F.causal_anchor_features(d, anchor, sid, k_pat, beta_pat)
    if not feat:
        return _abstain("no cuff at or before the anchor in the frozen session")
    hrow = ctx["hist"][ctx["hist"]["session_id"] == sid]
    hist_vals = {c: hrow.iloc[0][c] for c in HIST_FEATURES} \
        if len(hrow) == 1 else {c: np.nan for c in HIST_FEATURES}
    oracle = A.oracle_future_uf(d, anchor)
    if not oracle.get("observable"):
        return _abstain(
            "the observed UF trajectory is not covered for 60 minutes after "
            f"the anchor ({oracle.get('reason')})")
    values = dict(feat)
    values.update(hist_vals)
    values.update(A.gbdt_uf_features(oracle["future"], oracle["reference"], 60))
    h30 = A.gbdt_uf_features(oracle["future"], oracle["reference"], 30)
    return _finish(bundle, values, "playback_full", anchor,
                   horizon30_extra=h30)


def _manual_forecast(bundle: dict, start: dict, cuffs: list) -> dict:
    d, warnings_list, err = validate_session(start, cuffs)
    if err or d is None:
        # Minimum set (current BP/UF block + cuff-cadence windows) not
        # computable from this entry -> abstain entirely.
        return _abstain(f"minimum feature set not computable: {err}",
                        warnings_list)
    sid = str(d.get("session_id") or "manual_session")
    anchor = float(d["as_of_min"])
    # Cuff-only machine-log proxy: cuff times/rates stand in for the machine
    # stream; cumulative UF is the established cuff-only trapezoid
    # reconstruction (same rule as the shadow scoring path).
    store = {
        "et": d["et"], "es": d["es"], "ed": d["ed"],
        "mt": d["et"], "muf": d["cuff_uf"], "cum_uf": d["cuff_cum"],
        "dry": d["dry"], "pre": d["pre"], "goal": d["goal"],
        "age": d["age"], "sex": d["sex"], "dm": d["dm"],
        "vintage": d["vintage"],
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        feat = F.causal_anchor_features(store, anchor, sid, np.nan, np.nan)
    if not feat:
        return _abstain("no cuff at or before the scoring time",
                        warnings_list)
    values = dict(feat)
    values.update({c: np.nan for c in HIST_FEATURES})
    # No observed UF trajectory exists beyond "now" in a live manual session;
    # substituting a held rate would condition on an unobserved counterfactual,
    # so the whole future-UF block stays NaN (out-of-distribution, labelled).
    values.update({c: np.nan for c in UF_BLOCK_FEATURES})
    return _finish(bundle, values, "manual_limited", anchor,
                   warnings_list=warnings_list)


def forecast(session_state: dict) -> dict:
    """Serve the conditional forecast for one session state (display-only).

    session_state: {"start": {...sidebar start context...},
                    "cuffs": [...],
                    "source": "playback" | "manual"}
    """
    bundle = load_bundle()
    if bundle is None:
        return _abstain("forecast model artifacts unavailable")
    start = dict((session_state or {}).get("start") or {})
    cuffs = list((session_state or {}).get("cuffs") or [])
    source = str((session_state or {}).get("source") or "manual")
    if source == "playback":
        return _playback_forecast(bundle, start)
    return _manual_forecast(bundle, start, cuffs)


# ---------------------------------------------------------------------------
# exact TreeSHAP attribution (v1 product surface)
# ---------------------------------------------------------------------------

STATIC_EHR_FEATURES = ("age", "sex_M", "dm", "vintage_years", "dry_weight",
                       "pre_weight", "uf_goal_L")


def explain_forecast_drivers(features, top_k: int = 5) -> dict:
    """Exact 3-seed TreeSHAP attribution for the Forecast-v2 nadir model.

    `features` is a mapping (dict/Series) keyed by the 72-feature contract.
    Returns the top negative (downward) and positive (stabilizing) drivers
    plus per-block contribution totals in mmHg. Absent artifacts return a
    deterministic unavailable record rather than raising.
    """
    bundle = load_bundle()
    if bundle is None:
        return {"available": False,
                "reason": "forecast model artifacts unavailable"}
    names = list(bundle["features"])
    try:
        values = [float(features.get(n, np.nan))  # type: ignore[union-attr]
                  for n in names]
    except AttributeError:
        values = [np.nan] * len(names)
    x = np.asarray(values, dtype=float).reshape(1, -1)
    contribs, biases = [], []
    for booster in bundle["boosters"]["nadir"]:
        c = np.asarray(booster.predict(x, pred_contrib=True), dtype=float)[0]
        contribs.append(c[:-1])
        biases.append(c[-1])
    if not contribs:
        return {"available": False, "reason": "no nadir boosters loaded"}
    contrib = np.mean(np.vstack(contribs), axis=0)
    bias = float(np.mean(biases))
    pairs = list(zip(names, contrib))
    downward = [{"feature": n, "contribution_mmHg": float(v)}
                for n, v in sorted(pairs, key=lambda t: t[1])
                if v < 0.0][:max(int(top_k), 1)]
    stabilizing = [{"feature": n, "contribution_mmHg": float(v)}
                   for n, v in sorted(pairs, key=lambda t: -t[1])
                   if v > 0.0][:max(int(top_k), 1)]
    blocks = {
        "STATIC_EHR": STATIC_EHR_FEATURES,
        "PATIENT_HISTORY_MEMORY": tuple(HIST_FEATURES),
        "DYNAMIC_INTRA_SESSION": tuple(
            n for n in names
            if n not in STATIC_EHR_FEATURES
            and n not in HIST_FEATURES
            and n not in UF_BLOCK_FEATURES
            and n not in TELEMETRY_FEATURES),
        "FUTURE_UF_ORACLE": tuple(UF_BLOCK_FEATURES),
        "MACHINE_TELEMETRY": tuple(TELEMETRY_FEATURES),
    }
    index = {n: i for i, n in enumerate(names)}
    totals = {label: float(sum(contrib[index[n]] for n in cols
                               if n in index))
              for label, cols in blocks.items()}
    return {
        "available": True,
        "model_version": MODEL_VERSION,
        "n_seeds": int(len(contribs)),
        "prediction_mmHg": float(bias + contrib.sum()),
        "base_value_mmHg": bias,
        "top_downward": downward,
        "top_stabilizing": stabilizing,
        "block_totals_mmHg": totals,
        "primary_block_totals_mmHg": {
            k: totals[k] for k in
            ("STATIC_EHR", "PATIENT_HISTORY_MEMORY",
             "DYNAMIC_INTRA_SESSION")},
        "scope_note": ("Forecast-v2 consumes the observed future-UF block; "
                       "the oracle block total is reported separately and is "
                       "not a causal effect."),
    }


# ---------------------------------------------------------------------------
# 59-feature pre-anchor attribution (no future-UF oracle)
# ---------------------------------------------------------------------------
V4_MODELS_DIR = MODELS / "physiotwin_v4" / "models"
V4_META = MODELS / "physiotwin_v4" / "train_meta.json"


@lru_cache(maxsize=1)
def load_v4_bundle() -> dict | None:
    try:
        meta = json.loads(V4_META.read_text(encoding="utf-8"))
        names = list(meta["features"])
        boosters = [_load_booster(V4_MODELS_DIR / f"base_seed{s}.txt")
                    for s in SEEDS]
        if any(b is None or b.num_feature() != len(names) for b in boosters):
            return None
        return {"features": names, "boosters": boosters}
    except Exception:  # noqa: BLE001 - absent artifacts degrade, never crash
        return None


def explain_pre_anchor_drivers(features, top_k: int = 5) -> dict:
    """TreeSHAP attribution for the 59-feature pre-anchor v4 forecast."""
    bundle = load_v4_bundle()
    if bundle is None:
        return {"available": False,
                "reason": "v4 pre-anchor model artifacts unavailable"}
    names = bundle["features"]

    def _as_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return np.nan

    values = [_as_float(features.get(n, np.nan)) for n in names]
    x = np.asarray(values, dtype=float).reshape(1, -1)
    contribs, biases = [], []
    for booster in bundle["boosters"]:
        c = np.asarray(booster.predict(x, pred_contrib=True), dtype=float)[0]
        contribs.append(c[:-1])
        biases.append(c[-1])
    contrib = np.mean(np.vstack(contribs), axis=0)
    bias = float(np.mean(biases))
    pairs = list(zip(names, contrib))
    downward = [{"feature": n, "contribution_mmHg": float(v)}
                for n, v in sorted(pairs, key=lambda t: t[1])
                if v < 0.0][:max(int(top_k), 1)]
    stabilizing = [{"feature": n, "contribution_mmHg": float(v)}
                   for n, v in sorted(pairs, key=lambda t: -t[1])
                   if v > 0.0][:max(int(top_k), 1)]
    blocks = {
        "STATIC_EHR": tuple(STATIC_EHR_FEATURES),
        "PATIENT_HISTORY_MEMORY": tuple(HIST_FEATURES),
        "MACHINE_TELEMETRY": tuple(TELEMETRY_FEATURES),
        "TWIN_STATE": tuple(TWIN_FEATURES),
        "DYNAMIC_INTRA_SESSION": tuple(
            n for n in names
            if n not in STATIC_EHR_FEATURES
            and n not in HIST_FEATURES
            and n not in TELEMETRY_FEATURES
            and n not in TWIN_FEATURES),
    }
    index = {n: i for i, n in enumerate(names)}
    totals = {label: float(sum(contrib[index[n]] for n in cols
                               if n in index))
              for label, cols in blocks.items()}
    return {
        "available": True,
        "model_version": "physiotwin-v4.1-59f",
        "n_seeds": int(len(contribs)),
        "prediction_mmHg": float(bias + contrib.sum()),
        "base_value_mmHg": bias,
        "top_downward": downward,
        "top_stabilizing": stabilizing,
        "block_totals_mmHg": totals,
        "primary_block_totals_mmHg": {
            k: totals[k] for k in
            ("STATIC_EHR", "PATIENT_HISTORY_MEMORY",
             "DYNAMIC_INTRA_SESSION")},
        "scope_note": ("Pre-anchor 59-feature model; no future-UF oracle. "
                       "Display-only attribution; not a causal effect."),
    }
