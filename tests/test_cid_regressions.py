"""Focused regressions for predicate availability, idempotency, and null data."""

from __future__ import annotations

import sqlite3

import pytest

from controlplane.decide import decide
from controlplane.errors import SourceUnavailable
from controlplane.idempotency import DuplicateExecutionSuppressed, reset_execution_ledger
from controlplane.intercept import Pending, _run_gate, dispatch_tool, register_tool
from controlplane.manifest import load_manifest
from controlplane.predicates import evaluate
from controlplane.registry.clock import now
from controlplane.registry.orders import OrdersResolver
from controlplane.schema import (
    Claim,
    ClaimKind,
    Confidence,
    Decision,
    Evidence,
    Intervention,
    ProposedAction,
    Reliability,
    SessionContext,
    Tier,
    Verdict,
)

MANIFEST = {
    "reliability_floor": "corroborated",
    "verdict_handling": {"UNVERIFIABLE": "escalate"},
}


def _predicate_decision(result: dict) -> Decision:
    claim = Claim(
        id="c1",
        kind=ClaimKind.WITHIN_REFUND_WINDOW,
        subject="ORD-1",
        tier=Tier.C2,
        load_bearing=True,
    )
    evidence = Evidence(
        claim_id=claim.id,
        value="2026-08-11",
        source="orders.db",
        query="SELECT delivered_at FROM orders WHERE order_id = 'ORD-1'",
        fetched_at=now(),
        reliability_class=Reliability.CORROBORATED,
        confidence=Confidence.HIGH,
    )
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100)
    return decide("trace", "servicing-v1", action, [claim], [evidence], result, MANIFEST)


@pytest.mark.parametrize("result", [{"within_window": None}, {}, {"within_window": "yes"}])
def test_unavailable_or_malformed_predicate_never_allows(result):
    decision = _predicate_decision(result)

    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is Intervention.ESCALATE


@pytest.mark.parametrize("omit_field", [False, True])
def test_null_or_missing_date_is_an_unavailable_predicate_not_a_zen_exception(omit_field):
    evidence = {
        "authority_ceiling_paise": 1000,
        "order": {
            "customer_id": "CUST-1",
            "amount_paise": 1000,
            "item_colour": "blue",
            "item_category": "shoes",
        },
        "session": {"customer_id": "CUST-1"},
        "clock": {"today": "2026-08-14"},
    }
    if not omit_field:
        evidence["delivered_at"] = None
    action = ProposedAction(
        tool="issue_refund",
        order_id="ORD-1",
        amount_paise=100,
        item_colour="blue",
        item_category="shoes",
    )

    outcome = evaluate(evidence, action, {"window_days": 7})

    assert outcome["result"]["within_window"] is None
    assert "within_window" in outcome["trace"]["unavailable_predicates"]


@pytest.fixture(autouse=True)
def _clear_idempotency_ledger():
    reset_execution_ledger()
    yield
    reset_execution_ledger()


def _allow_decision(key: str) -> Decision:
    return Decision(
        trace_id="trace",
        manifest_id="servicing-v1",
        verdict=Verdict.VERIFIED,
        intervention=Intervention.ALLOW,
        idempotency_key=key,
    )


def _knowledge_unverifiable_decision() -> Decision:
    action = ProposedAction(
        tool="send_document",
        recipient_id="EMP-4410",
        doc_id="DOC-2277",
        excerpt="original sensitive excerpt",
    )
    claim = Claim(
        id="DOC-2277:classification",
        kind=ClaimKind.DOC_CLASSIFICATION_PERMITTED,
        subject="DOC-2277",
        tier=Tier.C2,
        load_bearing=True,
    )
    manifest = load_manifest("knowledge_assistant")
    return decide(
        "knowledge-trace",
        manifest["manifest_id"],
        action,
        [claim],
        [],
        {},
        manifest,
    )


def test_unverifiable_modify_without_args_never_executes_original(monkeypatch):
    original_args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-2277",
        "excerpt": "original sensitive excerpt",
    }
    calls = []
    register_tool("cid_unavailable_modify", lambda **kwargs: calls.append(kwargs) or "sent")
    decision = _knowledge_unverifiable_decision()
    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is Intervention.MODIFY
    assert decision.modified_args is None
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *args, **kwargs: (decision, {}))

    with pytest.raises(Pending):
        dispatch_tool(
            "cid_unavailable_modify",
            original_args,
            SessionContext(trace_id="knowledge-trace"),
        )

    assert calls == []


def test_modify_with_explicit_args_executes_only_modified_values(monkeypatch):
    original_args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-2277",
        "excerpt": "original sensitive excerpt",
    }
    modified_args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-2277",
        "excerpt": "[redacted]",
    }
    calls = []
    register_tool("cid_valid_modify", lambda **kwargs: calls.append(kwargs) or "sent")
    decision = _knowledge_unverifiable_decision()
    decision.modified_args = modified_args
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *args, **kwargs: (decision, {}))

    result = dispatch_tool(
        "cid_valid_modify",
        original_args,
        SessionContext(trace_id="knowledge-trace"),
    )

    assert result == "sent"
    assert calls == [modified_args]
    assert calls[0] != original_args


def test_equivalent_allowed_dispatch_executes_only_once(monkeypatch):
    calls = []
    register_tool("cid_once", lambda **kwargs: calls.append(kwargs) or {"call": len(calls)})
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *args, **kwargs: (_allow_decision("same"), {}))
    session = SessionContext(trace_id="trace")

    first = dispatch_tool("cid_once", {"value": 1}, session)
    second = dispatch_tool("cid_once", {"value": 1}, session)

    assert first == second == {"call": 1}
    assert calls == [{"value": 1}]


def test_distinct_idempotency_keys_execute_independently(monkeypatch):
    calls = []
    register_tool("cid_distinct", lambda **kwargs: calls.append(kwargs) or len(calls))
    monkeypatch.setattr(
        "controlplane.intercept._run_gate",
        lambda _name, _args, session, *_rest: (_allow_decision(session.trace_id), {}),
    )

    assert dispatch_tool("cid_distinct", {"value": 1}, SessionContext(trace_id="first")) == 1
    assert dispatch_tool("cid_distinct", {"value": 1}, SessionContext(trace_id="second")) == 2
    assert len(calls) == 2


def test_failed_execution_keeps_an_indeterminate_marker(monkeypatch):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("uncertain tool outcome")

    register_tool("cid_failure", fail)
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *args, **kwargs: (_allow_decision("failed"), {}))
    session = SessionContext(trace_id="trace")

    with pytest.raises(RuntimeError, match="uncertain tool outcome"):
        dispatch_tool("cid_failure", {"value": 1}, session)
    with pytest.raises(DuplicateExecutionSuppressed):
        dispatch_tool("cid_failure", {"value": 1}, session)
    assert calls == [{"value": 1}]


def _order_claim(order_id: str) -> Claim:
    return Claim(
        id=f"{order_id}:within_refund_window",
        kind=ClaimKind.WITHIN_REFUND_WINDOW,
        subject=order_id,
        tier=Tier.C2,
        load_bearing=True,
    )


def test_missing_order_and_null_field_are_distinct_unverified_evidence(tmp_path, monkeypatch):
    from controlplane.registry import orders

    database = tmp_path / "orders.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE orders (order_id TEXT PRIMARY KEY, delivered_at TEXT)")
    connection.execute("INSERT INTO orders VALUES ('NULL-DATE', NULL)")
    connection.commit()
    connection.close()
    monkeypatch.setattr(orders, "DB", database)
    resolver = OrdersResolver()
    session = SessionContext(trace_id="trace")

    missing = resolver.resolve(_order_claim("MISSING"), session)
    null_field = resolver.resolve(_order_claim("NULL-DATE"), session)

    assert missing.value is None and missing.confidence is Confidence.NONE
    assert "no order found" in missing.note
    assert null_field.value is None and null_field.confidence is Confidence.NONE
    assert null_field.reliability_class is Reliability.UNVERIFIED
    assert "is NULL" in null_field.note


def test_missing_source_is_typed_and_not_created(tmp_path, monkeypatch):
    from controlplane.registry import orders

    database = tmp_path / "absent-orders.db"
    monkeypatch.setattr(orders, "DB", database)

    with pytest.raises(SourceUnavailable):
        OrdersResolver().resolve(_order_claim("ORD-1"), SessionContext(trace_id="trace"))
    assert not database.exists()


def test_schema_failure_remains_loud(tmp_path, monkeypatch):
    from controlplane.registry import orders

    database = tmp_path / "malformed-orders.db"
    sqlite3.connect(database).close()
    monkeypatch.setattr(orders, "DB", database)

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        OrdersResolver().resolve(_order_claim("ORD-1"), SessionContext(trace_id="trace"))


def test_gate_translates_source_outage_to_explicit_manifest_outcome(monkeypatch):
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100)
    monkeypatch.setattr("controlplane.intercept.extract_action", lambda **_kwargs: action)
    monkeypatch.setattr(
        "controlplane.intercept.resolve_all",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SourceUnavailable(source="orders.db", operation="connect")
        ),
    )
    monkeypatch.setattr("controlplane.intercept.record", lambda *_args, **_kwargs: None)

    decision, _ = _run_gate(
        "issue_refund",
        {"order_id": "ORD-1", "amount_paise": 100},
        SessionContext(trace_id="trace"),
        "",
        [],
    )

    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is Intervention.ALLOW  # servicing compensable fail posture is explicitly open
    assert decision.root_cause == "authoritative_source_unavailable"
    assert decision.reasons[0].rule == "authoritative_source_available"
