# FACTS — single source of truth for all copy

> Every number that appears in the README, deck, video, or dashboard **must** match this file. If a number is not here, do not invent it — write "not evaluated".

## Product

- **Name:** HemoTwin
- **Hook:** *Predict the crash. Price the fix.*
- **One-liner:** A remote-operations digital twin for haemodialysis that predicts intradialytic hypotension 15–60 minutes ahead, then simulates holding, tapering, and stopping ultrafiltration and shows the blood-pressure gain against the fluid left behind.
- **Status:** research-stage clinical decision-support prototype. **Not a medical device.** Does not issue prescriptions.
- **Label:** first IDH event of the session (nadir SBP < 90 mmHg) with onset in `(t+15, t+60]` minutes.

## Verified model results (HEMOBP, patient-disjoint test split)

| Metric | Value |
|---|---|
| Cohort | HEMOBP, Taiwan, **1,070 patients** |
| Sessions (after quality filters) | **205,482** |
| Telemetry rows | **4,190,926** |
| BP measurement events | **2,342,586** |
| Prediction anchors (cohort) | **1,268,990** |
| Positive anchors (cohort) | **32,221 (2.54%)** |
| Sessions with ≥1 anchor | **194,163** |
| Features | **40** |
| Test anchors / positives | **169,854 / 4,764 (2.80%)** |
| AUROC | **0.916** (95% CI 0.897–0.932, patient-clustered bootstrap) |
| AUPRC | **0.236** = **8.4×** prevalence |
| Sensitivity @ 90% specificity | **0.697** |
| Rule baseline R1 ("alarm when SBP is low") AUROC | **0.787** |
| Rule baseline R2 ("extrapolate BP slope") AUROC | **0.738** |
| Frozen operating threshold | **0.0410** (chosen on validation for 85% sensitivity) |
| Test sensitivity at threshold | **0.862** |
| Event-level detection | **1,783 / 2,073 evaluable = 86.0%**; **1,783 / 2,354 = 75.7% of all IDH sessions** |
| False-alarm session rate | **20.6%** |
| Sessions with no warnable window | **281** |
| Session-level PPV at threshold | **28.1%** (2,016 of 7,182 flagged sessions truly crashed) |

**Always report both detection numbers** (75.7% of all crash sessions; 86.0% of those with a usable warning window).

**Calibration:** isotonic regression is fitted on one half of validation and evaluated on the other. ECE **0.214 raw → 0.0008 calibrated** on the held-out half; **patient-disjoint test ECE 0.0017**; Brier **0.0235** on test. Caveat: the two validation halves are split by anchor row, not by patient, so the 0.0008 is optimistic. The test ECE is the stronger number.

## Twin validation (the layer that makes this a twin)

| Check | Value |
|---|---|
| Population refill rate `k_refill` | **0.30 /h** (session IQR 0.15–2.10) |
| Population BP sensitivity `beta_bp` | **19.6 mmHg/L** (session IQR 9.1–41.6) |
| Sessions with measured pre/post weight | **16,591** |
| Modelled minus measured UF, median | **+0.07 L** |
| Modelled minus measured UF, MAE | **0.40 L** |
| Sessions within 0.5 L of measured UF | **75.0%** |
| Correlation, modelled vs measured UF | **0.768** |
| Held-out nadir error (hold policy), MAE | **13.6 mmHg** |
| Held-out nadir residual, 5th–95th percentile | **−36.6 to +22.6 mmHg** |
| Sessions in the residual band | **1,472** |

The 5th–95th residual band is what the dashboard plots around each policy. It is wide. That is the honest uncertainty of a two-parameter model fitted to a 30-minute cuff cadence.

## Demo bundle (`demo/demo_bundle.json`, 8 real held-out sessions)

The highest-risk chair (Chair 1) is a real held-out session with a true IDH event:

| Field | Value |
|---|---|
| Predicted risk | **50%** |
| Current SBP | **97 mmHg** at minute **110** of a **202**-minute session |
| True onset | minute **140** |
| Hold current UF | nadir **70 mmHg** [33–92], **0.00 L** left behind |
| Taper UF 25% | nadir **77 mmHg** [40–99], **0.45 L** left behind |
| Stop UF + 250 mL | nadir **103 mmHg** [67–126], **1.79 L** left behind |
| Twin parameters | k = 0.165/h, β = 24.8 mmHg/L, fitted from **44** prior sessions |

**The story this tells:** a 25% taper is the cheap fix and it does not clear the threshold. Stopping ultrafiltration works and costs 1.8 L of fluid removal. That is the trade-off the console prices.

## Verified data findings (measured by us, not from a paper)

| Finding | Value | Source |
|---|---|---|
| Sessions with a >20% mid-session UF reduction | **87.2%** | 32,565 real sessions |
| Sessions ending below 80% of peak UF | **81.7%** | same |
| Median UF rate, session start → end | **0.58 → 0.10 L/h** | same |
| Measured UF (weight start − weight end) | median **2.2 L**; p99 5.4 L | 165,858 sessions |
| Prescribed dialysate temperature | median **36.4 °C**; p1–p99 **35.8–37.0 °C** | 165,858 sessions |
| Diabetic patients in cohort | **34.5%** (370 / 1,072) | idp.csv |
| Median dialysis vintage | **9.6 years** (IQR 6.5–14.5) | idp.csv `first_dialysis` |
| Sessions per patient per year | **156** (3/week) | arithmetic |
| Session-weight join rate after ±1 day fallback | **97.7%** of sessions | our pipeline |

## External cohort (Mendeley Dialysis Database, Spain)

| Metric | Value |
|---|---|
| Patients | **758** |
| Sessions | **97,640** |
| Hypotension prevalence | **25.5%** (24,912 / 97,640) |
| Label | `D_Hipotension` = `SI` / `NO` |
| Granularity | **session-level only** (one pre and one post BP — no time series) |
| Licence | **CC BY 4.0** |

**Never blend HEMOBP and Mendeley into one AUROC.** Two tasks, two tables.

**Transport check: FAILED.** A reduced six-feature session-level model scores **AUROC 0.720** on held-out HEMOBP patients and **0.474** on 97,633 Spanish sessions. The cause is a label-semantics difference: HEMOBP labels nadir SBP < 90, while the Spanish registry records clinician-defined symptomatic hypotension. Full analysis: `docs/EXTERNAL_VALIDATION.md`. **Do not describe Mendeley as external validation, and never blend the cohorts.**

## Combined data scale

**303,122 sessions** across **two countries** (205,482 + 97,640). **1,828 patients.** This is the data scale, **not** an external-validation claim: the Spanish transport check failed (AUROC 0.474).

## Citations (exact)

- Zhang et al., *Nephrology Dialysis Transplantation* 2023. XGBoost, 693 patients / 42,656 sessions, AUROC 0.89 at 15–75 min, deployed in 6 US clinics. PMID 37055366, DOI 10.1093/ndt/gfad070.
- Lin et al., *Scientific Data* 2019. HEMOBP. DOI 10.1038/s41597-019-0319-8.
- BestShape, *Clinical Kidney Journal* 2025. 4-year follow-up, two Taiwanese hospitals: fewer IDH episodes, CPR events, post-dialysis falls.
- ChiCTR2000036973 (preprint 2026): XGBoost-guided UF management reduced IDH vs conventional care.
- Kim et al. 2022: external AUPRC 0.106.
- Dong et al. 2023: 10-centre C-statistic 0.82.
- Naïve recurrence baseline (2026): AUROC 0.798 with zero training.

## India context

- ~101.3M people with diabetes and ~136M with prediabetes in India (ICMR-INDIAB 2023).
- **34.5%** of our dialysis cohort is diabetic — this is the terminal stage of India's diabetes epidemic.
- India operates **1,700+ dialysis centres under the Pradhan Mantri National Dialysis Programme (PMNDP)**, many in district hospitals without on-site nephrology → remote supervision is the scalable model.
- ~34M dialysis sessions per year in India (estimate — label it as an estimate).

## Rules for all copy

1. **Never** claim we beat Zhang et al. on AUROC. Our horizon (15–60 min) is narrower than theirs (15–75 min), and a narrower window is an easier task.
2. **Never** call the machine a "wearable". Call it **medical IoT**.
3. **Never** claim diagnosis, treatment, reversal, or regulatory approval.
4. **Always** state that the counterfactual is observational and within-policy-space.
5. **Always** attribute HEMOBP and Mendeley as **CC BY 4.0**.
6. **Never** imply proprietary machine data is used or redistributable.
7. Prefer "research prototype", "decision support", "simulation".
8. Numbers in tables, not in prose, where possible.
