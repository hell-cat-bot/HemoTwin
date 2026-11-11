# INTEGRATION — session-risk & crash-shape (crashrisk/)

How to recreate everything from the raw data, and how to wire the risk
card into earlier versions of HemoTwin (v1 `app/manual_app.py`, the v2
console `app/hemotwin.py`). Display-only everywhere: this is an
**observational pre-session risk stratifier**, never a treatment
recommendation.

## 1. What ships

| Artifact | Path | Purpose |
|---|---|---|
| Booster (LightGBM text) | `crashrisk/models/session_risk_booster.txt` | trained on TUNE only (pid-odd sessions of folds 0+1; fold 2 never in any fit) |
| Metadata + Platt + medians | `crashrisk/models/session_risk_meta.json` | feature list (incl. missing indicators), TUNE medians for imputation, Platt (a, b), provenance + confirm numbers |
| Scoring entry point | `crashrisk/src/serve.py::score_session` | dict of feature values → `risk_probability` + band + claim text |

Measured, honest numbers (pre-registered gates, fold 2 = untouched
patients, one read): dev EVAL recall@25 **0.7222** / AUROC **0.8866**;
fold-2 confirm recall@25 **0.6755** / AUROC **0.8788** / PPV@25 **0.6639**
/ ECE10 0.0332. Day-before variant (history features only, no starting-BP
anchor): fold-2 AUROC 0.8290, recall@25 0.6024.

## 2. Recreate from raw data (order matters)

Prereqs: the frozen substrates must exist (they are inputs, never
modified): `artifacts/review_20261108/predictions_outer_v2.parquet`,
`artifacts/review_20261108/hist_features_v3.parquet`,
`artifacts/review_20261108/cuff_scores.parquet` (universal tier),
`artifacts/review_20261107/task01/events_task01.parquet` (shape label
only). Those come from the v1 pipeline (`scripts/task01_build.py`,
`scripts/task05_memory_refit.py`, `scripts/build_cuff_scores.py`) on the
HEMOBP dataset; on a fresh clone without `artifacts/`, run those first.

```bash
# 1) assemble the per-session pre-start table (deterministic join; writes
#    crashrisk/evidence/sessions_table.parquet; sha recorded on first bench use)
python crashrisk/src/assemble.py

# 2) frozen benchmark: trains on TUNE, evaluates on EVAL, prints METRIC lines
#    (primary crash_recall_at_25; baselines B1 no-skill and B2 clinical prior)
bash .auto/measure.sh            # segment 11 = risk
#    (internally: python crashrisk/scripts/bench_sessionrisk.py)

# 3) one-read fold-2 confirm (pre-registered gates; run once at milestone)
python crashrisk/scripts/confirm_fold2_risk.py

# 4) serving bundle (booster + Platt + medians + meta)
python crashrisk/src/serve.py

# 5) pins: leakage surface, bundle provenance, monotonicity, Platt shape
python -m pytest crashrisk/tests/test_crashrisk.py -q
#    (or run the test functions directly; pytest may not be installed)
```

To recreate the *substrates themselves* from raw data (older machine /
earlier repo state): `python scripts/task01_build.py` →
`python scripts/task05_memory_refit.py` (needs `task03_refit_nadir.py`
for `predictions_outer_v2.parquet`) → `python scripts/build_cuff_scores.py`.
Sequence and intermediates are documented in `experiment.md` and
`docs/EVIDENCE_STATUS.md`.

## 3. Integrate into earlier software versions

### v2 console (`v2/app/hemotwin.py` → Live session view)

1. Copy `crashrisk/models/*` and `crashrisk/src/serve.py` into the v2 tree
   (v2 keeps its own `src/`; adjust `serve.py` imports to v2's paths).
2. In the Live session view, before the first cuff entry, render a card:

```python
from src.serve import score_session   # after copying into v2/src/
risk = score_session(feature_dict_from_session_state)
st.markdown(f"**Pre-session risk (observational): {risk['band']}** — "
            f"{risk['risk_probability']:.0%} historical crash probability. "
            "Display-only; not a recommendation.")
```

3. Feature sources in the v2 form: history features need the patient's
   prior-session summary (the same fields the Case Lab archetype cards
   show: prior IDH rate, prior nadir, weight gain, interdialytic interval);
   `sbp_anchor` = the session's starting BP field; `uf_ml_kg_h`/`uf_goal_L`
   = the prescription fields; `dm/age/vintage_years/sex_M/dry_weight` =
   the static patient block. Missing values are fine — the bundle imputes
   from stored TUNE medians and flags them.
4. Keep the claim text from `meta["claim"]` on the card verbatim.

### v1 manual app (`app/manual_app.py`)

Same pattern at session start (before the protocol pathway panel). The
risk card must NOT gate, suppress, or reorder any protocol step or alert:
it is an informational readout next to the existing display-only forecast.

### What must NOT be done (claim boundary)

- No treatment recommendation, no UF adjustment advice, no alarm from this
  score (it does not enter the alert policy or any gate).
- No counterfactual claim ("if you change X, risk drops by Y") — the model
  is observational; prescription features encode clinician behavior.
- No silent retraining: any retrain must re-run the fold discipline
  (train TUNE, confirm fold 2 once) and re-record gates.

## 4. Reliability statement (what "works" means here)

Pre-registered before measurement: gates on patient-disjoint dev halves
(recall@25 ≥ 0.40, AUROC ≥ 0.65, beat the clinical-prior baseline by ≥5pp,
calibration Brier/ECE bounds), then ONE read of the untouched confirm
fold with its own gate (recall@25 ≥ 0.38, AUROC ≥ 0.63, calibration
bounds). All passed (see `crashrisk/evidence/confirm_fold2_risk.json`).
Leakage audit: history features verified time-shifted (100.00% agreement
with prior-session events on 37,752 sessions); no post-start column in
the 31-column surface; strength survives feature pruning (day-before
variant 0.83 AUROC). Known limits: population = the 38,143-session
fold-managed census of the HEMOBP data; crash defined as timeline
SBP<90 (frozen task01/02 definition); 391 first-sessions lack history
(imputed with indicators).

## 5. Timing companion (segment 12, crash shape)

`crashrisk/models/session_shape_booster.txt` + `session_shape_meta.json`
score **P(early onset < 90 min | crash)** with `serve.py::
score_session_shape()` (same feature dict as the risk card). Deployed as
the second line of the pre-session card:

```python
shape = score_session_shape(feature_dict)
# risk['risk_probability'] high + shape['timing'] == 'front-loaded (first 90 min)'
#   -> front-load the watch window: tighter early cuff cadence, saline at hand
# high risk + 'final-hour profile' -> keep the final-hour ramp under watch
```

Confirmed on untouched fold-2 crashes: AUROC 0.7716, PPV@25 0.6615
(baseline prior-early-crash-rate 0.7006). Display-only planning guidance;
the claim text from the bundle meta must be shown verbatim. **Rate-drift
envelope (12b, descriptive):** the timing BAND is stable (100.00% of
sessions keep their band) across synthetic early-rates 0.20-0.45;
calibration holds (ECE <= 0.06) for unit early-rates 0.24-0.36 and
degrades beyond; enrichment over the unit base rate stays ~1.8-2.0x
throughout — display the enrichment, not an absolute PPV, and keep the
footnote ("probabilities are directional when the unit early-crash mix
differs"). To recreate: same pipeline as section 2 with
`bash .auto/measure.sh` (segment 12 runs `--task shape`) and
`python crashrisk/scripts/confirm_fold2_shape.py`; the envelope lives in
`session_shape_meta.json` under `rate_drift_envelope`.
