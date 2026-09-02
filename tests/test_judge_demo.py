"""PRODUCT-01 — focused tests for the judge-facing demo layer
(scripts/judge_demo.py). This does not re-test controlplane/*; it only
locks in that the demo layer correctly reuses the existing runtime:
dispatch_tool(), decide(), the idempotency ledger and receipt
verification. See tests/test_intercept.py, tests/test_decide.py,
tests/test_receipt.py and tests/test_knowledge_assistant.py for the
underlying runtime's own coverage.
"""

from __future__ import annotations

import pytest

from controlplane.idempotency import reset_execution_ledger
from controlplane.intercept import Blocked, dispatch_tool
from controlplane.schema import SessionContext
from scripts import judge_demo as demo


@pytest.fixture(autouse=True)
def _isolated_ledger():
    reset_execution_ledger()
    demo._call_log.clear()
    yield
    reset_execution_ledger()
    demo._call_log.clear()


def test_demo_initializes():
    assert callable(demo.main)
    assert demo.ENTITLEMENTS_DB.exists(), "run `make db` / `.\\make.ps1 db` before running the demo tests"


def test_eight_scenarios_load_without_changing_existing_indices():
    assert len(demo.SCENARIOS) == 8
    results = [fn() for fn in demo.SCENARIOS]
    assert [r.number for r in results] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_full_catalog_has_no_unavailable_scenarios():
    for fn in demo.SCENARIOS:
        reset_execution_ledger()
        demo._call_log.clear()
        r = fn()
        assert r.available is True, f"scenario {r.number} ({r.key!r}) is unexpectedly NOT_AVAILABLE"


def test_allow_scenario_works():
    r = demo.scenario_1_allow()
    assert r.evidence_source == "RUNTIME"
    assert r.verdict == "VERIFIED"
    assert r.intervention == "ALLOW"
    assert r.execution_status == "EXECUTED"
    assert r.call_count == "1"
    assert r.receipt_verified is True


def test_source_unreliable_scenario_works():
    r = demo.scenario_2_source_unreliable()
    assert r.evidence_source == "FIXTURE"
    assert r.verdict == "SOURCE_UNRELIABLE"
    assert r.call_count == "0"
    assert r.receipt_verified is True


def test_contradiction_scenario_works():
    r = demo.scenario_3_contradiction()
    assert r.evidence_source == "RUNTIME"
    assert r.verdict == "CONTRADICTED"
    assert r.intervention == "BLOCK"
    assert r.execution_status == "BLOCKED"
    assert r.call_count == "0"
    assert r.receipt_verified is True


def test_invalid_modify_prevents_execution_with_zero_calls():
    r = demo.scenario_4_invalid_modify()
    assert r.verdict == "UNVERIFIABLE"
    assert r.intervention == "MODIFY"
    assert r.call_count == "0"
    assert "not executed" in r.execution_result
    assert r.receipt_verified is True


def test_unsafe_modify_prevents_execution_with_zero_calls():
    r = demo.scenario_5_unsafe_modify()
    assert r.available is True
    assert r.verdict == "UNVERIFIABLE"
    assert r.intervention == "MODIFY"
    assert r.call_count == "0"
    assert "not executed" in r.execution_result
    assert r.receipt_verified is True


def test_duplicate_replay_executes_only_once():
    r = demo.scenario_6_duplicate_replay()
    assert r.verdict == "VERIFIED"
    assert r.intervention == "ALLOW"
    assert r.call_count == "1"
    assert "executed=True" in r.execution_status
    assert "executed=False" in r.execution_status


def test_customer_support_stale_policy_refund_blocks_without_calling_implementation():
    r = demo.scenario_7_stale_policy_refund()
    trace = r.receipt["predicate_trace"]

    assert r.number == 7
    assert r.key == "stale_policy_refund"
    assert r.title == "₹42,999 STALE-POLICY REFUND"
    assert r.evidence_source == "RUNTIME"
    assert trace["days_elapsed"] == 26
    assert trace["within_window"] is False
    assert trace["within_authority"] is False
    assert r.verdict == "CONTRADICTED"
    assert r.intervention == "BLOCK"
    assert r.execution_status == "BLOCKED"
    assert r.call_count == "0"
    assert demo._call_log == []
    assert r.receipt_verified is True


def test_customer_support_allow_control_executes_once():
    r = demo.scenario_8_servicing_allow()
    trace = r.receipt["predicate_trace"]

    assert r.number == 8
    assert r.key == "servicing_allow"
    assert r.receipt["action"]["args"]["order_id"] == "ORD-90233"
    assert trace["days_elapsed"] == 3
    assert trace["within_window"] is True
    assert trace["within_authority"] is True
    assert r.verdict == "VERIFIED"
    assert r.intervention == "ALLOW"
    assert r.execution_status == "EXECUTED"
    assert r.call_count == "1"
    assert len(demo._call_log) == 1
    assert r.receipt_verified is True


def test_receipt_verification_succeeds_and_detects_tampering():
    r = demo.scenario_1_allow()
    assert demo.verify_receipt(r.receipt) is True

    tampered = dict(r.receipt)
    tampered["verdict"] = "CONTRADICTED"
    assert demo.verify_receipt(tampered) is False


def test_reset_restores_deterministic_state(tmp_path, monkeypatch):
    monkeypatch.setattr("controlplane.receipt.OPERATIONAL_TRAIL", tmp_path / "decisions.jsonl")
    monkeypatch.setattr("controlplane.receipt.PRIVILEGED_TRAIL", tmp_path / "decisions_privileged.jsonl")

    first = demo.scenario_1_allow()
    demo.reset_demo()
    second = demo.scenario_1_allow()

    assert first.verdict == second.verdict
    assert first.intervention == second.intervention
    assert first.receipt["idempotency_key"] == second.receipt["idempotency_key"]
    assert first.call_count == second.call_count == "1"


def test_scenarios_are_isolated_from_each_other():
    """Running the ALLOW scenario twice back to back (as two independent,
    isolated scenario invocations, the way the demo runs them) must show a
    real execution each time, not a cross-scenario idempotency replay."""
    first = demo.scenario_1_allow()
    second = demo.scenario_1_allow()

    assert first.execution_status == "EXECUTED"
    assert second.execution_status == "EXECUTED"
    assert first.call_count == "1"
    assert second.call_count == "1"


def test_unexpected_exceptions_are_not_swallowed():
    with pytest.raises(KeyError):
        dispatch_tool("does_not_exist_at_all", {}, SessionContext(trace_id="t-demo-unregistered", gate_enabled=False))
