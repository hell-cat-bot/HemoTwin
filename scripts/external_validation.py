"""Two-country transport check.

The Spanish cohort (Mendeley Dialysis Database) records one pre- and one post-
dialysis BP per session -- there is no time series. So it cannot validate a
15-60 minute event model. What it *can* do is test whether a session-level model
built on the features both cohorts share transports across countries.

We report this as a reduced-feature transport check, not as validation of the
event model. If the number is poor, that is the honest finding and it is
reported as such.

Usage:
    python scripts/external_validation.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import data  # noqa: E402
from src.config import ARTIFACTS, CONFIG  # noqa: E402

MEND = ROOT / "data" / "raw" / "mendeley_dataset_1.csv"

SHARED = ["age", "sex_M", "dry_weight", "pre_sbp", "uf_rate_Lh", "dia_temp"]


# ---------------------------------------------------------------------------
def session_table(tables: dict) -> pd.DataFrame:
    """One row per HEMOBP session, restricted to features Spain also has."""
    ev = tables["events"]
    store = tables["session_store"]
    rows = []
    for sid, g in ev.groupby("session_id", observed=True):
        d = store.get(sid)
        if d is None:
            continue
        g = g.sort_values("t_min")
        rows.append({
            "session_id": sid,
            "pid": g.pid.iloc[0],
            "age": d["age"],
            "sex_M": float(d["sex"] == "M"),
            "dm": d["dm"],
            "dry_weight": d["dry"],
            "pre_sbp": float(g.sbp.iloc[0]),
            "uf_rate_Lh": float(np.nanmean(d["muf"])) if len(d["muf"]) else np.nan,
            "dia_temp": d["temp_presc"] if d["temp_presc"] == d["temp_presc"] else float(np.nanmedian(d["mdt"])),
            "nadir": float(g.sbp.min()),
            "is_idh": int(g.sbp.min() < CONFIG["IDH_SBP_THRESHOLD"]),
        })
    return pd.DataFrame(rows)


def mendeley_table() -> pd.DataFrame:
    if MEND.exists():
        df = pd.read_csv(MEND, sep=";")
    else:
        z = zipfile.ZipFile(ROOT / "data" / "raw" / "dataset_1.zip")
        raw = z.open("dataset_1.csv").read().decode("utf-8", errors="replace")
        rows = list(csv.reader(io.StringIO(raw), delimiter=";"))
        hdr = rows[0]
        data_rows = []
        for r in rows[1:]:
            if len(r) == len(hdr) + 1 and r[-1] == "":
                r = r[:-1]
            if len(r) == len(hdr):
                data_rows.append(r)
        df = pd.DataFrame(data_rows, columns=hdr)

    for c in df.columns:
        df[c] = pd.to_numeric(df[c].replace({"SI": 1, "NO": 0, "": np.nan}),
                              errors="coerce")

    out = pd.DataFrame({
        "age": df.D_Edad,
        "sex_M": (df.D_Sexo == 1).astype(float),   # Spanish coding: 1 = man, 2 = woman
        "dry_weight": df.D_PesoSeco.where(df.D_PesoSeco > 20),
        "pre_sbp": df.D_TAS.where(df.D_TAS > 60),
        "uf_rate_Lh": df.D_UF.where(df.D_UF >= 0),
        "dia_temp": df.D_TemperaturaBano.where(df.D_TemperaturaBano > 30),
        "is_idh": df.D_Hipotension,
    })
    out = out[out.is_idh.notna()]
    return out


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    x = df[SHARED].copy()
    x["dry_weight"] = x.dry_weight.where(x.dry_weight.between(25, 250))
    x["pre_sbp"] = x.pre_sbp.where(x.pre_sbp.between(50, 280))
    x["uf_rate_Lh"] = x.uf_rate_Lh.where(x.uf_rate_Lh.between(0, 4))
    x["dia_temp"] = x.dia_temp.where(x.dia_temp.between(33, 41))
    x["age"] = x.age.where(x.age.between(15, 100))
    return x


def main() -> None:
    print("=" * 74)
    print("Two-country transport check (reduced feature set)")
    print("=" * 74)

    data.download()
    tables = data.load_tables()
    tables["session_store"] = data.build_session_store(tables)

    cache = ARTIFACTS / "hemobp_session_table.parquet"
    if cache.exists():
        hem = pd.read_parquet(cache)
        print(f"loaded cached HEMOBP session table: {len(hem):,}")
    else:
        hem = session_table(tables)
        hem.to_parquet(cache, index=False)
        print(f"cached HEMOBP session table -> {cache}")
    print(f"\nHEMOBP sessions: {len(hem):,} | IDH prevalence {100*hem.is_idh.mean():.1f}%")

    rng = np.random.default_rng(CONFIG["SEED"])
    pids = np.asarray(hem.pid.unique(), dtype=object)
    rng.shuffle(pids)
    n_test = int(0.2 * len(pids))
    test_p = set(pids[:n_test])
    tr = hem[~hem.pid.isin(test_p)]
    te = hem[hem.pid.isin(test_p)]
    print(f"  train {len(tr):,} / internal test {len(te):,} sessions")

    Xtr, ytr = _clean(tr), tr.is_idh.values
    Xte, yte = _clean(te), te.is_idh.values

    params = dict(objective="binary", learning_rate=0.03, num_leaves=15,
                  min_child_samples=100, feature_fraction=0.9,
                  bagging_fraction=0.9, bagging_freq=1, verbosity=-1,
                  seed=CONFIG["SEED"], metric="auc")
    ds = lgb.Dataset(Xtr, label=ytr)
    model = lgb.train(params, ds, num_boost_round=400)

    p_int = model.predict(Xte)
    auc_int = roc_auc_score(yte, p_int)
    print(f"  internal (HEMOBP held-out patients): AUROC {auc_int:.3f}")

    mend = mendeley_table()
    print(f"\nMendeley sessions: {len(mend):,} | IDH prevalence {100*mend.is_idh.mean():.1f}%")
    Xm = _clean(mend)
    ok = Xm.notna().sum(axis=1) >= 3
    Xm, ym = Xm[ok], mend.is_idh.values[ok]
    p_m = model.predict(Xm)
    auc_ext = roc_auc_score(ym, p_m)
    print(f"  external (Spain, reduced features): AUROC {auc_ext:.3f}  (n={len(ym):,})")

    # --- direction replication: same sign of association in both cohorts? ---
    rep = []
    for col in SHARED:
        try:
            a_h = roc_auc_score(hem.is_idh.values, hem[col].fillna(hem[col].median()))
            a_m = roc_auc_score(ym, Xm[col].fillna(Xm[col].median()))
            rep.append({
                "feature": col,
                "hemobp_auc": round(float(a_h), 3),
                "mendeley_auc": round(float(a_m), 3),
                "same_direction": bool((a_h - 0.5) * (a_m - 0.5) > 0),
            })
        except Exception:  # noqa: BLE001
            continue

    print("\n  univariate association, both cohorts (AUROC; 0.5 = no signal):")
    for r in rep:
        print(f"    {r['feature']:14s} HEMOBP {r['hemobp_auc']:.3f} | "
              f"Spain {r['mendeley_auc']:.3f} | same direction: {r['same_direction']}")

    out = {
        "task": "session-level IDH, reduced shared feature set",
        "features": SHARED,
        "hemobp": {"n": int(len(hem)), "prevalence": float(hem.is_idh.mean()),
                   "internal_auroc": float(auc_int), "internal_n": int(len(te))},
        "mendeley": {"n": int(len(ym)), "prevalence": float(ym.mean()),
                     "external_auroc": float(auc_ext)},
        "direction_replication": rep,
        "interpretation": (
            "The Spanish cohort has one pre and one post BP per session, so this "
            "checks feature transport, not the 15-60 minute event model."
        ),
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "external_validation.json").write_text(json.dumps(out, indent=2))
    print(f"\n  saved -> {ARTIFACTS / 'external_validation.json'}")


if __name__ == "__main__":
    main()
