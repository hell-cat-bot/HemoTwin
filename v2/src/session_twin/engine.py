"""Deterministic assessment state, protocol pathway, and claim boundary."""
from __future__ import annotations

import hashlib
import json
from math import isfinite

from .protocol import VALID_ROLES, pathway_ids

URGENT = "URGENT_CLINICAL_REVIEW"
REVIEW = "REVIEW_NOW"
INSUFFICIENT = "INSUFFICIENT_INFORMATION"
NO_ALERT = "NO_ALERT"

STATE_TO_PATHWAY = {
    URGENT: "urgent", REVIEW: "review",
    NO_ALERT: "routine", INSUFFICIENT: "insufficient",
}
CLAIM_LABEL = ("Research workflow prototype. No validated clinical utility; "
               "no treatment recommendation.")


def snapshot_hash(snapshot: dict) -> str:
    blob = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _missing(value) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, float):
        return not isfinite(value)
    return False


def _eval_condition(cond: dict, snapshot: dict) -> bool | None:
    field = cond["field"]
    value = snapshot.get(field)
    op = cond["op"]
    if op == "is_true":
        return None if value is None else bool(value)
    if _missing(value):
        return None
    try:
        left = float(value)
        right = float(cond["value"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "lt": left < right, "le": left <= right,
        "gt": left > right, "ge": left >= right,
        "eq": left == right,
    }[op]


def _eval_rule(rule: dict, snapshot: dict) -> bool | None:
    results = [_eval_condition(c, snapshot) for c in rule["all"]]
    # Unknown-dominant: a rule whose required input is missing cannot be ruled
    # out, even when another clause is already false. Missing review data must
    # abstain rather than clear the assessment.
    if any(r is None for r in results):
        return None
    if any(r is False for r in results):
        return False
    return True


def _shadow(risk: dict | None, t_min: float) -> dict:
    risk = dict(risk or {})
    available = bool(risk.get("available", False))
    try:
        score = float(risk.get("score"))
        threshold = float(risk.get("threshold"))
        as_of = float(risk.get("as_of_min"))
        available = available and isfinite(score) and isfinite(threshold) and isfinite(as_of)
    except (TypeError, ValueError):
        score = threshold = as_of = None
        available = False
    stale = bool(available and isfinite(t_min) and (t_min - as_of) > 60.0)
    return {
        "available": available,
        "status": "unavailable" if not available else ("stale" if stale else "current"),
        "score": score if available else None,
        "threshold": threshold if available else None,
        "as_of_min": as_of if available else None,
        "model_version": risk.get("model_version"),
        "authority": "display_only",
        "note": "Research shadow score; it never creates or suppresses a review state.",
    }


def _step_available(step: dict, snapshot: dict, role: str) -> tuple[bool, str | None]:
    if role not in step.get("roles", []):
        return False, "role_not_permitted"
    for field in step.get("requires", []):
        if _missing(snapshot.get(field)):
            return False, f"missing_input:{field}"
    return True, None


def _pathway(protocol: dict, state: str, snapshot: dict) -> list[dict]:
    ids = pathway_ids(protocol, STATE_TO_PATHWAY[state])
    by_id = {s["id"]: s for s in protocol["steps"]}
    ordered = sorted((by_id[sid] for sid in ids), key=lambda s: s["sequence"])
    role = str(snapshot.get("role") or "")
    out = []
    for step in ordered:
        available, reason = _step_available(step, snapshot, role)
        out.append({
            "id": step["id"], "sequence": step["sequence"],
            "title": step["title"], "instruction": step["instruction"],
            "roles": list(step["roles"]), "requires": list(step.get("requires", [])),
            "available": available, "reason_code": reason,
        })
    return out


def recommend(snapshot: dict, protocol: dict) -> dict:
    t_min = snapshot.get("t_min")
    try:
        t_min_f = float(t_min)
    except (TypeError, ValueError):
        t_min_f = float("nan")

    urgent_hits, urgent_unknown = [], []
    for rule in protocol["escalation_rules"]["urgent"]:
        result = _eval_rule(rule, snapshot)
        if result is True:
            urgent_hits.append(rule)
        elif result is None:
            urgent_unknown.append(rule["id"])

    review_hits, review_unknown = [], []
    for rule in protocol["escalation_rules"]["review"]:
        result = _eval_rule(rule, snapshot)
        if result is True:
            review_hits.append(rule)
        elif result is None:
            review_unknown.append(rule["id"])

    data_quality = []
    sbp = snapshot.get("sbp")
    if _missing(sbp):
        data_quality.append("current_sbp")
    else:
        try:
            if not 40 <= float(sbp) <= 250:
                data_quality.append("invalid_current_sbp")
        except (TypeError, ValueError):
            data_quality.append("invalid_current_sbp")
    if not isfinite(t_min_f) or t_min_f < 0:
        data_quality.append("invalid_session_time")
    if _missing(snapshot.get("sbp_drop_from_session_baseline")):
        data_quality.append("sbp_drop_from_session_baseline")
    if _missing(snapshot.get("uf_rate_Lh")):
        data_quality.append("uf_rate_Lh")
    if _missing(snapshot.get("uf_goal_L")):
        data_quality.append("uf_goal_L")
    if _missing(snapshot.get("uf_removed_L")):
        data_quality.append("uf_removed_L")
    if snapshot.get("symptom_any") is None:
        data_quality.append("symptom_any")
    if snapshot.get("clinician_concern") is None:
        data_quality.append("clinician_concern")

    if urgent_hits:
        state = URGENT
        reasons = urgent_hits
    elif "current_sbp" in data_quality or "invalid_current_sbp" in data_quality \
            or "invalid_session_time" in data_quality or urgent_unknown:
        state = INSUFFICIENT
        reasons = []
    elif review_hits:
        state = REVIEW
        reasons = review_hits
    elif review_unknown:
        state = INSUFFICIENT
        reasons = []
    else:
        state = NO_ALERT
        reasons = []

    role = str(snapshot.get("role") or "")
    if role not in VALID_ROLES:
        data_quality.append("role_unrecognized")

    reason_text = " ".join(r["reason"] for r in reasons)
    if state == INSUFFICIENT:
        reason_text = ("Required assessment data are missing or invalid; no new "
                       "review decision is generated. Independent urgent rules "
                       "remain active.")
    elif state == NO_ALERT:
        reason_text = "No configured urgent or review criterion is met."

    return {
        "state": state,
        "state_reason_ids": [r["id"] for r in reasons],
        "state_reason_text": reason_text,
        "risk_shadow": _shadow(snapshot.get("risk_shadow"), t_min_f),
        "data_quality": data_quality,
        "pathway": _pathway(protocol, state, snapshot),
        "role_simulation": role if role in VALID_ROLES else "UNRECOGNIZED",
        "protocol_id": protocol["protocol_id"],
        "protocol_version": protocol["version"],
        "protocol_label": protocol["label"],
        "claim_label": CLAIM_LABEL,
        "snapshot_hash": snapshot_hash(snapshot),
        "snapshot": dict(snapshot),
    }
