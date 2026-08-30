"""S11 checkpoint. Every line written must parse as JSON with all four
measurement blocks present, even when one of them is an honest stub.
"""

from __future__ import annotations

import json
import os

from controlplane.compensation import compensation_for
from controlplane.receipt import OPERATIONAL_TRAIL
from controlplane.registry.clock import now
from controlplane.schema import Claim, ClaimKind, Confidence, Decision, Evidence, Intervention, Reliability, Tier, Verdict
from controlplane.telemetry import record

_COMPENSABLE = {"compensation": {"action": "reverse_refund", "compensability": "fully"}}

os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")


def _decision() -> Decision:
    claim = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1", tier=Tier.C2, load_bearing=True)
    ev = [Evidence(
        claim_id="c1", value="2026-08-11", source="orders.db", query="...",
        fetched_at=now(), reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
    )]
    return Decision(
        trace_id="t1", manifest_id="servicing-v1", verdict=Verdict.VERIFIED, intervention=Intervention.ALLOW,
        claims=[claim], evidence=ev, predicate_trace={"within_window": True},
        compensation=compensation_for(_COMPENSABLE), idempotency_key="k1",
    )


def test_record_writes_a_line_with_all_four_blocks(tmp_path, monkeypatch):
    log = tmp_path / "decisions.jsonl"
    monkeypatch.setattr("controlplane.receipt.OPERATIONAL_TRAIL", log)

    action_dict = {"tool": "issue_refund", "order_id": "ORD-1", "amount_paise": 100000, "currency": "INR"}
    line = record(_decision(), action_dict, latency_ms={"extract": 10.0, "resolve": 2.0, "predicate": 0.5, "decide": 0.1})

    assert log.exists()
    parsed = json.loads(log.read_text().splitlines()[0])
    assert parsed == line
    telem = parsed["telemetry"]
    for key in ("coverage", "extraction_accuracy", "latency", "rule_promotion_cost"):
        assert key in telem


def test_twenty_decisions_produce_twenty_valid_lines(tmp_path, monkeypatch):
    log = tmp_path / "decisions.jsonl"
    monkeypatch.setattr("controlplane.receipt.OPERATIONAL_TRAIL", log)
    action_dict = {"tool": "issue_refund", "order_id": "ORD-1", "amount_paise": 100000, "currency": "INR"}

    for _ in range(20):
        record(_decision(), action_dict, latency_ms={"predicate": 0.5, "decide": 0.1})

    lines = log.read_text().splitlines()
    assert len(lines) == 20
    for raw in lines:
        json.loads(raw)  # every line parses
