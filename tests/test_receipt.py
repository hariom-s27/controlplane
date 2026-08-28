"""S10 checkpoint. The milestone's own bar: under 2 KB, signature validates."""

from __future__ import annotations

import json
import os

from controlplane.compensation import compensation_for
from controlplane.receipt import build_receipt, verify
from controlplane.registry.clock import now
from controlplane.schema import Claim, ClaimKind, Confidence, Decision, Evidence, Intervention, Reliability, Reason, Tier, Verdict

os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")


def _decision() -> Decision:
    claim = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-88461", tier=Tier.C2, load_bearing=True)
    evidence = [Evidence(
        claim_id="c1", value="2026-07-19", source="orders.db",
        query="SELECT delivered_at FROM orders WHERE order_id = 'ORD-88461'",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )]
    reasons = [Reason(rule="within_window", expected=True, observed=False, passed=False, policy_version="servicing-v1")]
    return Decision(
        trace_id="t1", manifest_id="servicing-v1", verdict=Verdict.CONTRADICTED, intervention=Intervention.BLOCK,
        reasons=reasons, claims=[claim], evidence=evidence, predicate_trace={"within_window": False},
        compensation=compensation_for("issue_refund"), idempotency_key="abc123",
    )


def test_receipt_under_2kb_and_signature_validates():
    action_dict = {"tool": "issue_refund", "order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR"}
    receipt = build_receipt(_decision(), action_dict, latency_ms={"extract": 12.3, "resolve": 4.1, "predicate": 0.6, "decide": 0.1})

    size = len(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    assert size < 2048, f"receipt is {size} bytes, over the 2 KB bar"
    assert verify(receipt) is True


def test_tampered_receipt_fails_verification():
    action_dict = {"tool": "issue_refund", "order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR"}
    receipt = build_receipt(_decision(), action_dict, latency_ms={})
    receipt["verdict"] = "VERIFIED"  # tamper after signing
    assert verify(receipt) is False


def test_root_cause_names_the_failed_rule():
    action_dict = {"tool": "issue_refund", "order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR"}
    receipt = build_receipt(_decision(), action_dict, latency_ms={})
    assert receipt["root_cause"] == "outside_refund_window"
