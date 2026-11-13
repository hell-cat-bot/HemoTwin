# Evidence status — authoritative claim boundary

**Date:** 2026-11-11. **V2 package:** one console, five views; 235 package
tests (0 failures; the heavy-artifact skip count is 18 in this workspace, 28 in
the lean package, 6 with the full portable data/artifact pack); claim-boundary
verifier 14/14; G7 frozen and failed. The full lab suite in the research
workspace is 241 tests.
The fifth view, Chair board, is a separate pre-session risk surface and does not
change the G1–G7 twin verdict.

## Cohort and provenance

- HEMOBP (Taiwan): **205,482** QC-eligible sessions, **1,070** patients,
  **4,190,926** telemetry rows; de-identified, CC BY 4.0.
- Combined raw scale: **303,122** sessions across the Taiwan + Spanish frames.
- Spanish external frame: **AUROC 0.474** — external transport failed; label
  semantics differ. It is reported as a failure, not averaged into the headline.
- Labelled hypotension: **10.4%** of HEMOBP sessions (nadir <90 mmHg). Spanish
  clinician-defined symptomatic: **25.5%**. These are different labels and are
  never combined.
- The G7 census contains **205,113** sessions; 369 of the 205,482 QC-eligible
  sessions lack the required pre-anchor record.

## Two forecasts — never interchangeable

- **Fair pre-anchor twin:** 59 features, no future-UF oracle block; fold-2 MAE
  **10.99**, RMSE 14.65. This is the calibrated floor used in the console.
- **Forecast-v2 oracle display:** 72 features including 13 observed future-UF
  features; fold-2 MAE **9.60**. It is a display-only forecast and is **not** the
  G2 baseline. A smaller oracle number is not a better twin.

## Chair board — pre-session risk A2 (separate from G1–G7)

The Chair board is a display-only, fixed-order overview of five patient-disjoint
fold-2 Case Lab sessions. It uses **variant A2**, a feature-audit correction of
the crashrisk secondary model: history, static patient fields and the planned UF
goal only. It excludes `sbp_anchor` (the ~90-minute task anchor, not the starting
BP; 466/3,109 fold-2 crashes had anchor SBP below 90) and `uf_ml_kg_h` (the
current UF rate at that anchor). On untouched fold 2: **AUROC 0.8313, recall@25
0.6015, PPV@25 0.5914, ECE10 0.0184**; high band ≥0.35 = 27.8% of sessions with
57.0% crash rate; low band <0.20 = 59.5% with 8.9%; 21.5% of crashes were low.
The primary B model (AUROC 0.8788) and secondary A (AUROC 0.8356) are anchor-time
and are not used for this board.

Crash shape is **not predicted** on this pre-session board. The pre-registered
shape model uses anchor SBP/UF (AUROC 0.7716 vs baseline 0.7006); the no-anchor/
no-UF ablation reaches only 0.7047 vs 0.7006 and is not shipped. The board shows
the recorded onset only after the reveal. See [`CRASHRISK.md`](CRASHRISK.md).

Claim boundary: low band is not safe; no alarm, treatment recommendation, chair
allocation, or counterfactual. Single-centre, retrospective, one fold-2 read, no
external validation; crash is SBP<90, not symptomatic IDH.

## What passed

- Task 00: causal split, future-invariance, unit, observability, and state tests passed.
- Task 02: the ordinary-machine universal-input ablation is noninferior to the
  full telemetry model; the manual/CSV inference path works.
- Fluid arithmetic and protocol workflow in the current prototype are engineering
  artifacts, not clinical-effectiveness evidence.
- **Forecast-v2 (2026-11-08): nadir-specialized refit — the shippable
  conditional forecast.** A refit of the GBDT directly on the 60-minute
  cuff-sampled nadir target (72 causal features; regime-oracle label
  excluded; fold 2 never in any fit; agent-side determinism proven) removed
  the frozen model's +6 mmHg systematic over-prediction at the source. On
  the untouched confirmatory fold 2 (12,651 anchors): **raw refit MAE 9.601
  vs frozen raw GBDT 10.723 (−10.5%), bias +0.15, crash recall at the <90
  projection 0.526 vs 0.270, false90 0.033**. The forecast-v1 linear-stack
  corrector does NOT transfer to this substrate (fold-2 +0.61% vs raw — it
  patched a bias that no longer exists) and is retired as a historical
  artifact. Scope unchanged: **observational forecasting of the later
  cuff-measured nadir under the observed UF trajectory** — NOT a
  counterfactual or treatment-effect claim, NOT a policy engine (Task 01's
  kill stands), NOT a safety layer. Recorded nuance: the frozen Task 01
  "direct" GBDT consumed a twin prediction as an input feature (resolved by
  probe, prediction-distance MAD 0.49 vs 0.80), so its headline comparison
  vs the pure ODE twin was not fully direct; the v2 refit keeps the same
  feature set. Fold-0 serving artifacts:
  `models/forecast_v2/fold_0/` (3-seed nadir/30/60
  dumps + FEATURES.md + calibration.json).
- **Alert-v1 (2026-11-08): the rescue rule is the alerter; the model stays
  shadow-only.** On a fidelity-proven per-cuff score cache (replay reproduces
  all frozen Task 02 alerts exactly), a budget-allocation sweep over
  rescue-rule thresholds (SBP < ~98.9, non-resetting 60-min refractory,
  model channel closed) reached **16.0% timely detection at 0.22 burden** on
  development folds and **14.1% at 0.26 burden on the untouched confirmatory
  fold 2** — roughly twice the event model's 7.0% at the same budget. The
  model score channel adds only burden at any affordable slice (zero
  marginal alerts at raw-score gate 0.995; budget overflow at the Task 02
  threshold 0.98). This confirms Task 02's no-utility verdict under a
  corrected harness with a positive control. Scope: retrospective replay on
  HEMOBP; no prospective, symptomatic, or cross-unit claim.
- **Forecast-v1 (2026-11-08, superseded by v2)**: calibrated conditional
  nadir forecast (linear-stack recalibration of the frozen GBDT; fold-2
  confirmed −8.27% vs raw frozen, bias +0.21, recall90 0.524, band coverage
  0.955). Kept as the honest record of the calibration exercise; the refit
  supersedes it in the product.

## What failed

- Task 01: the actual-UF physiological twin failed its pre-registered gate.
  Taper MAE gain was 4.9% versus the required 10%, nadir bias was -7.45 mmHg
  overall and -9.23 mmHg in tapers, and it was 21.2% worse than a direct GBDT
  under the same future-UF oracle. Quantitative taper/pause/cooling/bolus/MET
  recommendations are retired.
- Task 02: the event model achieved AUROC 0.880 but detected only 8.2% of event
  sessions at the pre-registered alert budget, below the 60% utility threshold
  and below the current-SBP rule at 20.2%. The model has no clinical alert
  authority.
- **Twin-v3 (2026-11-08, Phase 2): second-generation patient-memory features
  add nothing.** A pre-registered refit substrate (85 features = the frozen 72
  + 13 new strictly-causal memory columns: interdialytic interval, true
  interdialytic weight gain, prior-session actual-UF aggregates, personal
  UF→nadir sensitivity, nadir trend/variability, typical first-to-nadir drop,
  prescribed dialysate temperature) measured on the dev EVAL half: MAE 9.1989
  vs the v2 refit's 9.1944 on identical rows (+0.05%), recall90 0.495 vs
  0.5007, crash-slice MAE equal. The pre-registered gate (fold-2 confirm
  only on ≥1.0% dev gain) failed at selection; fold 2 was not touched.
  Interpretation: the GBDT already extracts all patient memory the cuff data
  carries; fluid-load context adds nothing beyond the anchor-time UF state
  the model already sees. The v2 substrate remains the serving forecast.
- **Twin-v3b (2026-11-08, Phase 2): personalized alerting does not fit the
  budget.** A patient-relative drop-from-baseline alert channel (fire when
  SBP falls ≥ d mmHg below the session's own first-15-min baseline), swept
  d = 15–52.5 mmHg in union with the adopted absolute rule (SBP < 98.88,
  non-resetting 60-min refractory) on the development folds: NO grid point
  meets the pre-registered 0.25 false-alerts/session budget — minimum union
  burden 0.2837 (detection 0.1820) vs 0.2414 (detection 0.1451) for the
  absolute rule alone. Relative drops are routine in this population.
  Measured boundary, reported NOT claimed: at a relaxed ~0.62 budget the
  union detects 26.2% of crashes vs 14.5%. The adopted fixed rule remains
  the alerter; fold 2 was not touched. Implementation note: the new tests
  caught a union-bypass bug (drop rule outside the shared refractory gate)
  before any measurement — the alert-v1 bug class, re-pinned.
- **PhysioTwin-v4.1 (V2 package, 2026-11-09): the ODE counterfactual
  mechanism failed its own calibration.** A fair pre-anchor-only refit
  (59 features; the 13 observed future-UF oracle features removed) measured
  fold-2 MAE 10.986, bias −2.417, RMSE 14.652. The 3-state
  Starling-baroreflex correction's gain calibrated to 0 on dev; every
  positive gain worsened MAE (11.385 → 11.734 across γ 0–1.25), and the
  plan's forced 0.25 floor worsened dev (11.434) and fold-2 (11.042). The
  actual-vs-hold gate (G3) therefore fails: actual and hold predictions are
  identical at γ=0. The best dev gain including negative values was −0.5
  (MAE 11.320), which is a confounding proxy (the nurse tapers in response
  to symptoms), not the plan's positive UF mechanism; it is reported only.
  G1 passes because the pre-anchor substrate is much better than the retired
  v3 twin (374 taper anchors: MAE 11.595 vs 15.550; ratio 0.746), not
  because of the ODE. G2 passes against the fair pre-anchor baseline (a tie
  at γ=0) but fails the plan's oracle-assisted Forecast-v2 baseline (10.986
  vs 9.601). G4's monotonicity and anchor continuity pass at unit gain
  (0 violations in 3,086,844 checks; continuity error 0). G5 coverage is
  0.892 HOLD / 0.901 TAPER; G6 cold start (284 anchors) and future
  invariance (200/200) pass. Claim boundary: the V2 package ships the
  calibrated pre-anchor forecast plus a clearly labelled mechanism
  illustration; it is not a validated counterfactual twin. Evidence:
  `docs/physiotwin_v4_evidence.json` and
  `evidence/benchmark_report.json`.
- **G7 (2026-11-09): the pre-registered non-reactive UF step-down
  experiment failed.** Protocol frozen at SHA-256
  `9ec625eca753144ae492e60fc359d7cd1cc3fc2d2503c469c33d261973c2fd73`
  before estimation. Stage 0 found 581 matched events across 158 dev
  patients (MDE 2.33 mmHg); fold 2 had 65 pre-anchor events and 28 at-anchor
  events. The matched within-patient estimate at +30 min was **+0.13 mmHg
  per 0.25 L/h UF reduction** (95% CI [−2.63, +3.06]), indistinguishable
  from zero; the structural gain was 0.28 (CI [−1.32, +1.74]). The
  pre-trend control passed, but the pre-registered sham-time control failed
  (mean +2.91 mmHg, CI [2.31, 3.54]), and P6a worsened out-of-sample
  trajectory MAE (+0.43 mmHg, CI [0.15, 0.65]); P6b was underpowered
  (28 < 50 at-anchor events). Verdict: **FAIL**. The temporal-order
  diagnostic on the 397 G3 rows also weakened the earlier reverse-causality
  explanation: 234 cuts occurred at the anchor with no preceding observed
  drop, 76 after a drop, and 12 at an intermediate cuff after a drop. The
  twin therefore remains a mechanism illustration; the operational gain is
  0.

## What this prototype may claim

HemoTwin mirrors a manually entered dialysis session state, structures a
unit-defined review pathway, and calculates arithmetic fluid carry-forward for
user-selected scenarios. It is a research workflow prototype. It does not
prescribe treatment, predict treatment response, or claim clinical benefit.
For the V2 package only: a calibrated pre-anchor nadir forecast (fold-2 MAE
10.986, RMSE 14.652) and arithmetic fluid carry-forward; the PhysioTwin-v4.1
counterfactual fan is a labelled mechanism illustration, not a validated
effect. The G7 non-reactive step-down experiment did not support a positive
UF-response effect, so the operational gain remains 0.

## What it must not claim

- validated risk utility or alert effectiveness;
- physiological digital-twin prediction;
- a validated counterfactual PhysioTwin-v4.1 effect or a validated per-policy
  SBP lift, including a positive effect from the G7 experiment;
- that any option will raise SBP, prevent IDH, or is minimum effective;
- that the fluid scenario is a safe or feasible prescription;
- authentication, role enforcement, immutable audit, or machine integration;
- external, prospective, symptomatic-IDH, or Indian-unit validation.

## Next evidence required

Local label harmonization, symptom/action labels, prospective silent-mode
evaluation, and a pre-registered comparison of the response workflow.
