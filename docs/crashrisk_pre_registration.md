# PRE-REGISTRATION — crashrisk (segments 11-12)

Frozen before any measurement on 2026-11-11 (mirrored from the ledger's
charter .auto/prompt.md; the ledger is the source of truth). Metric gates,
baselines, and the fold discipline were fixed before the first benchmark
run; the one amendment (imputation vs complete-case) was made BEFORE any
metric was observed and is documented below.

# SESSION-RISK CHARTER (2026-11-11 morning, owner directive)

Owner (awake, verbatim intent): lack of continuous HR is the major data
drawback (confirmed); new work = (1) session-level crash-risk BEFORE
session start, (2) crash-shape (early vs late onset), in a SEPARATE folder
with an integration.md (recreate + integrate even into earlier software
versions); work in loops until reliable given clinical needs; no cheating.
Alert campaign (segments 8-10) stays closed; its adopted alerter is final.

## Segment 11 pre-registration: session-risk (crashrisk/ folder)

UNIVERSE: the fold-managed 38,143-session substrate (predictions_outer_v2
fold manifest; verified patient-disjoint: 0 overlap between folds 0/1/2;
crash rate 0.211/0.186/0.246 by fold). Label: session_event==1 (frozen
task01/02 definition: session timeline first crosses SBP<90). 391 sessions
lack history features (first sessions) — complete-case drop, reported.
SPLIT: TUNE = pid-odd within folds 0+1 (train + calibration fit); EVAL =
pid-even (all reported dev metrics); fold 2 = confirmatory only, ONE read
at milestone.

FEATURES (pre-registered, strictly pre-start/at-anchor — leakage surface):
(a) the 21 hist_features_v3 history aggregates; (b) static/prescription:
dm, sex_M, age, vintage_years, uf_ml_kg_h, dry_weight, pre_weight,
uf_goal_L, n_prior_sessions; (c) variant B adds sbp_anchor (start-of-
session BP, known at the chair). EXCLUDED on timing grounds (uncertain
in-session availability, per the regime-oracle precedent): regime,
max_gap_min, t_anchor, all pred_* columns, twin params (k/beta).
Variant A = (a)+(b) history-only (computable the day before) — secondary
readout; variant B = (a)+(b)+(c) — PRIMARY (actionable at the chair).

MODEL: LightGBM, single pre-registered config (no search): 200 trees,
31 leaves, lr 0.05, min_child 100, feature_fraction 0.9, class_weight
balanced, seed 11. Platt calibration fit on 5-fold CV out-of-fold TUNE
predictions (deterministic seed 11). Determinism: full retrain rerun
compared exactly.

METRIC (primary, higher): crash_recall_at_25 = fraction of true crash
sessions inside the top-25%-by-predicted-risk referral set on EVAL
(25% referral = the campaign's accepted burden precedent).
SECONDARIES (reported): auroc, ppv_at_25, brier_cal, ece10_cal.

BASELINES (pre-registered, referral-matched on EVAL):
B1 no-skill: recall@25 = 0.25.
B2 clinical prior: score = hist_last_idh (prior session crashed) — same
referral count as the model's 25%; model must beat it.
FAMILY VERDICT (dev): proceed to fold-2 confirm iff EVAL recall@25 >= 0.40
AND auroc >= 0.65 AND recall@25 beats B2 by >= 5pp AND auroc beats B2's
AUROC by >= 0.05 AND calibration holds (brier_cal < brier of the
constant base-rate predictor on EVAL, ece10_cal <= 0.05); else measured
negative, log + close (iterate only on NEW pre-registered changes).
FOLD-2 GATE (one read, pre-registered): recall@25 >= 0.38 AND auroc >=
0.63 AND brier_cal < base-rate brier AND ece10_cal <= 0.06. PASS => the
model + serving bundle ship in crashrisk/ with INTEGRATION.md and the
claim boundary gains an OBSERVATIONAL PRE-SESSION RISK DISPLAY entry
(display-only, not a recommendation). FAIL => reported honestly, model
stays research-only.

SEGMENT 12 (queued, separate pre-registration after 11 settles): crash
shape — among crash sessions, predict early onset (onset < 90 min;
population n~5,060 dev). Baseline B: hist_early_crash10. Same split +
calibration discipline. AUROC gates: dev >= 0.62 (beat baseline + 0.05),
fold-2 >= 0.59.

Code under test: crashrisk/ (self-contained; reads frozen substrates read-
only; writes its own evidence/ outputs). .auto/measure.sh re-frozen for
segment 11 (new benchmark; new segment => sanctioned). The root alert
ledger continues (single audit trail).

