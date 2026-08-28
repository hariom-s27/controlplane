"""S4 checkpoint — three fixtures, per the roadmap's own verify list:
(1) a full justification with a date, (2) a justification with no date,
(3) a justification citing v3.8. Case 2 must yield claimed_delivered_at is
None and must not raise — a missing claim is a normal, correct outcome.

These replay from committed fixtures (data/fixtures/extract/) by default,
so `pytest` stays offline. Re-record with CP_MODE=live if the fixtures ever
need to change (e.g. EXTRACT_PROMPT wording changes materially).
"""

from __future__ import annotations

from controlplane.extract import build_claims, extract_action
from controlplane.schema import ProposedAction

_TOOL_CALL_ARGS = {"order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR"}


def test_build_claims_raises_for_unmodeled_tool():
    """A tool with no row in _CLAIM_KINDS_BY_TOOL must fail loudly, not
    return [] — an empty claim list would let decide() sail straight to
    VERIFIED/ALLOW with nothing actually checked."""
    import pytest

    with pytest.raises(KeyError):
        build_claims(ProposedAction(tool="some_unmodeled_tool"))


def test_full_justification_with_a_date_extracts_it():
    action = extract_action(
        tool="issue_refund",
        tool_call_args=_TOOL_CALL_ARGS,
        justification=(
            "The customer's order ORD-88461 was delivered on 2026-07-19. "
            "Per the current returns policy, this is within the refund "
            "window, so I'm issuing a full refund."
        ),
        retrieved_chunks=[
            "Refunds and returns. Customers may request a full refund "
            "within 7 days of the delivery date."
        ],
    )
    assert action.claimed_delivered_at is not None
    assert action.claimed_delivered_at.isoformat() == "2026-07-19"
    # structural fields must come from tool_call_args, never from the LLM
    assert action.order_id == "ORD-88461"
    assert action.amount_paise == 4299900


def test_justification_with_no_date_yields_none_and_does_not_raise():
    action = extract_action(
        tool="issue_refund",
        tool_call_args=_TOOL_CALL_ARGS,
        justification=(
            "The customer says the blue running shoes they received don't "
            "fit and they'd like a full refund. Issuing the refund as "
            "requested."
        ),
        retrieved_chunks=[
            "Refunds and returns. Customers may request a full refund "
            "within 7 days of the delivery date."
        ],
    )
    assert action.claimed_delivered_at is None


def test_justification_citing_v38_extracts_the_version():
    action = extract_action(
        tool="issue_refund",
        tool_call_args=_TOOL_CALL_ARGS,
        justification=(
            "Per refund policy version v3.8, customers may request a full "
            "refund within 30 days of delivery. This order qualifies, so "
            "I'm approving the refund."
        ),
        retrieved_chunks=[
            "Refunds and returns. Customers may request a full refund "
            "within 30 days of the delivery date."
        ],
    )
    assert action.claimed_policy_version is not None
    assert "3.8" in action.claimed_policy_version
