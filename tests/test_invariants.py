"""S15 — the five metamorphic invariants over decide(), formally stated in
docs/invariants.md. hypothesis generates the scenarios; "more permissive"
and "stricter" are Intervention.rank comparisons, never a lookup table.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from hypothesis import given
from hypothesis import strategies as st

from controlplane.decide import decide
from controlplane.ladder import classify_claims
from controlplane.schema import (
    Claim,
    ClaimKind,
    Confidence,
    Evidence,
    Intervention,
    ProposedAction,
    Reliability,
    Tier,
)

TODAY = date(2026, 8, 14)
NOW = datetime.now(timezone.utc)
MANIFEST = {
    "reliability_floor": "corroborated", "verdict_handling": {},
    "manifest_id": "servicing-v1", "_name": "servicing",
    "compensation": {"action": "reverse_refund", "compensability": "fully"},
}


def _decide(
    days_ago: int,
    amount_paise: int,
    ceiling_paise: int = 2_500_000,
    window_reliability: Reliability = Reliability.CORROBORATED,
    claimed_version: str | None = None,
    current_version: str = "v4.2",
    order_id: str = "ORD-X",
):
    window_claim = Claim(id=f"{order_id}:w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject=order_id, tier=Tier.C2)
    authority_claim = Claim(id=f"{order_id}:a", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject=order_id, tier=Tier.C2)
    claims = classify_claims([window_claim, authority_claim])

    delivered_at = (TODAY - timedelta(days=days_ago)).isoformat()
    evidence = [
        Evidence(claim_id=window_claim.id, value=delivered_at, source="orders.db", query="...",
                  fetched_at=NOW, reliability_class=window_reliability, confidence=Confidence.HIGH),
        Evidence(claim_id=authority_claim.id, value=ceiling_paise, source="manifest:servicing", query="...",
                  fetched_at=NOW, reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
    ]
    predicate_result = {"within_window": days_ago <= 7, "within_authority": amount_paise <= ceiling_paise}
    action = ProposedAction(
        tool="issue_refund", order_id=order_id, amount_paise=amount_paise, currency="INR",
        claimed_policy_version=claimed_version,
    )
    clause_match = (claimed_version == current_version) if claimed_version is not None else None
    return decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST, clause_match=clause_match)


_days = st.integers(min_value=0, max_value=60)
_amount = st.integers(min_value=10_000, max_value=10_000_000)


@given(days_ago=_days, amount_paise=_amount, extra_days=st.integers(min_value=1, max_value=30))
def test_m1_strictness_monotonicity_on_window(days_ago, amount_paise, extra_days):
    """Making delivered_at strictly older (a strictly less favourable
    evidence value) must not make the intervention more permissive."""
    before = _decide(days_ago, amount_paise)
    after = _decide(days_ago + extra_days, amount_paise)
    assert not after.intervention.more_permissive_than(before.intervention), (
        f"days_ago {days_ago}->{days_ago + extra_days}: "
        f"{before.intervention} -> {after.intervention} got MORE permissive"
    )


@given(days_ago=_days, low=_amount, extra=st.integers(min_value=1, max_value=5_000_000))
def test_m2_amount_monotonicity(days_ago, low, extra):
    """Lower amount, all else equal, must not make the decision stricter."""
    high = low + extra
    lower_amount_decision = _decide(days_ago, low)
    higher_amount_decision = _decide(days_ago, high)
    assert lower_amount_decision.intervention.rank <= higher_amount_decision.intervention.rank, (
        f"amount {low} -> {high}: "
        f"{lower_amount_decision.intervention} -> {higher_amount_decision.intervention} got stricter for the LOWER amount"
    )


@given(days_ago=_days, amount_paise=_amount)
def test_m3_policy_equivalence(days_ago, amount_paise):
    """Two concrete scenarios that differ only in cosmetic details (order_id,
    claim/evidence identifiers) but are policy-identical in every fact
    decide() actually reads must get identical verdicts."""
    a = _decide(days_ago, amount_paise, order_id="ORD-AAAA")
    b = _decide(days_ago, amount_paise, order_id="ORD-ZZZZ")
    assert a.verdict == b.verdict
    assert a.intervention == b.intervention


@given(days_ago=_days, amount_paise=_amount)
def test_m4_idempotence(days_ago, amount_paise):
    """The same action re-submitted unchanged: same verdict, same
    intervention, same idempotency_key (decide() is pure, so this must
    hold exactly, not approximately)."""
    first = _decide(days_ago, amount_paise)
    second = _decide(days_ago, amount_paise)
    assert first.verdict == second.verdict
    assert first.intervention == second.intervention
    assert first.idempotency_key == second.idempotency_key


@given(days_ago=_days, amount_paise=_amount)
def test_m5_source_degradation_monotonicity(days_ago, amount_paise):
    """Swapping in a lower-reliability source for the same load-bearing
    claim must never make the verdict more permissive. It may become
    SOURCE_UNRELIABLE / ESCALATE; never ALLOW where it was BLOCK."""
    corroborated = _decide(days_ago, amount_paise, window_reliability=Reliability.CORROBORATED)
    inferred = _decide(days_ago, amount_paise, window_reliability=Reliability.INFERRED)
    assert not inferred.intervention.more_permissive_than(corroborated.intervention), (
        f"degrading reliability corroborated->inferred: "
        f"{corroborated.intervention} -> {inferred.intervention} got MORE permissive"
    )
    if corroborated.intervention is Intervention.BLOCK:
        assert inferred.intervention is not Intervention.ALLOW
