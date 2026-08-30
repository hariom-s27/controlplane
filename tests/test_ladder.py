"""S5 checkpoint.

Completeness (a row for every ClaimKind) is enforced at import time in
ladder.py itself, loudly, per schema.py's own ClaimKind docstring. This
file checks the two things the roadmap calls out by name: the refund
scenario's actual claim mix, and the within-window claim's load-bearing
status.
"""

from __future__ import annotations

import pytest

from controlplane import ladder as ladder_module
from controlplane.extract import build_claims
from controlplane.ladder import classify, classify_claims, is_load_bearing
from controlplane.schema import ClaimKind, ProposedAction, Tier


def test_every_claim_kind_has_a_tier_and_a_load_bearing_row():
    for kind in ClaimKind:
        classify(kind)  # raises KeyError if a row is missing
        is_load_bearing(kind)


def test_ladder_completeness_is_an_invariant_not_a_metric():
    """The retired 'coverage ratio 1.0' figure was just this invariant,
    dressed up as a measurement: every ClaimKind a governed tool emits is
    C1/C2/C3, so (C1+C2+C3)/total was always 1.0. It measured nothing about
    traffic. The real property — every ClaimKind is mapped — is enforced
    here, and an unmapped kind is a BUG, not a low number.

    See docs/experiment-audit.md and docs/retired-figures.md.
    """
    # the import-time guard in ladder.py must actually fire on a missing row
    original = dict(ladder_module._TIER)
    a_kind = next(iter(ClaimKind))
    try:
        ladder_module._TIER.pop(a_kind)
        with pytest.raises(KeyError):
            ladder_module.classify(a_kind)
    finally:
        ladder_module._TIER.clear()
        ladder_module._TIER.update(original)

    # and no ClaimKind silently defaults to C5
    assert set(ladder_module._TIER) == set(ClaimKind)
    assert set(ladder_module._LOAD_BEARING) == set(ClaimKind)


def _refund_action() -> ProposedAction:
    return ProposedAction(
        tool="issue_refund",
        order_id="ORD-88461",
        amount_paise=4299900,
        currency="INR",
    )


def _servicing_manifest() -> dict:
    from controlplane.manifest import load_manifest

    return load_manifest("servicing")


def test_refund_scenario_produces_c1_and_c2_claims():
    claims = classify_claims(build_claims(_refund_action(), _servicing_manifest()))
    tiers = {c.tier for c in claims}
    assert Tier.C1 in tiers
    assert Tier.C2 in tiers


def test_within_refund_window_claim_is_load_bearing():
    """The roadmap's own phrasing: 'the delivery date is load-bearing.' The
    claim that's actually about the delivery date is WITHIN_REFUND_WINDOW."""
    claims = classify_claims(build_claims(_refund_action(), _servicing_manifest()))
    window_claim = next(c for c in claims if c.kind == ClaimKind.WITHIN_REFUND_WINDOW)
    assert window_claim.load_bearing is True


def test_customer_intent_is_not_load_bearing():
    """C5, genuinely unverifiable — there is never evidence to contradict it
    with, so it can never be the reason an action is CONTRADICTED."""
    assert is_load_bearing(ClaimKind.CUSTOMER_INTENT) is False
