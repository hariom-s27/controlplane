"""Focused regressions for canonical C/I/D safety semantics."""

from __future__ import annotations

import sqlite3

import pytest

from controlplane.decide import decide
from controlplane.errors import AmbiguousPolicyState, SourceUnavailable
from controlplane.idempotency import DuplicateExecutionSuppressed, reset_execution_ledger
from controlplane.intercept import Blocked, Pending, _run_gate, dispatch_tool, register_tool
from controlplane.manifest import load_manifest
from controlplane.predicates import evaluate
from controlplane.registry.clock import now
from controlplane.registry.orders import OrdersResolver
from controlplane.registry.policy import PolicyResolver
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
    # P02: decide() reads compensability from the manifest's own
    # `compensation` block, not from the tool name.
    "compensation": {"action": "reverse_refund", "compensability": "fully"},
}


@pytest.fixture(autouse=True)
def _clear_idempotency_ledger():
    reset_execution_ledger()
    yield
    reset_execution_ledger()


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


def test_true_predicate_preserves_verified_allow():
    decision = _predicate_decision({"within_window": True})

    assert decision.verdict is Verdict.VERIFIED
    assert decision.intervention is Intervention.ALLOW


def test_false_predicate_preserves_contradicted_block():
    decision = _predicate_decision({"within_window": False})

    assert decision.verdict is Verdict.CONTRADICTED
    assert decision.intervention is Intervention.BLOCK


@pytest.mark.parametrize("result", [{"within_window": None}, {}, {"within_window": "yes"}])
def test_unavailable_or_malformed_predicate_never_allows(result):
    decision = _predicate_decision(result)

    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is Intervention.ESCALATE
    assert any(reason.rule == "within_window_available" for reason in decision.reasons)


def test_missing_evidence_object_is_unverifiable():
    claim = Claim(
        id="c1",
        kind=ClaimKind.WITHIN_REFUND_WINDOW,
        subject="ORD-1",
        tier=Tier.C2,
        load_bearing=True,
    )
    decision = decide(
        "trace",
        "servicing-v1",
        ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100),
        [claim],
        [],
        {"within_window": True},
        MANIFEST,
    )

    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is Intervention.ESCALATE


@pytest.mark.parametrize("omit_field", [False, True])
def test_null_or_missing_date_is_unavailable_not_a_zen_exception(omit_field):
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

    manifest = {
        "window_days": 7,
        "predicate_graph": "graphs/servicing.json",
        "claim_bindings": [
            {
                "claim_kind": "WITHIN_REFUND_WINDOW",
                "resolver": "orders",
                "subject": "action.order_id",
                "predicate_key": "delivered_at",
            }
        ],
    }
    outcome = evaluate(evidence, action, manifest)

    assert outcome["result"]["within_window"] is None
    assert "within_window" in outcome["trace"]["unavailable_predicates"]


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


def _mock_gate(monkeypatch, decision: Decision) -> None:
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *args, **kwargs: (decision, {}, {}))


def test_modify_without_args_never_executes_original(monkeypatch):
    original_args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-2277",
        "excerpt": "original sensitive excerpt",
    }
    calls = []
    register_tool("cid_missing_modify", lambda **kwargs: calls.append(kwargs) or "sent")
    decision = _knowledge_unverifiable_decision()
    assert decision.intervention is Intervention.MODIFY
    assert decision.modified_args is None
    _mock_gate(monkeypatch, decision)

    with pytest.raises(Pending):
        dispatch_tool("cid_missing_modify", original_args, SessionContext(trace_id="knowledge-trace"))

    assert calls == []


def test_structurally_invalid_modify_args_never_execute_original(monkeypatch):
    calls = []
    register_tool("cid_invalid_modify", lambda **kwargs: calls.append(kwargs) or "sent")
    decision = _knowledge_unverifiable_decision()
    decision.modified_args = ["not", "a", "mapping"]
    _mock_gate(monkeypatch, decision)

    with pytest.raises(Pending):
        dispatch_tool("cid_invalid_modify", {"original": True}, SessionContext(trace_id="knowledge-trace"))

    assert calls == []


def test_modify_with_valid_args_executes_exactly_modified_values(monkeypatch):
    original_args = {"recipient_id": "EMP-4410", "doc_id": "DOC-2277", "excerpt": "sensitive"}
    modified_args = {"recipient_id": "EMP-4410", "doc_id": "DOC-2277", "excerpt": "[redacted]"}
    calls = []
    register_tool("cid_valid_modify", lambda **kwargs: calls.append(kwargs) or "sent")
    decision = _knowledge_unverifiable_decision()
    decision.modified_args = modified_args
    _mock_gate(monkeypatch, decision)

    result = dispatch_tool("cid_valid_modify", original_args, SessionContext(trace_id="knowledge-trace"))

    assert result == "sent"
    assert calls == [modified_args]


def test_modify_with_empty_mapping_does_not_reuse_original_args(monkeypatch):
    calls = []
    register_tool("cid_empty_modify", lambda **kwargs: calls.append(kwargs) or "called")
    decision = _knowledge_unverifiable_decision()
    decision.modified_args = {}
    _mock_gate(monkeypatch, decision)

    result = dispatch_tool("cid_empty_modify", {"original": True}, SessionContext(trace_id="knowledge-trace"))

    assert result == "called"
    assert calls == [{}]


def _decision(intervention: Intervention, key: str) -> Decision:
    verdict = Verdict.VERIFIED if intervention is Intervention.ALLOW else Verdict.CONTRADICTED
    return Decision(
        trace_id="trace",
        manifest_id="servicing-v1",
        verdict=verdict,
        intervention=intervention,
        idempotency_key=key,
    )


def test_ordinary_allow_executes_original_args(monkeypatch):
    calls = []
    register_tool("cid_allow", lambda **kwargs: calls.append(kwargs) or "allowed")
    _mock_gate(monkeypatch, _decision(Intervention.ALLOW, "allow-key"))

    result = dispatch_tool("cid_allow", {"original": True}, SessionContext(trace_id="trace"))

    assert result == "allowed"
    assert calls == [{"original": True}]


def test_ordinary_block_never_executes(monkeypatch):
    calls = []
    register_tool("cid_block", lambda **kwargs: calls.append(kwargs) or "unsafe")
    _mock_gate(monkeypatch, _decision(Intervention.BLOCK, "block-key"))

    with pytest.raises(Blocked):
        dispatch_tool("cid_block", {"original": True}, SessionContext(trace_id="trace"))

    assert calls == []


def test_completed_duplicate_replays_without_reexecution(monkeypatch):
    calls = []
    register_tool("cid_once", lambda **kwargs: calls.append(kwargs) or {"call": len(calls)})
    _mock_gate(monkeypatch, _decision(Intervention.ALLOW, "same-key"))
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
        lambda _name, _args, session, *_rest, **_kwargs: (_decision(Intervention.ALLOW, session.trace_id), {}, {}),
    )

    assert dispatch_tool("cid_distinct", {"value": 1}, SessionContext(trace_id="first")) == 1
    assert dispatch_tool("cid_distinct", {"value": 1}, SessionContext(trace_id="second")) == 2
    assert len(calls) == 2


def test_failed_execution_remains_indeterminate(monkeypatch):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("uncertain tool outcome")

    register_tool("cid_failure", fail)
    _mock_gate(monkeypatch, _decision(Intervention.ALLOW, "failed-key"))
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


def test_missing_order_and_null_field_remain_distinct_unverified_evidence(tmp_path, monkeypatch):
    from controlplane.registry import orders

    database = tmp_path / "orders.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE orders (order_id TEXT PRIMARY KEY, delivered_at TEXT)")
        connection.execute("INSERT INTO orders VALUES ('NULL-DATE', NULL)")
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

    with pytest.raises(SourceUnavailable) as caught:
        OrdersResolver().resolve(_order_claim("ORD-1"), SessionContext(trace_id="trace"))

    assert caught.value.source == "orders.db"
    assert caught.value.operation == "connect"
    assert not database.exists()


def test_schema_failure_remains_loud(tmp_path, monkeypatch):
    from controlplane.registry import orders

    database = tmp_path / "malformed-orders.db"
    sqlite3.connect(database).close()
    monkeypatch.setattr(orders, "DB", database)

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        OrdersResolver().resolve(_order_claim("ORD-1"), SessionContext(trace_id="trace"))


def test_ambiguous_current_policy_rows_are_typed(tmp_path, monkeypatch):
    from controlplane.registry import policy

    database = tmp_path / "policy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE clauses (policy_id TEXT, version TEXT, text TEXT, effective_to TEXT)"
        )
        connection.executemany(
            "INSERT INTO clauses VALUES ('refund_window', ?, 'policy', NULL)",
            [("v1",), ("v2",)],
        )
    monkeypatch.setattr(policy, "DB", database)
    claim = Claim(
        id="policy",
        kind=ClaimKind.POLICY_CLAUSE_CURRENT,
        subject="refund_window",
        tier=Tier.C2,
        load_bearing=True,
    )

    with pytest.raises(AmbiguousPolicyState) as caught:
        PolicyResolver().resolve(claim, SessionContext(trace_id="trace"))

    assert caught.value.row_count == 2


@pytest.mark.parametrize(
    ("posture", "expected_intervention"),
    [("open", Intervention.ALLOW), ("closed", Intervention.BLOCK)],
)
def test_gate_honors_configured_source_unavailability_posture(
    posture, expected_intervention, monkeypatch
):
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100)
    manifest = load_manifest("servicing")
    # servicing's risk_tier_default is 2, so active_fail_posture() reads
    # fail_posture["tier_2"] — not a "compensable"/"non_compensable" key.
    manifest["fail_posture"]["tier_2"] = posture
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    monkeypatch.setattr("controlplane.intercept.extract_action", lambda **_kwargs: action)
    monkeypatch.setattr("controlplane.intercept.load_manifest", lambda _name: manifest)
    monkeypatch.setattr(
        "controlplane.intercept.resolve_bindings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SourceUnavailable(source="orders.db", operation="connect")
        ),
    )
    monkeypatch.setattr("controlplane.intercept.record", lambda *_args, **_kwargs: {"receipt": {}})

    decision, _, _ = _run_gate(
        "issue_refund",
        {"order_id": "ORD-1", "amount_paise": 100},
        SessionContext(trace_id="trace"),
        "",
        [],
    )

    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is expected_intervention
    assert decision.root_cause == "authoritative_source_unavailable"
    assert decision.reasons[0].rule == "authoritative_source_available"


def test_gate_blocks_ambiguous_policy_state(monkeypatch):
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100)
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    monkeypatch.setattr("controlplane.intercept.extract_action", lambda **_kwargs: action)
    monkeypatch.setattr(
        "controlplane.intercept.resolve_bindings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AmbiguousPolicyState(
                policy_id="refund_window",
                row_count=2,
                query="SELECT current policy",
            )
        ),
    )
    monkeypatch.setattr("controlplane.intercept.record", lambda *_args, **_kwargs: {"receipt": {}})

    decision, _, _ = _run_gate(
        "issue_refund",
        {"order_id": "ORD-1", "amount_paise": 100},
        SessionContext(trace_id="trace"),
        "",
        [],
    )

    assert decision.verdict is Verdict.SOURCE_UNRELIABLE
    assert decision.intervention is Intervention.BLOCK
    assert decision.root_cause == "ambiguous_current_policy_state"
    assert decision.reasons[0].observed == 2
