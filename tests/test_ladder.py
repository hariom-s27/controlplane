"""S5 checkpoint.

Completeness (a row for every ClaimKind) is enforced at import time in
ladder.py itself, loudly, per schema.py's own ClaimKind docstring. This
file checks the two things the roadmap calls out by name: the refund
scenario's actual claim mix, and the within-window claim's load-bearing
status.
"""

from __future__ import annotations

from controlplane.extract import build_claims
from controlplane.ladder import classify, classify_claims, is_load_bearing
from controlplane.schema import ClaimKind, ProposedAction, Tier


def test_every_claim_kind_has_a_tier_and_a_load_bearing_row():
    for kind in ClaimKind:
        classify(kind)  # raises KeyError if a row is missing
        is_load_bearing(kind)


def _refund_action() -> ProposedAction:
    return ProposedAction(
        tool="issue_refund",
        order_id="ORD-88461",
        amount_paise=4299900,
        currency="INR",
    )


def test_refund_scenario_produces_c1_and_c2_claims():
    claims = classify_claims(build_claims(_refund_action()))
    tiers = {c.tier for c in claims}
    assert Tier.C1 in tiers
    assert Tier.C2 in tiers


def test_within_refund_window_claim_is_load_bearing():
    """The roadmap's own phrasing: 'the delivery date is load-bearing.' The
    claim that's actually about the delivery date is WITHIN_REFUND_WINDOW."""
    claims = classify_claims(build_claims(_refund_action()))
    window_claim = next(c for c in claims if c.kind == ClaimKind.WITHIN_REFUND_WINDOW)
    assert window_claim.load_bearing is True


def test_customer_intent_is_not_load_bearing():
    """C5, genuinely unverifiable — there is never evidence to contradict it
    with, so it can never be the reason an action is CONTRADICTED."""
    assert is_load_bearing(ClaimKind.CUSTOMER_INTENT) is False
