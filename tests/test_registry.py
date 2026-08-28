"""S6 checkpoint — the three required verifications, each testing the
resolver directly rather than through the full agent loop.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from controlplane.registry import freshness
from controlplane.registry.clock import now
from controlplane.registry.orders import OrdersResolver
from controlplane.registry.policy import PolicyResolver
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Reliability, SessionContext, Verdict

ROOT = Path(__file__).resolve().parent.parent
ORDERS_DB = ROOT / "data" / "orders.db"

_SESSION = SessionContext(trace_id="t-registry")


def test_policy_resolver_returns_v42_even_when_agent_retrieved_v38():
    """This is the whole demo. The claim below is deliberately built as if
    the agent's stale retrieval had asserted v3.8 — the resolver must never
    see, or be swayed by, that assertion. It doesn't even have a field to
    receive it: PolicyResolver.resolve() takes only (claim, session), and
    claim.subject is just the policy_id, never the agent's claimed version."""
    claim = Claim(
        id="refund_window:policy_clause_current",
        kind=ClaimKind.POLICY_CLAUSE_CURRENT,
        subject="refund_window",
        asserted_value="v3.8",  # what the agent claimed — irrelevant to the query
    )
    evidence = PolicyResolver().resolve(claim, _SESSION)
    assert evidence.value == "v4.2"
    assert "effective_to IS NULL" in evidence.query


def test_missing_order_id_returns_none_confidence_not_an_exception():
    claim = Claim(
        id="ORD-99999:order_belongs_to_customer",
        kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER,
        subject="ORD-99999",  # does not exist
    )
    evidence = OrdersResolver().resolve(claim, _SESSION)
    assert evidence.confidence == Confidence.NONE
    assert evidence.value is None


def test_inferred_field_on_load_bearing_claim_yields_source_unreliable():
    """order_status is orders.db's one INFERRED field (D36 / USPS OIG) —
    confirm the DB's own field_reliability table still classifies it that
    way, then confirm the escalation rule turns that into SOURCE_UNRELIABLE
    when the claim depending on it is load-bearing."""
    conn = sqlite3.connect(ORDERS_DB)
    reliability = freshness.reliability_for_field("orders", "order_status", conn)
    conn.close()
    assert reliability == Reliability.INFERRED

    evidence = Evidence(
        claim_id="ORD-88461:hypothetical",
        value="delivered",
        source="orders.db",
        query="SELECT order_status FROM orders WHERE order_id = 'ORD-88461'",
        fetched_at=now(),
        reliability_class=reliability,
    )
    load_bearing_claim = Claim(
        id="ORD-88461:hypothetical", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-88461", load_bearing=True
    )
    assert freshness.escalation_for(evidence, load_bearing_claim) == Verdict.SOURCE_UNRELIABLE

    not_load_bearing_claim = Claim(
        id="ORD-88461:hypothetical", kind=ClaimKind.CUSTOMER_INTENT, subject="ORD-88461", load_bearing=False
    )
    assert freshness.escalation_for(evidence, not_load_bearing_claim) is None


def test_order_attributes_resolves_the_real_distractor_pair():
    """R3 extended (D52), against real seed data rather than hand-fed
    dicts: ORD-88461 is blue running SHOES; ORD-88472 is the distractor —
    same customer, same colour, blue running SHORTS. The resolver must
    report each order's own actual attributes, not conflate them."""
    shoes_claim = Claim(id="ORD-88461:order_attributes_match", kind=ClaimKind.ORDER_ATTRIBUTES_MATCH, subject="ORD-88461")
    shoes_evidence = OrdersResolver().resolve(shoes_claim, _SESSION)
    assert shoes_evidence.value == {"colour": "blue", "category": "shoes"}

    shorts_claim = Claim(id="ORD-88472:order_attributes_match", kind=ClaimKind.ORDER_ATTRIBUTES_MATCH, subject="ORD-88472")
    shorts_evidence = OrdersResolver().resolve(shorts_claim, _SESSION)
    assert shorts_evidence.value == {"colour": "blue", "category": "shorts"}

    assert shoes_evidence.reliability_class == Reliability.CORROBORATED
    assert shoes_evidence.confidence == Confidence.HIGH
