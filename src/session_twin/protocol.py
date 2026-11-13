"""Load and validate the versioned research protocol."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT / "config" / "protocols" / "idh_review_research_v1.json"
VALID_ROLES = frozenset({"TECH", "RN", "NEPHROLOGIST"})
VALID_STATES = frozenset({"urgent", "review", "routine", "insufficient"})
VALID_OPS = frozenset({"lt", "le", "gt", "ge", "eq", "is_true"})


class ProtocolError(ValueError):
    """Raised when the protocol JSON is missing or invalid."""


def load_protocol(path: str | Path | None = None) -> dict:
    source = Path(path) if path is not None else DEFAULT_PROTOCOL
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProtocolError(f"protocol not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"protocol is not valid JSON: {source}: {exc}") from exc
    validate_protocol(data)
    return data


def validate_protocol(protocol: dict) -> None:
    required = {"protocol_id", "version", "status", "label", "owner",
                "escalation_rules", "pathways", "steps"}
    missing = required - set(protocol)
    if missing:
        raise ProtocolError(f"missing protocol keys: {sorted(missing)}")
    if protocol["status"] != "research":
        raise ProtocolError("this MVP accepts only a research-status protocol")
    if "not approved" not in str(protocol["label"]).lower():
        raise ProtocolError("research label must state that it is not approved")

    steps = protocol["steps"]
    if not isinstance(steps, list) or not steps:
        raise ProtocolError("steps must be a non-empty list")
    step_ids = [str(s.get("id", "")) for s in steps]
    if any(not sid for sid in step_ids):
        raise ProtocolError("every step needs a non-empty id")
    if len(step_ids) != len(set(step_ids)):
        raise ProtocolError("duplicate step ids")
    sequences = [s.get("sequence") for s in steps]
    if any(not isinstance(n, int) or n < 1 for n in sequences):
        raise ProtocolError("every step needs a positive integer sequence")
    if len(sequences) != len(set(sequences)):
        raise ProtocolError("duplicate step sequences")

    for step in steps:
        unknown = set(step.get("roles", [])) - VALID_ROLES
        if unknown:
            raise ProtocolError(f"step {step['id']} has unknown roles: {sorted(unknown)}")
        if not isinstance(step.get("requires", []), list):
            raise ProtocolError(f"step {step['id']} requires must be a list")
        if not step.get("title") or not step.get("instruction"):
            raise ProtocolError(f"step {step['id']} needs title and instruction")

    pathways = protocol["pathways"]
    if set(pathways) != VALID_STATES:
        raise ProtocolError(f"pathways must be exactly {sorted(VALID_STATES)}")
    known = set(step_ids)
    for state, ids in pathways.items():
        if not isinstance(ids, list) or not ids:
            raise ProtocolError(f"pathway {state} must be a non-empty list")
        unknown = set(ids) - known
        if unknown:
            raise ProtocolError(f"pathway {state} references unknown steps: {sorted(unknown)}")
        if len(ids) != len(set(ids)):
            raise ProtocolError(f"pathway {state} contains duplicate steps")

    for group in ("urgent", "review"):
        rules = protocol["escalation_rules"].get(group)
        if not isinstance(rules, list) or not rules:
            raise ProtocolError(f"escalation_rules.{group} must be non-empty")
        for rule in rules:
            if not rule.get("id") or not rule.get("reason") or not rule.get("all"):
                raise ProtocolError(f"invalid {group} rule: {rule}")
            for cond in rule["all"]:
                if cond.get("op") not in VALID_OPS or not cond.get("field"):
                    raise ProtocolError(f"invalid condition in rule {rule['id']}")


def pathway_ids(protocol: dict, state_key: str) -> list[str]:
    try:
        return list(protocol["pathways"][state_key])
    except KeyError as exc:
        raise ProtocolError(f"unknown pathway: {state_key}") from exc
