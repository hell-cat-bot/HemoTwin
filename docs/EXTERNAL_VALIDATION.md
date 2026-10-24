# External transport check — the result is negative, and that is the finding

> **Short version:** a session-level model trained on HEMOBP does **not** transport to the Spanish Mendeley cohort. AUROC **0.474** on 97,633 sessions, against **0.720** on held-out HEMOBP patients. The likely cause is that the two datasets do not share a label definition. We report the failure and claim no external validity.

This document exists because the alternative — quietly dropping the check and calling the Spanish cohort "validation" — would be the one thing a clinical judge should punish.

---

## 1. What was tested

The Spanish cohort has **one blood pressure before dialysis and one after**. There is no intra-session time series, so it physically cannot test the 15–60 minute event model. The only testable question is a different, easier one:

> Given six features both cohorts record, does a session-level model of "will this session be labelled hypotensive?" transport across countries?

| Item | HEMOBP (Taiwan) | Mendeley (Spain) |
|---|---|---|
| Unit | session | session |
| Sessions | 205,482 | 97,640 |
| Labelled hypotensive | **10.4%** (nadir SBP < 90) | **25.5%** (`D_Hipotension` = `SI`) |
| Features used | age, sex, dry weight, pre-dialysis SBP, mean UF rate, dialysate temperature | same six |
| Split | patient-disjoint, 20% held out | all rows, external |

The model is a small LightGBM (15 leaves, 400 rounds), deliberately reduced to the shared feature set. It is **not** the 40-feature event model.

## 2. Result

| Cohort | n | AUROC |
|---|---|---|
| HEMOBP, held-out patients (internal) | 50,044 | **0.720** |
| Mendeley, Spain (external) | 97,633 | **0.474** |

An AUROC below 0.5 is worse than a coin flip on the external cohort. It is not a rounding error and it is not "near chance". Something is systematically reversed.

## 3. Why it fails

The univariate directions explain it:

| Feature | HEMOBP AUROC | Spain AUROC | Same direction? |
|---|---|---|---|
| Age | 0.499 | 0.524 | no |
| Sex (male) | 0.449 | 0.491 | yes |
| Dry weight | 0.485 | 0.527 | no |
| Pre-dialysis SBP | **0.325** | **0.611** | **no** |
| Mean UF rate | 0.588 | 0.623 | yes |
| Dialysate temperature | 0.463 | 0.506 | no |

**Pre-dialysis SBP reverses.** In HEMOBP, a lower starting systolic predicts a nadir below 90 — the patient starts close to the threshold. In the Spanish registry, a higher starting systolic predicts the `SI` label, because that label is **clinician-defined symptomatic hypotension**, which is closer to a *fall* from baseline than to an absolute nadir. A patient starting at 160 who drops to 95 may be labelled hypotensive; a patient starting at 100 who stays at 95 may not.

That is a **label-semantics difference**, not a modelling bug. It is also exactly the kind of difference that makes cross-hospital deployment hard.

Secondary contributors:

- **No time series in Spain.** A session-level label cannot distinguish a transient nadir from a sustained one.
- **Different coding and units.** Sex coding, zero-coded missing values, and UF conventions differ between registries.
- **Case mix.** 25.5% prevalence versus 10.4% implies a different threshold for applying the label, not just a sicker population.

## 4. What this does and does not mean

**It does not invalidate the event model.** The event model is trained and tested inside HEMOBP with patient-disjoint splits and a time-series label. That result stands on its own cohort.

**It does invalidate any claim of external validation.** We will not say "validated in two countries". We will say: *trained on 205,482 Taiwanese sessions; the Spanish cohort was used as an external frame and a transport stress test, and the test failed.*

**It changes the deployment plan, for the better.** You cannot transplant probabilities across health systems. You retrain on the partner unit's own label, after harmonising the definition of hypotension. That is the honest path, and it is what the product proposes.

**It is a limitation to state on camera.** A judge who asks "did you validate externally?" gets a direct answer: "We tried. It failed at 0.47, because the Spanish label is symptomatic hypotension, not nadir SBP. Here is the analysis. We claim internal validity only."

## 5. Reproduce

```bash
python scripts/external_validation.py
```

Outputs:

- `artifacts/external_validation.json` — all numbers above
- `artifacts/external_log.txt` — run log

The script caches the HEMOBP session table at `artifacts/hemobp_session_table.parquet` on first run. Raw data is downloaded by `src/data.py` and is not committed.

## 6. What would make this a positive result

1. A Spanish **intra-session** BP series, so the same event label can be constructed.
2. A harmonised label: either nadir SBP < 90 for both, or a symptomatic definition for both, applied by the same rule.
3. Retraining inside Spain with a held-out patient split, then comparing to the Taiwanese model.
4. A prospective silent trial in one unit before any claim of clinical utility.

Until then, the correct statement is: **one cohort, internally validated; one external frame, transport failed.**
