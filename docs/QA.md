# HemoTwin — judge Q&A

Twenty-one questions we expect, with answers short enough to say in one breath. Every number is from `docs/FACTS.md`.

**How to use this:** answer, then stop talking. The silence is what makes it sound certain. If a judge wants more, they will ask a second question — and a second question is a good sign.

---

### 1. "Is dialysis a chronic condition? It's an acute treatment."

ESRD is the chronic condition; dialysis is its treatment. These patients receive **156 sessions a year**, for a median vintage of **9.6 years**. That is a denser longitudinal physiological record than any consumer wearable produces. The chronic disease is kidney failure. The machine is where we observe it.

---

### 2. "The machine isn't a wearable."

The brief says **wearable/IoT**. A haemodialysis machine is IoT in the strictest sense: a certified medical device streaming **4,190,926 timestamped measurements** and **2,342,586 BP events**. Unlike a step counter, it measures the physiology that drives the event. We say **medical IoT**, never wearable.

---

### 3. "This is already published."

Correct. Zhang et al. published the 15–75 min predictor in *NDT* 2023 — AUROC 0.89, deployed in six US clinics. **We do not claim the predictor.** We claim the taper-policy twin, a volume state checked against measured weight loss, two cohorts across two countries, and a remote-operations workflow. Our horizon is narrower, so we never compare AUROCs.

---

### 4. "Your counterfactual is observational."

Yes, and it is on the limitations slide. It is a **within-policy-space** simulation: 87.2% of sessions already taper, so we are choosing timing, not inventing an intervention. It is validated on held-out patients, carries intervals, and is a decision aid — not a prescription or a causal claim.

---

### 5. "You have no Indian data."

Correct. HEMOBP is Taiwanese, Mendeley is Spanish, and we say so without being asked. Deployment means **retraining on partner-machine data** with local thresholds; we never transplant probabilities across health systems. The method travels. The weights do not.

---

### 6. "Why should a nurse trust it?"

Because it shows its work: calibration on held-out patients, an alarm budget the nursing team chooses, drivers in plain language, and a log of every override. And because it does not act. It prices two options and leaves the choice with the nurse.

---

### 7. "What's the business model?"

Per-session SaaS for dialysis chains and PMNDP-empanelled centres, priced per chair per month. India runs roughly **34 million sessions a year** — an estimate, labelled as one. The buyer is the operator, not the patient. We have no pilot contract and no revenue; this is a research prototype.

---

### 8. "How is this different from an alarm?"

An alarm says a number is low now. HemoTwin prices three policies: hold gives a nadir of **70 mmHg**; a 25% taper gives **77** (interval **40–99**) and leaves **0.45 L** behind; stopping UF gives **103** and leaves **1.79 L** behind. A threshold versus a priced decision.

---

### 9. "What if the model is wrong?"

The interval is on screen, not just the point. If the twin is wrong, the nurse still has the trend, the drivers, and the rule baselines. Nothing fires automatically, and the action sheet needs a human click. The system fails as advice, not as automation.

---

### 10. "Did you calibrate on the test set?"

No. Calibration is fitted on validation, never test. We score it on held-out patients with a reliability curve and a Brier score — not with a binning artefact. The near-zero ECE in the original notebook was exactly that artefact, so we rebuilt calibration on a held-out half and report Brier as well.

---

### 11. "Why 15–60 minutes and not 15–75?"

Because the next hour is the action window: taper, stop, recheck, call. Zhang's 15–75 model is published and deployed; ours is a narrower, easier task at 15–60. We report detection strictly inside that window, and we never compare the two AUROCs.

---

### 12. "How many false alarms per shift?"

At a **20.6% false-alarm session rate** and eight chairs per shift, about **1.6** uncomplicated sessions alarm per shift. That is arithmetic on eight chairs, not a measured ward count — and it is why the nursing team sets the threshold, not us.

---

### 13. "What happens when the nurse overrides you?"

It is logged, not argued with. Time, recommendation, action taken and next BP are recorded. Overrides are reviewed weekly because they mark where the model and the ward disagree — and they are the most useful data we collect.

---

### 14. "What's the regulatory pathway?"

India: CDSCO medical device rules. A decision-support tool that does not diagnose or prescribe is lower risk, but any claim of clinical benefit needs evidence. The path is research prototype → shadow mode → prospective comparison → regulatory advice. We are at step one, and we say so.

---

### 15. "What about data privacy?"

Both cohorts are de-identified, open and **CC BY 4.0**. No proprietary machine data is in the repo. At deployment, inference runs inside the unit, FHIR/ABDM-aligned, with no patient identifiers leaving the network and audit logs held locally.

---

### 16. "Why not do T2D? That's the bigger problem."

T2D is upstream; dialysis is downstream. **34.5%** of this cohort is diabetic, and these patients generate **156 machine-measured sessions a year**. A CGM samples glucose every few minutes; this cohort gives **4.19 million** timestamped measurements. We chose the denser signal and the harder event.

---

### 17. "What would you do with three more months?"

Shadow mode on one Indian unit: retrain on local data, measure alarm burden per shift, then a pre-registered prospective comparison against standard care. Also prospective validation of the twin's nadir interval — that is the claim with the least evidence behind it.

---

### 18. "How do you handle missing BP?"

Anchors with no BP in the label window are dropped, not filled. The twin propagates state from the last measured value and widens its interval as the gap grows. At ~30-minute cuffing, **228** crash sessions had no usable warning anchor — we report them.

---

### 19. "Is the twin identifiable from one session?"

Two parameters per patient, fitted with a population prior and updated from that patient's **prior** sessions — never the session being predicted. From one session they are weakly identified, and the interval says so. With five to ten sessions they stabilise. We report the distributions.

---

### 20. "What's the failure mode?"

Two. A patient whose refill collapses faster than the prior allows: the twin lags, and the interval widens instead of the point estimate warning. And alarm fatigue at **20.6%** false-alarm sessions. Both are written down in the model card, and both are tracked in shadow mode.

---

### 21. "Did you validate externally?"

Yes, and it failed. A reduced session-level model scored **0.720** on held-out HEMOBP patients and **0.474** on 97,633 Spanish sessions. The cause is label semantics: HEMOBP uses nadir SBP < 90, Spain records clinician-defined symptomatic hypotension. We publish the analysis and claim **internal validity only**. Retraining on the partner's label is the deployment path.

---

## If you get a question we did not prepare

Say: *"We don't have that number. What we do have is —"* and give the nearest verified number, with its units and its source. Then say what you would measure to answer it.

Never improvise a metric. A judge who catches one invented number will distrust the other thirty.

