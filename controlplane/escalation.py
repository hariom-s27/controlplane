"""Persistent pending-action queue and escalation-budget accounting."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controlplane.receipt import OPERATIONAL_TRAIL
from controlplane.schema import Decision, Intervention

ROOT = Path(__file__).resolve().parent.parent
PENDING_QUEUE = ROOT / "pending_actions.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def escalation_budget_exhausted(
    decision: Decision,
    manifest: dict,
    *,
    trail_path: Path = OPERATIONAL_TRAIL,
) -> bool:
    """Apply ``escalation_budget_pct`` to a rolling 100-decision window.

    The current decision is already in the operational trail when this is
    called.  A short history is normalized to a 100-decision window so a 2%
    budget means two escalation slots, rather than making the first escalation
    mathematically impossible.
    """
    budget_pct = float(manifest.get("escalation_budget_pct", 0))
    entries = _read_jsonl(trail_path)
    receipts = [entry.get("receipt", entry) for entry in entries]
    matching = [
        r for r in receipts
        if r.get("manifest_id") == decision.manifest_id and r.get("intervention")
    ][-100:]
    used = sum(r.get("intervention") == Intervention.ESCALATE.value for r in matching)
    window = max(100, len(matching))
    allowed = max(0, math.floor(window * budget_pct / 100.0))
    return used > allowed


def enqueue_pending(decision: Decision, receipt: dict, *, path: Path = PENDING_QUEUE) -> dict:
    entry = {
        "queue_id": str(uuid.uuid4()),
        "status": "pending",
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "manifest_id": decision.manifest_id,
        "receipt": receipt,
        "review": None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str) + "\n")
    return entry


def record_budget_exhaustion(
    decision: Decision,
    receipt: dict,
    *,
    risk_tier: int,
    fail_posture: str,
    trail_path: Path = OPERATIONAL_TRAIL,
) -> dict:
    """Persist the policy fallback applied when no escalation slot remains."""
    event = {
        "event": "escalation_budget_exhausted",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "trace_id": decision.trace_id,
        "manifest_id": decision.manifest_id,
        "risk_tier": risk_tier,
        "fail_posture": fail_posture,
        "outcome": "executed" if fail_posture == "open" else "blocked",
        "receipt_id": receipt.get("receipt_id"),
    }
    trail_path.parent.mkdir(parents=True, exist_ok=True)
    with trail_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def pending_items(*, path: Path = PENDING_QUEUE) -> list[dict]:
    return [entry for entry in _read_jsonl(path) if entry.get("status") == "pending"]


def record_review(queue_id: str, reviewer_decision: str, *, path: Path = PENDING_QUEUE) -> dict:
    reviewer_decision = reviewer_decision.upper()
    if reviewer_decision not in {"APPROVE", "BLOCK"}:
        raise ValueError("reviewer decision must be APPROVE or BLOCK")
    entries = _read_jsonl(path)
    reviewed = None
    for entry in entries:
        if entry.get("queue_id") != queue_id:
            continue
        if entry.get("status") != "pending":
            raise ValueError(f"queue item {queue_id} is not pending")
        verdict = entry["receipt"]["verdict"]
        gate_decision = "APPROVE" if verdict == "VERIFIED" else "BLOCK"
        entry["status"] = "reviewed"
        entry["review"] = {
            "decision": reviewer_decision,
            "gate_decision": gate_decision,
            "agreement": reviewer_decision == gate_decision,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        reviewed = entry
        break
    if reviewed is None:
        raise KeyError(f"unknown queue item {queue_id}")
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return reviewed


__all__ = [
    "PENDING_QUEUE",
    "enqueue_pending",
    "escalation_budget_exhausted",
    "pending_items",
    "record_budget_exhaustion",
    "record_review",
]
