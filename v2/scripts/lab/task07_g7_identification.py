"""Task 07 — G7 non-reactive UF step-down identification experiment.

Stages:
  census   : Stage 0 feasibility, power gate, diagnostics; writes g7_report.json
  estimate : matched FE-DR, negative controls, P6a/P6b, final verdict

The protocol is frozen in artifacts/physiotwin_v4/g7_protocol.md and its
SHA-256 is recorded in g7_report.json. Fold 2 is never used for estimation or
matching.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.paths import ARTIFACTS  # noqa: E402
from src.physiotwin_v4 import (  # noqa: E402
    counterfactual_batch, estimate_patient_posterior_params, params_to_batch,
    segments_to_minutes,
)
from src.session_twin import g7_identification as G  # noqa: E402

TASK01 = ARTIFACTS / "review_20261107" / "task01"
OUT = ARTIFACTS / "physiotwin_v4"
TABLE = OUT / "anchor_table.parquet"
PROTOCOL = OUT / "g7_protocol.md"
HASH_FILE = OUT / "g7_protocol.sha256"
CACHE = OUT / "g7_cache.pkl"
REPORT = OUT / "g7_report.json"

INTERV_REGIMES = ("moderate", "aggressive", "pause")
TAPER_REGIMES = ("moderate", "aggressive")
MIN_DEV_EVENTS = 200
MIN_DEV_PATIENTS = 50
MIN_FOLD2_EVENTS = 50
MDE_GATE_ASSOC = 2.50
MDE_GATE_PRODUCT = 1.50

_T0 = time.time()


def log(msg: str) -> None:
    print(f"[{(time.time() - _T0) / 60:6.1f} min] {msg}", flush=True)


def _protocol_hash() -> str:
    return hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()


def _load_store():
    log("loading base_store.pkl ...")
    with (TASK01 / "base_store.pkl").open("rb") as fh:
        return pickle.load(fh)


def _table_maps(tab: pd.DataFrame):
    fold_by_pid = (tab.groupby("pid")["fold"].agg(lambda s: int(s.iloc[0]))
                   .to_dict())
    first = (tab.sort_values(["pid", "t_anchor"])
                .groupby("pid", as_index=False).first())
    prior_by_pid = {
        str(r.pid): {
            "n_prior_sessions": int(r.n_prior_sessions),
            "k_pat": float(r.k_pat),
            "beta_pat": float(r.beta_pat),
        } for r in first.itertuples(index=False)
    }
    anchors = {}
    for sid, grp in tab.sort_values("t_anchor").groupby("session_id"):
        row = grp.iloc[0]
        anchors[str(sid)] = {
            "t_anchor": float(row["t_anchor"]),
            "sbp_anchor": float(row["sbp_anchor"]),
            "regime": str(row["regime"]),
            "fold": int(row["fold"]),
            "pid": str(row["pid"]),
            "n_prior_sessions": int(row["n_prior_sessions"]),
            "k_pat": float(row["k_pat"]),
            "beta_pat": float(row["beta_pat"]),
        }
    return fold_by_pid, prior_by_pid, anchors


def _params_for(d, pid: str, anchor_row: dict | None,
                prior_by_pid: dict):
    row = {
        "age": d.get("age", np.nan),
        "dm": d.get("dm", 0.0),
        "dry_weight": d.get("dry", np.nan),
        "pre_weight": d.get("pre", np.nan),
    }
    if anchor_row is not None:
        row.update(n_prior_sessions=anchor_row["n_prior_sessions"],
                   k_pat=anchor_row["k_pat"],
                   beta_pat=anchor_row["beta_pat"])
    else:
        p = prior_by_pid.get(pid, {})
        row.update(n_prior_sessions=p.get("n_prior_sessions", 0),
                   k_pat=p.get("k_pat", np.nan),
                   beta_pat=p.get("beta_pat", np.nan))
    return estimate_patient_posterior_params(row)


def _has_step(d, t_min: float = 30.0) -> bool:
    mt, muf = G.dedupe_machine(d.get("mt", []), d.get("muf", []))
    end = G.session_end(d)
    for st in G.uf_steps(mt, muf, end):
        dose = st["prev"] - st["new"]
        if (0.20 - 1e-9 <= dose <= 0.80 + 1e-9
                and st["t"] >= t_min - 1e-9
                and st["held_until"] - st["t"] >= 30.0 - 1e-9):
            return True
    return False


def _patient_step_times(d, sid: str, t_min: float = 30.0):
    mt, muf = G.dedupe_machine(d.get("mt", []), d.get("muf", []))
    end = G.session_end(d)
    out = []
    for st in G.uf_steps(mt, muf, end):
        dose = st["prev"] - st["new"]
        if (0.20 - 1e-9 <= dose <= 0.80 + 1e-9
                and st["t"] >= t_min - 1e-9
                and st["held_until"] - st["t"] >= 30.0 - 1e-9):
            out.append((sid, float(st["t"])))
    return out


def _scan_at_anchor(d, sid: str, pid: str, fold: int, t_a: float,
                    sbp_a: float, params) -> list[G.Event]:
    et, es = G._finite_arrays(d.get("et", []), d.get("es", []))
    mt, muf = G.dedupe_machine(d.get("mt", []), d.get("muf", []))
    end = G.session_end(d)
    if len(et) < 2 or len(mt) < 2 or not np.isfinite(end):
        return []
    stab = G.pre_stability(et, es, t_a)
    if stab is None or not stab["ok"]:
        return []
    oh0 = G.session_oh0(d)
    out = []
    for st in G.uf_steps(mt, muf, end):
        dose = st["prev"] - st["new"]
        if not (0.20 - 1e-9 <= dose <= 0.80 + 1e-9):
            continue
        if abs(st["t"] - t_a) > 2.0:
            continue
        if st["held_until"] - st["t"] < 30.0 - 1e-9:
            continue
        deltas = G.outcome_deltas(et, es, st["t"], stab["sbp_now"],
                                  st["held_until"], None, held_min=45)
        if deltas.get(30) is None:
            continue
        out.append(G.Event(
            session_id=sid, pid=pid, fold=fold, t_anchor=t_a,
            t_e=float(st["t"]), u_prev=float(st["prev"]),
            u_new=float(st["new"]), dose_l_h=float(dose),
            dose_units=float(dose / G.DOSE_UNIT),
            held_until=float(st["held_until"]),
            sbp_now=stab["sbp_now"], sbp_min=stab["sbp_min"],
            slope=stab["slope"], last_change=stab["last_change"],
            n_cuffs=stab["n_cuffs"],
            cum_uf_l=G.cumulative_uf(d, st["t"]), oh0_l=oh0,
            deltas=deltas,
            pre_change=G.pre_change(et, es, st["t"], stab["sbp_now"]),
            anchor_aligned=True,
        ))
    return out


def census(limit_patients: int | None = None) -> dict:
    tab = pd.read_parquet(TABLE)
    fold_by_pid, prior_by_pid, anchors = _table_maps(tab)
    if limit_patients:
        keep = set(list(fold_by_pid)[:int(limit_patients)])
        fold_by_pid = {k: v for k, v in fold_by_pid.items() if k in keep}
        log(f"SMOKE limit: {len(fold_by_pid)} patients")
    store = _load_store()

    dev_events: list[G.Event] = []
    dev_controls: list[G.Control] = []
    fold2_events: list[G.Event] = []
    fold2_at_anchor: list[G.Event] = []
    step_rows: dict[str, list[tuple[str, float]]] = {}
    patient_dev_sessions: dict[str, int] = {}
    n_sessions = {"dev": 0, "fold2": 0}
    n_sessions_with_step = {"dev": 0, "fold2": 0}
    n1_any_step = 0
    n2_events = 0
    n3_events = 0

    for sid, d in store.items():
        pid = str(sid).split("_")[0]
        fold = fold_by_pid.get(pid)
        if fold is None:
            continue
        if limit_patients and pid not in fold_by_pid:
            continue
        a = anchors.get(str(sid))
        t_a = None if a is None else float(a["t_anchor"])
        params = _params_for(d, pid, a, prior_by_pid)
        if fold in (0, 1):
            n_sessions["dev"] += 1
            patient_dev_sessions[pid] = patient_dev_sessions.get(pid, 0) + 1
            has = _has_step(d)
            n_sessions_with_step["dev"] += int(has)
            n1_any_step += int(has)
            step_rows.setdefault(pid, []).extend(
                _patient_step_times(d, str(sid)))
            evs_all = G.scan_step_events(
                d, str(sid), pid, fold, t_a, anchor_mode=(t_a is not None),
                t_max=120.0, require_stable=False)
            evs = [e for e in evs_all if e.is_stable]
            ctrls = G.scan_controls(
                d, str(sid), pid, fold, t_a, anchor_mode=(t_a is not None),
                t_max=120.0)
            n2_events += len(evs_all)
            n3_events += len(evs)
            dev_events.extend(evs)
            dev_controls.extend(ctrls)
        elif fold == 2:
            n_sessions["fold2"] += 1
            has = _has_step(d)
            n_sessions_with_step["fold2"] += int(has)
            if t_a is not None:
                evs = G.scan_step_events(
                    d, str(sid), pid, fold, t_a, anchor_mode=True)
                fold2_events.extend(evs)
                fold2_at_anchor.extend(_scan_at_anchor(
                    d, str(sid), pid, fold, t_a, a["sbp_anchor"], params))

    log(f"scanned: dev sessions {n_sessions['dev']:,} | "
        f"fold2 sessions {n_sessions['fold2']:,}")
    log(f"dev events {len(dev_events):,} | controls {len(dev_controls):,} | "
        f"fold2 events {len(fold2_events):,} | fold2 at-anchor "
        f"{len(fold2_at_anchor):,}")

    # E1a classification (unique sessions with a step within +/-10 min).
    for ev in dev_events:
        rows = step_rows.get(ev.pid, [])
        near = {s for s, t in rows if abs(t - ev.t_e) <= 10.0}
        n_pat_sessions = max(patient_dev_sessions.get(ev.pid, 1), 1)
        ev.is_e1a = bool(len(near) >= 3 and len(near) / n_pat_sessions >= 0.5)

    controls_by_pid: dict[str, list[G.Control]] = {}
    for c in dev_controls:
        controls_by_pid.setdefault(c.pid, []).append(c)

    pairs = G.match_pairs(dev_events, controls_by_pid, horizon=30)
    log(f"matched pairs at +30: {len(pairs):,} "
        f"({len({p['pid'] for p in pairs})} patients)")

    # ODE stress denominator for matched events only.
    ev_by_key = {(e.session_id, round(e.t_e, 3)): e for e in dev_events}
    for pair in pairs:
        ev = ev_by_key.get((pair["session_id"], round(pair["t_e"], 3)))
        if ev is None:
            continue
        d = store.get(pair["session_id"])
        a = anchors.get(pair["session_id"])
        if d is None:
            continue
        params = _params_for(d, pair["pid"], a, prior_by_pid)
        ev.dh = G.event_dh(d, ev, params)
        pair["dh"] = ev.dh.get(30)
        pair["dh15"] = ev.dh.get(15)
        pair["dh45"] = ev.dh.get(45)

    # P6a: fold-2 pre-anchor events with ODE stress and outcomes.
    f2_by_key = {(e.session_id, round(e.t_e, 3)): e for e in fold2_events}
    for ev in fold2_events:
        d = store.get(ev.session_id)
        a = anchors.get(ev.session_id)
        if d is None:
            continue
        params = _params_for(d, ev.pid, a, prior_by_pid)
        ev.dh = G.event_dh(d, ev, params)

    # Outcome availability and power.
    avail = {h: int(sum(1 for e in dev_events
                        if e.deltas.get(h) is not None))
             for h in G.HORIZON_MINUTES}
    f2_avail = {h: int(sum(1 for e in fold2_events
                           if e.deltas.get(h) is not None))
                for h in G.HORIZON_MINUTES}
    outcomes = np.asarray([p["outcome"] for p in pairs], dtype=float)
    pids = np.asarray([p["pid"] for p in pairs], dtype=object)
    power = G.mde_power(outcomes, pids, len(pairs))
    n4a = int(sum(1 for p in pairs if p.get("e1a")))
    n4b = int(len(pairs) - n4a)

    # Temporal-ordering diagnostic on the 397 G3 intervention rows.
    g3 = tab[(tab.fold == 2) & tab.regime.isin(INTERV_REGIMES)]
    order_counts: dict[str, int] = {}
    cuff_counts = {0: 0, 1: 0, 2: 0}
    for r in g3.itertuples(index=False):
        d = store.get(str(r.session_id))
        if d is None:
            continue
        diag = G.temporal_order_diagnostic(
            d, float(r.t_anchor), float(r.sbp_anchor))
        order_counts[diag["class"]] = order_counts.get(diag["class"], 0) + 1
        nc = int(diag["n_cuffs"])
        cuff_counts[0 if nc == 0 else 1 if nc == 1 else 2] += 1

    stage0_ok = bool(
        len(pairs) >= MIN_DEV_EVENTS
        and len({p["pid"] for p in pairs}) >= MIN_DEV_PATIENTS
        and np.isfinite(power["mde80"]) and power["mde80"] <= MDE_GATE_ASSOC)
    product_power_ok = bool(stage0_ok and np.isfinite(power["mde80"])
                            and power["mde80"] <= MDE_GATE_PRODUCT)
    report = {
        "protocol_sha256": _protocol_hash(),
        "generated": "2026-11-09",
        "stage": "census",
        "stage0": {
            "n_sessions": n_sessions,
            "n_sessions_with_step": n_sessions_with_step,
            "n1_any_step_sessions": int(n1_any_step),
            "n2_pre_window_events": int(n2_events),
            "n3_stability_events": int(n3_events),
            "n4_matched_events": int(len(pairs)),
            "n4_patients": int(len({p["pid"] for p in pairs})),
            "n4a_e1a": n4a,
            "n4b_e1b": n4b,
            "n_control_candidates": int(len(dev_controls)),
            "outcome_availability": avail,
            "fold2_events": int(len(fold2_events)),
            "fold2_outcome_availability": f2_avail,
            "fold2_at_anchor_events": int(len(fold2_at_anchor)),
            "power": power,
            "stage0_ok": stage0_ok,
            "product_power_ok": product_power_ok,
            "gates": {
                "n4_ge_200": bool(len(pairs) >= MIN_DEV_EVENTS),
                "patients_ge_50": bool(len({p["pid"] for p in pairs})
                                       >= MIN_DEV_PATIENTS),
                "mde_le_2_5": bool(np.isfinite(power["mde80"])
                                   and power["mde80"] <= MDE_GATE_ASSOC),
                "mde_le_1_5": bool(np.isfinite(power["mde80"])
                                   and power["mde80"] <= MDE_GATE_PRODUCT),
            },
        },
        "temporal_order": {
            "n_g3_rows": int(len(g3)),
            "classes": order_counts,
            "cuff_density": {
                "zero": cuff_counts[0], "one": cuff_counts[1],
                "two_or_more": cuff_counts[2],
            },
        },
        "verdict": ("POWERED" if stage0_ok else "INCONCLUSIVE"),
        "claim": ("Stage 0 only. No effect estimate is adopted until the "
                  "estimate stage."),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with CACHE.open("wb") as fh:
        pickle.dump({
            "stage0": report["stage0"],
            "dev_events": dev_events,
            "dev_controls": dev_controls,
            "pairs": pairs,
            "fold2_events": fold2_events,
            "fold2_at_anchor": fold2_at_anchor,
            "prior_by_pid": prior_by_pid,
            "anchors": {k: v for k, v in anchors.items()},
        }, fh)
    log(f"wrote {REPORT} and {CACHE}")
    log(f"stage0_ok={stage0_ok} | product_power_ok={product_power_ok} | "
        f"MDE80={power['mde80']:.2f} mmHg | pairs={len(pairs)}")
    return report


def _mae_delta(y, pred, base, pids, n_boot=1000, seed=20261109):
    y = np.asarray(y, float)
    pred = np.asarray(pred, float)
    base = np.asarray(base, float)
    pids = np.asarray(pids, object)
    e_pred = np.abs(pred - y)
    e_base = np.abs(base - y)
    delta = float(e_pred.mean() - e_base.mean())
    groups = {p: np.where(pids == p)[0] for p in np.unique(pids)}
    rng = np.random.default_rng(seed)
    boots = np.empty(int(n_boot), float)
    for b in range(int(n_boot)):
        samp = rng.choice(list(groups), size=len(groups), replace=True)
        idx = np.concatenate([groups[p] for p in samp])
        boots[b] = float(e_pred[idx].mean() - e_base[idx].mean())
    boots = boots[np.isfinite(boots)]
    return {
        "delta_mae": delta,
        "ci95": ([float(np.quantile(boots, 0.025)),
                  float(np.quantile(boots, 0.975))]
                 if len(boots) else [float("nan"), float("nan")]),
        "n": int(len(y)),
        "n_patients": int(len(groups)),
        "pass": bool(delta < 0.0 and len(boots)
                     and np.quantile(boots, 0.975) < 0.0),
    }


def estimate() -> dict:
    if not CACHE.exists():
        raise SystemExit("Run --stage census first.")
    with CACHE.open("rb") as fh:
        cache = pickle.load(fh)
    stage0 = cache["stage0"]
    base_report = json.loads(REPORT.read_text(encoding="utf-8"))
    if not stage0.get("stage0_ok"):
        base_report["verdict"] = "INCONCLUSIVE"
        base_report["claim"] = (
            "Stage 0 minimums were not met; the clean-event sample is too "
            "small to test the UF-to-SBP mechanism.")
        REPORT.write_text(json.dumps(base_report, indent=2), encoding="utf-8")
        return base_report

    store = _load_store()
    anchors = {str(k): v for k, v in cache["anchors"].items()}
    prior_by_pid = cache["prior_by_pid"]
    pairs = cache["pairs"]

    # Primary + sensitivity pairs (horizons). dH is already attached in census.
    fit30 = G.fit_fe_dr(pairs, "dose_units", "outcome")
    boot30 = G.bootstrap_slope(pairs, "dose_units", "outcome")
    fit_gamma = G.fit_fe_dr(pairs, "dh", "outcome")
    boot_gamma = G.bootstrap_slope(pairs, "dh", "outcome")
    pre_pairs = [p for p in pairs if p.get("pre_change") is not None]
    fit_pre = G.fit_fe_dr(pre_pairs, "dose_units", "pre_change")
    boot_pre = G.bootstrap_slope(pre_pairs, "dose_units", "pre_change")

    # Sham time: 30-min change on matched control sessions, pseudo-event at
    # t_c-15, tested against 0 with a patient-clustered bootstrap.
    sham_rows = []
    seen_sessions = set()
    for c in cache["dev_controls"]:
        if c.session_id in seen_sessions:
            continue
        d = store.get(c.session_id)
        if d is None:
            continue
        et, es = G._finite_arrays(d.get("et", []), d.get("es", []))
        a = G.nearest_cuff(et, es, c.t_c - 15.0, 10.0)
        b = G.nearest_cuff(et, es, c.t_c + 15.0, 10.0)
        if a is None or b is None:
            continue
        seen_sessions.add(c.session_id)
        sham_rows.append({"pid": c.pid, "value": float(b[1] - a[1])})
    sham_mean = (float(np.mean([r["value"] for r in sham_rows]))
                 if sham_rows else float("nan"))
    sham_ci = [float("nan"), float("nan")]
    if len(sham_rows) >= 10:
        rng = np.random.default_rng(20261109)
        vals = np.asarray([r["value"] for r in sham_rows], float)
        pids = np.asarray([r["pid"] for r in sham_rows], object)
        groups = {p: np.where(pids == p)[0] for p in np.unique(pids)}
        boots = np.empty(1000, float)
        for b in range(1000):
            samp = rng.choice(list(groups), size=len(groups), replace=True)
            idx = np.concatenate([groups[p] for p in samp])
            boots[b] = float(vals[idx].mean())
        sham_ci = [float(np.quantile(boots, 0.025)),
                   float(np.quantile(boots, 0.975))]

    gamma_plug = (float(fit30["slope"] / np.nanmean(
        [p["dh"] / p["dose_units"] for p in pairs
         if p.get("dh") is not None and p["dose_units"] > 0]))
        if pairs and np.isfinite(fit30["slope"]) else float("nan"))
    gamma_e1 = float(fit_gamma["slope"])
    gamma_use = (gamma_e1 if np.isfinite(gamma_e1) and gamma_e1 > 0
                 else 0.0)

    # P6a: out-of-sample fold-2 pre-anchor trajectory change.
    f2 = cache["fold2_events"]
    p6a = {}
    for h, dh_key in ((15, "dh15"), (30, "dh"), (45, "dh45")):
        rows = []
        for ev in f2:
            if ev.deltas.get(h) is None or not ev.dh.get(h):
                continue
            rows.append({
                "pid": ev.pid,
                "y": float(ev.deltas[h]),
                "pred": float(gamma_use * ev.dh[h]),
            })
        if not rows:
            p6a[h] = {"status": "INCONCLUSIVE", "n": 0}
            continue
        if len(rows) < MIN_FOLD2_EVENTS:
            p6a[h] = {"status": "INCONCLUSIVE", "n": int(len(rows))}
            continue
        y = np.asarray([r["y"] for r in rows], float)
        pred = np.asarray([r["pred"] for r in rows], float)
        pids = np.asarray([r["pid"] for r in rows], object)
        res = _mae_delta(y, pred, np.zeros_like(y), pids)
        res["status"] = ("PASS" if res["pass"] else "FAIL")
        p6a[h] = res

    # P6b: fold-2 at-anchor fan branches. Uses the table row's state and
    # expected/actual UF segments.
    tab = pd.read_parquet(TABLE)
    pred = pd.read_parquet(OUT / "fold2_predictions.parquet")
    seg_cols = ["uf_seg_1_15", "uf_seg_16_30", "uf_seg_31_45",
                "uf_seg_46_60"]
    exp_cols = [f"exp_{c}" for c in seg_cols]
    merged = tab.merge(
        pred[["session_id", "t_anchor", "base_pred"] + exp_cols],
        on=["session_id", "t_anchor"], how="left")
    row_by_sid = (merged.sort_values("t_anchor").groupby("session_id")
                      .first().to_dict("index"))
    p6b = {}
    for h in (15, 30, 45):
        rows = []
        for ev in cache["fold2_at_anchor"]:
            sid = ev.session_id
            d = store.get(sid)
            r = row_by_sid.get(sid)
            if d is None or r is None:
                continue
            et, es = G._finite_arrays(d.get("et", []), d.get("es", []))
            target = float(r["t_anchor"]) + h
            c = G.nearest_cuff(et, es, target, 12.5)
            if c is None:
                continue
            params = estimate_patient_posterior_params(r)
            actual_seg = np.asarray([r[c] for c in seg_cols], float)
            exp_seg = np.asarray([r[c] for c in exp_cols], float)
            if not (np.all(np.isfinite(actual_seg))
                    and np.all(np.isfinite(exp_seg))):
                continue
            state0 = {"D": np.array([r["D0"]]), "R": np.array([r["R0"]]),
                      "C": np.array([r["C0"]]), "OH": np.array([r["OH0"]])}
            pdict = params_to_batch([params])
            uf_exp = segments_to_minutes(exp_seg)[None, :]
            uf_act = segments_to_minutes(actual_seg)[None, :]
            terms = counterfactual_batch(
                state0, pdict, np.array([r["sbp_anchor"]]),
                np.array([r["base_pred"]]), uf_exp, uf_act)
            curve0 = terms["B"][0]
            curve1 = (terms["B"][0] - gamma_use
                      * (terms["dh_policy"][0] - terms["dh_expected"][0]))
            rows.append({"pid": ev.pid, "y": float(c[1]),
                         "pred0": float(curve0[h]),
                         "pred1": float(curve1[h])})
        if len(rows) < MIN_FOLD2_EVENTS:
            p6b[h] = {"status": "INCONCLUSIVE", "n": int(len(rows))}
            continue
        y = np.asarray([r["y"] for r in rows], float)
        p0 = np.asarray([r["pred0"] for r in rows], float)
        p1 = np.asarray([r["pred1"] for r in rows], float)
        pids = np.asarray([r["pid"] for r in rows], object)
        res = _mae_delta(y, p1, p0, pids)
        res["status"] = ("PASS" if res["pass"] else "FAIL")
        p6b[h] = res

    tau = float(fit30["slope"])
    tau_ci = boot30["ci95"]
    controls_ok = bool(
        np.isfinite(fit_pre["slope"]) and abs(fit_pre["slope"]) < 1.0
        and boot_pre["ci95"][0] <= 0.0 <= boot_pre["ci95"][1]
        and (not np.isfinite(sham_ci[0]) or sham_ci[0] <= 0.0 <= sham_ci[1]))
    association = bool(
        tau > 0 and tau_ci[0] > 0 and controls_ok)
    p6a30 = p6a.get(30, {})
    p6a_pass = bool(p6a30.get("status") == "PASS")
    p6a_incon = bool(p6a30.get("status") == "INCONCLUSIVE")
    p6b30 = p6b.get(30, {})
    p6b_pass = bool(p6b30.get("status") == "PASS")
    p6b_incon = bool(p6b30.get("status") == "INCONCLUSIVE")
    if not association:
        verdict = "FAIL"
    elif tau < 1.50 or not p6a_pass:
        verdict = "STATISTICAL_ASSOCIATION_ONLY"
    elif p6b_pass:
        verdict = "PRODUCT_GRADE_PASS"
    else:
        verdict = "MECHANISM_PASS" if not p6b_incon else "MECHANISM_PASS"
    claim = {
        "PRODUCT_GRADE_PASS": (
            "Associational decision support for UF-policy review, "
            "conditioned on pre-event stability, with uncertainty. Not causal."),
        "MECHANISM_PASS": (
            "Out-of-sample validated associational trajectory correction; "
            "the anchor-branch fan remains an illustration."),
        "STATISTICAL_ASSOCIATION_ONLY": (
            "A small statistical association was detected; it is not used "
            "for decisions."),
        "INCONCLUSIVE": (
            "The clean-event sample is too small to test the mechanism."),
        "FAIL": (
            "The non-reactive step-down experiment did not support a "
            "positive effect."),
    }[verdict]

    report = {
        **{k: v for k, v in base_report.items()
           if k not in {"verdict", "claim", "stage"}},
        "stage": "estimate",
        "estimates": {
            "tau30_per_0.25_l_h": fit30,
            "tau30_bootstrap": boot30,
            "tau_pre": fit_pre,
            "tau_pre_bootstrap": boot_pre,
            "sham": {"mean": sham_mean, "ci95": sham_ci,
                     "n_sessions": int(len(sham_rows))},
            "gamma_struct": fit_gamma,
            "gamma_struct_bootstrap": boot_gamma,
            "gamma_plug": gamma_plug,
            "controls_pass": controls_ok,
        },
        "p6a_fold2_trajectory": p6a,
        "p6b_fold2_anchor_fan": p6b,
        "verdict": verdict,
        "claim": claim,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"tau30={tau:.3f} CI {tau_ci} | gamma={gamma_e1:.3f} | "
        f"P6a={p6a30.get('status')} | P6b={p6b30.get('status')} | "
        f"verdict={verdict}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="census",
                    choices=("census", "estimate"))
    ap.add_argument("--limit-patients", type=int, default=None)
    args = ap.parse_args()
    if args.stage == "census":
        census(args.limit_patients)
    else:
        estimate()
