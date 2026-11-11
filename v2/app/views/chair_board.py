"""Chair board: a display-only, pre-session risk view for five chairs."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.ui import theme

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"
BOARD = EVIDENCE / "chair_risk.json"

CSS = """
<style>
.st-key-chair_rail [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
  gap: 10px !important;
}
.st-key-chair_rail [data-testid="column"] {
  flex: 1 1 158px !important;
  width: auto !important;
  min-width: 158px !important;
}
.st-key-chair_rail div[data-testid="stButton"] > button {
  min-height: 2.35rem;
  padding: 6px 8px;
  font-size: 11px;
}
.cb-axis {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid var(--ht-line);
  padding-top: 7px;
  margin: 12px 0 6px;
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.cb-axis span::before {
  content: "";
  display: inline-block;
  width: 1px;
  height: 7px;
  margin-right: 6px;
  background: var(--ht-line-strong);
  vertical-align: middle;
}
.cb-axis-note {
  margin: 0 0 12px;
  color: var(--ht-muted);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.cb-card {
  min-height: 248px;
  padding: 13px 14px 12px;
  border: 1px solid var(--ht-line);
  border-radius: 12px;
  background: linear-gradient(155deg, rgba(15, 23, 42, 0.9), rgba(7, 13, 26, 0.95));
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.cb-card--high { border-color: rgba(34, 211, 238, 0.34); }
.cb-card--moderate { border-color: rgba(251, 191, 36, 0.32); }
.cb-card--low { border-color: rgba(148, 163, 184, 0.18); }
.cb-card.is-selected {
  border-color: rgba(34, 211, 238, 0.66);
  box-shadow: inset 0 2px 0 var(--ht-cyan);
}
.cb-card--empty {
  border-style: dashed;
  opacity: 0.62;
}
.cb-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}
.cb-card__no {
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 9px;
  letter-spacing: 0.14em;
  white-space: nowrap;
  flex: 0 0 auto;
}
.cb-card__name {
  color: var(--ht-text);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.15;
}
.cb-card__session, .cb-card__patient {
  color: var(--ht-muted);
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 10px;
  line-height: 1.35;
}
.cb-card__prob {
  color: var(--ht-text);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 32px;
  line-height: 1;
  letter-spacing: -0.03em;
}
.cb-card__prob span {
  color: var(--ht-muted);
  font-size: 12px;
  letter-spacing: 0;
  margin-left: 2px;
}
.cb-card__prob--low { color: #B8C6D9; }
.cb-badge {
  border: 1px solid var(--ht-line);
  border-radius: 999px;
  padding: 3px 5px;
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 8px;
  letter-spacing: 0.1em;
  white-space: nowrap;
  flex: 0 0 auto;
}
.cb-badge--high { color: #67E8F9; border-color: rgba(34, 211, 238, 0.42); }
.cb-badge--moderate { color: #FCD34D; border-color: rgba(251, 191, 36, 0.4); }
.cb-badge--low { color: #B8C6D9; }
.cb-gauge {
  position: relative;
  height: 6px;
  border-radius: 3px;
  background: rgba(148, 163, 184, 0.16);
  overflow: hidden;
  margin-top: 2px;
}
.cb-gauge__fill {
  display: block;
  height: 100%;
  width: var(--cb-p);
  border-radius: 3px;
  background: var(--ht-cyan);
}
.cb-gauge__fill--moderate { background: var(--ht-amber); }
.cb-gauge__fill--low { background: #64748B; }
.cb-gauge__mark {
  position: absolute;
  top: 0;
  width: 1px;
  height: 100%;
  background: rgba(244, 248, 251, 0.52);
}
.cb-gauge__scale {
  display: flex;
  justify-content: space-between;
  color: var(--ht-muted);
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 8px;
}
.cb-watch {
  border: 1px solid var(--ht-line);
  border-radius: 8px;
  padding: 6px 7px;
  background: rgba(5, 10, 18, 0.36);
}
.cb-watch--off {
  color: var(--ht-muted);
  font-size: 9px;
  line-height: 1.35;
}
.cb-watch__head {
  display: flex;
  justify-content: space-between;
  gap: 4px;
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 8px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.cb-watch__track {
  display: flex;
  gap: 2px;
  margin: 6px 0 4px;
  position: relative;
}
.cb-watch__seg {
  flex: 1;
  height: 5px;
  border-radius: 2px;
  background: rgba(148, 163, 184, 0.14);
}
.cb-watch__seg.is-on { background: var(--ht-cyan); }
.cb-watch__onset {
  position: absolute;
  top: -3px;
  width: 2px;
  height: 11px;
  background: var(--ht-coral);
  border-radius: 1px;
}
.cb-watch__foot {
  color: var(--ht-muted);
  font-size: 8px;
  line-height: 1.35;
}
.cb-outcome {
  margin-top: auto;
  padding-top: 4px;
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  min-height: 22px;
}
.cb-outcome--event { color: #FDA4AF; }
.cb-outcome--clear { color: #B8C6D9; }
.cb-card__empty-label {
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 14px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.cb-card__empty-copy {
  color: var(--ht-muted);
  font-size: 10px;
  line-height: 1.45;
  margin-top: 4px;
}
.cb-detail {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 14px;
  border: 1px solid var(--ht-line);
  border-radius: 14px;
  padding: 18px 20px;
  background: linear-gradient(155deg, rgba(15, 23, 42, 0.72), rgba(7, 13, 26, 0.82));
  margin-top: 14px;
}
.cb-detail__kicker {
  color: #67E8F9;
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.cb-detail__title {
  color: var(--ht-text);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.1;
  margin: 4px 0 5px;
}
.cb-detail__session {
  color: var(--ht-muted);
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 10px;
}
.cb-detail__risk {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 12px 0 4px;
}
.cb-detail__risk strong {
  color: var(--ht-text);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 34px;
  font-weight: 600;
  line-height: 1;
}
.cb-detail__risk span { color: var(--ht-muted); font-size: 11px; }
.cb-detail__section {
  border-top: 1px solid var(--ht-line);
  padding-top: 10px;
  margin-top: 10px;
}
.cb-detail__label {
  color: var(--ht-muted);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.cb-kv {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  margin: 0;
  font-size: 11px;
}
.cb-kv dt { color: var(--ht-muted); margin: 0; }
.cb-kv dd {
  color: var(--ht-text);
  margin: 0;
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 10px;
  text-align: right;
}
.cb-note {
  color: var(--ht-muted);
  font-size: 10px;
  line-height: 1.45;
  margin: 6px 0 0;
}
.cb-observed {
  border-left: 2px solid var(--ht-line-strong);
  padding-left: 9px;
  color: #C7D6E6;
  font-size: 11px;
  line-height: 1.5;
}
.cb-observed--event { border-left-color: var(--ht-coral); }
.cb-observed--clear { border-left-color: var(--ht-line-strong); }
.cb-model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin: 8px 0 10px;
}
.cb-model-cell {
  border: 1px solid var(--ht-line);
  border-radius: 10px;
  padding: 10px 12px;
}
.cb-model-cell b {
  display: block;
  color: var(--ht-text);
  font-family: "Bahnschrift", "Segoe UI Variable Display", sans-serif;
  font-size: 11px;
  letter-spacing: 0.04em;
}
.cb-model-cell span {
  color: var(--ht-muted);
  font-size: 10px;
  line-height: 1.4;
}
.cb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  margin: 8px 0 10px;
}
.cb-table th, .cb-table td {
  border-bottom: 1px solid var(--ht-line);
  padding: 6px 8px;
  text-align: left;
}
.cb-table th { color: var(--ht-muted); font-weight: 500; }
.cb-table td { color: var(--ht-text); }
.cb-model-note { color: var(--ht-muted); font-size: 10px; line-height: 1.5; }
@media (max-width: 980px) {
  .cb-detail { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .cb-detail { padding: 14px; }
  .cb-card { min-height: 0; }
  .st-key-chair_rail [data-testid="column"] {
    flex: 1 1 100% !important;
    min-width: 100% !important;
  }
}
</style>
"""


@st.cache_data(show_spinner=False)
def load_board(mtime: float) -> dict:
    # mtime is part of the cache key so a rebuilt sidecar is picked up.
    return json.loads(BOARD.read_text(encoding="utf-8"))


def _e(value) -> str:
    return theme.e(value)


def _sid_short(sid: str) -> str:
    pid, _, day = sid.partition("_")
    return f"{pid} · {day}"


def _sex(patient: dict) -> str:
    return "M" if float(patient.get("sex_M") or 0) >= 0.5 else "F"


def _patient_line(patient: dict) -> str:
    age = patient.get("age")
    vintage = patient.get("vintage_years")
    if age is None:
        return _sex(patient)
    if vintage is None:
        return f"Age {float(age):.0f} · {_sex(patient)}"
    return f"Age {float(age):.0f} · {_sex(patient)} · {float(vintage):.1f}y"


def _risk_label(band: str) -> str:
    return {"high": "HIGH", "moderate": "MODERATE", "low": "LOW"}[band]


def _risk_glyph(band: str) -> str:
    return {"high": "◆", "moderate": "◐", "low": "○"}[band]


def _recorded_shape_label(band: str) -> str:
    return {"early": "EARLY",
            "mid_session": "MID-SESSION",
            "final_hour": "FINAL-HOUR",
            "no_event": "NO EVENT"}.get(band, "NO EVENT")


def _pct(prob: float, digits: int = 0) -> str:
    return f"{100.0 * float(prob):.{digits}f}%"


def _badge(band: str) -> str:
    return (f'<span class="cb-badge cb-badge--{band}">'
            f'<span aria-hidden="true">{_risk_glyph(band)}</span> '
            f'{_risk_label(band)}</span>')


def _gauge(prob: float, band: str, detail: bool = False) -> str:
    width = max(2.0, min(100.0, 100.0 * float(prob)))
    cls = f" cb-gauge__fill--{band}" if band in ("moderate", "low") else ""
    scale = (
        '<div class="cb-gauge__scale"><span>low</span>'
        '<span>20</span><span>35</span><span>high</span></div>'
        if detail else ""
    )
    return (
        f'<div class="cb-gauge" role="img" aria-label="'
        f'{_e(_risk_label(band))} risk, {_pct(prob, 1)}">'
        f'<span class="cb-gauge__fill{cls}" style="--cb-p:{width:.1f}%"></span>'
        f'<i class="cb-gauge__mark" style="left:20%"></i>'
        f'<i class="cb-gauge__mark" style="left:35%"></i></div>{scale}'
    )


def _recorded_watch(chair: dict, reveal: bool, detail: bool = False) -> str:
    obs = chair["observed"]
    if not reveal:
        return ('<div class="cb-watch cb-watch--off">Recorded shape hidden.'
                '</div>')
    if not obs.get("event"):
        return ('<div class="cb-watch cb-watch--off">No IDH event recorded.'
                '</div>')
    band = obs.get("recorded_shape", "mid_session")
    label = _recorded_shape_label(band)
    end = obs.get("session_end_min")
    onset = obs.get("onset_min")
    marker = ""
    if end and onset is not None:
        pct = max(2.0, min(98.0, 100.0 * float(onset) / float(end)))
        marker = f'<i class="cb-watch__onset" style="left:{pct:.1f}%"></i>'
    foot = ("Onset {onset:.0f} min · session {end:.0f} min.").format(
        onset=float(onset) if onset is not None else 0.0,
        end=float(end) if end else 0.0)
    return (
        f'<div class="cb-watch" role="img" aria-label="Recorded crash onset '
        f'{float(onset):.0f} minutes; {_e(label.lower())}">'
        f'<div class="cb-watch__head"><span>RECORDED SHAPE</span>'
        f'<span>{label}</span></div>'
        f'<div class="cb-watch__track">'
        f'<span class="cb-watch__seg"></span>'
        f'<span class="cb-watch__seg"></span>'
        f'<span class="cb-watch__seg"></span>{marker}</div>'
        f'<div class="cb-watch__foot">{foot}</div></div>'
    )


def _outcome(chair: dict, reveal: bool, detail: bool = False) -> str:
    obs = chair["observed"]
    if not reveal:
        return '<span class="cb-outcome cb-outcome--hidden">Outcome hidden</span>'
    if obs.get("event"):
        onset = obs.get("onset_min")
        return (f'<span class="cb-outcome cb-outcome--event">'
                f'Crash · {float(onset):.0f} min</span>'
                if onset is not None else
                '<span class="cb-outcome cb-outcome--event">Crash recorded</span>')
    return ('<span class="cb-outcome cb-outcome--clear">'
            'No IDH event</span>')


def _card(chair: dict, reveal: bool, selected: bool) -> str:
    band = chair["risk_band"]
    patient = chair["patient"]
    first = patient.get("n_prior_sessions") in (0, 0.0, None)
    cls = f"cb-card cb-card--{band}" + (" is-selected" if selected else "")
    session = _sid_short(chair["session_id"])
    first_line = ("First recorded session" if first
                  else f"{int(patient['n_prior_sessions'])} prior sessions")
    return (
        f'<article class="{cls}" aria-label="Chair {chair["chair"]}, '
        f'{_e(chair["case_select"])}, {_risk_label(band)} risk, '
        f'{_pct(chair["risk_probability"], 0)}">'
        f'<div class="cb-card__top"><span class="cb-card__no">CHAIR '
        f'{chair["chair"]:02d}</span>{_badge(band)}</div>'
        f'<div class="cb-card__name">{_e(chair["case_select"])}</div>'
        f'<div class="cb-card__session">{_e(session)}</div>'
        f'<div class="cb-card__prob cb-card__prob--{band}">'
        f'{100.0 * float(chair["risk_probability"]):.0f}<span>%</span></div>'
        f'{_gauge(chair["risk_probability"], band)}'
        f'<div class="cb-card__patient">{_e(_patient_line(patient))} · '
        f'{_e(first_line)}</div>'
        f'{_outcome(chair, reveal)}'
        f'</article>'
    )


def _empty_card() -> str:
    return (
        '<article class="cb-card cb-card--empty" aria-label="Chair 6, no '
        'session in this demo"><div class="cb-card__no">CHAIR 06</div>'
        '<div class="cb-card__empty-label">Unoccupied</div>'
        '<div class="cb-card__empty-copy">No session in this demo.</div>'
        '</article>'
    )


def _kv(rows: list[tuple[str, str]]) -> str:
    return '<dl class="cb-kv">' + "".join(
        f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in rows
    ) + "</dl>"


def _input_rows(chair: dict) -> list[tuple[str, str]]:
    p = chair["patient"]

    def fmt(value, digits=1, suffix=""):
        if value is None:
            return "no history"
        try:
            return f"{float(value):.{digits}f}{suffix}"
        except (TypeError, ValueError):
            return "—"

    return [
        ("Prior sessions", fmt(p.get("n_prior_sessions"), 0)),
        ("Prior 10-session IDH rate",
         fmt(p.get("hist_idh_rate10"), 2)),
        ("Prior early-crash share",
         fmt(p.get("hist_early_crash10"), 2)),
        ("UF goal", fmt(p.get("uf_goal_L"), 2, " L")),
        ("Vintage", fmt(p.get("vintage_years"), 1, " y")),
        ("Diabetes", "yes" if float(p.get("dm") or 0) >= 0.5 else "no"),
        ("Dry weight", fmt(p.get("dry_weight"), 1, " kg")),
    ]


def _detail(chair: dict, reveal: bool) -> str:
    band = chair["risk_band"]
    obs = chair["observed"]
    patient = chair["patient"]
    first = patient.get("n_prior_sessions") in (0, 0.0, None)
    first_note = (
        '<p class="cb-note">First recorded session. The history block is '
        'missing; the model imputes TUNE medians and flags the missingness. '
        'Do not read this as a history-based estimate.</p>'
        if first else ""
    )
    if not reveal:
        observed = (
            '<div class="cb-observed">Outcome hidden. Turn on '
            '<b>Reveal recorded outcomes</b> above to compare the pre-session '
            'estimate with the record.</div>'
        )
    elif obs.get("event"):
        onset = obs.get("onset_min")
        low = obs.get("lowest_sbp")
        onset_txt = (f" at {float(onset):.0f} min"
                     if onset is not None else "")
        low_txt = (f" · lowest recorded SBP {float(low):.0f} mmHg"
                   if low is not None else "")
        observed = (
            f'<div class="cb-observed cb-observed--event">Recorded crash'
            f'{onset_txt}{low_txt}.</div>'
        )
    else:
        low = obs.get("lowest_sbp")
        low_txt = (f" · lowest recorded SBP {float(low):.0f} mmHg"
                   if low is not None else "")
        observed = (
            f'<div class="cb-observed cb-observed--clear">No IDH event '
            f'recorded{low_txt}.</div>'
        )
    return (
        f'<div class="cb-detail">'
        f'<div><div class="cb-detail__kicker">CHAIR {chair["chair"]:02d} · '
        f'FOLD 2 · PRE-SESSION</div>'
        f'<div class="cb-detail__title">{_e(chair["case_select"])}</div>'
        f'<div class="cb-detail__session">{_e(chair["session_id"])} · '
        f'{_e(_patient_line(patient))}</div>'
        f'<div class="cb-detail__risk"><strong>{_pct(chair["risk_probability"], 1)}</strong>'
        f'<span>{_risk_label(band)} band · calibrated estimate</span></div>'
        f'{_gauge(chair["risk_probability"], band, detail=True)}'
        f'<div class="cb-detail__section"><div class="cb-detail__label">'
        f'Model inputs · not causes</div>{_kv(_input_rows(chair))}'
        f'{first_note}</div>'
        f'</div>'
        f'<div><div class="cb-detail__label">Recorded crash shape</div>'
        f'{_recorded_watch(chair, reveal, detail=True)}'
        f'<div class="cb-detail__section"><div class="cb-detail__label">'
        f'Recorded session</div>{observed}</div>'
        f'</div></div>'
    )


def _model_card(board: dict) -> None:
    risk = board["risk_model"]
    shape = board["shape_policy"]
    audit = board["feature_audit"]
    rm = risk["metrics"]
    rb = risk["bands"]
    anchor = shape["anchor_model"]
    abl = shape["pre_session_ablation"]
    st.markdown(
        f'<div class="cb-model-grid">'
        f'<div class="cb-model-cell"><b>Pre-session risk · A2</b>'
        f'<span>Fold 2: n={int(rm["n"]):,}, crashes={int(rm["n_event"]):,}; '
        f'AUROC {rm["auroc"]:.3f}; recall@25 {rm["recall_at_25"]:.3f}; '
        f'PPV@25 {rm["ppv_at_25"]:.3f}; ECE10 {rm["ece10"]:.3f}. '
        f'History, static fields and planned UF goal; no BP, no current UF '
        f'rate.</span></div>'
        f'<div class="cb-model-cell"><b>Shape · not shipped pre-session</b>'
        f'<span>The anchor-based shape model (AUROC '
        f'{anchor["fold2_auroc"]:.3f}) needs anchor SBP and anchor UF. The '
        f'no-anchor/no-UF ablation is AUROC {abl["auroc"]:.3f} vs baseline '
        f'{abl["baseline_auroc"]:.3f}; too weak for a watch window. Recorded '
        f'onset is shown only after the reveal.</span></div>'
        f'<div class="cb-model-cell"><b>High band on fold 2</b>'
        f'<span>{100 * rb["high"]["share"]:.1f}% of sessions; '
        f'{100 * rb["high"]["event_rate"]:.1f}% crash rate. Low band: '
        f'{100 * rb["low"]["share"]:.1f}% of sessions, '
        f'{100 * rb["low"]["event_rate"]:.1f}% crash rate; '
        f'{100 * rb["low"]["share_of_events"]:.1f}% of crashes were low.'
        f'</span></div>'
        f'<div class="cb-model-cell"><b>Feature audit</b>'
        f'<span>{audit["sbp_anchor_below_90"]:,} of '
        f'{audit["fold2_events"]:,} fold-2 crashes had anchor SBP below 90. '
        f'<code>uf_ml_kg_h</code> is the UF rate at that anchor. A2 excludes '
        f'both.</span></div></div>'
        f'<p class="cb-model-note"><b>Limits.</b> Single-centre HEMOBP, '
        f'retrospective, one fold-2 read, no external validation. Crash is '
        f'SBP&lt;90, not symptomatic IDH. A low band is not safe. '
        f'Display-only; not an alarm, treatment recommendation, or '
        f'chair-allocation order.</p>'
        f'<p class="cb-model-note"><b>Source.</b> {_e(board["source"])}; '
        f'curated demo cases, not a prevalence sample. See '
        f'<code>docs/CRASHRISK.md</code>.</p>',
        unsafe_allow_html=True,
    )


def render() -> None:
    board = load_board(BOARD.stat().st_mtime)
    chairs = board["chairs"]
    summary = board["demo"]["summary"]
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(theme.section(
        "Chair board",
        "Five chairs, before the first cuff",
        "A pre-session estimate from history and the planned UF goal. No BP "
        "or current UF rate is read."), unsafe_allow_html=True)

    left, right = st.columns([3, 1])
    with right:
        reveal = st.toggle(
            "Reveal recorded outcomes", value=False, key="chair_reveal",
            help="Retrospective demo only. The default view is the "
                 "pre-session view; revealing outcomes is not a model input.")
    with left:
        pills = [
            theme.pill(f"{summary['n_chairs']} sessions · 6 bays", "info"),
            theme.pill(f"{summary['high']} high · {summary['low']} low"),
            theme.pill("fold 2 · patient-disjoint", "violet"),
            theme.pill("display-only", "warn"),
        ]
        st.markdown('<div class="ht-pills">' + "".join(pills) + "</div>",
                    unsafe_allow_html=True)

    st.markdown(
        '<div class="cb-axis">'
        '<span>01</span><span>02</span><span>03</span>'
        '<span>04</span><span>05</span><span>06</span></div>'
        '<div class="cb-axis-note">fixed chair order · pre-session risk</div>',
        unsafe_allow_html=True)

    st.session_state.setdefault("chair_selected", None)
    with st.container(key="chair_rail"):
        cols = st.columns(6)
        for i, chair in enumerate(chairs, start=1):
            with cols[i - 1]:
                with st.container(key=f"chair_{i}"):
                    selected = st.session_state.get("chair_selected") == i
                    st.markdown(_card(chair, reveal, selected),
                                unsafe_allow_html=True)
                    if st.button(
                            f"Inspect chair {i}",
                            key=f"chair_btn_{i}",
                            type="primary" if selected else "secondary",
                            use_container_width=True):
                        st.session_state["chair_selected"] = i
        with cols[5]:
            with st.container(key="chair_6"):
                st.markdown(_empty_card(), unsafe_allow_html=True)

    if reveal:
        crashed = ", ".join(
            f"{summary[f'{band}_crashes']}/{summary[band]} {band}"
            for band in ("high", "moderate", "low") if summary[band])
        st.caption(f"Crashes in this curated set: {crashed}. "
                   "Not an accuracy estimate.")

    selected_index = st.session_state.get("chair_selected")
    chair = next((c for c in chairs if c["chair"] == selected_index), None)
    if chair is None:
        st.markdown(theme.callout(
            "Select a chair above to inspect its model inputs and, after the "
            "reveal, its recorded crash shape. The board order is fixed; it "
            "is not a priority list.", ""), unsafe_allow_html=True)
    else:
        st.markdown(_detail(chair, reveal), unsafe_allow_html=True)
        if st.button("Open in Case lab", key="chair_open_case",
                     type="primary"):
            st.session_state["case_id"] = chair["case_id"]
            st.session_state["case_select"] = chair["case_select"]
            st.switch_page("views/case_lab_page.py")

    with st.expander("Model card & limits", expanded=False):
        _model_card(board)

    st.markdown(theme.callout(
        "Display-only. A low band is not safe. Not a treatment recommendation, "
        "an alarm, or a chair-allocation order. Crash shape is recorded after "
        "the reveal, not predicted.", "warn"), unsafe_allow_html=True)
    st.caption(
        "Five fold-2 Case Lab sessions, one per patient; the synthetic "
        "stale-cuff guardrail is not on the board. Curated, not a prevalence "
        "sample. Risk variant A2 (no anchor BP, no anchor-time UF).")
