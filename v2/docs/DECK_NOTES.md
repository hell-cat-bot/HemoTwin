# HemoTwin V2 — deck notes and Q&A

The deck is `deck/HemoTwin_v2.pptx` (16 slides, 16:9) with a PDF export. It is
story-first: field reality → why prediction alone fails → product → case lab →
forecast lineage → fluid arithmetic → protocol → G7 failure → claim boundary →
evidence stack → engineering → pilot ask → close → appendix.

## Slide-by-slide

**01 · Cover — "Buy time before the crash."**
Open with the field, not the technology. The doctor is remote; the technician is
at the chair; IDH does not wait. The product is a chair-side decision-support
layer, not a prescription engine. The 3D kidney is a concept illustration, not a
patient image.

**02 · The field reality — "The doctor is remote. The technician is at the chair."**
This is your background: a remotely operable, IoT-enabled dialysis machine; the
person at the chair often has to act before a doctor can be reached. The gap is
time and a shared trade-off. Say the two prevalence numbers with their labels:
10.4% HEMOBP labelled nadir <90; 25.5% Spanish clinician-defined symptomatic. They
are not the same label and are never combined.

**03 · The gap — "A monitor is not a plan."**
CLIMB (2005): monitoring plus an algorithm made outcomes worse. Our own event
model: AUROC 0.880 ranking, but 8.2% detection at the 0.26 false-alert budget,
below the current-SBP rule. The field reports AUROC; the chair needs mmHg and a
budget. The deployed system that paired prediction with a nursing response
reported 26.1% → 12.9%; we do not claim our workflow is validated.

**04 · The product — "One console. Three views. One honest boundary."**
Case lab (showpiece), Live session (working console), Evidence & handoff (proof).
The screenshot is the real app. "Mirror the session. Show the trade-off. Buy time
to react."

**05 · Case lab — "Seven stories. One honest chart."**
The amber diamonds are ground truth; the cyan line is the only validated
projection; the violet X is the retired v3 twin (167 vs observed 115). The dashed
mechanism fan is hidden by default because G3 and G7 failed. The archetypes:
stable hold, taper, paused UF, true crash, stale cuff, mixed, taper showcase.

**06 · Forecast lineage — "Two forecasts. Do not mix them."**
Fair pre-anchor twin: 59 features, no future-UF oracle, fold-2 MAE 10.99, RMSE
14.65, used in the console. Forecast-v2 oracle display: 72 features including 13
observed future-UF features, fold-2 MAE 9.60, display-only, not the G2 baseline.
The smaller oracle number is not a better twin.

**07 · Fluid arithmetic — "The trade-off, in litres."**
Use the g1_taper_showcase: calibrated 116.6 vs observed 115. The calibrated nadir
is identical across policies at gain 0; fluid left and next-session UF change. The
table: 0.50 L / 16.5, 0.68 / 17.4, 0.88 / 18.4, 1.18 / 19.9, pause 0.88 / 18.4.
This is arithmetic, not a prescription; it gives the technician a number to
discuss with a doctor.

**08 · Decision support — "The next step is a pathway, not a score."**
True crash case: observed nadir 59, state REVIEW NOW. Measured criteria activate
URGENT / REVIEW_NOW / NO_ALERT / INSUFFICIENT. The pathway steps are role-scoped:
assess the patient, repeat and verify BP, review the UF state. The forecast never
gates the state; the shadow score has no alert authority.

**09 · The twin experiment — "We tested it. It failed."**
581 matched events / 158 patients. τ30 +0.13 mmHg per 0.25 L/h, 95% CI [−2.63,
+3.06]. Sham-time control +2.91 [2.31, 3.54] fails. P6a +0.43 [0.15, 0.65] worse
out of sample. Verdict FAIL. The effect is indistinguishable from zero; the
operational gain stays 0.

**10 · Claim boundary — "What we refuse to claim."**
We can claim the calibrated forecast, fluid arithmetic, protocol pathway, honest
negative results, FHIR/audit. We refuse a validated twin effect, a recommendation,
alert utility, prospective/external validation, and a prescription. The boundary
is why the rest is trustworthy.

**11 · The evidence — "205,482 sessions. 581 matched events."**
205,482 QC-eligible sessions; 1,070 patients; 4,190,926 telemetry rows; 10.4%
labelled hypotension. 205,113 sessions enter the G7 census; 369 lack the required
pre-anchor record. 25.5% Spanish clinician-defined symptomatic; different label.
External transport AUROC 0.474 failed. HEMOBP CC BY 4.0.

**12 · Engineering — "Built to be inspected."**
217 package tests, 0 failures, 28 heavy-artifact tests explicitly skip-gated; full
lab suite 241. 14/14 claim-boundary checks. FHIR R4 + bilingual handoff. SHA-256
audit chain, demo-only, not clinical. The retired v3 console is not shipped.

**13 · The ask — "Give us a chair, not a stage."**
Silent mode (2–4 weeks, no machine control), local recalibration, prospective
evaluation. We are not asking for a trial on day one; we are asking to run beside
the team and measure whether the console buys time to react.

**14 · Close — "The twin knows what it cannot do."**
A chair-side decision-support layer for dialysis. Research prototype; not a medical
device; no treatment recommendation.

**15 · Appendix A — gates.** G1 pass; G2 pass vs base / fail vs oracle; G3 fail;
G4 pass; G5 pass; G6 pass; G7 fail. A pass is an engineering check, not clinical
validation.

**16 · Appendix B — Q&A.** Model, twin, alert and deployment answers. Every number
is traceable to `evidence/` and `docs/EVIDENCE_STATUS.md`.

## Q&A ammunition

**"Why not just predict IDH?"** Ranking is not timing. Our AUROC 0.880 model
detected 8.2% at the alert budget, below the current-SBP rule. The product is a
workflow layer; the model stays shadow.

**"Did the twin work?"** No. G3 actual-vs-hold is identical at gain 0; G7 τ is
+0.13 with a CI including zero; the sham control fails; P6a gets worse. The fan is
a labelled illustration.

**"Why show the twin at all?"** Because the experiment is the evidence. It shows
what we tested and what we refuse to claim. The console's validated surface is the
pre-anchor forecast plus the fluid arithmetic and protocol.

**"Which forecast is 10.99?"** The fair 59-feature pre-anchor model used in the
console. The 9.60 is the oracle display forecast with 13 future-UF features; it is
not the G2 baseline.

**"What about the alert?"** AUROC 0.880, 8.2% detection at 0.26 false alerts per
session, below the current-SBP rule. Shadow only; no alert authority.

**"Is this validated?"** No prospective, external, symptomatic-IDH or Indian-unit
validation. No authentication, no machine integration. The audit chain is local
and demo-only. That is the boundary.

**"What would a pilot look like?"** Silent mode beside the team, local
recalibration, then a pre-registered prospective evaluation of time-to-review and
workflow.

## What not to say

- Do not say the twin predicts or prevents crashes.
- Do not say the fan is a treatment effect.
- Do not say "6/6 gates" or "validated".
- Do not mix the 9.60 and 10.99 numbers.
- Do not call the audit chain immutable or clinical.
- Do not offer a default dose or a machine action.

## Timing

A 10-minute version: cover (1 min), field + gap (2 min), product + case lab
(2 min), lineage + fluid (2 min), G7 + boundary (2 min), pilot/close (1 min).
The live demo can replace slides 4–8 if the judges want to interact.
