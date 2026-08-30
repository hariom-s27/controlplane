"""P08 regression tests for robustness and failure injection.

All mutable stores are temporary copies.  These tests deliberately exercise
the runtime boundary rather than the frozen P03/P04/P05 benchmark artifacts.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

import pytest

import controlplane.escalation as escalation_module
import controlplane.ground as ground_module
import controlplane.intercept as intercept
import controlplane.receipt as receipt_module
import controlplane.registry.entitlements as entitlements_registry
import controlplane.registry.orders as orders_registry
import controlplane.registry.policy as policy_registry
import controlplane.telemetry as telemetry_module
from controlplane.errors import AmbiguousPolicyState, SourceUnavailable
from controlplane.idempotency import reset_execution_ledger
from controlplane.manifest import load_manifest
from controlplane.receipt import verify
from controlplane.registry.entitlements import EntitlementsResolver
from controlplane.registry.orders import OrdersResolver
from controlplane.registry.policy import PolicyResolver
from controlplane.schema import (
    Claim,
    ClaimKind,
    Confidence,
    Intervention,
    ProposedAction,
    Reliability,
    SessionContext,
    Verdict,
)


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CURRENT_CLAUSE = (
    "Customers may request a full refund within 7 days of the delivery date. "
    "Requests made after 7 days may be eligible for store credit at the "
    "discretion of a supervisor. Refunds are issued to the original payment "
    "method within 5-7 business days of approval."
)


@pytest.fixture(autouse=True)
def _clean_execution_ledger():
    reset_execution_ledger()
    yield
    reset_execution_ledger()


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect every P08 write to the test's temporary directory."""
    trail = tmp_path / "decisions.jsonl"
    pending = tmp_path / "pending_actions.jsonl"

    monkeypatch.setenv("CP_RECEIPT_SECRET", "p08-test-secret")
    monkeypatch.setenv("CP_GROUNDING", "off")
    monkeypatch.setattr(receipt_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(telemetry_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(escalation_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(escalation_module, "PENDING_QUEUE", pending)

    return {"trail": trail, "pending": pending, "root": tmp_path}


def _copy_store(tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    shutil.copy2(DATA / name, target)
    return target


def _servicing_action() -> ProposedAction:
    return ProposedAction(
        tool="issue_refund",
        order_id="ORD-90233",
        amount_paise=849900,
        currency="INR",
        item_colour="grey",
        item_category="shirt",
        claimed_delivered_at="2026-08-11",
        claimed_policy_version="v4.2",
        claimed_clause_text=CURRENT_CLAUSE,
        claimed_reasoning="Current record and policy support the refund.",
    )


def _knowledge_action() -> ProposedAction:
    return ProposedAction(
        tool="send_document",
        doc_id="DOC-2277",
        recipient_id="EMP-4410",
        excerpt="Requested support document.",
        claimed_reasoning="Send the requested document.",
    )


def _args(action: ProposedAction) -> dict:
    return {
        k: v
        for k, v in action.facts_for_predicate().items()
        if k != "tool" and v is not None
    }


def _fixed_extractor(action: ProposedAction, after_extract: Callable[[], None] | None = None):
    def extract_action(**_kwargs):
        if after_extract is not None:
            after_extract()
        return action

    return extract_action


def _take_store_offline(path: Path) -> None:
    """Replace a live SQLite file with a directory after extraction.

    Connecting to a missing SQLite path would create a fresh empty database;
    using a directory forces a genuine ``unable to open database file`` error.
    """
    if path.is_file():
        path.replace(path.with_suffix(path.suffix + ".offline"))
        path.mkdir()


def _read_entries(path: Path) -> list[dict]:
    assert path.exists(), "the failure path produced no operational receipt"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _receipt_from(entry: dict) -> dict:
    return entry.get("receipt", entry)


def _latest_envelope(path: Path) -> dict:
    entries = _read_entries(path)
    for entry in reversed(entries):
        if "receipt" in entry:
            return entry
    raise AssertionError("operational trail contains no receipt envelope")


def _assert_signed(receipt: dict) -> None:
    assert receipt.get("sig", "").startswith("hmac-sha256:")
    assert verify(receipt) is True


def _assert_failure_context(
    receipt: dict,
    *,
    kind: str,
    stage: str,
    source: str,
    risk_tier: int,
    fail_posture: str,
    posture_outcome: str,
) -> None:
    assert receipt["verification_state"] == "unverified"
    context = receipt["failure_context"]
    assert context["kind"] == kind
    assert context["stage"] == stage
    assert context["source"] == source
    assert context["risk_tier"] == risk_tier
    assert context["fail_posture"] == fail_posture
    assert context["posture_outcome"] == posture_outcome
    assert context["detail"]


# ---------------------------------------------------------------------------
# Scenario 2: record unavailable, both configured manifests
# ---------------------------------------------------------------------------


def test_p08_record_unavailable_servicing_honours_closed_posture(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    orders_db = _copy_store(isolated_runtime["root"], "orders.db")
    monkeypatch.setattr(orders_registry, "DB", orders_db)
    monkeypatch.setenv("CP_MANIFEST", "servicing")

    action = _servicing_action()
    monkeypatch.setattr(
        intercept,
        "extract_action",
        _fixed_extractor(action, lambda: _take_store_offline(orders_db)),
    )
    executions: list[dict] = []
    monkeypatch.setitem(
        intercept.REGISTRY,
        "issue_refund",
        lambda **kwargs: executions.append(kwargs) or {"executed": True},
    )

    with pytest.raises(intercept.Blocked):
        intercept.dispatch_tool(
            "issue_refund",
            _args(action),
            SessionContext(trace_id="p08-unavailable-servicing", customer_id="CUST-2291"),
        )

    assert executions == []
    receipt = _receipt_from(_latest_envelope(isolated_runtime["trail"]))
    _assert_signed(receipt)
    _assert_failure_context(
        receipt,
        kind="source_unavailable",
        stage="resolve",
        source="orders.db",
        risk_tier=2,
        fail_posture="closed",
        posture_outcome="blocked",
    )
    assert receipt["action"]["compensability"] == "fully"

    claim = Claim(
        id="ORD-90233:owner",
        kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER,
        subject="ORD-90233",
    )
    with pytest.raises(SourceUnavailable):
        OrdersResolver().resolve(claim, SessionContext(trace_id="p08-source-type"))


def test_p08_record_unavailable_knowledge_honours_open_posture_and_marks_unverified(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    entitlements_db = _copy_store(isolated_runtime["root"], "entitlements.db")
    monkeypatch.setattr(entitlements_registry, "DB", entitlements_db)
    monkeypatch.setenv("CP_MANIFEST", "knowledge_assistant")

    action = _knowledge_action()
    monkeypatch.setattr(
        intercept,
        "extract_action",
        _fixed_extractor(action, lambda: _take_store_offline(entitlements_db)),
    )
    executions: list[dict] = []
    monkeypatch.setitem(
        intercept.REGISTRY,
        "send_document",
        lambda **kwargs: executions.append(kwargs) or {"executed": True},
    )

    result = intercept.dispatch_tool(
        "send_document",
        _args(action),
        SessionContext(
            trace_id="p08-unavailable-knowledge",
            subject_id="EMP-4410",
            use_case="knowledge_assistant",
        ),
    )

    assert result == {"executed": True}
    assert executions == [_args(action)]
    receipt = _receipt_from(_latest_envelope(isolated_runtime["trail"]))
    _assert_signed(receipt)
    _assert_failure_context(
        receipt,
        kind="source_unavailable",
        stage="resolve",
        source="entitlements.db",
        risk_tier=0,
        fail_posture="open",
        posture_outcome="executed",
    )
    assert receipt["action"]["compensability"] == "partially"

    claim = Claim(
        id="DOC-2277:classification",
        kind=ClaimKind.DOC_CLASSIFICATION_PERMITTED,
        subject="DOC-2277",
    )
    with pytest.raises(SourceUnavailable):
        EntitlementsResolver().resolve(
            claim,
            SessionContext(trace_id="p08-source-type", subject_id="EMP-4410"),
        )


# ---------------------------------------------------------------------------
# Scenario 3: NULL load-bearing field
# ---------------------------------------------------------------------------


def test_p08_null_delivered_at_is_source_unreliable_not_an_exception(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    orders_db = _copy_store(isolated_runtime["root"], "orders.db")
    with sqlite3.connect(orders_db) as conn:
        conn.execute("UPDATE orders SET delivered_at = NULL WHERE order_id = ?", ("ORD-90233",))
        conn.commit()

    monkeypatch.setattr(orders_registry, "DB", orders_db)
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    action = _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))

    decision, _latency, receipt = intercept._run_gate(
        "issue_refund",
        _args(action),
        SessionContext(trace_id="p08-null-delivered", customer_id="CUST-2291"),
        "",
        [],
    )

    assert decision.verdict is Verdict.SOURCE_UNRELIABLE
    assert decision.intervention is Intervention.ESCALATE
    assert receipt["verification_state"] == "unverified"
    assert receipt["root_cause"] == "evidence_below_reliability_floor"
    resolved = next(e for e in receipt["evidence"] if "delivered_at" in e["query"])
    assert resolved["value"] is None
    assert resolved["confidence"] == Confidence.NONE.value
    assert resolved["reliability_class"] == Reliability.UNVERIFIED.value
    _assert_signed(receipt)


# ---------------------------------------------------------------------------
# Scenario 4: inferred order status on a high-severity/load-bearing claim
# ---------------------------------------------------------------------------


def test_p08_inferred_order_status_high_severity_is_source_unreliable_then_escalates(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    orders_db = _copy_store(isolated_runtime["root"], "orders.db")
    monkeypatch.setattr(orders_registry, "DB", orders_db)
    action = _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))

    manifest = load_manifest("servicing")
    manifest["claim_bindings"] = [
        *manifest["claim_bindings"],
        {
            "claim_kind": "ORDER_STATUS_SUPPORTS_ACTION",
            "resolver": "orders",
            "subject": "action.order_id",
            "predicate_key": None,
        },
    ]
    monkeypatch.setattr(intercept, "_active_manifest", lambda: manifest)

    decision, _latency, receipt = intercept._run_gate(
        "issue_refund",
        _args(action),
        SessionContext(trace_id="p08-inferred-status", customer_id="CUST-2291"),
        "",
        [],
    )

    status_claim = next(c for c in decision.claims if c.kind is ClaimKind.ORDER_STATUS_SUPPORTS_ACTION)
    status_evidence = next(e for e in decision.evidence if e.claim_id == status_claim.id)
    assert status_claim.load_bearing is True
    assert status_evidence.value == "delivered"
    assert "order_status" in status_evidence.query
    assert status_evidence.reliability_class is Reliability.INFERRED
    assert decision.verdict is Verdict.SOURCE_UNRELIABLE
    assert decision.intervention is Intervention.ESCALATE
    assert receipt["verification_state"] == "unverified"
    assert receipt["root_cause"] == "evidence_below_reliability_floor"
    _assert_signed(receipt)


# ---------------------------------------------------------------------------
# Scenario 5: ambiguous current policy state
# ---------------------------------------------------------------------------


def test_p08_two_current_policy_rows_fail_closed_and_log_data_quality(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    policy_db = _copy_store(isolated_runtime["root"], "policy_store.db")
    with sqlite3.connect(policy_db) as conn:
        conn.execute(
            """
            INSERT INTO clauses (
                clause_id, policy_id, version, title, text, window_days,
                effective_from, effective_to, superseded_by
            )
            SELECT ?, policy_id, ?, title, text, window_days,
                   effective_from, NULL, NULL
            FROM clauses
            WHERE policy_id = ? AND effective_to IS NULL
            """,
            ("refund-window-v4.2-p08-duplicate", "v4.2-p08-duplicate", "refund_window"),
        )
        conn.commit()

    monkeypatch.setattr(policy_registry, "DB", policy_db)
    monkeypatch.setenv("CP_MANIFEST", "servicing")

    policy_claim = Claim(
        id="refund_window:current",
        kind=ClaimKind.POLICY_CLAUSE_CURRENT,
        subject="refund_window",
    )
    with pytest.raises(AmbiguousPolicyState):
        PolicyResolver().resolve(policy_claim, SessionContext(trace_id="p08-ambiguous-type"))

    action = _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))
    executions: list[dict] = []
    monkeypatch.setitem(
        intercept.REGISTRY,
        "issue_refund",
        lambda **kwargs: executions.append(kwargs) or {"executed": True},
    )

    with pytest.raises(intercept.Blocked):
        intercept.dispatch_tool(
            "issue_refund",
            _args(action),
            SessionContext(trace_id="p08-ambiguous-policy", customer_id="CUST-2291"),
        )

    assert executions == []
    envelope = _latest_envelope(isolated_runtime["trail"])
    receipt = envelope["receipt"]
    _assert_signed(receipt)
    _assert_failure_context(
        receipt,
        kind="ambiguous_policy_state",
        stage="resolve",
        source="policy_store.db",
        risk_tier=2,
        fail_posture="closed",
        posture_outcome="blocked",
    )
    data_quality = envelope["telemetry"]["data_quality"]
    assert data_quality["status"] == "detected"
    assert data_quality["policy_id"] == "refund_window"
    assert data_quality["current_row_count"] == 2


# ---------------------------------------------------------------------------
# Scenario 6: optional grounding timeout
# ---------------------------------------------------------------------------


def test_p08_grounding_timeout_degrades_to_c1_c2_and_marks_c3_unavailable(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    orders_db = _copy_store(isolated_runtime["root"], "orders.db")
    policy_db = _copy_store(isolated_runtime["root"], "policy_store.db")
    monkeypatch.setattr(orders_registry, "DB", orders_db)
    monkeypatch.setattr(policy_registry, "DB", policy_db)
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    monkeypatch.setenv("CP_GROUNDING", "on")

    action = _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))
    monkeypatch.setattr(
        ground_module,
        "score",
        lambda **_kwargs: (_ for _ in ()).throw(TimeoutError("P08 injected HHEM timeout")),
    )

    decision, _latency, receipt = intercept._run_gate(
        "issue_refund",
        _args(action),
        SessionContext(trace_id="p08-ground-timeout", customer_id="CUST-2291"),
        "",
        [],
    )

    assert decision.verdict is Verdict.VERIFIED
    assert decision.intervention is Intervention.ALLOW
    assert decision.predicate_trace["grounding_score"] is None
    assert decision.component_status["C3"] == {"status": "unavailable", "reason": "timeout"}
    assert receipt["component_status"]["C3"] == {"status": "unavailable", "reason": "timeout"}
    _assert_signed(receipt)


def test_p08_grounding_non_timeout_errors_remain_loud(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    orders_db = _copy_store(isolated_runtime["root"], "orders.db")
    policy_db = _copy_store(isolated_runtime["root"], "policy_store.db")
    monkeypatch.setattr(orders_registry, "DB", orders_db)
    monkeypatch.setattr(policy_registry, "DB", policy_db)
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    monkeypatch.setenv("CP_GROUNDING", "on")

    action = _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))
    monkeypatch.setattr(
        ground_module,
        "score",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("not a timeout")),
    )

    with pytest.raises(ValueError, match="not a timeout"):
        intercept._run_gate(
            "issue_refund",
            _args(action),
            SessionContext(trace_id="p08-ground-non-timeout", customer_id="CUST-2291"),
            "",
            [],
        )


# ---------------------------------------------------------------------------
# Scenario 7: persisted receipt tampering
# ---------------------------------------------------------------------------


def test_p08_tampered_persisted_receipt_fails_signature_validation(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    orders_db = _copy_store(isolated_runtime["root"], "orders.db")
    policy_db = _copy_store(isolated_runtime["root"], "policy_store.db")
    monkeypatch.setattr(orders_registry, "DB", orders_db)
    monkeypatch.setattr(policy_registry, "DB", policy_db)
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    action = _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))

    intercept._run_gate(
        "issue_refund",
        _args(action),
        SessionContext(trace_id="p08-persisted-tamper", customer_id="CUST-2291"),
        "",
        [],
    )

    entries = _read_entries(isolated_runtime["trail"])
    assert len(entries) == 1
    original = entries[0]["receipt"]
    _assert_signed(original)

    entries[0]["receipt"]["verdict"] = Verdict.CONTRADICTED.value
    isolated_runtime["trail"].write_text(
        json.dumps(entries[0], sort_keys=True) + "\n",
        encoding="utf-8",
    )

    persisted_tamper = _read_entries(isolated_runtime["trail"])[0]["receipt"]
    assert persisted_tamper["verdict"] == Verdict.CONTRADICTED.value
    assert verify(persisted_tamper) is False


# ---------------------------------------------------------------------------
# Scenario 8: retry after gate timeout
# ---------------------------------------------------------------------------


def test_p08_retry_after_timeout_with_same_idempotency_key_executes_once(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    entitlements_db = _copy_store(isolated_runtime["root"], "entitlements.db")
    monkeypatch.setattr(entitlements_registry, "DB", entitlements_db)
    monkeypatch.setenv("CP_MANIFEST", "knowledge_assistant")

    executions: list[dict] = []
    monkeypatch.setitem(
        intercept.REGISTRY,
        "send_document",
        lambda **kwargs: executions.append(kwargs) or {"executed": True, "sequence": len(executions)},
    )
    action = _knowledge_action().model_copy(update={"doc_id": "DOC-1042", "excerpt": "Refund policy FAQ."})
    monkeypatch.setattr(intercept, "extract_action", _fixed_extractor(action))
    session = SessionContext(
        trace_id="p08-timeout-retry",
        subject_id="EMP-4410",
        use_case="knowledge_assistant",
    )
    key = "p08-caller-supplied-idempotency-key"

    # The first governed execution commits, but its response is lost to the
    # caller.  This is the only timeout placement that can prove at-most-once
    # behavior; timing out before execution and then succeeding once cannot.
    with pytest.raises(TimeoutError, match="lost after committed execution"):
        first = intercept.dispatch_tool(
            "send_document", _args(action), session, idempotency_key=key
        )
        raise TimeoutError("P08 caller timeout: response lost after committed execution")
    second = intercept.dispatch_tool(
        "send_document", _args(action), session, idempotency_key=key
    )

    assert first == {"executed": True, "sequence": 1}
    assert second == first
    assert executions == [_args(action)]

    receipts = [_receipt_from(entry) for entry in _read_entries(isolated_runtime["trail"]) if "receipt" in entry]
    assert len(receipts) == 3  # first decision, retry decision, signed replay event
    assert all(r["idempotency_key"] == key for r in receipts)
    assert all(verify(r) for r in receipts)
    replay = receipts[-1]
    assert replay["failure_context"]["kind"] == "idempotent_replay"
    assert replay["failure_context"]["stage"] == "execute"
    assert replay["failure_context"]["posture_outcome"] == "replay"
    assert replay["component_status"]["execution"] == {
        "status": "duplicate_suppressed",
        "reason": "completed_result_replayed",
    }


def test_p08_dispatch_does_not_swallow_unclassified_non_timeout_errors(
    isolated_runtime, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CP_MANIFEST", "knowledge_assistant")
    monkeypatch.setattr(
        intercept,
        "_run_gate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("unclassified gate bug")),
    )
    executions: list[dict] = []
    monkeypatch.setitem(
        intercept.REGISTRY,
        "send_document",
        lambda **kwargs: executions.append(kwargs) or {"executed": True},
    )

    with pytest.raises(ValueError, match="unclassified gate bug"):
        intercept.dispatch_tool(
            "send_document",
            _args(_knowledge_action()),
            SessionContext(trace_id="p08-loud-error", subject_id="EMP-4410"),
            idempotency_key="p08-loud-error-key",
        )

    assert executions == []
