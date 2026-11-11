# Chair board — pre-session risk (variant A2) and recorded crash shape

> Display-only research surface. Not a medical device, not an alarm, not a
> treatment recommendation, not a chair-allocation order. A low band is not
> safe. Crash shape is recorded, not predicted.

The Chair board is the fifth V2 view. It shows five de-identified, patient-
disjoint fold-2 Case Lab sessions at session start. The risk score is computed
from history, static patient fields, and the planned UF goal only. No blood
pressure and no current UF rate are read.

The board order is fixed by chair number. It is not sorted by risk and is not a
priority or allocation order.

## Why A2, not the shipped A or B

The shared research bundle was trained with two features that are not known at
session start:

| Feature | What it actually is | Why it is excluded |
|---|---|---|
| `sbp_anchor` | BP at the task01 anchor, roughly 90 minutes in | **466 of 3,109 fold-2 crashes (15.0%) had anchor SBP below 90.** A "pre-session" card using it is partly circular. |
| `uf_ml_kg_h` | Current UF rate at that anchor (`src/features.py` uses `uf_now`) | It is the rate at that anchor, not the planned pre-session rate. |

The primary B model (fold-2 AUROC 0.8788, recall@25 0.6755, PPV@25 0.6639) and
the pre-registered secondary A model (AUROC 0.8356, recall@25 0.6102, PPV@25
0.5997) are therefore **anchor-time** models. They are not used by the Chair
board. A2 is the same recipe with both anchor-time features removed.

| Model | Fold-2 AUROC | Recall@25 | PPV@25 | ECE10 |
|---|---:|---:|---:|---:|
| B, anchor (primary; not used) | 0.8788 | 0.6755 | 0.6639 | 0.0332 |
| A, anchor-time UF (secondary; not used) | 0.8356 | 0.6102 | 0.5997 | 0.0197 |
| **A2, strictly pre-session (used)** | **0.8313** | **0.6015** | **0.5914** | **0.0184** |

Fold 2 is the untouched confirm set (12,651 sessions, 3,109 crashes, 24.6%
event rate). The A2 difference from A is small; the card is now computable
before the first cuff.

**Display bands on fold 2** (conventions, not the pre-registered 25% referral
rule): high `≥0.35` = 27.8% of sessions / 57.0% crash rate; moderate
`0.20–0.35` = 12.7% / 27.1%; low `<0.20` = 59.5% / 8.9%. **669 of 3,109 crashes
(21.5%) were low-band.** A low band is not safe.

## The five chairs

All five are fold 2 and out-of-sample. They are curated examples chosen to show
the model's range; the fold-2 metrics above are the performance estimate, not
this five-chair set. The synthetic stale-cuff guardrail is not on the board.

| Chair | Case | A2 risk | Band | Recorded outcome |
|---|---|---:|---|---|
| 01 | Stable Hold | 0.047 | low | no IDH event; nadir 160 |
| 02 | Taper | 0.051 | low | no IDH event; nadir 129 |
| 03 | Pause | 0.155 | low | no IDH event; UF paused and resumed, nadir 117 |
| 04 | True Crash | 0.702 | high | crash at 112 min (final hour); nadir 78 |
| 05 | G1 Taper Showcase | 0.096 | low | no IDH event; nadir 127 |

When outcomes are revealed, the board shows **1/1 high and 0/4 low chairs
crashed**. That is a curated five-chair story, not an accuracy estimate.

## Why crash shape is recorded, not predicted

The pre-registered shape model is conditioned on a crash and uses anchor SBP and
anchor UF. It is not a pre-session model. Its fold-2 metrics are AUROC 0.7716,
recall@25 0.4626, PPV@25 0.6615, ECE10 0.0575 against a **baseline AUROC of
0.7006** and an early-crash base rate of 0.3573. The 0.7006 figure in the
original `INTEGRATION.md` is the baseline **AUROC**, not a PPV or base rate.

We evaluated the no-anchor/no-UF ablation: AUROC **0.7047**, recall@25 0.4095,
PPV@25 0.5856, ECE10 0.0361 against the same 0.7006 baseline. That is too close
to baseline to justify a per-chair watch window, so **the board does not ship a
pre-session shape prediction**. After the reveal it shows the recorded onset only.
The anchor-based shape model remains a separate anchor-time research output.

## Claim boundary and limits

- Single-centre HEMOBP, retrospective, one fold-2 read, no external validation.
- Crash = timeline SBP <90; not symptomatic IDH.
- Planned UF goal encodes clinician behaviour; observational, no counterfactual.
- 391 sessions lack history; the model uses TUNE medians plus missing indicators.
- The high band is not a diagnosis; 43.0% of high-band fold-2 sessions did not
  crash. The low band is not safe; 21.5% of crashes were low.
- No alarm authority, no treatment advice, no chair allocation.
- Recorded shape is a fact about the record, not a prediction.

## Provenance and regeneration

Source: `crashrisk` segments 11/12 in the Digitwin research workspace. The V2
package ships the A2 booster and metadata, the A2 fold-2 re-read, the original
B confirm files, and the pre-registration copy. The training table stays in the
research workspace; the running app only reads `evidence/chair_risk.json`.

Regenerate from V2:

```bash
python scripts/lab/fit_crashrisk_noanchor.py \
    --crashrisk-dir "<path>/crashrisk"
python scripts/lab/build_chair_risk.py \
    --crashrisk-dir "<path>/crashrisk"
```

The model artifacts use LF line endings; `.gitattributes` pins them so the
LightGBM text booster stays loadable on Windows.
