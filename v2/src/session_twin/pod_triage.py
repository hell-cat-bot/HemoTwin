"""12-chair pod triage board and nurse-attention budget projection.

The board is a workflow sort, not a diagnosis and not a prescription. The
shadow ML score is displayed but never changes the protocol status.
"""
from __future__ import annotations

import math

STATUS_PRIORITY = {
    "URGENT_CLINICAL_REVIEW": 0,
    "REVIEW_NOW": 1,
    "INSUFFICIENT_INFORMATION": 2,
    "NO_ALERT": 3,
}


def _g(row, key, default=None):
    try:
        return row.get(key, default)
    except AttributeError:
        return getattr(row, key, default)


def _f(value, default=float("nan")) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else float(default)
    except (TypeError, ValueError):
        return float(default)


def triage_status(sbp_now=None, projected_nadir=None, cuff_age_min=None,
                  risk_shadow=None, stale_min: float = 35.0) -> str:
    age = _f(cuff_age_min, 0.0)
    if math.isfinite(age) and age > float(stale_min):
        return "INSUFFICIENT_INFORMATION"
    sbp = _f(sbp_now)
    if math.isfinite(sbp) and sbp < 90.0:
        return "URGENT_CLINICAL_REVIEW"
    nadir = _f(projected_nadir)
    if math.isfinite(nadir) and nadir < 90.0:
        return "REVIEW_NOW"
    return "NO_ALERT"


def build_pod_board(rows, n_chairs: int = 12,
                    fa_per_session: float = 0.26) -> dict:
    items = []
    for row in rows:
        status = str(_g(row, "status") or triage_status(
            _g(row, "sbp_now"), _g(row, "projected_nadir"),
            _g(row, "cuff_age_min"), _g(row, "risk_shadow")))
        items.append({
            "session_id": str(_g(row, "session_id", "")),
            "pid": str(_g(row, "pid", "")),
            "status": status,
            "sbp_now": _f(_g(row, "sbp_now")),
            "projected_nadir": _f(_g(row, "projected_nadir")),
            "cuff_age_min": _f(_g(row, "cuff_age_min")),
            "risk_shadow": _f(_g(row, "risk_shadow")),
            "role": str(_g(row, "role", "RN")),
        })
    items.sort(key=lambda r: (STATUS_PRIORITY.get(r["status"], 9),
                              r["projected_nadir"]
                              if math.isfinite(r["projected_nadir"]) else 999))
    board = []
    for i in range(int(n_chairs)):
        if i < len(items):
            chair = dict(items[i])
            chair["chair"] = i + 1
            chair["occupied"] = True
        else:
            chair = {"chair": i + 1, "occupied": False,
                     "status": "EMPTY", "session_id": "", "pid": ""}
        board.append(chair)
    return {
        "n_chairs": int(n_chairs),
        "occupied": int(min(len(items), int(n_chairs))),
        "board": board,
        "budget": budget_projection(fa_per_session, n_chairs),
        "governance": "Workflow sort only; the shadow score never gates care.",
    }


def budget_projection(fa_per_session: float, n_chairs: int = 12) -> dict:
    fa = max(float(fa_per_session), 0.0)
    return {
        "false_alerts_per_session": fa,
        "expected_false_alerts_per_shift": fa * int(n_chairs),
        "sessions_per_shift": int(n_chairs),
        "note": "PMNDP reference points: 0.26 ~ 3.1 false alarms/shift; "
                "0.62 ~ 7.4 false alarms/shift.",
    }
