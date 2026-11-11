# HemoTwin V2 — judge Q&A

> Read [`EVIDENCE_STATUS.md`](EVIDENCE_STATUS.md) before using any number in this
> document. The V2 package is a research prototype: not a medical device, not a
> prescription engine, and not a validated treatment-effect model.

**How to use this:** answer, then stop talking. If a judge wants more, they will
ask a second question.

---

### 1. "What is HemoTwin?"

One console with four views for the dialysis chair: **Case lab** (seven curated
stories and the calibrated chart), **Live session** (enter a real session, get a
protocol state and the fluid arithmetic), **Session replay** (watch the forecast,
then the recorded cuffs and UF steps roll forward), and **Evidence & handoff**
(gates, G7, FHIR, audit, pod triage). It mirrors the session, structures the
review, and makes the fluid trade-off explicit. It does not prescribe.

### 2. "Why not just predict IDH?"

Because ranking is not timing. Our event model ranked well (AUROC 0.880) but
detected only **8.2%** of event sessions at the **0.26 false-alert budget**, below
the current-SBP rule. The product is the workflow layer around the prediction; the
model stays shadow. In the field, prediction without a response workflow has
failed, while prediction plus a nursing response has been reported to halve IDH.
We do not claim our workflow is validated.

### 3. "Did the physiological twin work?"

No. **G3** actual-vs-hold is identical at calibrated gain 0. **G7**, a
pre-registered non-reactive UF step-down experiment with matched within-patient
controls, gives **τ30 +0.13 mmHg per 0.25 L/h** with a 95% CI of **[−2.63,
+3.06]**; the sham-time control fails (+2.91), and P6a gets worse out of sample
(+0.43). Verdict **FAIL**. The dashed fan is a labelled mechanism illustration,
off by default. The operational gain is 0.

### 4. "Which forecast is which?"

The console uses the **fair 59-feature pre-anchor model**: fold-2 MAE **10.99**,
RMSE 14.65, no future-UF oracle. The **9.60** number is the Forecast-v2 oracle
display: 72 features including 13 observed future-UF features. It is display-only
and **not** the G2 baseline. The smaller oracle number is not a better twin.

### 5. "What is the alert model doing?"

It is a shadow display only. AUROC 0.880 ranking, 8.2% detection at 0.26 false
alerts per session, below the current-SBP rule. It never gates the protocol, never
fires an alert, and has no clinical authority.

### 6. "Is the audit trail real?"

It is a local SHA-256 chain over demo events. It is append-only by construction,
but **not authenticated, not tamper-evident, and not an immutable clinical audit
record**. The app says so. The live-session log uses a separate local schema and
is also demo-only.

### 7. "You have no Indian data."

Correct. HEMOBP is Taiwanese and the external Spanish frame failed transport
(AUROC 0.474; label semantics differ). No Indian cohort has been collected. The
method travels; the weights do not. Deployment requires retraining on
partner-machine data and local recalibration.

### 8. "What is the evidence?"

**205,482** QC-eligible HEMOBP sessions, **1,070** patients, **4,190,926**
telemetry rows, CC BY 4.0. The G7 census uses **205,113** sessions; 369 lack the
required pre-anchor record. Labelled hypotension is **10.4%** (nadir <90); the
Spanish clinician-defined symptomatic label is **25.5%** — different labels, never
combined. Fold 2 was untouched by tuning.

### 9. "What would a pilot look like?"

A **silent-mode** run beside the team for 2–4 weeks: no machine control, no alert
authority, log what the console would have shown. Then local recalibration, then a
pre-registered prospective evaluation of time-to-review and workflow. The next
experiment is a workflow, not another model.

### 10. "What do you refuse to claim?"

A validated counterfactual or treatment effect from the twin; that any UF policy
will raise SBP, prevent IDH, or is minimum effective; alert utility, clinical
benefit, or a safety layer; prospective, external, symptomatic-IDH, or Indian-unit
validation; a prescription, a default dose, or autonomous machine action.

---

**One-line close:** the twin knows what it cannot do; that is what makes it usable
as a chair-side decision-support layer.
