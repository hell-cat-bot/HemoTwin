# G7 pre-registration — non-reactive UF step-down experiment

**Status:** FROZEN before estimation. Any change after this point is a protocol
deviation and must be reported as such.
**Date:** 2026-11-09
**Experiment owner:** HemoTwin v1 (research prototype)
**Data:** HEMOBP, Taiwan, CC BY 4.0 (Lin et al., *Scientific Data* 2019).
1,070 patients; 205,482 quality-eligible sessions; 4,190,926 telemetry rows.
The Spanish external frame is not used for identification (different label
semantics; transport failed, AUROC 0.474 vs 0.720 internal).

This protocol is a retrospective, pre-registered association experiment. It
cannot establish a causal treatment effect without randomized UF assignment or
symptom timestamps, neither of which exists in HEMOBP. Even a pass permits
only **associational decision support conditioned on pre-event stability**.

---

## 1. Question and estimand

Does a reduction in machine UF rate, made while the patient is still
haemodynamically stable, predict a higher systolic blood pressure over the
next 15/30/45 minutes than holding UF?

For a step-down at dialysis minute `t_e`, define
`du_e = UF(t_e+) - UF(t_e-)` in L/h. The primary dose band is
`du_e in [-0.80, -0.20] L/h` so that machine pauses and tiny changes do not
dominate a linear dose-response. Normalize the dose as
`d_e = -du_e / 0.25` (units of 0.25 L/h reductions; range 0.80-3.20).

Primary estimand:

`tau(+30) = E[ SBP(t_e+30) - SBP(t_e) | treated at dose d_e, stable pre-event ]
           - E[ same change | matched same-patient control, UF held ]`

normalized per `d_e = 1` (i.e., per 0.25 L/h reduction). Units: mmHg.
`+15` and `+45` are secondary horizons. The 60-minute nadir is not the
primary endpoint: a dip at +15 minutes can lock in the nadir even if the
step-down raises pressure at +30/+45 (transcapillary refill lag ~22 min).

---

## 2. Event definition (pre-event data only; no outcome peeking)

A UF step-down event qualifies when all of the following hold:

1. The machine UF rate changes from `u_prev` to `u_new` at time `t_e` with
   `u_prev - u_new in [0.20, 0.80] L/h`.
2. The new rate is held within +/-0.05 L/h for at least 30 minutes
   (45 minutes for the +45 horizon).
3. `t_e >= 30` minutes.
4. On anchor sessions, `t_e + h <= t_a` for the horizon `h` being analyzed.
   On non-anchor dev sessions, `t_e in [30, 120]` and at least one cuff is
   observed in `[t_e+10, t_e+45]`.
5. Pre-event stability over `[t_e-30, t_e]`:
   - at least 2 cuffs; the last cuff is within 15 minutes of `t_e`;
   - `SBP(t_e) >= 115 mmHg` and `min SBP >= 110 mmHg`;
   - last cuff change `>= -3 mmHg`;
   - OLS slope over the window `>= -4 mmHg/h`.

These filters are deliberately conservative. They select stable,
normotensive events; the estimates may not generalize to crash-prone patients.
A pre-declared exploratory stratum (`SBP(t_e) in [100, 115)`,
`min SBP >= 95`, slope `>= -4`) is reported separately and never used for the
primary verdict.

Events are partitioned into:

- **E1a (scheduled/recurring):** a step-down occurs within `t_e +/- 10 min`
  in at least 3 of the patient's dev sessions and in at least 50% of those
  sessions. These are the most plausibly routine UF-profile changes.
- **E1b (ad hoc stable):** all other qualifying events.

If `N(E1a) >= 200`, E1a alone is primary; otherwise E1a and E1b are reported
separately and pooled only if the interaction test `p > 0.10` (reported
regardless).

---

## 3. Matched control definition

For each treated event, a control is a time `t_c` in a **different session of
the same patient, in the same fold**, with:

- `|t_c - t_e| <= 15 min`;
- the same pre-event stability criteria at `t_c`;
- UF held within +/-0.03 L/h over `[t_c-30, t_c+30]`;
- `|SBP(t_c) - SBP(t_e)| <= 12 mmHg`;
- outcomes available at the horizon being analyzed.

If multiple controls qualify, use the mean of their outcomes and covariates.
Treated events without any control are excluded from the matched estimate and
counted in the census.

Fold discipline: E1 estimation and matching use folds 0/1 only. Fold 2 is
untouched for P6a/P6b. No fold-2 session contributes to event selection,
matching, gamma estimation, or any tuning decision.

---

## 4. Outcome definition

For horizon `h in {15, 30, 45}` minutes, the outcome is the cuff nearest to
`t_e + h` within tolerance `{10, 12.5, 15}` minutes respectively, minus the
last cuff at or before `t_e` (within 15 minutes). If no cuff is available,
the horizon is missing (not imputed).

The matched difference is:

`dY_e(h) = [SBP_treated(t_e+h) - SBP_treated(t_e)]
         - mean_c [SBP_control(t_c+h) - SBP_control(t_c)]`

The pre-trend outcome uses the same structure over
`[t_e-30, t_e]` and must be null.

---

## 5. Estimator

Sole primary estimator: within-patient matched difference-in-differences,
continuous dose-response OLS (FE-DR), on dev (folds 0/1):

`dY_e(h) = alpha + tau(h) * d_e
          + b1 * dSBP_now_e + b2 * dCumUF_e + b3 * dOH0_e + eps_e`

with patient-clustered bootstrap (1,000 resamples of `pid`) for 95% CIs.
The secondary robustness estimator is an out-of-fold R-learner residual
regression; it cannot change the verdict.

Negative controls (both must pass for a product-grade verdict):

1. **Pre-trend:** the same estimator with the pre-event change as outcome must
   have `|tau_pre| < 1.0 mmHg` and a 95% CI including 0.
2. **Sham time:** a fake event at `t_c - 15 min` on control sessions (UF held,
   same stability window) must have a 95% CI including 0 (`p > 0.10`).

---

## 6. tau -> gamma mapping

For each dev event, compute the pre-event ODE state at `t_e-1` using the
causal UF grid, then simulate two 45-minute branches from that state:

- hold branch: `u_prev` constant;
- step branch: `u_new` constant (valid for 30 min by definition; 45 min where
  the held condition allows).

The unit-gain stress difference at horizon `h` is

`dH_e(h) = [beta_vol*(D_hold - D0) + beta_baro*(C_hold - C0)]
         - [beta_vol*(D_step - D0) + beta_baro*(C_step - C0)]`

which is positive when the step-down reduces the modeled stress.

- **Primary structural gain:** regress the matched `dY_e(30)` directly on
  `dH_e(30)` (controls have `dH = 0`). The slope is `gamma_E1`.
- **Closed-form check:** `gamma_plug = tau_30 / mean(dH_e(30) / d_e)`.
- Both are reported. `gamma_E1` is used for P6a/P6b. If `gamma_E1 <= 0`, the
  operational gain remains 0.

---

## 7. Stage 0 census and power gate (run before estimation)

The census reports, separately for dev and fold 2:

`N0` sessions; `N1` sessions with a qualifying step-down; `N2` events passing
the pre-anchor/early-window rule; `N3` events passing stability; `N4` events
with a matched control; `N4a/N4b` E1a/E1b counts; `N5` fold-2 events for P6a;
`N6` fold-2 at-anchor events for P6b; outcome availability at +15/+30/+45;
per-patient counts; and the cuff-density and temporal-ordering diagnostics on
the 397 G3 intervention rows.

Pre-declared minimums for any estimation:

- `N4(dev) >= 200` treated events across `>= 50` patients;
- `MDE_80% <= 2.50 mmHg` at the observed residual SD and clustering.

Product-grade power additionally requires `MDE_80% <= 1.50 mmHg` (the product
threshold). If the minimums are not met, the verdict is
**INCONCLUSIVE (UNDERPOWERED)** and no estimate is adopted.

The MDE is `2.80 * SE`, with `SE = sigma_delta * sqrt(DEFF / N4)`.
`sigma_delta` is the residual SD of the matched outcome; `DEFF` is estimated
from the patient-level intraclass correlation, with 1.5 as the fallback.

---

## 8. Verdicts (pre-declared)

Order of evaluation:

1. **INCONCLUSIVE (UNDERPOWERED):** Stage 0 minimums fail.
2. **FAIL:** Stage 0 passes, but `tau_30 <= 0`, or the 95% CI includes 0, or a
   negative control fails.
3. **STATISTICAL_ASSOCIATION_ONLY:** `tau_30 > 0`, CI excludes 0, controls
   pass, but `tau_30 < 1.50 mmHg` per 0.25 L/h, or P6a fails.
4. **MECHANISM_PASS:** all of the following:
   - `tau_30 >= 1.50 mmHg` per 0.25 L/h;
   - 95% CI excludes 0;
   - sign and significance stable across stability windows `{30, 45}` and
     last-drop thresholds `{-3, -5}`;
   - both negative controls pass;
   - **P6a passes:** on untouched fold-2 pre-anchor E1-style events, the
     gamma-corrected predicted 30-minute trajectory change has lower MAE than
     the zero-change baseline, with a patient-clustered 95% CI below 0.
   This is an out-of-sample mechanism validation, not a calibrated fan.
5. **PRODUCT_GRADE_PASS:** MECHANISM_PASS plus **P6b**:
   - on fold-2 anchors with a non-reactive step-down at the anchor
     (`N6 >= 50`), the gamma-corrected trajectory MAE at +30/+45 is lower than
     gamma = 0 on the same slice, with a patient-clustered 95% CI below 0.

If P6b is INCONCLUSIVE (N6 < 50), the maximum achievable verdict is
MECHANISM_PASS. If P6a is INCONCLUSIVE, the maximum verdict is
STATISTICAL_ASSOCIATION_ONLY.

---

## 9. Claim mapping

| Verdict | Product language |
|---|---|
| PRODUCT_GRADE_PASS | "Associational decision support for UF-policy review, conditioned on pre-event stability, with a 90% band." The fan may be shown as a calibrated projection. Never "causal." |
| MECHANISM_PASS | "Out-of-sample validated associational trajectory correction; the anchor-branch fan remains an illustration." Fan stays off by default. |
| STATISTICAL_ASSOCIATION_ONLY | "A small statistical association was detected; it is not used for decisions." |
| INCONCLUSIVE | "The clean-event sample is too small to test the mechanism." |
| FAIL | "The non-reactive step-down experiment did not support a positive effect." |

No verdict permits: autonomous prescription, recommendation-system language,
safety-layer language, "6/6 gates passed," "partial identification," or a
causal treatment-effect claim.

---

## 10. Gate scoreboard wording (frozen)

The G1-G6 booleans remain unchanged: G1, G2, G4, G5, G6 are true; G3 is false;
`all_pass` is false. The prose must be:

> "5 of 6 gate booleans are true. G2 is a vacuous self-tie at gain 0 and G4 is
> vacuous at gain 0 (the separate unit-gain consistency check passes 0
> violations in 3,086,844). The substantive passes are G1, G5 and G6; G3
> fails. all_pass is false."

No unqualified "X/6 gates passed" claim is allowed.

---

## 11. Deviations already known

- HEMOBP has no symptom timestamps and no centre/nurse identifiers. "Non-
  reactive" is approximated by BP stability; unobserved symptom-driven cuts
  may remain. E2 (practice instrument) is impossible.
- The ODE parameters for non-anchor events use the patient's anchor-derived
  prior (or the covariate prior if the patient has no anchor). This is a
  modeling choice, not a measured per-event parameter.
- The sham test is a weak falsification check because the data lack a
  randomized placebo; it can detect gross regression-to-the-mean but not all
  confounding.
- The 60-minute nadir is not the primary endpoint; a trajectory pass does not
  imply a nadir or fan pass.
