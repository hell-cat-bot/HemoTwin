# HemoTwin — 20-minute video script

**Submission:** HemoTwin — *Predict the crash. Price the fix.*
**Format:** screen recording + voice-over, 1920 × 1080, 20:00 hard limit.
**Rules for this script:** every number below is from `docs/FACTS.md`. Never compare our AUROC to Zhang et al. Never call the machine a wearable. Never say "product" — it is a research prototype.

**How to read this document:** spoken lines are in block quotes. Everything in *italics* is a stage direction and is not spoken. Target pace is 130–140 words per minute. Total spoken words: **2,651**.

---

## 0:00–0:10 · Cold open

*Black screen for one second. White text fades in, centred, nothing else:*

**EVERY 30 MINUTES, SOMEONE GUESSES.**

*Hard cut to the live console. Do not fade. The cursor is already on screen.*

> Four hours. Two point two litres of fluid. One blood-pressure cuff every thirty minutes. This is a dialysis session — and the crash usually happens in the gap.

*Cut to slide 2.*

---

## 0:10–2:00 · The problem

*Slide 2. Stand still. Do not read the slide.*

> A dialysis session is a four-hour tightrope.
>
> The machine has to remove the fluid this patient has accumulated since the last session. Remove too little, and they come back overloaded: breathless, swollen, and back on the machine in two days. Remove too much, too fast, and the blood pressure falls during the session.
>
> That fall has a name: intradialytic hypotension. We use one definition throughout — a systolic below ninety millimetres of mercury during the session.
>
> It is not a minor event. In cohort studies it is associated with twice the rate of vascular-access thrombosis, nine point four times the rate of intradialytic arrhythmia, and a hazard ratio of one point five seven for mortality.
>
> Notice the word: associated. We are not claiming that hypotension causes those outcomes. We are claiming it is a signal worth acting on before it happens.
>
> Here is the operational problem. Blood pressure is measured by a cuff, and in this data the cuff fires about every thirty minutes. In between, the machine keeps working. A patient can fall from a hundred and ten to seventy-four in the gap, and the first alarm the nurse hears is the monitor confirming that it has already happened.
>
> And this is not one nurse watching one patient. In a district unit, one nurse may be watching eight chairs, and the nephrologist may be in another town.
>
> So the question is not "can we detect hypotension?" The monitor does that. The question is whether we can say something useful before the gap closes.

*Pause two seconds. Move to slide 3.*

---

## 2:00–4:00 · Why India, why now

*Slide 3. Slow down on the three numbers; they are the ones judges will repeat.*

> We are building this for India, and the reason is arithmetic.
>
> India runs more than one thousand seven hundred dialysis centres under the Pradhan Mantri National Dialysis Programme. Many are in district hospitals, and many have no nephrologist in the building. One specialist may cover a district, or several.
>
> That is not a temporary staffing problem. It is the shape of the system. If the model requires a nephrologist at every chair, it does not scale. Remote supervision is the only version that does.
>
> The second number is thirty-four point five percent. That is the share of our dialysis cohort with diabetes — three hundred and seventy of one thousand and seventy-two patients. India has about one hundred and one million people with diabetes, and a hundred and thirty-six million with prediabetes.
>
> Diabetic kidney disease is where that epidemic ends. Not in a gym, and not on a phone app. On a dialysis machine, three times a week.
>
> The third number is the one that makes the data possible: a hundred and fifty-six sessions per patient per year. The median dialysis vintage in this cohort is nine point six years. That is hundreds of sessions per patient, each one streaming machine telemetry and repeated blood pressures.
>
> No home sensor produces that density. This is one of the most densely measured chronic populations in medicine, and almost none of that data is used to make a decision in the moment.

*Advance to slide 4.*

---

## 4:00–6:00 · What exists — and what we are not claiming

*Slide 4. Say the disclaimer early. Do not let the judge ask it.*

> We are not the first people to predict this. In 2023, Zhang and colleagues published a boosted-tree model in *Nephrology Dialysis Transplantation*. Six hundred and ninety-three patients. Forty-two thousand six hundred and fifty-six sessions. An AUROC of zero point eight nine, at a horizon of fifteen to seventy-five minutes. It is deployed in six clinics in the United States.
>
> We do not claim the predictor. If the pitch were "we built an IDH classifier", you should mark us down for arriving late.
>
> Two things follow from that paper, and we take both seriously.
>
> First, our horizon is fifteen to sixty minutes, not fifteen to seventy-five. That is narrower, and a narrower horizon is an easier prediction task. So we never put our AUROC beside theirs and declare a winner. That comparison would be dishonest, and a judge who knows this literature would find it in one question.
>
> Second, if the prediction already exists, the interesting question moves downstream. What does the nurse do with it?
>
> Their output is a probability. That is the right output for their question. It is the wrong output for the question a nurse has at minute one hundred and ten, which is not "how likely is a crash" but "what happens if I act now, and what does it cost me later?"
>
> A risk number on its own produces an alarm, and every ward already has enough alarms. The brief asks for a twin: simulate this patient's physiology, personalise the protocol. A classifier cannot do that. It scores a moment. It has no state, no dynamics, and no counterfactual.
>
> That gap is what we built.

*Cut to slide 5. Say nothing for two seconds. Let the 87.2% land.*

---

## 6:00–8:00 · The insight

*Slide 5. Point at the number, then at the two bars.*

> We went looking for the intervention. If you are going to simulate a treatment, you need to know what the treatment is.
>
> So we measured what staff actually do, on thirty-two thousand five hundred and sixty-five real sessions.
>
> In eighty-seven point two percent of them, ultrafiltration is cut by more than twenty percent partway through the session. Eighty-one point seven percent end below eighty percent of their peak rate. The median rate falls from zero point five eight litres an hour at the start to zero point one zero at the end.
>
> Read that again. In almost every session, the staff already taper.
>
> Which means "reduce ultrafiltration" is not a novel intervention. It is the observed default. If we built a slider that proposed it, we would be proposing what already happens — and any risk reduction we showed would be an artefact of the data, not a treatment effect.
>
> The real decision is not whether to taper. It is when, and how much fluid you are willing to leave behind.
>
> That is a genuine bedside trade-off. Taper early, and the pressure holds, but the patient ends the session above target weight. Hold, and you finish the prescription, but you may spend the last hour managing a crash.
>
> Everyone in that unit makes this trade several times a shift. Nobody has a tool that prices it.

*Advance to slide 6, then walk the axes with the cursor.*

---

## 8:00–12:00 · What we built

*Slide 6 for the first 20 seconds, then slide 7 for the architecture.*

> Every dialysis decision sits between two harms. Pressure too low, now: access thrombosis, arrhythmia, a session that ends in saline and a stretcher. Fluid left behind, later: overload, a harder next session, and the same trade-off again on Thursday.
>
> A risk score has one number. A decision has a price. So we put both costs on the same picture — nadir on the vertical, litres left behind on the horizontal — and every policy becomes a point.

*Cut to slide 7.*

> The system has three layers.
>
> Layer one is the event model. It takes forty features from the machine stream — ultrafiltration rate, cumulative volume removed, blood flow, venous pressure, time into the session — plus a small EHR side: age, sex, diabetes, and dialysis vintage. It is trained on two hundred and five thousand four hundred and eighty-two sessions from one thousand and seventy patients, split by patient, not by session. It answers one question: what is the probability that systolic falls below ninety in the next fifteen to sixty minutes?
>
> Layer two is the twin. I want to be careful here, because "digital twin" is a phrase people use for a dashboard with a slider.
>
> The twin keeps a state for this patient. Two states, really: how much volume has been removed, and how far that volume is from what this patient's plasma refill can keep up with. It updates at every blood pressure.
>
> It has two personal parameters.

*Say "kay-refill" and "beta-b-p".*

> *k*-refill is how fast plasma refills from tissue. Beta-bp is how many millimetres of mercury you lose per litre still removed. Both start from a population prior and update on that patient's own sessions.
>
> The forward model is two equations. Volume falls with ultrafiltration and rises with refill, in proportion to the deficit. Pressure rides on volume, scaled by beta. There is no separate time-drift term, because at a thirty-minute cuff cadence it is not identifiable.
>
> That is deliberately simple. With a cuff every thirty minutes, anything richer than two parameters is not identifiable from one session — it is curve-fitting with a nicer diagram. A nephrologist can look at these two numbers and argue with them, which is exactly what we want.
>
> The parameters are fitted on the patient's prior sessions, never on the session being predicted. That matters. If we fitted the twin on the same session we were forecasting, we would be predicting backwards.
>
> Layer three is the counterfactual engine. It takes the state, projects pressure over the next hour, and runs three policies: hold the current rate, taper by twenty-five percent, or stop ultrafiltration and give fluid. Each returns a predicted nadir with an empirical interval, and the fluid not removed by session end.
>
> The interval is not decoration. It is the honest part. On the stop card, the point estimate is one hundred and three, and the interval is sixty-seven to one hundred and twenty-six. If the interval is wide, the twin is telling the nurse it does not know this patient well enough yet — and that is information too.
>
> That is the output. Not a risk score — two numbers per policy. Millimetres of mercury, and litres.
>
> Then the workflow. An eight-chair console for one nurse or one remote nephrologist. Green, amber, red. Click a chair, see the curve, see the forecast band, see the three policies, open an action sheet: taper to this rate, recheck in fifteen minutes, escalate if the nadir is below ninety.
>
> Nothing fires automatically. The sheet is a suggestion with a price tag. The nurse decides.

*Cut to the live console. Full screen. Cursor visible.*

---

## 12:00–13:00 · The demo — 60 seconds, rehearse exactly

*Do not narrate the UI. Narrate the decision. Click only three times. Hover and scroll are not clicks.*

**12:00 — Console. Eight chairs. One at fifty percent, seven under watch.**

*Hold the wide shot. Let the room see the board before you touch anything.*

> Eight chairs. One at fifty percent. Seven more under watch.

**12:05 — Chair 1**

*Click the top tile. One click.*

> Chair one. Fifty-eight, diabetic, about eighteen months on dialysis. One hundred and ten minutes into a two-hundred-and-two-minute session.

**12:12 — BP curve**

*Click once. The last two hours of real measurements appear, then the forecast band bends down.*

> This is her actual pressure for the last two hours, and this is the forecast band. It bends down.

**12:20 — Risk**

*Hover the band. Do not move the mouse away.*

> Fifty percent chance she has a hypotensive episode in the next hour.

**12:28 — What-if panel**

*Scroll once. Three cards appear: Hold, Taper 25%, Stop UF + 250 mL.*

> So here are the three things we can do.

**12:35 — Hold**

*Hover card A.*

> If we hold the current ultrafiltration, her nadir is seventy. She crashes. The real onset in this session was minute one forty.

**12:43 — Taper**

*Hover card B.*

> The cheap fix is to taper by twenty-five percent. Nadir seventy-seven, interval forty to ninety-nine. Still below the threshold, and it leaves zero point four five litres behind. Not enough.

**12:51 — Stop**

*Hover card C. It is the highlighted card.*

> So we stop ultrafiltration and give two hundred and fifty millilitres. Nadir one hundred and three, interval sixty-seven to one hundred and twenty-six. She does not crash. The price is one point seven nine litres of prescribed fluid not removed.

**12:58 — The point**

*Stop. Look at the camera, not the screen. Two full seconds of silence before this line.*

> That is the decision. Not "is she at risk" — every monitor answers that. Which cost do you want to pay?

**13:04 — Action sheet**

*Click once. The sheet slides in.*

> Stop UF now. Give two hundred and fifty millilitres. Recheck in fifteen. Escalate to the remote nephrologist. Nothing fires on its own.

**13:10 — Cut back to camera.**

---

## 13:10–16:00 · The trust panel

*Slide 8, then slide 12. Move through it quickly — this is the answer to "why should a nurse believe you?"*

> That is the demo. Now the part that decides whether anyone uses it.
>
> Trust, for a nurse, is not an AUROC. It is four things, and one honest gap.
>
> First, calibration. A fifty percent has to mean fifty out of a hundred. We show a reliability diagram, a Brier score, and the base rate beside every probability. If the model says fifty and the ward sees fifteen, the model is finished, whatever its discrimination.
>
> Second, the alarm budget. We do not pick a threshold in a paper and hide it. We expose the operating point. At ours — zero point zero four one, fixed on validation — test sensitivity is zero point eight six two, and twenty point six percent of uncomplicated sessions raise an alarm. The threshold and its false-alarm rate sit on the screen, next to the risk. Choosing that point is a staffing decision, not a modelling one.
>
> Third, reasons. SHAP values are not a nurse-facing object, so we translate them. The ultrafiltration rate is above her usual. She is one hundred and ten minutes in. Her refill index is below her own baseline. Reasons a nurse can check against the machine in front of them.
>
> Fourth, the audit log. Every recommendation, every override, every recheck, timestamped. Overrides are not failures. They are the most useful data in the system, because they mark the places where the model and the ward disagree.
>
> If a nurse overrides us, nothing argues back. The override is logged with the action taken and the next pressure reading. On Monday, we look at the overrides first — not to defend the model, but to find the patients it does not understand.
>
> And the model is not allowed to be mysterious about its limits. The subgroup analysis — vintage, diabetes, sex, age band — is pre-specified and not yet run. We will publish where it gets worse. Until then, we do not claim fairness we have not measured.

---

## 16:00–18:00 · Validation — two tasks, two tables

*Slide 11. Read the table with your hand, not your eyes. Never say the word "accuracy".*

> Now the evidence, in two tables — because there are two different tasks, and we refuse to blend them.
>
> Table one. HEMOBP, Taiwan. One thousand and seventy patients. Two hundred and five thousand four hundred and eighty-two sessions. Four point one nine million telemetry rows. Two point three four million blood-pressure events. Event-level prediction, fifteen to sixty minutes ahead, patient-disjoint test split.
>
> AUROC zero point nine one six, interval zero point eight nine seven to zero point nine three two. AUPRC zero point two three six, which is eight point four times prevalence. Sensitivity at ninety percent specificity, zero point six nine seven.
>
> But the numbers we lead with are operational. Seventy-five point seven percent of all crash sessions caught at least fifteen minutes early. Eighty-six percent of those with a usable warning window. Twenty point six percent false-alarm session rate.
>
> Two rule baselines sit underneath: zero point seven eight seven for "alarm when systolic is already low", and zero point seven three eight for "extrapolate the slope". That gap is the model earning its place.
>
> Table two. Mendeley, Spain. Seven hundred and fifty-eight patients. Ninety-seven thousand six hundred and forty sessions. Twenty-five point five percent prevalence. But it has one blood pressure before dialysis and one after — no time series. So it cannot test a fifteen-to-sixty-minute event model. It can ask a different question, will this session be labelled hypotensive. We ran that transport check; it failed. Zero point seven two internally, zero point four seven in Spain, because the Spanish label is symptomatic hypotension, not a nadir below ninety. We publish the failure and claim no external validity. Two tasks, never one blended AUROC.
>
> One more check, and it is the one we are proudest of. The twin's volume state is not a latent variable we invented. We compare modelled ultrafiltration against measured weight loss — start weight minus end weight — across a hundred and sixty-five thousand sessions. The median difference is zero point zero seven litres, the mean absolute error is zero point four, and three quarters of sessions agree within half a litre. The state is checked against the scale.

*Pause. Then slide 13.*

---

## 18:00–19:00 · Limitations, without flinching

*Slide 13. Do not soften any line. Do not add "but".*

> Now the limits.
>
> The data is Taiwanese. The Spanish cohort is an external frame, and our transport check on it failed: zero point four seven against zero point seven two internally, because the label definitions differ. We report the failure rather than hide it, and we claim no external validity. There is no Indian cohort yet. Deployment means retraining on partner-machine data, not transplanting probabilities across health systems.
>
> Blood pressure is cuffed about every thirty minutes. Two hundred and eighty-one crash sessions had no anchor inside a warnable window. The model cannot see what the machine does not measure.
>
> "Systolic under ninety" is a definition, not a symptom. We are not predicting how a patient feels.
>
> The counterfactual is observational. Everyone already tapers, so we are choosing timing within observed practice, validated on held-out patients, with intervals. It is a decision aid, not a prescription.
>
> And it is not a medical device. No clearance, no diagnosis, no automatic action. It is a research prototype in front of clinicians, and it should be judged as one.

---

## 19:00–19:50 · What next

*Slide 14.*

> Three steps.
>
> Shadow mode on a partner machine. Silent. It logs predictions, overrides and outcomes, and takes no clinical action. That is how we find out what the alarm burden really is on an Indian ward.
>
> Then a pre-registered prospective comparison against standard care, measuring hypotensive episodes, alarm burden, and fluid removed.
>
> Then retraining in India, on Indian machines, with local thresholds. The model travels as a method, not as weights.
>
> We are looking for one unit with a machine we can read, and a nursing team who will tell us when we are wrong.
>
> We are not asking for a leap of faith. We are asking for one ward, one month, and the permission to be corrected.

---

## 19:50–20:00 · Close

*Slide 14. Same framing as the cold open. Say it slowly.*

> We predict the crash, fifteen to sixty minutes early. Then we price the fix. HemoTwin — research prototype, not a medical device.

*Cut to black. Hold two seconds. End.*

---

# Say this, not that

| Say | Not | Why |
|---|---|---|
| "medical IoT", "the machine stream" | "wearable" | A haemodialysis machine is a certified device streaming 4.19M rows. It is not worn. |
| "research prototype", "decision support" | "product", "platform", "solution" | We have no clearance and no customers. The honest word is stronger. |
| "75.7% of all crash sessions" | "78%", "79%" | 86.0% uses a smaller denominator (1,783/2,073). 75.7% is all 2,354. |
| "15–60 minutes ahead" | "15–75 minutes", "up to 75 minutes" | Our labels, our evaluation and our claim are all 15–60. |
| "associated with" | "causes", "prevents", "reverses" | These are cohort associations, not causal effects. |
| "simulated within observed practice" | "what will happen" | The counterfactual is observational and within-policy-space. |
| "sensitivity 0.862 at the frozen threshold" | "accuracy", "94% accurate" | Accuracy is meaningless at 2.54% prevalence. |
| "modelled UF agrees with measured weight loss" | "we measure true blood volume" | We validate the state against the scale, not against a gold-standard volume trace. |
| "the nurse decides" | "the AI recommends treatment" | It does not prescribe. It prices two options. |
| "two cohorts, two tasks" | "303,000 sessions, one model" | Never blend the AUROCs. |
| "no Indian cohort yet" | "validated in India" | HEMOBP is Taiwanese; Mendeley is Spanish. |
| "AUPRC 0.236, 8.4× lift" | "AUROC 0.916, state of the art" | AUROC at 1% prevalence is cosmetic. Lift and alarm burden are the honest framing. |

---

# How to record

**Kit.** OBS Studio (free) or PowerPoint's *Record Slide Show*. A USB headset beats a laptop microphone; record in a small carpeted room, door closed, phone in another room.

**OBS settings.**

| Setting | Value |
|---|---|
| Canvas and output | 1920 × 1080 |
| Frame rate | 30 fps |
| Encoder | x264, CQP 18–20 (or hardware encoder at 8,000 kbps) |
| Audio | 48 kHz, mono, −12 dB peak, noise suppression on |
| Sources | Display Capture (the console) + Window Capture (the deck) + Audio Input |
| Scene discipline | One scene per section, cut on the timestamp — do not zoom during a take |

**PowerPoint route.** *Slide Show → Record Slide Show → From Beginning.* Export as MP4 at 1080p. Use it if OBS intimidates you; the deck is already 16:9.

**Recording order.**

1. Record the demo first, alone, three takes. It is the only part that needs the app to behave.
2. Record voice-over against the slide timings, section by section. Ten short files beat one 20-minute take.
3. Assemble in any editor (CapCut, DaVinci Resolve, PowerPoint). Cut on the section boundaries.
4. Loudness-normalise the whole track to −16 LUFS. Check on a phone speaker, not just headphones.

**Upload.**

- YouTube, **Unlisted** — not Private, or the judges cannot open it.
- Title: `HemoTwin — Predict the crash. Price the fix. | 20-minute submission`
- Description: one paragraph, the three numbers, dataset attributions (HEMOBP and Mendeley, CC BY 4.0), and the repo link.
- **Captions:** upload a corrected `.srt`. YouTube auto-captions will mangle "ultrafiltration", "AUPRC", "Mendeley" and every number. Fix them by hand; judges often watch muted.
- Thumbnail: the three policy cards, no faces, no stock photography.
- Keep a local MP4 copy and a second cloud copy. Do not rely on one upload finishing at 3 a.m.

**If you run out of time.** Ship the 60-second demo as a standalone clip and the slide walkthrough as a second clip, both in one unlisted playlist. A finished 18-minute video beats an unfinished 20-minute one.

---

# Timing check

| Section | Clock | Spoken words |
|---|---|---|
| Cold open | 0:00–0:10 | 27 |
| The problem | 0:10–2:00 | 253 |
| Why India, why now | 2:00–4:00 | 238 |
| What exists — and what we are not claiming | 4:00–6:00 | 267 |
| The insight | 6:00–8:00 | 225 |
| What we built | 8:00–12:00 | 567 |
| The demo — 60 seconds, rehearse exactly | 12:00–13:00 | 164 |
| The trust panel | 13:00–16:00 | 318 |
| Validation — two tasks, two tables | 16:00–18:00 | 313 |
| Limitations, without flinching | 18:00–19:00 | 140 |
| What next | 19:00–19:50 | 118 |
| Close | 19:50–20:00 | 21 |
| **Total** | **20:00** | **2,651** |

*The count excludes stage directions. That is 132 words per minute across the whole script — a normal presenting pace. Number-heavy sections read slower than the raw count suggests, so if validation runs past 18:00, drop the sensitivity-at-90%-specificity line and the two rule-baseline sentence; the deck carries both. Never cut a limitation.*
