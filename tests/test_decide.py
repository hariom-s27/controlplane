"""S9 checkpoint. One test per docs/compensability.md row, then the D49
demonstration: identical weak (C3-only) evidence, different intervention,
purely because compensability differs. That's the actual proof, not a
paragraph.
"""

from __future__ import annotations

from controlplane.compensation import compensation_for
from controlplane.decide import decide
from controlplane.registry.clock import now
from controlplane.schema import (
    Claim,
    ClaimKind,
    Compensability,
    Confidence,
    Evidence,
    Intervention,
    ProposedAction,
    Reliability,
    Tier,
    Verdict,
)

MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {"UNVERIFIABLE": "escalate"}}


# --- one test per docs/compensability.md row ---------------------------


def test_issue_refund_is_fully_compensable():
    c = compensation_for("issue_refund")
    assert c.compensability is Compensability.FULLY
    assert c.action == "reverse_refund"


def test_update_entitlement_is_partially_compensable():
    c = compensation_for("update_entitlement")
    assert c.compensability is Compensability.PARTIALLY
    assert c.action == "restore_entitlement"


def test_send_customer_email_is_not_compensable():
    c = compensation_for("send_customer_email")
    assert c.compensability is Compensability.NOT
    assert c.action is None


def test_send_document_is_partially_compensable():
    c = compensation_for("send_document")
    assert c.compensability is Compensability.PARTIALLY
    assert c.action == "revoke_access"


def test_unregistered_tool_raises():
    import pytest

    with pytest.raises(KeyError):
        compensation_for("delete_customer_account")


# --- decide() basics ------------------------------------------------------


def test_all_predicates_pass_verifies_and_allows():
    claim = Claim(
        id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-88461",
        tier=Tier.C2, load_bearing=True,
    )
    ev = [Evidence(
        claim_id="c1", value="2026-08-11", source="orders.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )]
    action = ProposedAction(tool="issue_refund", order_id="ORD-88461", amount_paise=849900, currency="INR")
    d = decide("t1", "servicing-v1", action, [claim], ev, {"within_window": True}, MANIFEST)
    assert d.verdict == Verdict.VERIFIED
    assert d.intervention == Intervention.ALLOW


def test_hard_predicate_failure_blocks_even_when_compensable():
    claim = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-88461", tier=Tier.C2, load_bearing=True)
    ev = [Evidence(
        claim_id="c1", value="2026-07-19", source="orders.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )]
    action = ProposedAction(tool="issue_refund", order_id="ORD-88461", amount_paise=4299900, currency="INR")
    d = decide("t1", "servicing-v1", action, [claim], ev, {"within_window": False}, MANIFEST)
    assert d.verdict == Verdict.CONTRADICTED
    assert d.intervention == Intervention.BLOCK  # a real C1/C2 failure blocks regardless of compensability


def test_unresolvable_load_bearing_claim_is_unverifiable():
    """Isolated from the reliability-floor condition on purpose: a missing
    order in practice trips both (see test_below_reliability_floor_...
    below), but confidence=NONE alone must independently route to
    UNVERIFIABLE — that's the property this test checks."""
    claim = Claim(id="c1", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="ORD-99999", tier=Tier.C1, load_bearing=True)
    ev = [Evidence(
        claim_id="c1", value=None, source="orders.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.NONE,
    )]
    action = ProposedAction(tool="issue_refund", order_id="ORD-99999", amount_paise=100000, currency="INR")
    d = decide("t1", "servicing-v1", action, [claim], ev, {}, MANIFEST)
    assert d.verdict == Verdict.UNVERIFIABLE
    assert d.intervention == Intervention.ESCALATE


def test_below_reliability_floor_is_source_unreliable_and_outranks_contradiction():
    claim = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1", tier=Tier.C2, load_bearing=True)
    ev = [Evidence(
        claim_id="c1", value="2026-07-01", source="orders.db", query="...",
        fetched_at=now(), reliability_class=Reliability.INFERRED, confidence=Confidence.HIGH,
    )]
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100000, currency="INR")
    d = decide("t1", "servicing-v1", action, [claim], ev, {"within_window": False}, MANIFEST)
    # even though the predicate also failed, SOURCE_UNRELIABLE outranks CONTRADICTED
    assert d.verdict == Verdict.SOURCE_UNRELIABLE


def test_idempotency_key_is_deterministic():
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100000, currency="INR")
    d1 = decide("t1", "servicing-v1", action, [], [], {}, MANIFEST)
    d2 = decide("t1", "servicing-v1", action, [], [], {}, MANIFEST)
    assert d1.idempotency_key == d2.idempotency_key
    d3 = decide("t2", "servicing-v1", action, [], [], {}, MANIFEST)
    assert d3.idempotency_key != d1.idempotency_key


# --- D49's own demonstration: same weak evidence, different intervention --


def _c3_only_claim_and_evidence():
    claim = Claim(
        id="c1", kind=ClaimKind.CLAUSE_SEMANTICS_MATCH, subject="refund_window",
        tier=Tier.C3, load_bearing=True,
    )
    ev = [Evidence(
        claim_id="c1", value="a paraphrase", source="policy_store.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.MODERATE,
    )]
    return claim, ev


def test_d49_demonstration_irreversibility_dominates_severity():
    """Identical weak (C3-only, grounding score below threshold) evidence.
    Fully compensable -> escalates (D3: low confidence never blocks).
    Not compensable -> blocks anyway (D49: no undo for this class)."""
    claim, ev = _c3_only_claim_and_evidence()

    compensable_action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100000, currency="INR")
    compensable_decision = decide(
        "t1", "servicing-v1", compensable_action, [claim], ev, {}, MANIFEST, grounding_score=0.2,
    )

    not_compensable_action = ProposedAction(tool="send_customer_email", order_id=None, currency="INR")
    not_compensable_decision = decide(
        "t2", "servicing-v1", not_compensable_action, [claim], ev, {}, MANIFEST, grounding_score=0.2,
    )

    assert compensable_decision.verdict == Verdict.CONTRADICTED
    assert not_compensable_decision.verdict == Verdict.CONTRADICTED
    assert compensable_decision.intervention == Intervention.ESCALATE
    assert not_compensable_decision.intervention == Intervention.BLOCK
    assert compensable_decision.intervention != not_compensable_decision.intervention
