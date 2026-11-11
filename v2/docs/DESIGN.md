# HemoTwin V2 — design notes

## Direction

**Cinematic medical digital twin.** The console should feel like a clinical
instrument from the near future: deep midnight, luminous cyan/teal, a hint of
violet for uncertainty, amber for ground truth, coral for failure. The 3D kidney,
dialysis circuit and twin orb carry the "digital twin" idea; the data surfaces stay
quiet enough to read.

It is deliberately not a generic dark dashboard and not a flat clinical form. The
visual hierarchy does the work: large numbers, thin rules, glass-like cards,
generous space, one focal point per screen.

## UX principles

1. **One console, five views.** Case lab is the showpiece; Chair board is the
   pre-session overview; Live session is the working console; Session replay is
   the retrospective; Evidence & handoff is the proof. No second app, no
   ambiguous "current demo".
2. **One primary action per screen.** Pick a case, or evaluate a session, or open
   the evidence. Secondary controls stay in the sidebar or behind an expander.
3. **Progressive disclosure.** The chart, state and arithmetic are visible first;
   the 4-block state vector, full protocol pathway and TreeSHAP sit in expanders.
4. **Plain language first.** "See the pressure falling", "What each policy leaves
   behind", "What we can claim / what we refuse". Technical contract language is
   available, not forced.
5. **The guardrail is part of the demo.** A stale cuff returns
   INSUFFICIENT_INFORMATION; the system refuses to guess. The mechanism fan is off
   by default because G3 and G7 failed.
6. **Status is text + colour.** PASS / PARTIAL / FAIL / NO ALERT / REVIEW NOW,
   never colour alone.
7. **No emoji as icons.** Material icons in the nav; SVG or typographic marks
   elsewhere.
8. **Accessible on a projector.** High-contrast body text, 14–16 px minimum in the
   data surfaces, generous row heights, visible focus states, reduced-motion
   support.

## Tokens

| Role | Value |
|---|---|
| Background | `#050A12` |
| Panel | `#0B1524` / `#07111F` |
| Border | `#1E3A4A` / `rgba(148,163,184,.16)` |
| Text | `#F4F8FB` |
| Body | `#C7D6E6` |
| Muted | `#93A4B8` |
| Primary accent | `#22D3EE` (cyan) |
| Secondary accent | `#2DD4BF` (teal) |
| Uncertainty / evidence | `#A78BFA` (violet) |
| Ground truth / caution | `#FBBF24` (amber) |
| Failure / boundary | `#FB7185` (coral) |
| Pass | `#34D399` |

Display type: **Bahnschrift** (fallback Segoe UI Variable Display). Body: **Segoe UI**.
Radii: 14–18 px on cards, 8 px on small chips. No heavy drop shadows on content;
depth comes from borders, dark fills and the 3D assets. Page background uses a
subtle grid and two soft radial glows.

Chart palette: cyan for the calibrated projection; amber diamonds for observed
cuffs; coral dotted line for the 90 mmHg floor; neutral gray for confidence
intervals that cross zero. Clicking a cuff adds a cyan inspection line and
updates the twin-state panel for that minute.

## Shell

- Top brand bar: mark + HEMOTWIN + "Chair-side session twin"; research-prototype
  and decision-support pills.
- Sidebar: page navigation, then view-specific controls (case selector, role,
  illustration toggle, handoff case).
- Main: view content, with a consistent footer (research prototype, data
  provenance, no treatment recommendation).
- Pages: `/` Case lab, `/chair_board_page` Chair board, `/manual_app` Live
  session, `/replay_page` Session replay, `/evidence_page` Evidence & handoff.
  Deep links use the default Streamlit paths; navigation is through the sidebar.

## View notes

**Case lab.** Hero image → demo-path pills → five archetype buttons + two extra
cases → selected case metrics → fan chart + twin orb → fluid arithmetic →
protocol panel → expanders (state vector, SHAP) → evidence CTA. The illustrations
are off by default. Hovering a cuff shows the calibrated and observed SBP;
clicking it shows SBP, DBP, UF, and the twin state at that minute.

**Chair board.** A fixed-order six-bay rail with five patient-disjoint fold-2
sessions. Each card shows a pre-session A2 risk band and calibrated probability;
clicking a chair opens the model inputs, the claim boundary and the recorded
session. Outcomes are hidden by default. The reveal adds the recorded crash shape
as a factual strip; it is never a pre-session shape prediction. High risk is cyan,
moderate amber, low muted; coral appears only on the two recorded crashes. The
board is not sorted by risk and not an allocation order.

**Live session.** The existing manual console, wrapped in the V2 shell and
restyled. Widget labels and session-state keys are preserved for testability. The
old twin panel and playback shortcut are not shipped; the Case lab carries the v4
surface. The shadow risk is real when the event model scores the session, and
"not scored" when it cannot; no invented numbers.

**Evidence & handoff.** Gate cards, forecast lineage table, G7 forest plot,
P6a/P6b cards, temporal-order chart, frozen protocol hash, claim boundary, then
tabs for FHIR, bilingual handoff and audit.

## Demo script (3 minutes)

1. **Open on Chair board.** "Five chairs before the first cuff. One high, four
   low. No BP or current UF was read — this is history and the planned UF goal.
   The order is fixed; it is not an allocation list." Reveal: "The high chair
   crashed; the four low chairs did not. Five curated chairs are a story, not an
   accuracy estimate."
2. **Case lab** (Taper or True crash). "The solid cyan line is the validated
   forecast; amber diamonds are what actually happened. Click a cuff to read SBP,
   DBP, UF, and the twin state at that minute." True crash: "Forecast 82, observed
   nadir 78. The protocol says REVIEW NOW. The product buys time to react and
   call for advice."
3. **Fluid arithmetic.** "At calibrated gain 0 the projection is the same across
   policies. The arithmetic is what changes: fluid left and next-session UF."
4. **Evidence.** "Seven pre-registered gates. Five pass, G7 fails. The twin is a
   labelled illustration, not a treatment effect."
5. **Live session.** "This is not a mockup: enter cuffs, evaluate, get the state,
   the arithmetic and a display-only forecast."
6. **Handoff.** "FHIR, bilingual handoff, and a hash-chained local audit."

## Testing

- `python -m unittest discover -s tests -t .` — 235 tests, 0 failures; the
  heavy-lab skip count is 18 in this workspace, 28 in the lean package, 6 with
  the full portable data/artifact pack.
- AppTest covers the shell, case selection, stale guardrail, true crash, live
  evaluation, session replay, evidence page, the Chair board reveal and the
  Case Lab link; it also pins the case-label sync after a page switch.
- Playwright covers every view, the archetype buttons, the chair board at
  1440×1000 and 390×844, the live example and the evidence CTA.
- The deck is rendered to PDF/PNG and visually inspected before delivery.

## What not to do

- Do not add a second "current" app.
- Do not default the mechanism fan on.
- Do not show a fake risk score or a default dose.
- Do not mix the 9.60 oracle display with the 10.99 fair pre-anchor model.
- Do not call the audit chain immutable, authenticated or clinical.
