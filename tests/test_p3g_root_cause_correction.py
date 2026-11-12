"""P3-G — receipt.py root_cause correction for the missing/unresolved
authoritative order-record case.

P3-F (docs/causal-precondition-annotation-design-review.md) established
that `_root_cause()` mislabels the missing-order-record condition as
`evidence_below_reliability_floor` (a "bad-but-present evidence" label) when
`decide.py:311-329` sets BOTH `source_unreliable` AND `unverifiable` for a
claim whose authoritative lookup returned `Confidence.NONE`. P3-G corrects
that ONE label, reusing the ledger's own existing name for exactly this
evidence shape (`decide.py:157`, `_verify_one_claim` -> reason
`"authoritative_lookup_empty"`) rather than inventing a new root_cause
value. This file is the regression suite for that fix: the four P3-E/P3-F
target cases (positive), and nine failure-surface-separation negative
controls (this must NOT broaden beyond the missing-record case).

No new root_cause enum/value is introduced anywhere in this file or in the
change it tests.
"""

from __future__ import annotations

import os

from controlplane.decide import decide
from controlplane.receipt import build_receipt, verify
from controlplane.registry.clock import now
from controlplane.schema import (
    Claim, ClaimKind, Confidence, Decision, Evidence, Intervention,
    ProposedAction, Reliability, Tier, Verdict,
)

os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")

_MANIFEST = {
    "reliability_floor": "corroborated",
    "verdict_handling": {},
    "manifest_id": "servicing-v1",
    "_name": "test",
    "compensation": {"action": "reverse_refund", "compensability": "fully"},
}
_ACTION = ProposedAction(tool="issue_refund", order_id="OR-X", amount_paise=100000, currency="INR")
_ACTION_DICT = {"tool": "issue_refund", "order_id": "OR-X", "amount_paise": 100000, "currency": "INR"}


def _ev(claim_id, value, reliability, confidence, note=None):
    return Evidence(
        claim_id=claim_id, value=value, source="orders.db",
        query="SELECT ... FROM orders WHERE order_id = 'OR-X'", fetched_at=now(),
        reliability_class=reliability, confidence=confidence, note=note,
    )


def _decide(claims, evidence, predicate_result):
    return decide("t-p3g", "servicing-v1", _ACTION, claims, evidence, predicate_result, _MANIFEST)


# ---------------------------------------------------------------------------
# Positive: the four P3-E/P3-F target cases, via the real corpus pipeline
# ---------------------------------------------------------------------------


def _p1_gold_case(case_id):
    from datetime import date

    from bench import extraction_completeness_bench as X
    from bench import foundational_requirement_coverage as F
    from controlplane.bindings import claim_specs
    from controlplane.manifest import load_manifest
    from controlplane.registry.clock import set_clock

    set_clock(date.fromisoformat(F.FROZEN_TODAY))
    manifest = load_manifest("servicing")
    specs = claim_specs(manifest)
    gset = F.load_gold_set()
    return X.run_p1(gset[case_id], manifest, specs)


import pytest


@pytest.mark.parametrize("case_id", ["gs-129", "gs-130", "gs-133", "gs-134"])
def test_missing_record_case_root_cause_is_authoritative_lookup_empty(case_id):
    """The P3-B/P3-E missing-order-record cases (record_lookup_status ==
    NO_MATCH in bench/human_label_sample.csv). Before P3-G these received
    the misleading `evidence_below_reliability_floor` label; after, the
    honest `authoritative_lookup_empty` label (already used per-claim in
    the P1 ledger, decide.py:157) -- with verdict, intervention, and
    verification coverage all UNCHANGED (decision-behaviour invariant)."""
    decision = _p1_gold_case(case_id)
    receipt = build_receipt(decision, {"tool": "issue_refund"}, {})

    assert receipt["root_cause"] == "authoritative_lookup_empty"
    assert decision.verdict is Verdict.SOURCE_UNRELIABLE
    assert decision.intervention is Intervention.ESCALATE
    L = decision.verification_ledger
    assert (L.coverage.verified, L.coverage.eligible) == (2, 7)
    assert L.coverage.value == pytest.approx(2 / 7)
    unavailable_reasons = {r.reason for r in L.claims if r.verification_status.value == "unavailable"}
    assert unavailable_reasons == {"authoritative_lookup_empty"}  # ledger reason unchanged
    assert verify(receipt) is True


# ---------------------------------------------------------------------------
# Negative controls A-I (failure-surface separation, task section 13)
# ---------------------------------------------------------------------------


def test_A_valid_record_normal_evidence_no_root_cause():
    c1 = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="OR-X", tier=Tier.C2, load_bearing=True)
    decision = _decide([c1], [_ev("c1", "2026-07-19", Reliability.CORROBORATED, Confidence.HIGH)], {"within_window": True})
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.VERIFIED
    assert receipt["root_cause"] is None


def test_B_valid_record_below_reliability_floor_keeps_existing_label():
    """Evidence PRESENT (not Confidence.NONE) but from a source below the
    reliability floor, and the check itself passes. Must retain
    `evidence_below_reliability_floor` -- must NOT receive the missing-
    record label, since there is no empty lookup here at all."""
    c1 = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="OR-X", tier=Tier.C2, load_bearing=True)
    decision = _decide([c1], [_ev("c1", "2026-07-19", Reliability.INFERRED, Confidence.HIGH)], {"within_window": True})
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.SOURCE_UNRELIABLE
    assert receipt["root_cause"] == "evidence_below_reliability_floor"


def test_C_source_unavailable_keeps_existing_label():
    """The typed operational-failure path (intercept.py:_operational_decision)
    sets `decision.root_cause` explicitly; `_root_cause()` returns it as-is
    without ever reaching the reasons scan this fix touches."""
    decision = Decision(
        trace_id="t-src", manifest_id="servicing-v1", verdict=Verdict.UNVERIFIABLE,
        intervention=Intervention.BLOCK, root_cause="authoritative_source_unavailable",
        verification_state="unverified",
    )
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert receipt["root_cause"] == "authoritative_source_unavailable"


def test_D_contradiction_on_valid_evidence_keeps_existing_label():
    c1 = Claim(id="c1", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="OR-X", tier=Tier.C1, load_bearing=True)
    decision = _decide([c1], [_ev("c1", "CUST-9999", Reliability.CORROBORATED, Confidence.HIGH)], {"entity_match": False})
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.CONTRADICTED
    assert receipt["root_cause"] == "entity_mismatch"


def test_E_unverified_no_evidence_at_all_keeps_raw_rule_label():
    """`ev is None` (no evidence resolved at all) is a DIFFERENT UNAVAILABLE
    path than `ev.confidence == Confidence.NONE` (decide.py:151-158) and
    must not collapse into the missing-record label."""
    c1 = Claim(id="c1", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="OR-X", tier=Tier.C1, load_bearing=True)
    decision = _decide([c1], [], {})
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.UNVERIFIABLE
    assert receipt["root_cause"] == "order_belongs_to_customer_resolved"
    assert receipt["root_cause"] != "authoritative_lookup_empty"


def test_F_valid_record_violated_claim_not_blamed_on_record_resolution():
    c1 = Claim(id="c1", kind=ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER, subject="OR-X", tier=Tier.C1, load_bearing=True)
    decision = _decide([c1], [_ev("c1", 100000, Reliability.CORROBORATED, Confidence.HIGH)], {"amount_sane": False})
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.CONTRADICTED
    assert receipt["root_cause"] == "amount_exceeds_source_record"


def test_G_valid_record_plus_independently_unavailable_claim():
    """One claim VERIFIED, a second UNAVAILABLE for an unrelated reason
    (`ev is None`, not an empty authoritative lookup). Must not receive the
    missing-record root cause."""
    c1 = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="OR-X", tier=Tier.C2, load_bearing=True)
    c2 = Claim(id="c2", kind=ClaimKind.ORDER_ATTRIBUTES_MATCH, subject="OR-X", tier=Tier.C2, load_bearing=True)
    decision = _decide(
        [c1, c2],
        [_ev("c1", "2026-07-19", Reliability.CORROBORATED, Confidence.HIGH)],
        {"within_window": True},
    )
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.UNVERIFIABLE
    assert receipt["root_cause"] == "order_attributes_match_resolved"
    assert receipt["root_cause"] != "authoritative_lookup_empty"


def test_H_missing_record_on_non_load_bearing_claim_yields_no_root_cause():
    """The authoritative lookup for c2 comes back empty, but c2 is NOT
    load-bearing -- decide()'s verdict loop (decide.py:298-300) skips it
    entirely, so it can never generate a `reliability_floor` reason to
    relabel. Must not receive the missing-record root cause merely because
    an unrelated (non-load-bearing) lookup is absent."""
    c1 = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="OR-X", tier=Tier.C2, load_bearing=True)
    c2 = Claim(id="c2", kind=ClaimKind.ORDER_ATTRIBUTES_MATCH, subject="OR-X", tier=Tier.C2, load_bearing=False)
    decision = _decide(
        [c1, c2],
        [
            _ev("c1", "2026-07-19", Reliability.CORROBORATED, Confidence.HIGH),
            _ev("c2", None, Reliability.UNVERIFIED, Confidence.NONE, note="no order found for order_id='OR-X'"),
        ],
        {"within_window": True},
    )
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.VERIFIED
    assert receipt["root_cause"] is None


def test_I_missing_record_plus_unrelated_contradiction_precedence_unchanged():
    """c1's authoritative lookup is empty (missing record); c2 is a genuine,
    independently-reliable contradiction. The verdict/intervention are
    correctly driven by the hard contradiction (decide.py's precedence:
    hard_contradiction wins outright). `_root_cause()`'s scan already
    returns on the FIRST failing reason in claim order -- pre-existing
    behaviour, unchanged by this fix -- which is c1's `reliability_floor`
    reason (c1 precedes c2 in the claims list). This test pins that the fix
    only corrects the LABEL at that position; it does not reorder which
    reason wins, and does not suppress the genuine contradiction's effect
    on verdict/intervention."""
    c1 = Claim(id="c1", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="OR-X", tier=Tier.C1, load_bearing=True)
    c2 = Claim(id="c2", kind=ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER, subject="OR-X", tier=Tier.C1, load_bearing=True)
    decision = _decide(
        [c1, c2],
        [
            _ev("c1", None, Reliability.UNVERIFIED, Confidence.NONE, note="no order found for order_id='OR-X'"),
            _ev("c2", 100000, Reliability.CORROBORATED, Confidence.HIGH),
        ],
        {"amount_sane": False},
    )
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.CONTRADICTED  # driven by c2, unaffected by this fix
    assert decision.intervention is Intervention.BLOCK
    assert receipt["root_cause"] == "authoritative_lookup_empty"  # relabeled; scan position unchanged


def test_null_field_on_existing_row_keeps_existing_label_not_missing_record():
    """A present row with a NULL field (orders.py:72-82) is a DIFFERENT
    failure surface than an absent row (orders.py:60-70) -- both produce
    `Confidence.NONE`, but only 'no order found' notes get the corrected
    label. See tests/test_cid_regressions.py::
    test_missing_order_and_null_field_remain_distinct_unverified_evidence,
    which pins 'no order found' vs. 'is NULL' as the note-level distinction
    this fix relies on, and tests/test_failure_injection.py::
    test_p08_null_delivered_at_is_source_unreliable_not_an_exception, which
    exercises this exact scenario end-to-end through the real DB/resolver
    and continues to assert `evidence_below_reliability_floor`."""
    c1 = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="OR-X", tier=Tier.C2, load_bearing=True)
    decision = _decide(
        [c1],
        [_ev("c1", None, Reliability.UNVERIFIED, Confidence.NONE, note="source field 'delivered_at' is NULL for order_id='OR-X'")],
        {},
    )
    receipt = build_receipt(decision, _ACTION_DICT, {})
    assert decision.verdict is Verdict.SOURCE_UNRELIABLE
    assert receipt["root_cause"] == "evidence_below_reliability_floor"
    assert receipt["root_cause"] != "authoritative_lookup_empty"
