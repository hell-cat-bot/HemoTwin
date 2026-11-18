# HemoTwin — Happiest Health Digital Twin Challenge 2026

**Finals:** Reimagining and Reforming Healthcare in India Summit 2026 · Bengaluru · 20 November 2026

**Deck files**
- `HemoTwin_Summit_2026.pptx` — 11 slides, ~7 minutes
- `HemoTwin_Summit_2026_14.pptx` — 14 slides, ~8–9 minutes
- `HemoTwin_Summit_2026.html` — HTML design proof of the 11-slide cut
- `contact_sheet_11.png`, `contact_sheet_14.png` — quick visual indexes
- `assets/` — cropped screenshots, charts and framed product images

**Claim rail for every sentence**
- Observational forecast only. No treatment-effect claim.
- The counterfactual twin test failed; it is a labelled mechanism illustration only.
- Chair board is display-only; not an alarm, not a chair-allocation order.
- No alert utility, no clinical-benefit claim, no Indian validation, no external validation.
- The audit chain is a local demo object; it is not immutable, authenticated, or a clinical record.
- No machine integration, no runtime network, no autonomous machine action.

---

## 20-second opening

> In a dialysis unit in India, a patient's blood pressure is falling. The nephrologist is remote. The technician at the chair has minutes to decide: taper the fluid, pause it, or call. HemoTwin gives that technician the next hour before the crash lands — and shows the trade-off.

## 20-second closing

> The twin knows what it cannot do — that is what makes it safe to try. One unit, four weeks, silent mode: no machine control, no alarms, just a log of what the twin would have said. If the Indian numbers hold, we earn the next study. If not, you will hear that from us too.

---

## 11-slide run of show (~7:00)

| Time | Slide | Say | Show |
|---|---|---|---|
| 0:00–0:20 | Cover | The 20-second opening. One session, one falling line, one shared state. | Dark bay, headline. Do not tour the 3D. |
| 0:20–0:55 | The problem | 1 in 10 sessions; the drop starts between cuffs; the decision lands on the technician. | The single-session chart and the 90 floor. |
| 0:55–1:30 | Ground reality | 34M sessions/year (estimate), 13,800 machines, 1–1.5 nephrologists per million. Staff already taper in 87.2% of sessions. | Three numbers and the current-deal band. |
| 1:30–2:05 | Why a twin | A score ends at a prediction; a twin mirrors state, forecasts the hour, and prices the trade-off. | Mirror / Forecast / Price + the three moments. |
| 2:05–2:40 | Before the first cuff | Five chairs, one high at 70.2%; no BP, no current UF. Reveal: the high chair crashed at 112 min, nadir 78. | Chair board + Chair 04 card. Say "curated story, not an accuracy estimate." |
| 2:40–3:15 | At the decision | The forecast is shared; the arithmetic changes. Hold 0.00 L, taper 0.25 L, keep-open 1.44 L today. | Fluid table + three price rows. |
| 3:15–3:50 | Prediction, then the record | Forecast crossed 90 at 128 min; first measured low 88 at 130 min; forecast low 84.4. Retrospective, not an alert. | Replay chart + four stats. |
| 3:50–4:40 | The boundary | We claim the hour, the band, the arithmetic. We refuse the what-if, alert utility, and Indian/external validation. The G7 test: +0.13 mmHg per 0.25 L/h, CI −2.63 to +3.06. | Claims/refusals + G7 number line. |
| 4:40–5:30 | Impact & integration | Impact is time-to-review, shared state, fluid carry-forward — not fewer crashes. One unit, 2–4 weeks, silent mode. | Three columns + the ask band. |
| 5:30–6:20 | Two models | Risk A2: AUROC 0.8313, no BP. Forecast: MAE 10.99, 59 features, no future-UF oracle. Zhang/Hong are intra-session, not comparable. | Two giant numbers + data fusion + dot plot. |
| 6:20–7:00 | What drives them | Prior IDH rate, prior nadirs, planned UF goal; recent BP minima, prior nadirs, BP sensitivity. Associations, not causes. Close on "safe to try." | Bars + closing band. |

**If you have 5 minutes:** cut slide 4 (why a twin) and slide 9 (impact/integration) to one line each; keep the product slides and the G7 test.

**If you have 10 minutes:** use the 14-slide cut.

---

## 14-slide run of show (~8–9:00)

1. Cover — 20 sec
2. The problem — 35 sec
3. Ground reality — 35 sec
4. Why a twin — 35 sec
5. One console, five views — 25 sec
6. Before the first cuff — 35 sec
7. At the decision — 35 sec
8. Prediction, then the record — 35 sec
9. The test we ran (G7) — 45 sec
10. The boundary (claims/refusals) — 35 sec
11. What we can measure now — 40 sec
12. Integration & next step — 40 sec
13. Two models — 45 sec
14. What drives them + close — 45 sec

The 14-slide cut adds the console map and splits the trust and impact beats so each one can breathe. Do not read the slides; use the screenshots as evidence and the numbers as anchors.

---

## Likely judge questions

1. **"Is this really a digital twin?"**
   A session-state twin: it mirrors the state, forecasts the next 60 minutes, and prices the fluid trade-off. The counterfactual failed and is retired; the forecast, risk band and arithmetic shipped.

2. **"Why dialysis, not diabetes or hypertension?"**
   IDH is acute, localized and frequent — 10.4% of 205,482 sessions. The machine is already the IoT stream in the room: cuffs, UF, machine settings. India has ~13,800 machines and ~34M sessions/year (estimate).

3. **"How accurate is it?"**
   Forecast: MAE 10.99 mmHg, RMSE 14.65 on untouched fold 2; 90% band coverage 89.2/90.1%. Pre-session risk: AUROC 0.8313; recall@25 0.60; PPV@25 0.59.

4. **"You have no Indian data."**
   Correct. No Indian cohort, and we will not manufacture an Indian number. Spain failed transport at 0.474 — barely better than chance. The method travels; the weights do not. India is a 2–4 week silent run, then local recalibration.

5. **"Does it alert or improve outcomes?"**
   No alert authority and no clinical-benefit claim. The event model is shadow-only: AUROC 0.880 ranking but 8.2% timely detection at the 0.26 false-alert budget, below a simple low-BP rule at 20.2%. The workflow is the intervention, tested next.

6. **"What is the ask?"**
   One unit, 2–4 weeks, silent mode: no machine control, no alarms, log what the twin would have shown. Then local recalibration and a pre-registered workflow study. CDSCO Class B intent; DPDP path.

7. **"How is this different from Fresenius TDMS or NephroPlus?"**
   They document or display reactively. HemoTwin brings pre-session risk, a +60 min forecast, and the fluid arithmetic into one device-agnostic console — with a published boundary.

8. **"Why should we trust a failed test?"**
   Because we kept it. Seven pre-registered checks, untouched fold 2, the failed G7 result in the product. A team that removes the claim that would have made it look best is a team a unit can trust.

---

## Do not say

- "The twin predicts treatment response."
- "This is what would have happened if we did what it says."
- "It reduces crashes / mortality / admissions."
- "It alerts early / catches crashes."
- "Validated in India / externally validated."
- "Immutable audit / machine integration / autonomous action."
- "The 9.60 oracle display is our fair model." The fair model is 10.99; the oracle display is display-only.
- "10.99 vs 15.55 on the taper slice." The taper slice is 11.6 vs 15.6 (n=374); 10.99 is overall fold 2.

---

## Source of truth

Every number in this deck is governed by `docs/FACTS.md` and `docs/EVIDENCE_STATUS.md`. If a number is not there, do not invent it — say "not evaluated."
