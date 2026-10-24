"""End-to-end training: data -> labels -> features -> event model -> twin -> demo bundle.

Usage:
    python scripts/train.py                # full cohort (~15-25 min on CPU)
    python scripts/train.py --patients 300 # quick smoke test
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import data, features as F, labels as L, model as M, twin as T  # noqa: E402
from src.bundle import build_bundle  # noqa: E402
from src.config import ARTIFACTS, CONFIG, DEMO  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=None)
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--demo-sessions", type=int, default=8)
    ap.add_argument("--reuse-features", action="store_true",
                    help="reuse cached feature frames from artifacts/cache")
    args = ap.parse_args()

    t_start = time.time()
    print("=" * 78)
    print("HemoTwin — training pipeline")
    print(f"label: first IDH (nadir SBP<90) onset in (t+{CONFIG['HORIZON_LO']}, "
          f"t+{CONFIG['HORIZON_HI']}] minutes")
    print("=" * 78)

    if not args.no_download:
        print("\n[1/7] data")
        data.download()
    else:
        print("\n[1/7] data (skipped download)")

    print("\n[2/7] load + join session weights")
    tables = data.load_tables(n_patients=args.patients)
    tables["session_store"] = data.build_session_store(tables)
    print(f"  session store: {len(tables['session_store']):,} sessions")

    print("\n[3/7] anchors + patient-disjoint split")
    anch = L.build_anchors(tables["events"])
    tr, va, te = L.patient_level_split(anch)
    tr = L.cap_train_negatives(tr)

    print("\n[4/7] features")
    t0 = time.time()
    cache = ARTIFACTS / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    cpath = {k: cache / f"{k}.parquet" for k in ("tr", "va", "te")}
    if args.reuse_features and all(p.exists() for p in cpath.values()):
        Ftr = pd.read_parquet(cpath["tr"])
        Fva = pd.read_parquet(cpath["va"])
        Fte = pd.read_parquet(cpath["te"])
        print("  loaded cached feature frames")
    else:
        Ftr = F.make_tabular_features(tables, tr)
        Fva = F.make_tabular_features(tables, va)
        Fte = F.make_tabular_features(tables, te)
        for k, f in (("tr", Ftr), ("va", Fva), ("te", Fte)):
            f.to_parquet(cpath[k], index=False)
    feats = F.feature_columns(Ftr)
    print(f"  {len(feats)} features ready in {time.time()-t0:.0f}s")
    print("  prevalence train/val/test: %.4f / %.4f / %.4f"
          % (Ftr.label.mean(), Fva.label.mean(), Fte.label.mean()))

    print("\n[5/7] event model")
    booster, iso, cal = M.train(Ftr, Fva, Fte, feats)
    rep, p_raw, p_cal = M.evaluate(booster, iso, Fte, feats, cal["threshold"])

    # keep the test predictions so the operating point can be re-tuned without retraining
    preds = Fte[["session_id", "pid", "t_min", "onset_min", "label"]].copy()
    preds["score"] = p_cal
    preds.to_parquet(ARTIFACTS / "predictions_test.parquet", index=False)

    # ---- honest event-level metrics on the SAME window as the labels ----
    evd = L.event_level_detection(Fte, p_cal, cal["threshold"])
    ppv = L.session_level_ppv(Fte, p_cal, cal["threshold"])
    r1, r2 = F.rule_baselines(Fte)
    from src.metrics import full_report
    base1 = full_report(Fte.label.values, r1, Fte.pid.values)
    base2 = full_report(Fte.label.values, r2, Fte.pid.values)

    print(f"\n  AUROC {rep['auroc']:.3f} [{rep['auroc_ci'][0]:.3f}-{rep['auroc_ci'][1]:.3f}] | "
          f"AUPRC {rep['auprc']:.3f} ({rep['lift']:.1f}x)")
    print(f"  sens@spec90 {rep['sens_at_spec90']:.3f} | "
          f"R1 {base1['sens_at_spec90']:.3f} | R2 {base2['sens_at_spec90']:.3f}")
    print(f"  event detection: {evd['detected']}/{evd['n_idh_sessions']} = "
          f"{100*evd['detection_rate_all_sessions']:.1f}% of all IDH sessions "
          f"({100*evd['detection_rate_evaluable']:.1f}% of {evd['detected']+evd['missed']} evaluable)")
    print(f"  false-alarm session rate: {100*evd['false_alarm_session_rate']:.1f}%")
    print(f"  session-level PPV: {100*ppv['session_ppv']:.1f}% "
          f"({ppv['sessions_flagged']:,} sessions flagged)")

    M.save(booster, iso, feats, cal, rep)

    # ---- twin layer ----
    print("\n[6/7] twin layer")
    store = tables["session_store"]
    train_sids = list(pd.Series(tr.session_id.unique()))
    test_sids = list(pd.Series(te.session_id.unique()))
    rng = np.random.default_rng(CONFIG["SEED"])
    pop_sample = list(rng.choice(train_sids, size=min(8000, len(train_sids)), replace=False))
    pop = T.fit_population(store, pop_sample)
    print(f"  population k_refill {pop['k_refill']:.2f}/h "
          f"(IQR {pop.get('k_iqr', [np.nan, np.nan])[0]:.2f}-{pop.get('k_iqr', [np.nan, np.nan])[1]:.2f}) | "
          f"beta_bp {pop['beta_bp']:.1f} mmHg/L")

    res_sample = list(rng.choice(test_sids, size=min(2500, len(test_sids)), replace=False))
    band = T.residual_quantiles(store, res_sample, pop)
    print(f"  hold-policy nadir error: MAE {band.get('mae', float('nan')):.1f} mmHg "
          f"| 5-95% residual {band.get('lo', float('nan')):+.1f} to {band.get('hi', float('nan')):+.1f}")

    vol_sample = list(rng.choice(test_sids, size=min(20000, len(test_sids)), replace=False))
    vol = T.volume_check(store, vol_sample)
    print(f"  volume check: modelled vs measured UF, median diff "
          f"{vol.get('median_difference_L', float('nan')):+.2f} L, "
          f"MAE {vol.get('mae_L', float('nan')):.2f} L, "
          f"{100*vol.get('within_0_5L_share', 0):.0f}% within 0.5 L")

    # ---- demo bundle ----
    print("\n[7/7] demo bundle")
    bundle = build_bundle(tables, Fte, p_cal, booster, feats, pop, band, vol,
                          rep, evd, ppv, base1, base2, cal, args.demo_sessions)
    out = DEMO / "demo_bundle.json"
    out.write_text(json.dumps(bundle, indent=2))
    print(f"  {len(bundle['chairs'])} sessions -> {out}")

    report = {
        "test": rep, "event_level": evd, "session_ppv": ppv,
        "baselines": {"r1": base1, "r2": base2},
        "calibration": cal, "twin": {"population": pop, "band": band, "volume": vol},
        "runtime_seconds": time.time() - t_start,
    }
    (ARTIFACTS / "train_report.json").write_text(json.dumps(report, indent=2, default=float))
    print(f"\nDone in {(time.time()-t_start)/60:.1f} min.")


if __name__ == "__main__":
    main()
