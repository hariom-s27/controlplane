"""S7 checkpoint — the eight-case table the spec calls for. Cases 1-7 go
through evaluate()'s guarded Zen Engine path; case 8 (clause version
mismatch) goes through clause_matches_claim(), which is deliberately a
separate, unguarded comparison — see controlplane/predicates/__init__.py's
docstring for why R5 can't live inside evaluate() without violating R1.
"""

from __future__ import annotations

import pytest

from controlplane.predicates import clause_matches_claim, evaluate
from controlplane.schema import Claim, ClaimKind, ProposedAction

MANIFEST = {"window_days": 7}


def _evidence(delivered_at="2026-07-19", today="2026-08-14", customer_id="CUST-2291",
              session_customer_id="CUST-2291", order_amount_paise=4299900, ceiling_paise=2500000,
              order_colour="blue", order_category="shoes"):
    return {
        "delivered_at": delivered_at,
        "authority_ceiling_paise": ceiling_paise,
        "order": {
            "customer_id": customer_id, "amount_paise": order_amount_paise,
            "item_colour": order_colour, "item_category": order_category,
        },
        "session": {"customer_id": session_customer_id},
        "clock": {"today": today},
    }


def _action(amount_paise=4299900, item_colour="blue", item_category="shoes"):
    return ProposedAction(
        tool="issue_refund", order_id="ORD-88461", amount_paise=amount_paise, currency="INR",
        item_colour=item_colour, item_category=item_category,
    )


@pytest.mark.parametrize(
    "name,evidence,action,expected_field,expected_value",
    [
        ("within_window_day_3", _evidence(delivered_at="2026-08-11"), _action(), "within_window", True),
        ("outside_window_day_26", _evidence(delivered_at="2026-07-19"), _action(), "within_window", False),
        ("exactly_at_boundary_day_7", _evidence(delivered_at="2026-08-07"), _action(), "within_window", True),
        ("amount_at_ceiling", _evidence(), _action(amount_paise=2500000), "within_authority", True),
        ("amount_over_ceiling", _evidence(), _action(amount_paise=2500001), "within_authority", False),
        ("customer_mismatch", _evidence(session_customer_id="CUST-9999"), _action(), "entity_match", False),
        ("amount_exceeding_order", _evidence(order_amount_paise=1000000), _action(amount_paise=4299900), "amount_sane", False),
        ("attributes_match", _evidence(), _action(), "attributes_match", True),
        ("attribute_colour_mismatch", _evidence(order_colour="grey"), _action(item_colour="blue"), "attributes_match", False),
        (
            "attribute_category_mismatch_the_D52_distractor",
            _evidence(order_colour="blue", order_category="shorts"),  # ORD-88472's actual attributes
            _action(item_colour="blue", item_category="shoes"),  # what the agent said (ORD-88461's item)
            "attributes_match", False,
        ),
    ],
)
def test_predicate_table(name, evidence, action, expected_field, expected_value):
    out = evaluate(evidence, action, MANIFEST)
    assert out["result"][expected_field] is expected_value, f"{name}: {out['result']}"


def test_boundary_day_8_is_outside():
    """The window is <= 7, not < 7 — R4 from way back: day 7 is inside, day
    8 is not. This is the exact off-by-one the frozen demo clock exists to
    prevent from drifting."""
    out = evaluate(_evidence(delivered_at="2026-08-06"), _action(), MANIFEST)  # 8 days before 2026-08-14
    assert out["result"]["within_window"] is False


def test_clause_version_mismatch():
    """Case 8: the agent claimed v3.8, the registry resolved v4.2. This is
    NOT a Zen predicate — see clause_matches_claim()'s docstring."""
    claim = Claim(id="c1", kind=ClaimKind.POLICY_CLAUSE_CURRENT, subject="refund_window", asserted_value="v3.8")
    from controlplane.schema import Confidence, Evidence, Reliability
    from controlplane.registry.clock import now

    evidence = Evidence(
        claim_id="c1", value="v4.2", source="policy_store.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )
    assert clause_matches_claim(claim, evidence) is False


def test_clause_version_match():
    claim = Claim(id="c1", kind=ClaimKind.POLICY_CLAUSE_CURRENT, subject="refund_window", asserted_value="v4.2")
    from controlplane.schema import Confidence, Evidence, Reliability
    from controlplane.registry.clock import now

    evidence = Evidence(
        claim_id="c1", value="v4.2", source="policy_store.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )
    assert clause_matches_claim(claim, evidence) is True


def test_no_claimed_field_reaches_the_engine():
    """R1, tested directly against S7: facts_for_predicate() strips
    claimed_* before evaluate() ever builds its payload."""
    action = ProposedAction(
        tool="issue_refund", order_id="ORD-88461", amount_paise=4299900, currency="INR",
        claimed_policy_version="v3.8", claimed_delivered_at=None,
    )
    facts = action.facts_for_predicate()
    assert "claimed_policy_version" not in facts
    assert "claimed_delivered_at" not in facts
