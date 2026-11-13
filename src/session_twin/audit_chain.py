"""SHA-256 hash-chained audit records (backward-compatible with audit.py)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.session_twin.audit import read_events

GENESIS = "GENESIS"


def _canonical(record: dict) -> bytes:
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def _sha256(record: dict) -> str:
    return hashlib.sha256(_canonical(record)).hexdigest()


def append_chained_event(path: str | Path, record: dict,
                         timestamp: str | None = None) -> dict:
    events = read_events(path)
    prev = (events[-1].get("record_sha256", GENESIS) if events else GENESIS)
    rec = dict(record)
    rec["timestamp"] = timestamp or datetime.now(timezone.utc).isoformat()
    rec["prev_record_sha256"] = prev
    rec["record_sha256"] = _sha256(rec)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def verify_audit_chain(path: str | Path) -> dict:
    events = read_events(path)
    prev = GENESIS
    errors: list[str] = []
    for i, rec in enumerate(events):
        if rec.get("prev_record_sha256") != prev:
            errors.append(f"event {i}: prev hash mismatch")
        expected = _sha256(rec)
        if rec.get("record_sha256") != expected:
            errors.append(f"event {i}: record hash mismatch")
        prev = rec.get("record_sha256", "")
    return {"ok": not errors, "n_events": len(events), "errors": errors,
            "head": prev if events else GENESIS}
