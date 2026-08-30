"""S10 checkpoint: minimal receipt stays under 2 KB; realistic sizes are measured separately."""

from __future__ import annotations

import json
import os

from controlplane.compensation import compensation_for
from controlplane.decide import decide
from controlplane.ladder import classify_claims
from controlplane.receipt import build_receipt, verify

_COMPENSABLE = {"compensation": {"action": "reverse_refund", "compensability": "fully"}}
from controlplane.registry.clock import now
from controlplane.schema import (
    Claim, ClaimKind, Confidence, Decision, Evidence, Intervention, ProposedAction, Reliability, Reason, Tier, Verdict,
)
from bench.receipt_size import measure_receipt_sizes

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
        compensation=compensation_for(_COMPENSABLE), idempotency_key="abc123",
    )


def test_minimal_receipt_under_2kb_and_signature_validates():
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
    assert receipt["root_cause"] == "outside_window"


# --- P02 renamed two servicing-flavoured root_cause labels so the engine
#     carries no use-case string. These regression-test both, driven through
#     the real decide() -> build_receipt() path (one load-bearing predicate
#     fails on corroborated, high-confidence evidence). ---

_RC_MANIFEST = {
    "reliability_floor": "corroborated",
    "verdict_handling": {},
    "manifest_id": "servicing-v1",
    "_name": "test",
    "compensation": {"action": "reverse_refund", "compensability": "fully"},
}


def _decision_and_receipt_for_failed_predicate(kind, predicate_key, evidence_value):
    claim = classify_claims([Claim(id="c1", kind=kind, subject="ORD-88461")])[0]
    assert claim.load_bearing, "the claim must be load-bearing or decide() ignores it"
    evidence = [Evidence(
        claim_id="c1", value=evidence_value, source="orders.db",
        query="SELECT ... FROM orders WHERE order_id = 'ORD-88461'",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )]
    action = ProposedAction(tool="issue_refund", order_id="ORD-88461", amount_paise=4299900, currency="INR")
    decision = decide("t-rc", "servicing-v1", action, [claim], evidence, {predicate_key: False}, _RC_MANIFEST)
    action_dict = {"tool": "issue_refund", "order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR"}
    return decision, build_receipt(decision, action_dict, latency_ms={})


def test_root_cause_entity_match_failure_is_entity_mismatch():
    """entity_match on a load-bearing ORDER_BELONGS_TO_CUSTOMER claim fails
    -> receipt root_cause is 'entity_mismatch' (P02 renamed it from the
    servicing-specific 'order_customer_mismatch')."""
    decision, receipt = _decision_and_receipt_for_failed_predicate(
        ClaimKind.ORDER_BELONGS_TO_CUSTOMER, "entity_match", evidence_value="CUST-9999",
    )
    assert decision.verdict == Verdict.CONTRADICTED
    assert [r.rule for r in decision.reasons if not r.passed] == ["entity_match"]
    assert receipt["root_cause"] == "entity_mismatch"
    assert verify(receipt) is True


def test_root_cause_amount_sane_failure_is_amount_exceeds_source_record():
    """amount_sane on a load-bearing AMOUNT_NOT_EXCEEDING_ORDER claim fails
    -> receipt root_cause is 'amount_exceeds_source_record' (P02 renamed it
    from 'amount_exceeds_order')."""
    decision, receipt = _decision_and_receipt_for_failed_predicate(
        ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER, "amount_sane", evidence_value=100000,
    )
    assert decision.verdict == Verdict.CONTRADICTED
    assert [r.rule for r in decision.reasons if not r.passed] == ["amount_sane"]
    assert receipt["root_cause"] == "amount_exceeds_source_record"
    assert verify(receipt) is True


def test_receipt_size_measurement_uses_at_least_100_real_receipts():
    measured = measure_receipt_sizes(100)

    assert measured["n"] == 100
    assert measured["median_bytes"] > 0
    assert measured["p95_bytes"] >= measured["median_bytes"]
    assert measured["raw_receipts_persisted"] is False
    assert "not persisted" in measured["evidence_limitation"]
