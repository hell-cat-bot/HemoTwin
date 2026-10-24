# Submission Checklist — Digital Twin Challenge 2026

Deadline: **24 October 2026, 7:00 PM IST** on Unstop. Internal target: **12:00 PM**.
Everything below must be true before the link is submitted. Each row is a gate, not a suggestion.

---

## 0. Fill the placeholders first

| Placeholder | Where it appears | Owner |
|---|---|---|
| `HemoTwin_TeamName_CollegeName` (folder name) | repository root | Team leader |
| `[Team Name]`, `[College / Incubator]` | README, video, deck | Team leader |
| `[Member 1 — role]` … `[Member 4 — role]`, phone, email | README, deck | Team leader |
| `[City, State]`, `[DD Month 2026]` | README | Team leader |
| `[Unlisted YouTube link]` | README | Video owner |

No square brackets may survive in the final repository. Run a search for `[` before submitting.

---

## 1. Repository and naming

| Done | Item | Detail |
|---|---|---|
| ☐ | Folder renamed | Root folder is `YourTeamName_YourCollegeName`. Not `HemoTwin_TeamName_CollegeName`. |
| ☐ | Public repository | Visibility is Public, not private. |
| ☐ | Default branch clean | `main` contains the final state. No stray branches, no merge conflict markers. |
| ☐ | No secrets | No API keys, no `.env`, no personal data. |
| ☐ | No raw data committed | `data/raw/` excluded. The 263 MB HEMOBP download must not be in git history. |
| ☐ | No absolute paths | No `D:\...` or `/Users/...` paths in code, notebooks, or docs. |

---

## 2. README: the six required sections

The brief requires six items in the README. Verify each is present and clearly headed.

| Done | Required item | Where in our README |
|---|---|---|
| ☐ | Team details and college/incubator info | "Team details & college" |
| ☐ | Project title | Top of file, with hook and badges |
| ☐ | Problem statement and healthcare use case | "Problem statement & healthcare use case" |
| ☐ | Technical stack and AI/ML model/framework details | "Technical stack & model details" |
| ☐ | Minimum 20-minute video explaining and demonstrating the prototype | "20-minute video" with a working unlisted link |
| ☐ | Open-source licence details | "Data & licence" plus the `LICENSE` file |

Additional sections that must also be present: what a digital twin means here, architecture, results, the 87.2% insight, dashboard, how to run, limitations and ethics, repository structure, citation.

| Done | Check | Detail |
|---|---|---|
| ☐ | Both detection denominators in the results table | 86.0% of evaluable sessions and 75.7% of all IDH sessions |
| ☐ | No claim of beating Zhang et al. on AUROC | The explicit disclaimer paragraph is present |
| ☐ | No marketing superlatives | No "revolutionary", "world-first", "state-of-the-art breakthrough" |
| ☐ | Every number matches `docs/FACTS.md` | Cross-check table by table |

---

## 3. Artefacts

| Done | Artefact | Format | Path |
|---|---|---|---|
| ☐ | Architecture diagram | **PDF** export (plus the SVG source) | `docs/architecture.pdf`, `docs/architecture.svg` |
| ☐ | Presentation deck | **PDF** export | `deck/HemoTwin_Deck.pdf` |
| ☐ | Video | Unlisted YouTube, 20:00 or longer | link in README |
| ☐ | Licence | `LICENSE` at repo root | MIT, "2026 HemoTwin Team" |
| ☐ | Model card | Markdown | `docs/MODEL_CARD.md` |
| ☐ | Architecture write-up | Markdown, one page | `docs/ARCHITECTURE.md` |
| ☐ | Video script | Markdown, timed | `docs/VIDEO_SCRIPT.md` |
| ☐ | Requirements | Pinned ranges, installs clean | `requirements.txt` |

**PDF export check.** Open the exported PDF on a machine that does not have the project fonts. The architecture diagram must be legible at A3 and at A4 landscape, with no clipped labels.

---

## 4. Video

| Done | Check | Detail |
|---|---|---|
| ☐ | Length ≥ 20:00 | Timestamp visible or stated. Do not submit 19:40. |
| ☐ | Unlisted, not private | Private links fail for judges. Test in an incognito window. |
| ☐ | Audio audible | Play on a laptop speaker at 50% volume; if inaudible, re-record. |
| ☐ | Screen text readable | 1080p minimum. Zoom the dashboard before recording. |
| ☐ | Live demo, not slides only | At least one real interaction: chair board → session → what-if → action. |
| ☐ | Both detection numbers spoken | 75.7% of all IDH sessions, 86.0% of evaluable sessions. |
| ☐ | Zhang disclaimer spoken | "We do not claim to beat Zhang on AUROC; our horizon is narrower." |
| ☐ | Limitations stated out loud | Taiwanese/Spanish data, cuff cadence, observational counterfactual, no Indian cohort. |
| ☐ | No patient identifiers on screen | The demo uses de-identified open data; say so on camera. |

Follow `docs/VIDEO_SCRIPT.md` for timings. Rehearse the 60-second demo at least three times.

---

## 5. Fresh-clone test

Run this on a clean machine or a fresh directory. If any step fails, fix it before submitting.

```bash
git clone <public-repo-url> hemo_test
cd hemo_test
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

| Done | Check | Detail |
|---|---|---|
| ☐ | Clone succeeds without credentials | Public URL, incognito browser |
| ☐ | `pip install` completes | No missing dependency, no network-locked package |
| ☐ | Demo starts with no raw data present | Falls back to `demo/demo_bundle.json` |
| ☐ | All five views open | Chair board, session, twin state, what-if, trust |
| ☐ | No network calls at runtime | Disconnect Wi-Fi and click through every view |
| ☐ | Console shows no exceptions | Check the terminal, not just the browser |
| ☐ | Loads in under 30 seconds | Judge patience is finite |

---

## 6. Incognito link audit

Open every link below in a logged-out browser. A 404 or a permission wall costs points silently.

| Done | Link |
|---|---|
| ☐ | Repository root |
| ☐ | `README.md` renders with images and tables |
| ☐ | `docs/architecture.pdf` |
| ☐ | `docs/architecture.svg` (opens or downloads) |
| ☐ | `deck/HemoTwin_Deck.pdf` |
| ☐ | `LICENSE` |
| ☐ | `docs/MODEL_CARD.md` |
| ☐ | `docs/ARCHITECTURE.md` |
| ☐ | `docs/VIDEO_SCRIPT.md` |
| ☐ | YouTube video |
| ☐ | HEMOBP DOI resolves; the Mendeley record is findable from the title given in the README |

---

## 7. Content integrity audit

| Done | Check | Detail |
|---|---|---|
| ☐ | No regulatory claim | Nothing says approved, cleared, certified, or clinical-grade |
| ☐ | No diagnostic claim | Nothing says the model diagnoses hypotension |
| ☐ | No treatment instruction | No specific mL/h is presented as a prescription |
| ☐ | Counterfactual labelled observational | Stated in README, model card, architecture and video |
| ☐ | "Medical IoT", never "wearable" for the machine | Search the repository for "wearable" |
| ☐ | Both datasets attributed as CC BY 4.0 | HEMOBP and Mendeley, with citation |
| ☐ | No proprietary data implied | No "our machines", no "our hospital data" |
| ☐ | Indian context labelled as context, not evidence | 1,700+ PMNDP centres and 34M sessions/year framed correctly; the 34M figure marked as an estimate |
| ☐ | Every number traceable to FACTS | Spot-check the results table, model card and deck |

---

## 8. What to submit on Unstop

Submit **only** these four items. Do not paste an essay into the form.

| Field | Value |
|---|---|
| Team leader name | `[Full name]` |
| Phone | `[+91 ...]` |
| Email | `[leader@...]` |
| Public repository link | `https://github.com/[org]/[TeamName_CollegeName]` |

| Done | Final step |
|---|---|
| ☐ | Submit by **12:00 PM IST**, not 7:00 PM |
| ☐ | Screenshot the confirmation page |
| ☐ | Save the submission ID |
| ☐ | Verify the repo link one final time after submitting |

---

## 9. Last 30 minutes

1. Re-run the fresh-clone test from a new directory.
2. Open the video in incognito and confirm it plays past 20:00.
3. Search the repository for `[`, `TODO`, `FIXME`, `D:\`.
4. Confirm the folder name and README team block are filled.
5. Submit, screenshot, stop editing.
