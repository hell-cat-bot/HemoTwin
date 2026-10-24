# Model Card — HemoTwin IDH Event Model and UF-Policy Twin

| Field | Detail |
|---|---|
| **Model name** | HemoTwin event model (v1) with volume-refill twin |
| **Version** | 1.0 |
| **Date** | 24 October 2026 |
| **Owner** | HemoTwin Team, `[College / Incubator]` |
| **License** | Code MIT; training data CC BY 4.0 |
| **Status** | Research prototype. Not a medical device. Not for clinical use. |
| **Paper or report** | This document, plus `docs/FACTS.md` and `docs/ARCHITECTURE.md` |

---

## 1. Intended use

HemoTwin estimates the probability that a haemodialysis patient's systolic blood pressure will fall below 90 mmHg with onset **15–60 minutes after the current blood-pressure reading**, and simulates the effect of three ultrafiltration policies on the predicted nadir.

**Intended setting.** A research or shadow-mode evaluation inside a dialysis unit, used by a nurse or nephrologist as a second opinion on *when* to taper ultrafiltration. The output is a probability with an interval and a simulated consequence, never an instruction.

**Intended population.** Adults on maintenance haemodialysis with intra-session blood-pressure telemetry at a cadence of roughly 30 minutes. The model was developed on a Taiwanese cohort with a median dialysis vintage of 9.6 years.

**Intended decision.** Attention allocation across chairs, and the timing and magnitude of an ultrafiltration taper. The model does not select dialysate composition, temperature, or drugs.

**What it explicitly does not do.** It does not diagnose hypotension, does not recommend a specific UF rate in mL/h, does not authorise a treatment change, and does not claim to reduce adverse events.

---

## 2. Users

| User | Expected interaction |
|---|---|
| Dialysis nurse at the chair | Sees the chair board and the what-if cards; decides whether to act; can override at any time |
| Remote nephrologist covering several units | Uses exception-based triage; reviews the twin state and the frontier before calling the unit |
| Clinical engineer or ML engineer | Recalibrates on local data, monitors drift, owns retraining |
| Auditor or regulator | Reviews the model card, the artifact trail, and the override log |

Assumed competence: the user can interpret a systolic blood pressure, an ultrafiltration rate, and a confidence interval. The interface must not require the user to understand gradient boosting.

---

## 3. Out-of-scope use

| Out of scope | Reason |
|---|---|
| Direct closed-loop control of a dialysis machine | No regulatory clearance, no prospective safety data, no fail-safe design |
| Diagnosis of intradialytic hypotension | The label is a threshold on SBP, not a symptomatic diagnosis |
| Use in paediatric, pregnant, or acute kidney injury populations | Not represented in training data |
| Use in peritoneal dialysis or continuous renal replacement therapy | Different physiology and different machine signals |
| Use without local recalibration | Calibration and feature distributions are cohort-specific |
| Individualised fluid prescription or dry-weight setting | Outside the model's evidence and outside its policy space |
| Triage in an emergency where the reading is already below 90 mmHg | The task is forecasting, not detecting an ongoing event |
| Any claim of mortality or morbidity benefit | Not evaluated |

---

## 4. Training data

| Item | Value |
|---|---|
| Primary cohort | HEMOBP, Taiwan |
| Patients | **1,070** |
| Sessions after quality filters | **205,482** |
| Telemetry rows | **4,190,926** |
| BP measurement events | **2,342,586** |
| Prediction anchors | **1,268,990** |
| Positive anchors | **32,221 (2.54%)** |
| Features | **40** |
| Static EHR fields | age, sex, diabetes status, dialysis vintage |
| External cohort (different task) | Mendeley Dialysis Database, Spain: **758 patients**, **97,640 sessions**, hypotension prevalence **25.5%** |
| Licence | Both datasets **CC BY 4.0** |
| Provenance | Open, de-identified research data. No proprietary machine data. No hospital records. |

**Cohort characteristics that matter for transportability.** 34.5% of patients are diabetic (370 / 1,072); median dialysis vintage is 9.6 years (IQR 6.5–14.5); median measured ultrafiltration is 2.2 L per session (p99 5.4 L); prescribed dialysate temperature has a median of 36.4 °C and a p1–p99 range of 35.8–37.0 °C.

**No Indian cohort has been collected.** This is the single largest evidence gap for the stated deployment context.

**Split.** Patient-disjoint 70 / 15 / 15, asserted in code. No patient appears in more than one split. All reported metrics are from the held-out test split.

---

## 5. Label definition

An anchor is a blood-pressure measurement at time `t` within a session.

```
label = 1  if a FIRST IDH event has nadir SBP < 90 mmHg
              and onset in (t + 15 min, t + 30 min]
label = 0  if the outcome is observable and no such event occurs in that window
dropped    if the anchor is within 15 min of an event onset
dropped    if no BP reading exists inside the window
```

Design consequences, stated plainly:

- **First event only.** Recurrence is trivially predictable from "it already happened this session" (a zero-training baseline reaches AUROC 0.798). Counting repeat events would inflate the score without adding clinical value.
- **Imminent onsets are dropped, not labelled.** A reading 8 minutes before a crash is neither a fair positive nor a fair negative.
- **Missing windows are dropped, not labelled 0.** Silence is not safety. This is why 281 crash sessions have no warnable anchor at all.
- **The label is not a symptomatic definition.** Nadir SBP < 90 mmHg is a physiological threshold; bedside IDH usually also requires symptoms or a nursing intervention. Expect disagreement with clinical adjudication.

---

## 6. Features

40 features from machine telemetry plus four static EHR fields. No labs, no notes, no imaging, no genetic data.

| Family | Examples |
|---|---|
| Blood pressure, current | SBP, DBP, MAP at the anchor |
| Blood pressure, history | rolling mean, minimum and slope over 15, 30, 60 and 120 minute windows; drop from session maximum; readings so far |
| Ultrafiltration | current rate, cumulative volume, UF intensity in mL/kg/h, fraction of prescription completed, gap to the required rate |
| Machine settings | dialysate temperature, conductivity, blood flow |
| Session context | elapsed fraction, minutes to session end, dry weight, pre-session weight |
| Patient history | prior-session IDH rate, prior mean nadir, prior first SBP, prior session count |
| Static | age, sex, diabetes status, dialysis vintage in years |

**Leakage control.** Every window looks backwards only; patient history uses strictly earlier sessions. Training and serving build the same 40 columns in the same order, frozen in the metadata file `artifacts/hemotwin_meta.json`.

**Known weakness.** HEMOBP's EHR side is minimal: five columns. Deployment would need comorbidities, eGFR, cardiac function, vascular access type and medication classes. Those are specified as a target schema, not present in this model. Dialysis vintage is the one static feature with real clinical signal, and it is included.

---

## 7. Performance

All values from the patient-disjoint HEMOBP test split. No value in this section is estimated or extrapolated.

| Metric | Value |
|---|---|
| AUROC | **0.916** (95% CI 0.897–0.932, patient-clustered bootstrap) |
| AUPRC | **0.236**, an **8.4×** lift over the 2.80% test prevalence |
| Sensitivity at 90% specificity | **0.697** |
| Rule baseline R1 ("alarm when SBP is low") | AUROC **0.787** |
| Rule baseline R2 ("extrapolate the BP slope") | AUROC **0.738** |
| False-alarm session rate | **20.6%** |
| Sessions with no warnable window | **281** |

### Event-level detection, both denominators

| Denominator | Detected | Rate | What it means |
|---|---|---|---|
| Sessions with at least one anchor in the 15–60 min warning window | 1,783 / 2,073 | **86.0%** | Detection among sessions the pipeline could physically warn about |
| All IDH sessions | 1,783 / 2,354 | **75.7%** | Detection in the population a unit actually sees |

**Use 75.7% as the headline.** The gap is 281 sessions where the cuff cadence left no usable anchor. That is a sensor limitation, not a model failure, but it is still a patient who was not warned, and hiding it would misrepresent the system.

### External cohort, different task

| Metric | Mendeley, Spain |
|---|---|
| Patients / sessions | 758 / 97,640 |
| Hypotension prevalence | 25.5% (24,912 / 97,640) |
| Granularity | session-level only, one pre and one post BP |

Mendeley cannot validate a 15–60 minute event model because it contains no intra-session time series. We therefore ran the only test it supports: a reduced six-feature **session-level** model, trained on HEMOBP and applied without retraining to Spain.

| Cohort | n | AUROC |
|---|---|---|
| HEMOBP, held-out patients (internal) | 50,044 | **0.720** |
| Mendeley, Spain (external) | 97,633 | **0.474** |

**The transport check failed.** The likely cause is that the labels mean different things: HEMOBP uses nadir SBP < 90 mmHg, while the Spanish registry records clinician-defined symptomatic hypotension. Pre-dialysis SBP reverses direction between cohorts (0.325 versus 0.611), which is the signature of a label-definition difference rather than a subtle distribution shift.

Consequences, stated plainly:

- We claim **internal validity only**.
- We do **not** describe the Spanish cohort as external validation.
- We never blend the two cohorts into one AUROC.
- Deployment requires local retraining after label harmonisation.

Full analysis: `docs/EXTERNAL_VALIDATION.md`.

### Comparison with published work

| Work | Task | Reported performance | Our position |
|---|---|---|---|
| Zhang et al., *NDT* 2023 | 15–75 min, XGBoost, 693 patients / 42,656 sessions, deployed in 6 US clinics | AUROC 0.89 | **We do not claim to beat this.** Our 15–60 min horizon is narrower and easier. We claim a different artifact, not a better predictor. |
| Kim et al. 2022 | External validation | AUPRC 0.106 | Different cohort, definition and horizon. We do not treat our higher value as a win. |
| Dong et al. 2023 | 10-centre validation | C-statistic 0.82 | Our AUROC is higher on a single cohort and an easier horizon. Not comparable. |
| Naive recurrence baseline 2026 | "It happened earlier this session" | AUROC 0.798, zero training | Our margin over this baseline is the honest measure of model value. |

The defensible claims are: patient-disjoint validation, event-level reporting with alarm burden, comparison with two clinical rule baselines at the same specificity, and a twin layer that no comparator provides.

---

## 8. Subgroup notes

| Subgroup | Cohort share | Model performance |
|---|---|---|
| Diabetic patients | **34.5%** (370 / 1,072) | **Not evaluated** |
| Non-diabetic patients | remainder | **Not evaluated** |
| Sex | not reported in this document | **Not evaluated** |
| Dialysis vintage above / below median (9.6 years, IQR 6.5–14.5) | approximately half each | **Not evaluated** |
| Age bands | not reported in this document | **Not evaluated** |

**This is a gap, not a null result.** Subgroup AUROCs, detection rates and calibration curves were not computed for the submission. Before any pilot, the following must be produced on held-out patients and reported with confidence intervals: sex, diabetes status, vintage quartile, age band, and ultrafiltration intensity.

Two risks follow from the missing analysis. First, the model could be materially weaker in the group with the highest baseline risk (long vintage, diabetic, high UF), which is also the group a nurse most needs help with. Second, a subgroup with few positives could be systematically over-confident, and the residual band would not reveal it because coverage is marginal, not conditional. Both are testable and both are unresolved here.

---

## 9. Calibration

**Method.** Isotonic regression fitted on one half of the validation split, evaluated on the other half. The test split is untouched by the calibrator.

**Why the split matters.** Fitting and describing calibration on the same rows produces a near-zero error by construction: the isotonic step function's flat segments land inside the evaluation bins. Any such figure is discarded. Calibration is reported graphically as a reliability curve plus Brier score, because a single binned ECE is sensitive to bin count and to where the isotonic steps fall.

**One caveat.** The two validation halves are split by anchor row, not by patient, so a patient can appear in both halves. The validation-holdout ECE (0.0008) is therefore optimistic. The **patient-disjoint test ECE is 0.0017** and the test Brier is 0.0235; those are the numbers we treat as primary.

**What the user should assume.** Probabilities are approximately calibrated for a population like HEMOBP. They are not calibrated for an Indian cohort, for a different machine model, or for a unit with a different cuffing cadence. Local recalibration is a prerequisite, not a refinement.

**Practical rule for the dashboard.** Never show a bare probability. Show the probability with its interval and the alarm threshold in force, so the user can see how far the estimate sits from the decision boundary.

---

## 10. Alarm budget trade-off

The threshold is a staffing decision, not a modelling decision. Two operating points are reported:

| Operating point | What is fixed | Consequence |
|---|---|---|
| High specificity | Sensitivity at 90% specificity = **0.697** | Fewer false alarms, roughly one third of true events missed at this point |
| Shipped default | Chosen on validation for high sensitivity | False-alarm session rate **20.6%** |

Both numbers describe the same trade-off from different ends: moving the threshold trades missed crashes against nursing attention. At eight chairs, an 20.6% false-alarm session rate is a real workload, and a unit that cannot absorb it should raise the threshold and accept lower detection.

**What the dashboard must expose.** The threshold in force, the resulting false-alarm rate, and a one-click way for the unit to choose a different point. A hidden threshold is an unauditable product.

**What is not claimed.** No cost-effectiveness analysis, no nursing-time study, and no evidence that alarm reduction improves outcomes. The 20.6% figure comes from held-out sessions, not from a live unit.

---

## 11. Limitations

| Limitation | Detail and consequence |
|---|---|
| **Geography** | Training data is Taiwanese; external data is Spanish. No Indian cohort. Probabilities must not be transplanted to an Indian unit without retraining and recalibration. |
| **Sensor cadence** | NIBP is recorded roughly every 30 minutes. The 15–60 minute horizon is therefore near the resolution limit of the input. 281 crash sessions had no anchor in the warnable window and cannot be detected at all. |
| **Label construct** | Nadir SBP < 90 mmHg is not a symptomatic definition. Expect false positives that a nurse would call clinically fine, and false negatives where symptoms precede the threshold. |
| **Counterfactual is observational** | The taper policies are simulated, not randomised. Staff already taper UF in 87.2% of sessions (median rate 0.58 → 0.10 L/h), so the simulation stays inside observed practice, but confounding by indication remains: the sessions where staff tapered early are not exchangeable with the sessions where they did not. This is a decision aid, not a causal effect estimate. |
| **Twin simplicity** | Two parameters (`k_refill`, `beta_bp`), with the time-trend term `gamma` fixed at 0 because it is collinear with `beta_bp` at a 30-minute cadence. The model cannot represent compartment shifts, autonomic reflexes, or arrhythmia. Residual structure is absorbed by the held-out band rather than modelled. |
| **Band coverage** | The 90% band is an empirical residual interval, not a distribution-free guarantee. Marginal coverage holds only if held-out and live patients are exchangeable, does not hold conditionally per patient, and degrades under drift. |
| **Single split** | One patient-disjoint split, not repeated cross-validation. The patient-clustered bootstrap CI is reported, but split-to-split variance is not characterised. |
| **Minimal EHR** | Five static fields. Comorbidities, medications, access type and cardiac function are absent. |
| **No prospective evaluation** | No shadow-mode deployment, no comparison against standard care, no outcome data. |
| **Alarm burden** | 20.6% false-alarm session rate is a genuine cost, not a footnote. |

---

## 12. Ethical considerations

| Issue | Position |
|---|---|
| **Not a medical device** | Research prototype. No regulatory approval in any jurisdiction. No diagnosis, treatment, or prescription. |
| **Human authority** | The nurse decides. Every simulated policy is advisory, carries an interval and a fluid cost, and can be overridden. An override log is a requirement for any pilot. |
| **Automation bias** | A confident-looking nadir can anchor a clinician. Mitigations: always show the interval, show the measured-versus-modelled check, and show the false-alarm rate alongside the alert. |
| **Deskilling and attention** | The chair board could reduce vigilance if treated as complete. The board ranks chairs; it does not certify the unranked ones as safe. |
| **Privacy and law** | Only CC BY 4.0 de-identified research data is used. No protected health information is processed. A clinical pilot falls under the DPDP Act 2023 (India) and would require ethics approval, a data-processing agreement, and a security review; HIPAA would apply in the US. |
| **Equity** | The cohort is Taiwanese and Spanish and long-vintage. Performance in Indian district hospitals, in younger patients, or with different machine vendors is unknown. Deploying without local validation would export a calibration from one health system to another. |
| **Data attribution** | HEMOBP (Lin et al., *Scientific Data* 2019, DOI 10.1038/s41597-019-0319-8) and the Mendeley Dialysis Database, both CC BY 4.0. Attribution is mandatory and preserved in the README. |
| **Commercial interest** | None declared at submission. Any future commercial deployment would require regulatory strategy and prospective evidence before marketing claims. |

---

## 13. Maintenance and retraining plan

| Trigger | Action | Owner |
|---|---|---|
| New unit or machine vendor onboarded | Collect a local cohort, re-fit isotonic calibration, re-estimate `k_refill` and `beta_bp`, re-check band coverage | Clinical engineer |
| Monthly monitoring | Input distribution shift (UF rate, dialysate temperature, cuff cadence), alert rate, override rate, missed-event review | Clinical engineer + nursing lead |
| Alert rate drifts materially from the level observed at validation | Re-examine threshold and calibration before touching the model | Nursing lead |
| Band coverage below nominal on held-out patients | Re-fit residuals; if still failing, widen the band and flag the model as degraded | ML owner |
| Annual or on guideline change | Full retrain with patient-disjoint split, re-run rule baselines, re-issue this card | ML owner |
| Any safety event involving a missed alert | Root-cause review; publish the finding internally; do not silently retrain | Clinical governance |

**Retraining discipline.** The split is regenerated patient-disjoint, the rule baselines are recomputed, and both detection denominators plus the false-alarm session rate are reported. A new model ships only if it does not regress event-level detection at the same alarm budget. A model that improves AUROC while worsening alarm burden is rejected.

**Versioning.** The model file, isotonic knots, metadata (including the feature list) and the train report (including twin parameters and band) are versioned together. A model without its calibrator and band is not deployable.

---

## 14. Citation

```bibtex
@misc{hemotwin2026,
  title        = {HemoTwin: a UF-policy digital twin for intradialytic hypotension},
  author       = {{HemoTwin Team}},
  year         = {2026},
  howpublished = {Digital Twin Challenge 2026, Happiest Health},
  note         = {Research prototype. Not a medical device.}
}
```

Data: Lin et al., *Scientific Data* 2019, DOI 10.1038/s41597-019-0319-8 (HEMOBP, CC BY 4.0); Mendeley Dialysis Database, Spain (CC BY 4.0).

*Every number in this card is governed by [`FACTS.md`](FACTS.md). If a value is not there, it is marked "not evaluated".*
