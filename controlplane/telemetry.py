"""S11 — the four loggers, called from dispatch_tool: the single choke
point every governed decision passes through, which is exactly why it's
the right instrumentation point. One append-only writer; every line is
{"receipt": {...signed S10 receipt...}, "telemetry": {four blocks}}.

Logger 2 (extraction accuracy under noise, the SEB-1 sweep) is honestly
stubbed: SEB-1's harness (bench/seb1_v2_recoverability.py,
servicing_extraction_bench.py) lives in phase 1's scratch folders and has
not been ported into this repo. Reporting a number for it here would be
exactly the kind of invented figure CLAUDE.md's own hard constraints rule
out — it's `not_measured`, not a guess.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from controlplane.receipt import OPERATIONAL_TRAIL, build_receipt, persist
from controlplane.schema import Decision

_TIER_KEYS = ("C1", "C2", "C3", "C4", "C5")


def _coverage_block(decision: Decision) -> dict:
    # Per-tier counts only. No coverage_ratio: it was deterministically 1.0
    # for every decision the system can produce (see schema.Decision.coverage
    # and docs/experiment-audit.md).
    cov = decision.coverage
    by_tier = {t: cov["by_tier"].get(t, 0) for t in _TIER_KEYS}
    block = {
        "claims_total": cov["claims_total"],
        **{f"{t.lower()}_n": n for t, n in by_tier.items()},
        "unverifiable_n": by_tier["C4"] + by_tier["C5"],
    }
    c3 = decision.component_status.get("C3", {})
    if isinstance(c3, dict) and c3.get("status") == "unavailable":
        block["c3_available_n"] = 0
        block["c3_unavailable_n"] = by_tier["C3"]
    return block


def _extraction_accuracy_block() -> dict:
    return {
        "status": "not_measured",
        "note": "SEB-1 sweep (S16) not yet ported into this repo — see phase 1/ for the harness",
    }


def _latency_block(latency_ms: dict[str, float]) -> dict:
    """Per-decision raw stage timings. p50/p95/p99 need many decisions —
    use latency_percentiles() below once decisions.jsonl has enough lines."""
    return dict(latency_ms)


def _promotion_cost_block(latency_ms: dict[str, float]) -> dict:
    ground_ms = latency_ms.get("ground")
    predicate_ms = latency_ms.get("predicate")
    if ground_ms is None or not predicate_ms:
        return {"status": "not_measured", "note": "no grounding (C3) ran on this decision"}
    return {"ground_ms": ground_ms, "predicate_ms": predicate_ms, "ratio": round(ground_ms / predicate_ms, 1)}


def record(decision: Decision, action_dict: dict[str, Any], latency_ms: dict[str, float]) -> dict:
    receipt = build_receipt(decision, action_dict, latency_ms)
    telemetry = {
        "coverage": _coverage_block(decision),
        "extraction_accuracy": _extraction_accuracy_block(),
        "latency": _latency_block(latency_ms),
        "rule_promotion_cost": _promotion_cost_block(latency_ms),
    }
    data_quality = decision.component_status.get("data_quality")
    if isinstance(data_quality, dict):
        telemetry["data_quality"] = data_quality

    line = {
        "receipt": receipt,
        "telemetry": telemetry,
    }
    persist(line)
    return line


def latency_percentiles(stage: str, path: Path = OPERATIONAL_TRAIL) -> dict[str, float] | None:
    """Aggregates across every line in decisions.jsonl. Needs multiple
    decisions logged first — the roadmap's own verify step for this logger
    is "run the demo 20 times", not a single call."""
    samples = []
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = json.loads(raw_line)
        ms = line.get("telemetry", {}).get("latency", {}).get(stage)
        if ms is not None:
            samples.append(ms)
    if not samples:
        return None
    samples.sort()

    def pct(p: float) -> float:
        idx = min(len(samples) - 1, int(round(p * (len(samples) - 1))))
        return samples[idx]

    return {"p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99), "n": len(samples), "mean": statistics.mean(samples)}


__all__ = ["record", "latency_percentiles"]
