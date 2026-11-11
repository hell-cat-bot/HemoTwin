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
def _read_vip(keep: set | None = None,
              usecols: list[str] | None = None) -> pd.DataFrame:
    """Stream the 263 MB machine table and return valid-BP telemetry rows.

    Machine channels are logged on change, so they carry last-known semantics.
    """
    all_usecols = ["pid", "datatime", "measuretime", "sbp", "dbp",
                   "dia_temp_value", "conductivity", "uf", "blood_flow", "time"]
    usecols = all_usecols if usecols is None else usecols
    all_dtypes = {"pid": "int64", "measuretime": "int32", "sbp": "float32",
                  "dbp": "float32", "dia_temp_value": "float32",
                  "conductivity": "float32", "uf": "float32",
                  "blood_flow": "float32", "time": "int16"}
    dtypes = {k: v for k, v in all_dtypes.items() if k in usecols}
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
    return vip.sort_values(["session_id", "time", "datatime"])


def _events_from_vip(vip: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """BP events with session quality filters applied.

    Telemetry repeats the last BP between cuffs, so deduplicate on the cuff
    timestamp before counting sessions.
    """
    ev = (vip.drop_duplicates(subset=["session_id", "measuretime", "time"])
             [["session_id", "pid", "date", "measuretime", "time", "sbp", "dbp"]]
             .rename(columns={"time": "t_min"}))
    ev = (ev.sort_values(["session_id", "t_min"])
            .drop_duplicates(subset=["session_id", "t_min"]))

    sess = ev.groupby("session_id", observed=True).agg(n=("sbp", "size"),
                                                       dur=("t_min", "max"))
    good = sess[(sess.n >= CONFIG["MIN_EVENTS_PER_SESSION"]) &
                (sess.dur.between(CONFIG["MIN_SESSION_MINUTES"],
                                  CONFIG["MAX_SESSION_MINUTES"]))].index
    ev = ev[ev.session_id.isin(good)].copy()
    vip = vip[vip.session_id.isin(good)].copy()
    return ev, vip


def load_events_only(n_patients: int | None = None, verbose: bool = True) -> pd.DataFrame:
    """Load only the BP event table needed for splits, labels, and flow counts.

    This is the lightweight path for Task 00: it never joins weights or
    computes any patient-level fallback, so it cannot leak future sessions
    into a prior.
    """
    t0 = time.time()
    keep = None
    if n_patients is not None:
        idp = pd.read_csv(RAW / "idp.csv", usecols=["pid"])
        rng = np.random.default_rng(CONFIG["SEED"])
        keep = set(int(x) for x in rng.choice(
            idp.pid.unique(), size=min(n_patients, len(idp)), replace=False))
    vip = _read_vip(keep, usecols=["pid", "datatime", "measuretime",
                                   "sbp", "dbp", "time"])
    ev, _ = _events_from_vip(vip)
    if verbose:
        print(f"Loaded events in {time.time()-t0:.0f}s: {len(ev):,} BP events | "
              f"{ev.session_id.nunique():,} sessions | {ev.pid.nunique():,} patients")
    return ev


def load_machine_only(keep: set | None = None,
                      verbose: bool = True) -> pd.DataFrame:
    """Load machine channels without any BP/cuff QC filter.

    Task 01 needs the observed UF intervention to be independent of cuff
    validity. Rows with a valid timestamp and a finite UF in [0, 6] L/h are
    retained; no SBP/DBP filter is applied. The result carries raw machine
    records, not an interpolated series.
    """
    t0 = time.time()
    usecols = ["pid", "datatime", "time", "uf", "blood_flow",
               "conductivity", "dia_temp_value"]
    dtypes = {"pid": "int64", "time": "int16", "uf": "float32",
              "blood_flow": "float32", "conductivity": "float32",
              "dia_temp_value": "float32"}
    chunks = []
    for ch in pd.read_csv(RAW / "vip.csv", usecols=usecols, dtype=dtypes,
                          parse_dates=["datatime"], chunksize=1_000_000):
        if keep is not None:
            ch = ch[ch.pid.isin(keep)]
        uf = pd.to_numeric(ch.uf, errors="coerce")
        ch = ch[uf.notna() & uf.between(0.0, 6.0)]
        if len(ch):
            chunks.append(ch)
    vip = pd.concat(chunks, ignore_index=True)
    del chunks
    vip["pid"] = vip.pid.astype(str)
    vip["date"] = vip.datatime.dt.normalize()
    vip["session_id"] = vip.pid + "_" + vip.date.dt.strftime("%Y-%m-%d")
    vip = vip.sort_values(["session_id", "time", "datatime"])
    if verbose:
        print(f"Loaded machine-only UF in {time.time()-t0:.0f}s: "
              f"{len(vip):,} records | {vip.session_id.nunique():,} sessions")
    return vip


def load_tables(n_patients: int | None = None, verbose: bool = True) -> dict:
    """Load and clean HEMOBP. Returns events, telemetry, factors, patients.

    Corrected semantics: `dry_weight`, `pre_weight`, and `uf_goal_L` are
    session-sheet values only. No all-session patient median is computed here.
    Call `resolve_weights(..., fit_pids=...)` inside a fold before building a
    model store.
    """
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

    vip = _read_vip(keep)
    ev, vip = _events_from_vip(vip)

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
    ev["pre_weight_sess"] = ev.pre_weight
    ev["uf_goal_session_L"] = ev.uf_goal_L
    ev["dry_weight"] = ev.dry_weight_sess
    ev["pre_weight"] = ev.pre_weight_sess
    ev["uf_goal_L"] = ev.uf_goal_session_L
    ev["uf_goal_source"] = np.where(
        ev.dry_weight_sess.notna() & ev.pre_weight_sess.notna(),
        "session", "unresolved")

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


def resolve_weights(ev: pd.DataFrame, fit_pids: set[str]) -> pd.DataFrame:
    """Resolve dry/pre weight and the weight-derived UF goal causally.

    Precedence for each session:
      1. session-sheet measurement (matched within +/-1 day),
      2. median of the same patient's strictly earlier measured sessions,
      3. median over fit-role patients only (never all patients),
      4. missing.

    The fit-population median is computed from session-sheet measurements of
    fit patients only. Same-patient earlier sessions are a causal
    personalization rule, not development fitting.
    """
    pids = {str(p) for p in fit_pids}
    cols = ["pid", "session_id", "date", "dry_weight_sess", "pre_weight_sess"]
    missing = [c for c in cols if c not in ev.columns]
    if missing:
        raise KeyError(f"resolve_weights needs columns {missing}")
    sess = (ev[cols].drop_duplicates("session_id").copy())
    sess["pid"] = sess.pid.astype(str)
    sess["date"] = pd.to_datetime(sess.date)
    sess = sess.sort_values(["pid", "date", "session_id"])

    fit_rows = sess[sess.pid.isin(pids)]
    pop_dry = float(fit_rows.dry_weight_sess.median()) if fit_rows.dry_weight_sess.notna().any() else np.nan
    pop_pre = float(fit_rows.pre_weight_sess.median()) if fit_rows.pre_weight_sess.notna().any() else np.nan

    out = []
    for pid, g in sess.groupby("pid", sort=False):
        prior_dry: list[float] = []
        prior_pre: list[float] = []
        for row in g.itertuples(index=False):
            dry_raw = _f(row.dry_weight_sess)
            pre_raw = _f(row.pre_weight_sess)
            dry = dry_raw
            pre = pre_raw
            used_prior = False
            used_pop = False
            if not np.isfinite(dry):
                if prior_dry:
                    dry = float(np.median(prior_dry))
                    used_prior = True
                elif np.isfinite(pop_dry):
                    dry = pop_dry
                    used_pop = True
            if not np.isfinite(pre):
                if prior_pre:
                    pre = float(np.median(prior_pre))
                    used_prior = True
                elif np.isfinite(pop_pre):
                    pre = pop_pre
                    used_pop = True
            if np.isfinite(dry_raw):
                prior_dry.append(dry_raw)
            if np.isfinite(pre_raw):
                prior_pre.append(pre_raw)

            if np.isfinite(dry_raw) and np.isfinite(pre_raw):
                source = "session"
            elif used_prior:
                source = "prior_patient"
            elif used_pop:
                source = "fit_population"
            elif np.isfinite(dry) and np.isfinite(pre):
                source = "fit_population"
            else:
                source = "missing"

            goal = np.nan
            if np.isfinite(dry) and np.isfinite(pre) and dry > 20 and pre > 0:
                goal = max(pre - dry, 0.0)
                if goal <= 0.3:
                    goal = np.nan
            out.append({
                "session_id": row.session_id,
                "pid": pid,
                "dry_weight": dry,
                "pre_weight": pre,
                "uf_goal_L": goal,
                "weight_source": source,
            })
    return pd.DataFrame(out)


def build_session_store(tables: dict, weights: pd.DataFrame | None = None) -> dict:
    """Per-session numpy arrays + static factors, for fast causal feature extraction.

    If `weights` is supplied, it must come from `resolve_weights` and supplies
    causal dry/pre/goal values. Without it, only session-sheet values are used
    and missing sessions stay missing (no all-patient fallback).
    """
    ev, vip = tables["events"], tables["telemetry"]
    w = None
    if weights is not None:
        w = weights.set_index("session_id")
    store: dict[str, dict] = {}

    grp = ev.groupby("session_id", observed=True)
    for sid, g in grp:
        g = g.sort_values("t_min")
        row = g.iloc[0]
        et = g.t_min.to_numpy(float)
        if w is not None and sid in w.index:
            wr = w.loc[sid]
            dry, pre, goal = _f(wr.dry_weight), _f(wr.pre_weight), _f(wr.uf_goal_L)
            wsrc = str(wr.weight_source)
        else:
            dry, pre, goal = _f(row.dry_weight), _f(row.pre_weight), _f(row.uf_goal_L)
            wsrc = str(row.get("uf_goal_source", "unresolved"))
        store[sid] = dict(
            et=et,
            es=g.sbp.to_numpy(float),
            ed=g.dbp.to_numpy(float),
            age=_f(row.age), sex=str(row.sex), dm=_f(row.dm),
            vintage=_f(row.vintage_years),
            dry=dry, pre=pre, goal=goal, weight_source=wsrc,
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
        d["uf_first_min"] = float(mt[0]) if len(mt) else np.nan
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
