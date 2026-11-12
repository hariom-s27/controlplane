"""P1 — explicit claim lifecycle states and the per-action verification
coverage metric.

Coverage here is a RUNTIME OUTCOME, not a restatement of the ladder: a claim
counts toward the numerator only if authoritative evidence actually supported
its check on this decision. The retired "coverage_ratio = (C1+C2+C3)/total"
was circular because every governed claim is C1/C2/C3 by construction (see
docs/experiment-audit.md, tests/test_ladder.py). This suite exists to show
the new number genuinely varies and that no claim is ever dropped without an
explicit state.

Test matrix (P1 PART 11):
  1  5/5 verified          -> 100%
  2  4/5 verified          -> 80%
  3  3/5 verified          -> 60%
  4  0/5 verified          -> 0%
  5  contradiction         -> CONTRADICTED, never VERIFIED
  6  unavailable source    -> UNAVAILABLE, never VERIFIED
  7  unmodelled claim      -> UNMODELLED, never VERIFIED, not dropped
  8  zero eligible         -> N/A (never 100%)
  9  mixed states          -> counters + coverage all correct
  10 receipt reconstruction -> recomputed coverage == stored coverage
  (11 the rest of tests/ is the regression suite.)

PART 8 invariants:
  * MODELLED + UNMODELLED == EXTRACTED
  * VERIFIED + CONTRADICTED + UNVERIFIED + UNAVAILABLE <= VERIFICATION_ELIGIBLE
  * coverage == verified / eligible over the population named by coverage_basis
"""

from __future__ import annotations

import os

import pytest

from controlplane.decide import build_verification_ledger, decide
from controlplane.ladder import classify_claims, verification_eligible
from controlplane.receipt import build_receipt, verify
from controlplane.registry.clock import now
from controlplane.schema import (
    Claim,
    ClaimKind,
    Confidence,
    Evidence,
    Intervention,
    ModellingState,
    ProposedAction,
    Reliability,
    Tier,
    VerificationStatus,
    Verdict,
)

os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")

MANIFEST = {
    "reliability_floor": "corroborated",
    "verdict_handling": {"UNVERIFIABLE": "escalate", "SOURCE_UNRELIABLE": "escalate"},
    "manifest_id": "test-v1",
    "_name": "test",
    "compensation": {"compensability": "fully", "action": "reverse_it"},
}

# Five load-bearing, verification-eligible (C1/C2) ClaimKinds, each backed by
# its own Zen predicate flag — one lever per claim so a decision's coverage
# can be dialled to any k/5.
_FIVE = [
    (ClaimKind.ORDER_BELONGS_TO_CUSTOMER, "entity_match"),
    (ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER, "amount_sane"),
    (ClaimKind.WITHIN_REFUND_WINDOW, "within_window"),
    (ClaimKind.AMOUNT_WITHIN_AUTHORITY, "within_authority"),
    (ClaimKind.ORDER_ATTRIBUTES_MATCH, "attributes_match"),
]

_ACTION = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100_000, currency="INR")


def _evidence(claim_id: str, *, reliability=Reliability.CORROBORATED, confidence=Confidence.HIGH, value="x") -> Evidence:
    return Evidence(
        claim_id=claim_id, value=value, source="orders.db", query="SELECT ...",
        fetched_at=now(), reliability_class=reliability, confidence=confidence,
    )


def _decide_with(outcomes: list[str], *, reliabilities: list[Reliability] | None = None):
    """outcomes[i] in {'verified','contradicted','unverified','unavailable'} for
    the i-th of the five load-bearing eligible claims."""
    n = len(outcomes)
    reliabilities = reliabilities or [Reliability.CORROBORATED] * n
    claims = classify_claims([
        Claim(id=f"ORD-1:{kind.value}", kind=kind, subject="ORD-1")
        for kind, _ in _FIVE[:n]
    ])
    evidence: list[Evidence] = []
    predicate_result: dict[str, bool] = {}
    for (kind, field), outcome, rel in zip(_FIVE[:n], outcomes, reliabilities):
        cid = f"ORD-1:{kind.value}"
        if outcome == "unavailable":
            continue  # no evidence object at all
        evidence.append(_evidence(cid, reliability=rel))
        if outcome == "verified":
            predicate_result[field] = True
        elif outcome == "contradicted":
            predicate_result[field] = False
        elif outcome == "unverified":
            pass  # evidence present, predicate flag absent -> no conclusive check
        else:
            raise ValueError(outcome)
    return decide("t1", "test-v1", _ACTION, claims, evidence, predicate_result, MANIFEST)


def _cov(decision) -> dict:
    return decision.verification_ledger.coverage.model_dump()


# --------------------------------------------------------------------------
# 1-4 + 9: the coverage dial
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcomes, verified, value",
    [
        (["verified"] * 5, 5, 1.0),
        (["verified"] * 4 + ["contradicted"], 4, 0.8),
        (["verified"] * 3 + ["contradicted", "unverified"], 3, 0.6),
        (["contradicted", "unavailable", "unverified", "contradicted", "unavailable"], 0, 0.0),
    ],
    ids=["5of5-100pct", "4of5-80pct", "3of5-60pct", "0of5-0pct"],
)
def test_coverage_dial(outcomes, verified, value):
    d = _decide_with(outcomes)
    cov = _cov(d)
    assert cov["verified"] == verified
    assert cov["eligible"] == 5
    assert cov["value"] == pytest.approx(value)
    assert cov["n_a"] is False
    assert cov["basis"] == "load_bearing_verification_eligible_claims"


def test_100pct_needs_every_load_bearing_claim_actually_verified():
    """The one guard against the retired circular ratio: 1.0 is only reachable
    when every load-bearing eligible claim was checked and passed on
    authoritative evidence — not because the ladder maps every kind."""
    d = _decide_with(["verified", "verified", "verified", "verified", "unverified"])
    assert _cov(d)["value"] == pytest.approx(0.8)  # NOT 1.0


# --------------------------------------------------------------------------
# 5: contradiction is explicit and never counts as verified
# --------------------------------------------------------------------------


def test_contradiction_is_explicit_and_not_verified():
    d = _decide_with(["verified", "verified", "contradicted", "verified", "verified"])
    L = d.verification_ledger
    rows = {r.claim_id: r for r in L.claims}
    contradicted = rows["ORD-1:within_refund_window"]
    assert contradicted.verification_status is VerificationStatus.CONTRADICTED
    assert contradicted.verification_status is not VerificationStatus.VERIFIED
    assert L.contradicted_claims == 1
    assert L.verified_claims == 4
    assert d.verdict is Verdict.CONTRADICTED  # ledger agrees with the verdict


# --------------------------------------------------------------------------
# 6: unavailable source is explicit and never counts as verified
# --------------------------------------------------------------------------


def test_unavailable_source_is_explicit_unavailable():
    d = _decide_with(["verified", "unavailable", "verified", "verified", "verified"])
    L = d.verification_ledger
    row = next(r for r in L.claims if r.claim_id == "ORD-1:amount_not_exceeding_order")
    assert row.verification_status is VerificationStatus.UNAVAILABLE
    assert row.reason == "no_evidence_resolved"
    assert L.unavailable_claims == 1
    assert _cov(d)["verified"] == 4 and _cov(d)["value"] == pytest.approx(0.8)


def test_missing_record_confidence_none_is_unavailable_not_verified():
    claims = classify_claims([Claim(id="ORD-9:x", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="ORD-9")])
    ev = [_evidence("ORD-9:x", confidence=Confidence.NONE, value=None)]
    d = decide("t1", "test-v1", _ACTION, claims, ev, {}, MANIFEST)
    row = d.verification_ledger.claims[0]
    assert row.verification_status is VerificationStatus.UNAVAILABLE
    assert row.reason == "authoritative_lookup_empty"


# --------------------------------------------------------------------------
# 7: an unmodelled claim gets an explicit state and is not dropped
# --------------------------------------------------------------------------


def test_unmodelled_claim_is_explicit_and_not_dropped():
    modelled = classify_claims([Claim(id="ORD-1:w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1")])[0]
    # A claim that never went through (or failed) classification: tier is None.
    unmodelled = Claim(id="ORD-1:mystery", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1")
    assert unmodelled.tier is None

    ledger = build_verification_ledger(
        [modelled, unmodelled],
        [_evidence("ORD-1:w")],
        {"within_window": True},
    )
    assert ledger.claims_extracted == 2
    assert ledger.claims_modelled == 1
    assert ledger.claims_unmodelled == 1
    by_id = {r.claim_id: r for r in ledger.claims}
    assert by_id["ORD-1:mystery"].modelling_state is ModellingState.UNMODELLED
    assert by_id["ORD-1:mystery"].verification_status is VerificationStatus.NOT_ELIGIBLE
    assert by_id["ORD-1:mystery"].verification_status is not VerificationStatus.VERIFIED
    # it did not vanish, and it did not inflate coverage
    assert ledger.coverage.verified == 1 and ledger.coverage.eligible == 1


def test_unmodelled_claim_flows_through_decide():
    modelled = classify_claims([Claim(id="ORD-1:w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1")])[0]
    unmodelled = Claim(id="ORD-1:mystery", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject="ORD-1")
    d = decide("t1", "test-v1", _ACTION, [modelled, unmodelled],
               [_evidence("ORD-1:w")], {"within_window": True}, MANIFEST)
    assert d.verification_ledger.claims_unmodelled == 1
    assert {r.claim_id for r in d.verification_ledger.claims} == {"ORD-1:w", "ORD-1:mystery"}


# --------------------------------------------------------------------------
# 8: zero eligible -> N/A, never 100%
# --------------------------------------------------------------------------


def test_zero_eligible_is_na_never_one():
    claims = classify_claims([Claim(id="ORD-1:intent", kind=ClaimKind.CUSTOMER_INTENT, subject="ORD-1")])
    assert claims[0].tier is Tier.C5 and claims[0].load_bearing is False
    d = decide("t1", "test-v1", _ACTION, claims, [], {}, MANIFEST)
    cov = _cov(d)
    assert cov["eligible"] == 0
    assert cov["value"] is None
    assert cov["n_a"] is True
    assert cov["verified"] == 0


def test_no_claims_at_all_is_na():
    d = decide("t1", "test-v1", _ACTION, [], [], {}, MANIFEST)
    cov = _cov(d)
    assert cov["value"] is None and cov["n_a"] is True
    assert d.verification_ledger.claims_extracted == 0


def test_non_load_bearing_eligible_claim_excluded_from_denominator():
    # EXCERPT_CONTAINS_THIRD_PARTY_PII is C2 (eligible) but deliberately NOT
    # load-bearing — it must not enter the coverage denominator.
    claims = classify_claims([
        Claim(id="D:pii", kind=ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII, subject="DOC-1"),
    ])
    assert verification_eligible(ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII) is True
    assert claims[0].load_bearing is False
    d = decide("t1", "test-v1", _ACTION, claims, [_evidence("D:pii", value=True)], {}, MANIFEST)
    L = d.verification_ledger
    assert L.verification_eligible_claims == 1   # it IS eligible
    assert L.coverage.eligible == 0              # but not in the LB denominator
    assert L.coverage.n_a is True


# --------------------------------------------------------------------------
# 9: mixed states — counters and coverage all correct together
# --------------------------------------------------------------------------


def test_mixed_states_counters_and_coverage():
    d = _decide_with(["verified", "contradicted", "unverified", "unavailable", "verified"])
    L = d.verification_ledger
    assert (L.verified_claims, L.contradicted_claims, L.unverified_claims, L.unavailable_claims) == (2, 1, 1, 1)
    assert L.claims_extracted == 5 == L.claims_modelled
    assert L.claims_unmodelled == 0
    assert L.load_bearing_claims == 5
    assert L.verification_eligible_claims == 5
    cov = _cov(d)
    assert cov == {
        "verified": 2, "eligible": 5, "value": pytest.approx(0.4),
        "basis": "load_bearing_verification_eligible_claims", "n_a": False,
    }


def test_below_floor_pass_is_unverified_not_verified():
    """decide() labels the decision SOURCE_UNRELIABLE; the per-claim ledger
    must not call that claim VERIFIED — the check passed but not on a
    trusted-enough source."""
    d = _decide_with(["verified"], reliabilities=[Reliability.INFERRED])
    row = d.verification_ledger.claims[0]
    assert row.verification_status is VerificationStatus.UNVERIFIED
    assert row.reason == "source_below_reliability_floor"
    assert _cov(d)["value"] == 0.0
    assert d.verdict is Verdict.SOURCE_UNRELIABLE


# --------------------------------------------------------------------------
# PART 8 invariants — over a spread of decisions
# --------------------------------------------------------------------------


_SPREADS = [
    ["verified"] * 5,
    ["verified"] * 4 + ["contradicted"],
    ["verified", "contradicted", "unverified", "unavailable", "verified"],
    ["contradicted"] * 5,
    ["unavailable"] * 5,
    ["unverified"] * 5,
]


@pytest.mark.parametrize("outcomes", _SPREADS, ids=lambda o: "-".join(x[:3] for x in o))
def test_invariant_modelled_plus_unmodelled_equals_extracted(outcomes):
    L = _decide_with(outcomes).verification_ledger
    assert L.claims_modelled + L.claims_unmodelled == L.claims_extracted


@pytest.mark.parametrize("outcomes", _SPREADS, ids=lambda o: "-".join(x[:3] for x in o))
def test_invariant_status_counts_within_eligible(outcomes):
    L = _decide_with(outcomes).verification_ledger
    total = L.verified_claims + L.contradicted_claims + L.unverified_claims + L.unavailable_claims
    assert total <= L.verification_eligible_claims


@pytest.mark.parametrize("outcomes", _SPREADS, ids=lambda o: "-".join(x[:3] for x in o))
def test_invariant_coverage_equals_verified_over_eligible(outcomes):
    L = _decide_with(outcomes).verification_ledger
    lb_eligible = [r for r in L.claims if r.load_bearing and r.verification_eligible]
    verified = sum(1 for r in lb_eligible if r.verification_status is VerificationStatus.VERIFIED)
    if lb_eligible:
        assert L.coverage.value == pytest.approx(round(verified / len(lb_eligible), 6))
        assert L.coverage.n_a is False
    else:
        assert L.coverage.value is None and L.coverage.n_a is True


@pytest.mark.parametrize("outcomes", _SPREADS, ids=lambda o: "-".join(x[:3] for x in o))
def test_invariant_every_claim_has_exactly_one_state(outcomes):
    """No claim disappears without an explicit state."""
    L = _decide_with(outcomes).verification_ledger
    assert len(L.claims) == L.claims_extracted
    for r in L.claims:
        assert r.modelling_state in (ModellingState.MODELLED, ModellingState.UNMODELLED)
        assert r.verification_status in set(VerificationStatus)


# --------------------------------------------------------------------------
# 10: receipt reconstruction
# --------------------------------------------------------------------------


def _receipt_status(claim: dict) -> str | None:
    """The receipt's per-claim verification is a plain status string in the
    common case, a dict when there is more to say."""
    v = claim.get("verification")
    if v is None:
        return None
    return v if isinstance(v, str) else v["status"]


def _receipt_eligible(claim: dict) -> bool:
    v = claim.get("verification")
    if v is None:
        return False
    return True if isinstance(v, str) else v.get("eligible", True)


def test_receipt_reconstruction_recomputed_equals_stored():
    d = _decide_with(["verified", "verified", "contradicted", "unverified", "verified"])
    receipt = build_receipt(
        d, {"tool": "issue_refund", "order_id": "ORD-1", "amount_paise": 100_000, "currency": "INR"},
        latency_ms={"extract": 10.0},
    )
    assert verify(receipt) is True

    block = receipt["verification_coverage"]
    # Recompute purely from the per-claim rows on the receipt.
    lb = [c for c in receipt["claims"] if c.get("load_bearing") and _receipt_eligible(c)]
    recomputed_eligible = len(lb)
    recomputed_verified = sum(1 for c in lb if _receipt_status(c) == "verified")
    assert recomputed_verified == block["verified"]
    assert recomputed_eligible == block["eligible"]
    expected = round(recomputed_verified / recomputed_eligible, 6) if recomputed_eligible else None
    assert block["coverage"] == expected
    assert block["coverage"] == pytest.approx(0.6)


def test_receipt_compact_form_healthy_claim_is_a_bare_string():
    d = _decide_with(["verified", "verified"])
    receipt = build_receipt(d, {"tool": "issue_refund", "order_id": "ORD-1"}, latency_ms={})
    verifications = [c["verification"] for c in receipt["claims"] if c.get("load_bearing")]
    assert verifications == ["verified", "verified"]  # no dict noise when nothing to add


def test_receipt_block_absent_when_no_ledger():
    """A hand-built Decision with no ledger still produces a valid receipt —
    the block is present as null, older receipts do not break."""
    from controlplane.compensation import compensation_for
    from controlplane.schema import Decision

    d = Decision(
        trace_id="t1", manifest_id="test-v1", verdict=Verdict.VERIFIED,
        intervention=Intervention.ALLOW, claims=[], evidence=[],
        compensation=compensation_for(MANIFEST), idempotency_key="k1",
    )
    receipt = build_receipt(d, {"tool": "issue_refund"}, latency_ms={})
    assert receipt["verification_coverage"] is None
    assert verify(receipt) is True


# --------------------------------------------------------------------------
# operational-failure path: everything eligible is UNAVAILABLE
#
# The operational Decision (SourceUnavailable / AmbiguousPolicyState) is built
# directly in intercept.py without resolving evidence and without importing
# the ledger builder (intercept.py is a P06-protected artifact, kept
# byte-identical). resolved_verification_ledger() reconstructs the ledger from
# the facts that Decision *does* carry, and the signed receipt records it.
# --------------------------------------------------------------------------


def test_source_unavailable_path_reconstructs_all_unavailable_ledger(monkeypatch, tmp_path):
    import controlplane.intercept as intercept
    import controlplane.receipt as receipt_module
    import controlplane.telemetry as telemetry_module
    import controlplane.registry.orders as orders_registry
    from controlplane.decide import resolved_verification_ledger
    from controlplane.schema import SessionContext

    monkeypatch.setattr(receipt_module, "OPERATIONAL_TRAIL", tmp_path / "d.jsonl")
    monkeypatch.setattr(telemetry_module, "OPERATIONAL_TRAIL", tmp_path / "d.jsonl")
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    monkeypatch.setenv("CP_RECEIPT_SECRET", "test-secret-not-for-production")

    action = ProposedAction(tool="issue_refund", order_id="ORD-90233", amount_paise=849900, currency="INR",
                            item_colour="grey", item_category="shirt")
    monkeypatch.setattr(intercept, "extract_action", lambda **kw: action)

    def _boom(*a, **k):
        from controlplane.errors import SourceUnavailable
        raise SourceUnavailable(source="orders.db", operation="read order")

    monkeypatch.setattr(orders_registry.OrdersResolver, "resolve", _boom)

    decision, _lat, receipt = intercept._run_gate(
        "issue_refund", {"order_id": "ORD-90233", "amount_paise": 849900, "currency": "INR",
                         "item_colour": "grey", "item_category": "shirt"},
        SessionContext(trace_id="t-unavail", customer_id="CUST-2291"), "", [],
    )
    L = resolved_verification_ledger(decision)
    assert L is not None
    assert L.verified_claims == 0
    assert L.unavailable_claims == L.verification_eligible_claims > 0
    assert L.coverage.verified == 0
    assert L.coverage.value == 0.0  # 0 / N, never N/A here (servicing has eligible LB claims)

    block = receipt["verification_coverage"]
    assert block is not None
    assert block["verified"] == 0 and block["coverage"] == 0.0
    assert all(
        _receipt_status(c) == "unavailable"
        for c in receipt["claims"]
        if c["load_bearing"] and _receipt_eligible(c)
    )
    assert verify(receipt) is True
