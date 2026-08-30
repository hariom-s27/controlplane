from __future__ import annotations

import json

import pytest

import bench.reviewer_console as reviewer_console

from controlplane.compensation import compensation_for
from controlplane.escalation import (
    enqueue_pending,
    escalation_budget_exhausted,
    pending_items,
    record_budget_exhaustion,
    record_review,
)
from controlplane.intercept import Blocked, dispatch_tool, register_tool
from controlplane.schema import Decision, Intervention, SessionContext, Verdict


def _decision(*, compensability: str = "fully") -> Decision:
    return Decision(
        trace_id="trace-escalate",
        manifest_id="servicing-v1",
        verdict=Verdict.UNVERIFIABLE,
        intervention=Intervention.ESCALATE,
        compensation=compensation_for({
            "compensation": {
                "action": "undo" if compensability != "not" else None,
                "compensability": compensability,
            }
        }),
    )


def test_pending_queue_hides_then_records_review(tmp_path):
    path = tmp_path / "pending.jsonl"
    receipt = {"trace_id": "trace-escalate", "verdict": "UNVERIFIABLE", "intervention": "ESCALATE"}
    queued = enqueue_pending(_decision(), receipt, path=path)

    assert pending_items(path=path)[0]["receipt"]["verdict"] == "UNVERIFIABLE"
    reviewed = record_review(queued["queue_id"], "BLOCK", path=path)

    assert pending_items(path=path) == []
    assert reviewed["review"]["agreement"] is True
    assert reviewed["review"]["gate_decision"] == "BLOCK"


def test_escalation_budget_exhausted_after_more_than_two_in_rolling_hundred(tmp_path):
    trail = tmp_path / "decisions.jsonl"
    rows = []
    for i in range(100):
        rows.append({"receipt": {
            "manifest_id": "servicing-v1",
            "intervention": "ESCALATE" if i < 3 else "ALLOW",
        }})
    trail.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    assert escalation_budget_exhausted(
        _decision(), {"escalation_budget_pct": 2}, trail_path=trail
    ) is True


def test_budget_exhausted_uses_open_posture_for_tier_zero(monkeypatch):
    decision = _decision(compensability="fully")
    receipt = {"trace_id": decision.trace_id, "verdict": decision.verdict.value}
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *a, **k: (decision, {}, receipt))
    monkeypatch.setattr("controlplane.intercept.escalation_budget_exhausted", lambda *a, **k: True)
    monkeypatch.setattr("controlplane.intercept._active_manifest", lambda: {
        "risk_tier_default": 0, "fail_posture": {"tier_0": "open"}
    })
    monkeypatch.setattr("controlplane.intercept.record_budget_exhaustion", lambda *a, **k: {})
    register_tool("budget_open", lambda **kwargs: "executed")

    result = dispatch_tool("budget_open", {}, SessionContext(trace_id="t", gate_enabled=True))

    assert result == "executed"


def test_budget_exhausted_uses_closed_posture_for_tier_two(monkeypatch):
    decision = _decision(compensability="not")
    receipt = {"trace_id": decision.trace_id, "verdict": decision.verdict.value}
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *a, **k: (decision, {}, receipt))
    monkeypatch.setattr("controlplane.intercept.escalation_budget_exhausted", lambda *a, **k: True)
    monkeypatch.setattr("controlplane.intercept._active_manifest", lambda: {
        "risk_tier_default": 2, "fail_posture": {"tier_2": "closed"}
    })
    monkeypatch.setattr("controlplane.intercept.record_budget_exhaustion", lambda *a, **k: {})
    register_tool("budget_closed", lambda **kwargs: pytest.fail("held action executed"))

    with pytest.raises(Blocked):
        dispatch_tool("budget_closed", {}, SessionContext(trace_id="t", gate_enabled=True))


def test_escalation_returns_pending_state_and_queues_action(monkeypatch):
    decision = _decision()
    receipt = {"trace_id": decision.trace_id, "verdict": decision.verdict.value}
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *a, **k: (decision, {}, receipt))
    monkeypatch.setattr("controlplane.intercept.escalation_budget_exhausted", lambda *a, **k: False)
    monkeypatch.setattr("controlplane.intercept._active_manifest", lambda: {"fail_posture": {}})
    monkeypatch.setattr("controlplane.intercept.enqueue_pending", lambda *a, **k: {"queue_id": "q-1"})
    register_tool("pending_action", lambda **kwargs: pytest.fail("pending action executed"))

    result = dispatch_tool("pending_action", {}, SessionContext(trace_id="t", gate_enabled=True))

    assert result == {"status": "pending", "queue_id": "q-1", "trace_id": "trace-escalate"}


def _assert_hidden(output: str) -> None:
    assert "UNVERIFIABLE" not in output
    assert "ESCALATE" not in output
    assert "missing_evidence" not in output
    assert "evidence_present" not in output


def test_reviewer_cli_rejects_removed_auto_approve_path(monkeypatch):
    monkeypatch.setattr("sys.argv", ["reviewer_console.py", "--auto-approve"])
    with pytest.raises(SystemExit):
        reviewer_console.main()


def test_integrated_escalation_review_and_budget_exhaustion(monkeypatch, tmp_path, capsys):
    queue = tmp_path / "pending_actions.jsonl"
    trail = tmp_path / "decisions.jsonl"
    decision = _decision()
    receipt = {
        "receipt_id": "receipt-1", "trace_id": decision.trace_id,
        "action": {"tool": "integrated_action", "args": {}},
        "claims": [], "evidence": [], "verdict": "UNVERIFIABLE",
        "intervention": "ESCALATE", "root_cause": "missing_evidence",
        "reasons": [{"rule": "evidence_present", "expected": True, "observed": False}],
    }
    executed = []
    register_tool("integrated_action", lambda **kwargs: executed.append(True))
    monkeypatch.setattr("controlplane.intercept._run_gate", lambda *a, **k: (decision, {}, receipt))
    monkeypatch.setattr("controlplane.intercept._active_manifest", lambda: {
        "risk_tier_default": 2, "fail_posture": {"tier_2": "closed"}})
    monkeypatch.setattr("controlplane.intercept.escalation_budget_exhausted", lambda *a, **k: False)
    monkeypatch.setattr("controlplane.intercept.enqueue_pending",
                        lambda d, r: enqueue_pending(d, r, path=queue))
    pending = dispatch_tool("integrated_action", {}, SessionContext(trace_id="t", gate_enabled=True))
    assert pending["status"] == "pending"
    assert executed == []

    monkeypatch.setattr(reviewer_console, "pending_items", lambda: pending_items(path=queue))
    monkeypatch.setattr(reviewer_console, "record_review",
                        lambda q, d: record_review(q, d, path=queue))
    monkeypatch.setattr(reviewer_console, "OUT", tmp_path / "agreement.json")
    monkeypatch.setattr("builtins.input",
                        lambda prompt: (_assert_hidden(capsys.readouterr().out), "B")[1])
    reviewer_console.run()
    assert "actual verdict     : UNVERIFIABLE" in capsys.readouterr().out
    reviewed = json.loads(queue.read_text(encoding="utf-8"))
    assert reviewed["review"]["decision"] == "BLOCK"
    assert reviewed["review"]["agreement"] is True

    monkeypatch.setattr("controlplane.intercept.escalation_budget_exhausted", lambda *a, **k: True)
    monkeypatch.setattr("controlplane.intercept.record_budget_exhaustion",
                        lambda d, r, **kw: record_budget_exhaustion(d, r, trail_path=trail, **kw))
    with pytest.raises(Blocked):
        dispatch_tool("integrated_action", {}, SessionContext(trace_id="t2", gate_enabled=True))
    assert executed == []
    event = json.loads(trail.read_text(encoding="utf-8"))
    assert event["event"] == "escalation_budget_exhausted"
    assert event["risk_tier"] == 2
    assert event["fail_posture"] == "closed"
    assert event["outcome"] == "blocked"
