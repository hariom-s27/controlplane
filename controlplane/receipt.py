"""S10 — the Decision Receipt. A ~1 KB signed JSON artifact per governed
decision. Shaped with W3C PROV vocabulary in spirit (Entity/Activity/Agent,
wasDerivedFrom, wasAttributedTo) — the action is the Activity, the claims
and evidence are what it wasDerivedFrom, the session is who it
wasAttributedTo — so this inherits a decade of prior art instead of
inventing a schema from scratch.

Two tiers (D11), per the Mobley v. Workday privilege ruling: a real legal
design decision, not a flourish. See docs/decision-receipt.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from pathlib import Path
from typing import Any

from controlplane.registry.clock import now
from controlplane.schema import Decision

ROOT = Path(__file__).resolve().parent.parent
OPERATIONAL_TRAIL = ROOT / "decisions.jsonl"
PRIVILEGED_TRAIL = ROOT / "decisions_privileged.jsonl"


def _secret() -> bytes:
    key = os.environ.get("CP_RECEIPT_SECRET", "")
    if not key:
        raise RuntimeError("CP_RECEIPT_SECRET is not set — see .env.example")
    return key.encode()


def _canonical(obj: dict) -> bytes:
    """Sorted keys, no whitespace — HMAC must sign one exact byte string,
    not "some JSON that means the same thing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def _root_cause(decision: Decision) -> str | None:
    """Best-effort, human-and-machine-readable label for the first failing
    reason. Not exhaustive — picks the single most useful line for a
    receipt, not a full trace (that's predicate_trace's job)."""
    for r in decision.reasons:
        if r.passed is False and r.rule == "clause_current":
            return f"stale_clause_{r.expected}"
        if r.passed is False and r.rule == "within_window":
            return "outside_refund_window"
        if r.passed is False and r.rule == "within_authority":
            return "exceeds_authority_ceiling"
        if r.passed is False and r.rule == "entity_match":
            return "order_customer_mismatch"
        if r.passed is False and r.rule == "amount_sane":
            return "amount_exceeds_order"
        if r.passed is False and r.rule == "reliability_floor":
            return "evidence_below_reliability_floor"
        if r.passed is False:
            return r.rule
    return None


def build_receipt(decision: Decision, action_dict: dict[str, Any], latency_ms: dict[str, float]) -> dict:
    receipt = {
        "receipt_id": str(uuid.uuid5(uuid.NAMESPACE_URL, decision.idempotency_key or decision.trace_id)),
        "trace_id": decision.trace_id,
        "idempotency_key": decision.idempotency_key,
        "ts": now().isoformat(),
        "manifest_id": decision.manifest_id,
        "action": {
            "tool": action_dict.get("tool"),
            "args": {k: v for k, v in action_dict.items() if k != "tool"},
            "compensability": decision.compensation.compensability.value if decision.compensation else None,
        },
        "claims": [
            {"kind": c.kind.value, "tier": c.tier.value if c.tier else None,
             "asserted": c.asserted_value, "load_bearing": c.load_bearing}
            for c in decision.claims
        ],
        "evidence": [
            {"claim_id": e.claim_id, "value": e.value, "source": e.source, "query": e.query,
             "fetched_at": e.fetched_at.isoformat(), "freshness_ms": e.freshness_ms,
             "reliability_class": e.reliability_class.value, "confidence": e.confidence.value}
            for e in decision.evidence
        ],
        "predicate_trace": decision.predicate_trace,
        "verdict": decision.verdict.value,
        "intervention": decision.intervention.value,
        "reasons": [
            {"rule": r.rule, "expected": r.expected, "observed": r.observed, "policy_version": r.policy_version}
            for r in decision.reasons
        ],
        "root_cause": _root_cause(decision),
        "latency_ms": latency_ms,
        "compensation": (
            {"action": decision.compensation.action, "class": decision.compensation.compensability.value}
            if decision.compensation else None
        ),
    }
    signature = hmac.new(_secret(), _canonical(receipt), hashlib.sha256).hexdigest()
    receipt["sig"] = f"hmac-sha256:{signature}"
    return receipt


def verify(receipt: dict) -> bool:
    given = receipt.get("sig", "")
    unsigned = {k: v for k, v in receipt.items() if k != "sig"}
    expected = "hmac-sha256:" + hmac.new(_secret(), _canonical(unsigned), hashlib.sha256).hexdigest()
    return hmac.compare_digest(given, expected)


def persist(entry: dict, privileged: dict | None = None) -> None:
    """Operational trail: `entry` — a receipt on its own, or (from
    controlplane/telemetry.py) a receipt+telemetry envelope — always.
    Privileged trail (bias probes, counterfactual twins, red-team results):
    a separate file, only written when there's something privileged to
    say — kept apart per D11 so the operational trail stays freely
    discoverable."""
    with OPERATIONAL_TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    if privileged is not None:
        with PRIVILEGED_TRAIL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(privileged, sort_keys=True) + "\n")


__all__ = ["build_receipt", "verify", "persist"]
