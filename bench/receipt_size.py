"""Measure canonical signed receipt sizes using real gate executions."""

from __future__ import annotations

import json
import math
import os
import uuid

from controlplane import intercept
from controlplane.receipt import build_receipt
from controlplane.schema import ProposedAction, SessionContext

CASES = (
    (
        "servicing",
        "issue_refund",
        {"order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR", "item_colour": "blue", "item_category": "shoes"},
    ),
    (
        "knowledge_assistant",
        "send_document",
        {"doc_id": "DOC-2277", "recipient_id": "EMP-4410", "excerpt": "Priya Raghavan delivery dispute"},
    ),
    (
        "discount_approval",
        "approve_discount",
        {"order_id": "ORD-88461", "amount_paise": 800000, "currency": "INR"},
    ),
)

REDUNDANT_FIELD_CANDIDATES = [
    "action.args values repeated by claims[].asserted",
    "predicate outcomes repeated by reasons[].expected/observed and predicate_trace",
    "manifest_id repeated by reasons[].policy_version",
    "identical evidence source/query metadata repeated once per claim",
]


def measure_receipt_sizes(n: int = 120) -> dict:
    if n < 100:
        raise ValueError("receipt-size measurement requires at least 100 receipts")
    captured: list[dict] = []
    original_record = intercept.record
    original_extract_action = intercept.extract_action
    original_manifest = os.environ.get("CP_MANIFEST")
    os.environ.setdefault("CP_RECEIPT_SECRET", "measurement-secret-not-for-production")

    def capture(decision, action_dict, latency_ms):
        receipt = build_receipt(decision, action_dict, latency_ms)
        captured.append(receipt)
        return {"receipt": receipt}

    intercept.record = capture
    intercept.extract_action = lambda **kwargs: ProposedAction(
        tool=kwargs["tool"], **kwargs["tool_call_args"]
    )
    try:
        for i in range(n):
            manifest, tool, args = CASES[i % len(CASES)]
            os.environ["CP_MANIFEST"] = manifest
            intercept._run_gate(
                tool,
                args,
                SessionContext(trace_id=str(uuid.uuid4()), customer_id="CUST-2291", gate_enabled=True),
                "receipt-size measurement",
                [],
            )
    finally:
        intercept.record = original_record
        intercept.extract_action = original_extract_action
        if original_manifest is None:
            os.environ.pop("CP_MANIFEST", None)
        else:
            os.environ["CP_MANIFEST"] = original_manifest

    sizes = sorted(
        len(json.dumps(receipt, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
        for receipt in captured
    )
    median = (sizes[(n - 1) // 2] + sizes[n // 2]) / 2
    result = {
        "n": n,
        "median_bytes": int(median) if median.is_integer() else median,
        "p95_bytes": sizes[math.ceil(0.95 * n) - 1],
        "min_bytes": sizes[0],
        "max_bytes": sizes[-1],
        "method": f"{n} in-memory receipt builds from real resolver/predicate/decision executions rotating all three manifests; structural tool calls bypass only LLM extraction",
        "raw_receipts_persisted": False,
        "evidence_limitation": "aggregate sizes are reproducible, but the individual raw receipt payloads from this measurement were not persisted",
    }
    if result["p95_bytes"] > 2048:
        result["redundant_field_candidates_not_trimmed"] = REDUNDANT_FIELD_CANDIDATES
    return result


__all__ = ["measure_receipt_sizes"]
