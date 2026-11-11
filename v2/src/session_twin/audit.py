"""Append-only local demo evidence; not an immutable clinical audit system."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

EVENT_TYPES = frozenset({"displayed", "confirmed", "dismissed", "override"})


def _event_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "event_hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def append_event(path: str | Path, *, recommendation: dict, event_type: str,
                 role: str, action: str | None = None, reason: str = "",
                 timestamp: str | None = None) -> dict:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {sorted(EVENT_TYPES)}")
    record = {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "role_label": str(role),
        "role_enforced": False,
        "session_id": str(recommendation["snapshot"].get("session_id", "")),
        "snapshot_hash": recommendation["snapshot_hash"],
        "state": recommendation["state"],
        "state_reason_ids": list(recommendation["state_reason_ids"]),
        "protocol_id": recommendation["protocol_id"],
        "protocol_version": recommendation["protocol_version"],
        "claim_label": recommendation["claim_label"],
        "action": action,
        "reason": reason,
        "storage": "append_only_local_jsonl_demo",
    }
    record["event_hash"] = _event_hash(record)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_events(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()
            if line.strip()]
