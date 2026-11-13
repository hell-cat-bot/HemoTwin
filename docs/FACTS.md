# FACTS — single source of truth for all copy

> **V2 package (2026-11-10):** the console uses the **fair 59-feature pre-anchor
> v4 model** (fold-2 MAE **10.99**, RMSE 14.65, no future-UF oracle) for the
> calibrated floor, and the **72-feature Forecast-v2 oracle display** (fold-2 MAE
> **9.60**) only on the display-only card. These are different models and are
> never compared as if interchangeable. The pre-registered **G7** UF step-down
> experiment failed: τ30 **+0.13 mmHg per 0.25 L/h**, 95% CI **[−2.63, +3.06]**;
> sham control +2.91; P6a +0.43. The twin remains a labelled mechanism
> illustration; operational gain 0. See [`EVIDENCE_STATUS.md`](EVIDENCE_STATUS.md).

> **Superseded evidence notice (2026-11-07):** Task 01 and Task 02 failed their
> pre-registered utility gates. Quantitative treatment recommendations are
> retired. Read [`EVIDENCE_STATUS.md`](EVIDENCE_STATUS.md) before using any
> performance number in this document.

> Every number that appears in the README, deck, video, or dashboard **must** match this file. If a number is not here, do not invent it — write "not evaluated".

**Reproducibility note.** Event-model numbers are from the Nov 2026 v3 rerun of `python scripts/train.py` (HEMOBP, 1,070 patients): 62 features (twin-state block + research features), 3-seed ensemble, Python 3.14 / LightGBM / pandas. They are **historical development results**, not current performance claims. The twin numbers carry the v3 immediate-refill term (φ = 0.30, Wang 2023 physiology) and are likewise historical: the physiological twin is retired after the Task 01 gate failure, and the event model failed the Task 02 online alert-utility gate. The twin benchmark is `python scripts/eval_twin.py` (4,015 held-out sessions). The v2 event-model numbers (40 features, single booster: AUROC 0.916, AUPRC 0.237) are retained in docs/UPGRADE_LOG.md as the comparison point.

## Product

- **Name:** HemoTwin
- **Hook:** *Track the session. Structure the response. Show the fluid arithmetic.*
- **One-liner:** A device-agnostic session-state twin for haemodialysis. It mirrors a manually entered session state, structures a unit-defined review pathway, and calculates arithmetic fluid carry-forward for user-selected scenarios. It does not predict treatment response or recommend a prescription.
- **Status:** research workflow prototype. **Not a medical device.** Does not issue prescriptions. The risk model is a shadow display only and failed its pre-registered online alert-utility gate. Quantitative treatment recommendations are retired; see [`EVIDENCE_STATUS.md`](EVIDENCE_STATUS.md).
- **Label (historical):** first IDH event of the session (nadir SBP < 90 mmHg) with onset in `(t+15, t+60]` minutes.

## Legacy development results — not current product claims

> **Historical record only (24 October 2026).** The v3 numbers in this section
> were computed faithfully but are superseded by Task 01 and Task 02. They must
> not be presented as current model performance or clinical utility. Read
> [`EVIDENCE_STATUS.md`](EVIDENCE_STATUS.md) first.

### Event model legacy metrics (HEMOBP, patient-disjoint test split)

| Metric | Value |
|---|---|
| Cohort | HEMOBP, Taiwan, **1,070 patients** |
| Sessions (after quality filters) | **205,482** |
| Telemetry rows | **4,190,926** |
| BP measurement events | **2,342,586** |
| Prediction anchors (cohort) | **1,268,990** |
| Positive anchors (cohort) | **32,221 (2.54%)** |
| Sessions with ≥1 anchor | **194,163** |
| Features | **62** (40 v2 + 22 v3: twin-state block, history extensions, UF dynamics, BP variability) |
| Test anchors / positives | **169,854 / 4,764 (2.80%)** |
| AUROC | **0.923** (95% CI 0.906–0.937, patient-clustered bootstrap) |
| AUROC, crashes 15–30 min out | **0.933** (n_pos 1,576) |
| AUROC, crashes 30–60 min out | **0.933** (n_pos 3,188) |
| AUPRC | **0.250** = **8.9×** prevalence |
| Sensitivity @ 90% specificity | **0.721** |
| Rule baseline R1 ("alarm when SBP is low") AUROC | **0.787** |
| Rule baseline R2 ("extrapolate BP slope") AUROC | **0.738** |
| Frozen operating threshold | **0.0394** (chosen on validation for 85% sensitivity; 3-seed ensemble averaged before calibration) |
| Test sensitivity at threshold | **0.849** |
| Test alarm rate at threshold | **16.8% of anchors** |
| Event-level detection | **1,769 / 2,354 = 75.1%** of all IDH sessions; **85.3%** of the 2,073 with a usable warning window |
| Sessions with no warnable window | **281** |
| False-alarm session rate | **18.2%** |
| Session-level PPV at threshold | **30.6%** (6,563 sessions flagged) |
| Brier score | **0.0233** |
| ECE, patient-disjoint test | **0.0024** |

**Always report both detection numbers** (75.1% of all crash sessions; 85.3% of those with a usable warning window).

**Calibration:** isotonic fitted on one half of validation, evaluated on the other. ECE **0.203 raw → 0.0007 calibrated** on the held-out half (row split — optimistic by construction); the **patient-disjoint test ECE 0.0024** is the number we treat as primary.

### Legacy twin v3 validation — retired component

> **Historical record only.** The physiological twin and policy engine are
> retired: Task 01 failed its pre-registered gate. The numbers below are retained
> for the audit trail and must not be presented as current capability.

| Check | Value |
|---|---|
| Population refill rate `k_refill` | **0.245 /h** (session IQR 0.10–1.31) — literature range 0.12–0.36 /h (Mitsides 2019) |
| Population BP sensitivity `beta_bp` | **16.3 mmHg/L** (session IQR 7.8–32.2) |
| Population fit sample | **5,302 training sessions** |
| Band sample | **2,126 held-out sessions**, parameters from strictly earlier sessions only |
| Held-out nadir error (hold policy), MAE — train-report protocol, 2,126 sessions | **8.3 mmHg** (v2: 9.5; v1 constant-rate: 12.2) |
| Held-out nadir residual, 5th–95th percentile | **−22.1 to +14.4 mmHg** (v2: −19.7 to +18.7) |
| Band median residual | **+3.1 mmHg** |
| **Frozen twin benchmark** (`scripts/eval_twin.py`, 4,015 held-out sessions, anchor at 40% of session) | **MAE 8.85 mmHg**, bias **−0.57**, crash-recall 0.302, false-crash share **0.0062** (v2 on the identical benchmark: MAE 9.59, bias +2.07, false-crash 0.0118) |
| Sessions with measured pre/post weight | **16,536** |
| Modelled minus measured UF (machine vs scale), median | **+0.07 L** |
| Machine-vs-scale MAE | **0.40 L** |
| Sessions within 0.5 L of scale | **75.1%** |
| Correlation, machine-integrated vs scale UF | **0.772** |

**The changes that produced these numbers** (frozen benchmark: 4,015 held-out sessions, prior-session parameters, 40%-of-session anchor; keep-or-revert ledger in .auto/log.jsonl):

| Change | Held-out nadir MAE | Systematic bias | False crash-projections | Crash recall |
|---|---|---|---|---|
| v1 constant-rate hold | 12.6 mmHg | +5.6 mmHg | 4.2% | 0.397 |
| v2 trend-profile hold | 9.59 mmHg | +2.07 mmHg | 1.2% | 0.371 |
| **v3 = v2 + immediate refill φ = 0.30 (shipped)** | **8.85 mmHg** | **−0.57 mmHg** | **0.62%** | 0.302 |
| v3 at φ = 0.45 (better MAE, failed the recall gate — discarded) | 8.65 mmHg | −1.89 mmHg | 0.36% | **0.285** |
| v2 + within-session reconciliation (reverted in v2) | 17.7 mmHg | +11.1 mmHg | 6.1% | 0.284 |

φ is the immediate refill fraction: dD/dt = (1−φ)·UF/60 − k·D in the forward projection, with (k, β) still identified on the base structure. φ = 0.45 (upper half of Wang 2023's measured 30–50% refill band) cut MAE further but dropped crash-projection recall below the pre-registered 0.30 floor; the keep-or-revert gate discarded it and shipped the lower edge of the measured range instead.

The band is fitted out-of-sample (parameters never saw the session they predict) and clamped so its lower edge can never render a non-physiological nadir.

### Negative results we report on purpose (historical development)

- **Learned residual corrector on the twin** — ridge and LightGBM corrections fitted out-of-fold on session covariates made the held-out half WORSE on top of φ (7.54 vs 7.06 mmHg eval-half in the 12,158-session offline lab). The physiological parameter beats the black-box; nothing shipped.
- **EWMA prior weighting** — weighting recent session fits more heavily degraded the benchmark to 27+ mmHg; recent fits are the noisiest. Median of all priors stands.
- **Extra tree capacity** (63 leaves, lr 0.03) — AUPRC 0.246 vs 0.248, sensitivity at 90% specificity 0.704 vs 0.719; reverted.
- **φ = 0.45** — better MAE (8.65) but crash-projection recall 0.285 < 0.30 gate; discarded by the keep-or-revert gate (see the benchmark table above).
- **Within-session state reconciliation** — correcting the twin against cuffs observed in the current session degraded held-out nadir MAE from 9.5 to 17+ mmHg. Three to six noisy cuffs at a 30-minute cadence cannot identify a correction. Reverted; the retired console kept a display-only tracking chip.
- **Cohort-fitted thermal coefficient** — a within-patient fit of delivered dialysate temperature on SBP decline gave −0.9 ± 1.0 mmHg/°C (wrong sign; delivered temperatures span ~1.2 °C and are confounded with practice). The historical deliverable used **3.5 mmHg/°C**, the conservative end of the Cochrane RCT range (fixed cooling → end-dialysis MAP +6.5 mmHg at 1–2.2 °C; IDH rate ratio 0.52). The cooling lever is now retired with the policy engine.
- **Conditional uncertainty bands** — stratifying the band by prior-session count failed on held-out data (newer patients were not the noisier ones). One band, honestly wide.
- **External validity** — the Spanish transport check failed (AUROC 0.474 vs 0.720 internally; label semantics differ). We claim **no external validity**.
- **Actual-UF twin (Task 01)** — the physiological twin failed its pre-registered gate (taper MAE gain 4.9% < 10%; bias −7.45 / −9.23 mmHg; 21.2% worse than a direct GBDT). All quantitative treatment recommendations are retired.
- **Online alert utility (Task 02)** — the event model achieved AUROC **0.880**, but at the pre-registered alert budget it detected only **8.2%** of event sessions, below the **60%** utility threshold and below the current-SBP rule at **20.2%**. The ordinary-machine universal-input ablation was noninferior to the full telemetry model, and the manual/CSV inference path works; those are engineering and ranking results, not alert utility. The model has no alert authority.

### Forecast-v1 (2026-11-08): calibrated conditional nadir forecast

> **Observational forecasting claim only** — not a counterfactual, not a
> policy engine, not a safety layer (see `docs/EVIDENCE_STATUS.md`).

A linear-stack recalibration of the Task 01 direct GBDT nadir forecast (fit
on TUNE patients of folds 0+1 only; fold 2 untouched throughout; nonlinear
residual stages measured and discarded twice):

| Metric | Raw GBDT | Calibrated (dev EVAL) | Calibrated (fold 2, confirm) |
|---|---|---|---|
| 60-min cuff-sampled nadir MAE | 10.394 / 10.723 | **9.327 (−10.3%)** | **9.837 (−8.27%)** |
| Nadir bias (pred−obs) | +6.05 / +6.27 | −0.07 | **+0.21** |
| Crash recall at <90 projection | 0.228 / 0.270 | 0.494 | **0.524** |
| False <90 projection | 0.004 / 0.007 | 0.022 | **0.037** |
| 95% residual band coverage | — | 0.958 | **0.955** |

The dominant defect was systematic over-prediction of the nadir by ~6 mmHg;
one affine recalibration removed it (−8.9% MAE alone). Model persisted to
`artifacts/review_20261108/forecast_corrector.json` (coefficients + band +
claim note). Ledger: `.auto/log.jsonl` runs 1–8.

### Historical demo bundle (`demo/demo_bundle.json`, 8 real held-out sessions)

> **Legacy console only.** The current demo is `app/manual_app.py`; the bundle
> below feeds the retired v3 console, which is bannered as historical. Its
> contents are not current product claims.

- Eight **distinct patients**; triage mix 2 × ACT NOW, 3 × WATCH, 3 × STABLE, driven by the two engines (alarm fired × crash projected), not by a raw probability cutoff.
- Every policy card also prices the **cascade**: the litres a policy leaves behind reappear on the next prescription, shown as that session's UF intensity against the KDOQI 13 mL/kg/h ceiling.
- Chairs carry a **personal baseline** (median nadir of prior sessions, early-crash share — Keane 2021 phenotype) and a playbook-ordered action note with role scoping (tech: UF/temperature; RN: bolus).
- Twin state shown with tracking diagnostic (last cuff vs projection, display only).

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
| HEMOBP sessions with a hypotensive label | **10.4%** (nadir SBP < 90) | HEMOBP; see `docs/EXTERNAL_VALIDATION.md` |

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
- BestShape (Lin CJ et al.), *Clinical Kidney Journal* 2025. ~70,000 records, 4-year follow-up, two Taiwanese hospitals: IDH rate 26.1% → 12.9%, fewer CPR events and post-dialysis falls.
- Tsujimoto et al., Cochrane Review 2019. 25 RCTs: fixed dialysate cooling → IDH rate ratio **0.52**; end-dialysis MAP **+6.46 mmHg**; shivering RR 8.31.
- Garg et al., MyTEMP, *Lancet* 2022. 15,793 patients: personalised cooling safe; no reduction in CV death/hospitalisation; ~31% fewer IDH events in secondary analyses.
- Leung et al., CLIMB, *JAMA* 2005 / Kidney International 2020 review: biofeedback/monitoring without a structured action protocol did not reduce — and in CLIMB increased — IDH.
- Mitsides et al. 2019 (PMID 31288231): measured plasma refill rate 5.2 ± 2.9 mL/min ≈ 0.31 L/h, typical 0.12–0.36 L/h.
- Stefánsson et al., *Kidney International* 2014: IDH associated with ~60% higher 5-year mortality. Chang et al., *CJASN* 2011: IDH frequency and access thrombosis.
- Hong et al., *Scientific Reports* 2026 meta-analysis: 19 studies, pooled AUROC 0.86 (0.83–0.89); top critique = single-cohort, inconsistent definitions, uneven horizon reporting.
- ChiCTR2000036973 (preprint 2026): XGBoost-guided UF management reduced IDH vs conventional care.
- Wang et al., *Kidney360* 2023 (180,319 Crit-Line sessions): plasma refill 4.15→7.21 mL/h/kg over the first hour, scales with UFR (ρ = 0.72), refill-to-UF ratio spikes before collapse (OR 1.38 for IDH within 15 min) — the measured basis for the retired twin's φ term and the historical model's implied-refill feature.
- Keane et al., *Kidney Int* 2021 (785,682 sessions): IDH onset flat across session time; early-onset (<120 min) phenotype carries HR 1.40 all-cause / 1.64 cardiovascular mortality — the basis for the historical early-crash history feature.
- KDOQI 2015 HD Adequacy: avoid UFR >13 mL/kg/h — the reference ceiling used by the current arithmetic intensity flag and the retired cascade display.
- Cooled-dialysis meta-analysis, *Am J Nephrol* 2025: IDH RR 0.67 (0.48–0.93) — quoted alongside Cochrane's 0.52 in the historical cooling-card rationale; the lever is retired.
- Kim et al. 2022: external AUPRC 0.106. Dong et al. 2023: 10-centre C-statistic 0.82. Naïve recurrence baseline (2026): AUROC 0.798 with zero training.

## India context

- India operates **~13,800 dialysis machines across 751 PMNDP districts (1,856–1,925 centres)**; ~34M sessions/year (estimate — label it as an estimate).
- **1–1.5 nephrologists per million people** vs ~25 pmp in high-income systems; ~260–300 DM nephrology seats/year.
- **34.5%** of our dialysis cohort is diabetic — the terminal stage of India's diabetes epidemic (ICMR-INDIAB 2023: ~101.3M with diabetes).
- Cost anchors: PMNDP PPP session rate **₹1,350**; PM-JAY ₹1,200–1,800; public ICU bed-day **₹5,534** (tier-1). The historical business case used an indicative ROI ≈ **₹10–15 lakh/yr per 100 chairs** at a conservative 20–25% relative IDH reduction. That is an adjustable planning assumption, **not** an efficacy claim; the current prototype has no outcome evidence.
- Competitive: Fresenius TDMS (documentation), NephroPlus AI monitoring (Apr 2026, reactive dashboards), Medtronic HPI (5–15 min, arterial line). The current prototype does not claim prediction or policy pricing; its differentiator is a manual session-state mirror, a structured review pathway, and arithmetic fluid carry-forward.
- Regulatory: CDSCO SaMD under MDR 2017 (Class B intent; Oct 2025 AI-software guidance), DPDP Act 2023 rules notified Nov 2025 (obligations May 2027), ABDM HIP integration path.

## Rules for all copy

1. **Never** claim we beat Zhang et al. on AUROC. Our horizon (15–60 min) is narrower than theirs (15–75 min), and the current model has no alert-utility claim at all.
2. **Never** call the machine a "wearable". Call it **medical IoT**.
3. **Never** claim diagnosis, treatment, reversal, or regulatory approval.
4. **Always** state that the quantitative counterfactual and the physiological twin are retired, and that fluid scenarios are arithmetic, not prescriptions.
5. **Always** attribute HEMOBP and Mendeley as **CC BY 4.0**.
6. **Never** imply proprietary machine data is used or redistributable.
7. Prefer "research prototype", "workflow prototype", "decision support", "arithmetic".
8. Numbers in tables, not in prose, where possible.
9. The historical cooling coefficient was **literature-based** (cohort fit failed); the cooling lever itself is retired.
10. The machine-vs-scale check validates the **data join**, not a physiological twin. Do not swap those claims.
11. **Never** claim validated risk utility or alert effectiveness.
12. **Never** claim physiological digital-twin prediction.
13. **Never** claim that any option will raise SBP, prevent IDH, or is minimum effective.
14. **Never** claim the fluid scenario is a safe or feasible prescription.
15. **Never** claim authentication, role enforcement, immutable audit, or machine integration.
16. **Never** claim external, prospective, symptomatic-IDH, or Indian-unit validation.

## Must not claim

The authoritative list is in [`EVIDENCE_STATUS.md`](EVIDENCE_STATUS.md). In short:
validated risk utility or alert effectiveness; physiological digital-twin
prediction; that any option will raise SBP, prevent IDH, or is minimum effective;
that the fluid scenario is a safe or feasible prescription; authentication, role
enforcement, immutable audit, or machine integration; external, prospective,
symptomatic-IDH, or Indian-unit validation.
