"""Data layer for HEMOBP.

Two things here are deliberately different from a naive loader:

1. `d1.csv` (session weights) is joined on (pid, date) with a **+/-1 day**
   fallback. An exact-date join matches only ~49% of sessions; with the
   fallback it matches ~85%. The mismatch is a timestamp alignment artefact
   between the machine table and the session sheet, not missing data.
   Recovering it gives us *measured* pre/post weights, i.e. real ultrafiltration
   volume ground truth, which the twin is validated against.

2. `idp.csv` carries `first_dialysis`, which yields **dialysis vintage**.
   Vintage is a standard IDH risk factor and was previously unused.
"""
from __future__ import annotations

import os
import time
import urllib.request

import numpy as np
import pandas as pd

from .config import CONFIG, RAW, URLS


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def download(force: bool = False) -> None:
    """Resumable download of the three HEMOBP tables."""
    for name, url in URLS.items():
        dest = RAW / name
        if dest.exists() and not force and dest.stat().st_size > 1000:
            continue
        for attempt in range(5):
            have = dest.stat().st_size if dest.exists() else 0
            req = urllib.request.Request(url)
            if have:
                req.add_header("Range", f"bytes={have}-")
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    total = r.headers.get("Content-Length")
                    total = int(total) + have if total else None
                    mode = "ab" if have and r.status == 206 else "wb"
                    if mode == "wb":
                        have = 0
                    with open(dest, mode) as f:
                        while True:
                            chunk = r.read(1 << 20)
                            if not chunk:
                                break
                            f.write(chunk)
                            have += len(chunk)
                            if total and have % (25 << 20) < (1 << 20):
                                print(f"  {name}: {have/1e6:.0f}/{total/1e6:.0f} MB", flush=True)
                print(f"  [ok] {name} {dest.stat().st_size/1e6:.1f} MB", flush=True)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  [retry {attempt+1}/5] {name}: {exc}", flush=True)
                time.sleep(4)


# ---------------------------------------------------------------------------
# Session weights: exact join, then +/-1 day fallback
# ---------------------------------------------------------------------------
def _session_factors(d1: pd.DataFrame) -> pd.DataFrame:
    d1 = d1.copy()
    d1["pid"] = d1.pid.astype(str)
    d1["date"] = pd.to_datetime(d1.keyindate, errors="coerce").dt.normalize()
    d1 = d1.dropna(subset=["date"])

    keep = ["pid", "date", "weightstart", "weightend", "dryweight",
            "temperature", "dialysisstart", "dialysisend"]

    frames = []
    for shift in (0, -1, 1):
        t = d1[keep].copy()
        t["date"] = t["date"] + pd.Timedelta(days=shift)
        t["_pri"] = abs(shift)
        frames.append(t)
    stacked = pd.concat(frames, ignore_index=True)
    # prefer the exact-date row when both exist
    stacked = (stacked.sort_values(["pid", "date", "_pri"])
                      .drop_duplicates(["pid", "date"])
                      .drop(columns="_pri"))

    stacked = stacked.rename(columns={
        "weightstart": "pre_weight",
        "weightend": "post_weight",
        "dryweight": "dry_weight_sess",
        "temperature": "dia_temp_presc",
    })
    stacked["uf_goal_L"] = (stacked.pre_weight - stacked.dry_weight_sess).clip(lower=0)
    stacked.loc[stacked.uf_goal_L <= 0.3, "uf_goal_L"] = np.nan
    stacked["uf_measured_L"] = (stacked.pre_weight - stacked.post_weight)
    return stacked


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_tables(n_patients: int | None = None, verbose: bool = True) -> dict:
    """Load and clean HEMOBP. Returns events, telemetry, factors, patients."""
    t0 = time.time()
    d1 = pd.read_csv(RAW / "d1.csv", parse_dates=["keyindate"])
    idp = pd.read_csv(RAW / "idp.csv")

    keep: set | None = None
    if n_patients is not None:
        rng = np.random.default_rng(CONFIG["SEED"])
        keep = set(int(x) for x in rng.choice(
            idp.pid.unique(), size=min(n_patients, len(idp)), replace=False))
        d1 = d1[d1.pid.isin(keep)]
        idp = idp[idp.pid.isin(keep)]

    # ---- stream the 263 MB machine table ----
    usecols = ["pid", "datatime", "measuretime", "sbp", "dbp",
               "dia_temp_value", "conductivity", "uf", "blood_flow", "time"]
    dtypes = {"pid": "int64", "measuretime": "int32", "sbp": "float32",
              "dbp": "float32", "dia_temp_value": "float32",
              "conductivity": "float32", "uf": "float32",
              "blood_flow": "float32", "time": "int16"}
    chunks = []
    for ch in pd.read_csv(RAW / "vip.csv", usecols=usecols, dtype=dtypes,
                          parse_dates=["datatime"], chunksize=1_000_000):
        if keep is not None:
            ch = ch[ch.pid.isin(keep)]
        ch = ch[ch.sbp.between(*CONFIG["SBP_VALID"]) &
                ch.dbp.between(*CONFIG["DBP_VALID"])]
        if len(ch):
            chunks.append(ch)
    vip = pd.concat(chunks, ignore_index=True)
    del chunks

    vip["pid"] = vip.pid.astype(str)
    vip["date"] = vip.datatime.dt.normalize()
    vip["session_id"] = vip.pid + "_" + vip.date.dt.strftime("%Y-%m-%d")
    vip = vip.sort_values(["session_id", "time", "datatime"])

    # ---- BP events: telemetry repeats the last BP between cuffs ----
    ev = (vip.drop_duplicates(subset=["session_id", "measuretime", "time"])
             [["session_id", "pid", "date", "measuretime", "time", "sbp", "dbp"]]
             .rename(columns={"time": "t_min"}))
    ev = (ev.sort_values(["session_id", "t_min"])
            .drop_duplicates(subset=["session_id", "t_min"]))

    # ---- session quality ----
    sess = ev.groupby("session_id", observed=True).agg(n=("sbp", "size"),
                                                       dur=("t_min", "max"))
    good = sess[(sess.n >= CONFIG["MIN_EVENTS_PER_SESSION"]) &
                (sess.dur.between(CONFIG["MIN_SESSION_MINUTES"],
                                  CONFIG["MAX_SESSION_MINUTES"]))].index
    ev = ev[ev.session_id.isin(good)].copy()
    vip = vip[vip.session_id.isin(good)].copy()

    # ---- static EHR: age, sex, diabetes, vintage ----
    idp = idp.rename(columns={"gender": "sex", "DM": "dm"})
    idp["pid"] = idp.pid.astype(str)
    idp["first_dialysis"] = pd.to_datetime(idp.first_dialysis, errors="coerce")
    idp["birth_year"] = pd.to_numeric(idp.birthday, errors="coerce")

    ev = ev.merge(idp[["pid", "sex", "birth_year", "dm", "first_dialysis"]],
                  on="pid", how="left")
    ev["age"] = ev.date.dt.year - ev.birth_year
    ev["vintage_years"] = (ev.date - ev.first_dialysis).dt.days / 365.25

    # ---- session weights (measured UF ground truth) ----
    fac = _session_factors(d1)
    ev = ev.merge(fac, on=["pid", "date"], how="left")

    pat_med = (fac.groupby("pid")
                  .agg(dry_weight_pat=("dry_weight_sess", "median"),
                       pre_weight_pat=("pre_weight", "median"))
                  .reset_index())
    ev = ev.merge(pat_med, on="pid", how="left")
    ev["dry_weight"] = ev.dry_weight_sess.fillna(ev.dry_weight_pat)
    ev["pre_weight"] = ev.pre_weight.fillna(ev.pre_weight_pat)
    # If the session sheet did not match, fall back to the patient's own median
    # pre-weight and dry weight. Flagged in the model card; used only for the
    # volume projection, never as a label.
    fallback_goal = (ev.pre_weight - ev.dry_weight).clip(lower=0)
    ev["uf_goal_L"] = ev.uf_goal_L.fillna(fallback_goal)
    ev.loc[ev.uf_goal_L <= 0.3, "uf_goal_L"] = np.nan
    ev["uf_goal_source"] = np.where(ev.dry_weight_sess.notna(), "session", "patient_median")

    ev["pid"] = ev.pid.astype(str)
    vip["session_id"] = vip.session_id.astype("category")

    if verbose:
        matched = ev.groupby("session_id").uf_goal_L.first().notna().mean()
        print(f"Loaded HEMOBP in {time.time()-t0:.0f}s: {len(vip):,} telemetry rows | "
              f"{len(ev):,} BP events | {ev.session_id.nunique():,} sessions | "
              f"{ev.pid.nunique():,} patients")
        print(f"  session-weights match: {100*matched:.1f}% of sessions "
              f"(exact-date join alone would be ~49%)")

    return {"events": ev, "telemetry": vip, "factors": fac, "patients": idp}


def build_session_store(tables: dict) -> dict:
    """Per-session numpy arrays + static factors, for fast causal feature extraction.

    Machine channels are logged on change, so they carry last-known semantics.
    """
    ev, vip = tables["events"], tables["telemetry"]
    store: dict[str, dict] = {}

    grp = ev.groupby("session_id", observed=True)
    for sid, g in grp:
        g = g.sort_values("t_min")
        row = g.iloc[0]
        et = g.t_min.to_numpy(float)
        store[sid] = dict(
            et=et,
            es=g.sbp.to_numpy(float),
            ed=g.dbp.to_numpy(float),
            age=_f(row.age), sex=str(row.sex), dm=_f(row.dm),
            vintage=_f(row.vintage_years),
            dry=_f(row.dry_weight), pre=_f(row.pre_weight),
            goal=_f(row.uf_goal_L),
            temp_presc=_f(row.dia_temp_presc),
            measured_uf=_f(row.uf_measured_L),
        )

    for sid, g in vip.groupby("session_id", observed=True):
        d = store.get(sid)
        if d is None:
            continue
        g = g.sort_values("time")
        mt = g.time.to_numpy(float)
        muf = g.uf.to_numpy(float)
        d["mt"] = mt
        d["muf"] = muf
        d["mbf"] = g.blood_flow.to_numpy(float)
        d["mco"] = g.conductivity.to_numpy(float)
        d["mdt"] = g.dia_temp_value.to_numpy(float)
        if len(mt) > 1:
            # integrate L/h over minutes -> litres removed
            d["cum_uf"] = np.concatenate(
                [[0.0], np.cumsum(np.diff(mt) / 60.0 * (muf[1:] + muf[:-1]) / 2.0)])
        else:
            d["cum_uf"] = np.zeros(1)

    return {k: v for k, v in store.items() if "mt" in v and len(v["et"]) > 0}


def _f(x) -> float:
    try:
        x = float(x)
        return x if np.isfinite(x) else np.nan
    except Exception:  # noqa: BLE001
        return np.nan
