"""P3-A — the extraction-failure fallback must not be silent.

`controlplane/extract.py::extract_action` falls back to all-None
`_ClaimedFields` when the provider / schema retry loop gives up. That is the
safe direction (all-None routes to UNVERIFIABLE downstream) but
`docs/threat-model.md` T32 notes it is indistinguishable from "the agent
asserted nothing". P3-A adds one structured event on the
`controlplane.data_quality` logger. This suite proves the event fires, the
fallback is unchanged, and a failed extraction still cannot come out
VERIFIED.
"""

from __future__ import annotations

import json
import logging
import os

# Same pattern as tests/test_product_views.py — extract_action reads CP_MODEL
# unconditionally (it is part of the fixture cache key); the replay test below
# needs it to match the committed fixtures. setdefault so a real env wins.
os.environ.setdefault("CP_MODEL", "Qwen/Qwen3-8B")
os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")

import controlplane.extract as extract  # noqa: E402
from controlplane.decide import decide  # noqa: E402
from controlplane.ladder import classify_claims  # noqa: E402
from controlplane.manifest import load_manifest  # noqa: E402
from controlplane.schema import Verdict  # noqa: E402

_ARGS = {"order_id": "ORD-88461", "amount_paise": 4299900, "currency": "INR"}


def _force_failure(monkeypatch, tmp_path):
    """Point fixtures at a tmp dir, go down the live path, make the provider
    call raise. The model name is irrelevant here — the unique justification
    guarantees a cache miss."""
    monkeypatch.setattr(extract, "FIXTURES", tmp_path)
    monkeypatch.setenv("CP_MODE", "live")

    def _boom(*_a, **_k):
        raise RuntimeError("provider 500 / schema not held after retries")

    monkeypatch.setattr(extract, "call_with_key_fallback", _boom)


def _failure_events(caplog) -> list[dict]:
    out = []
    for rec in caplog.records:
        if rec.name == "controlplane.data_quality" and rec.getMessage().startswith("extraction_failure "):
            out.append(json.loads(rec.getMessage().split(" ", 1)[1]))
    return out


def test_extraction_failure_emits_one_structured_data_quality_event(monkeypatch, tmp_path, caplog):
    _force_failure(monkeypatch, tmp_path)
    caplog.set_level(logging.WARNING, logger="controlplane.data_quality")

    extract.extract_action(
        tool="issue_refund",
        tool_call_args=_ARGS,
        justification="p3a-nonce-force-a-cache-miss-and-a-provider-failure",
        retrieved_chunks=[],
    )

    events = _failure_events(caplog)
    assert len(events) == 1
    ev = events[0]
    assert ev["event"] == "extraction_failure"
    assert ev["stage"] == "extract"
    assert ev["tool"] == "issue_refund"
    assert ev["error_type"] == "RuntimeError"
    assert ev["fallback"] == "all_none_claimed_fields"
    assert isinstance(ev["cache_key"], str) and ev["cache_key"]


def test_extraction_failure_preserves_the_all_none_fallback(monkeypatch, tmp_path, caplog):
    _force_failure(monkeypatch, tmp_path)
    caplog.set_level(logging.WARNING, logger="controlplane.data_quality")

    action = extract.extract_action(
        tool="issue_refund",
        tool_call_args=_ARGS,
        justification="p3a-nonce-2-provider-failure",
        retrieved_chunks=["Refunds within 7 days of delivery."],
    )

    # structural fields still come straight from the tool call
    assert action.order_id == "ORD-88461"
    assert action.amount_paise == 4299900
    # every claimed_* field is None — unchanged fallback behaviour
    assert action.claimed_delivered_at is None
    assert action.claimed_policy_version is None
    assert action.claimed_clause_text is None
    assert action.claimed_reasoning is None


def test_a_failed_extraction_cannot_come_out_verified(monkeypatch, tmp_path, caplog):
    _force_failure(monkeypatch, tmp_path)
    caplog.set_level(logging.WARNING, logger="controlplane.data_quality")

    action = extract.extract_action(
        tool="issue_refund",
        tool_call_args=_ARGS,
        justification="p3a-nonce-3-provider-failure",
        retrieved_chunks=[],
    )
    manifest = load_manifest("servicing")
    claims = classify_claims(extract.build_claims(action, manifest))
    # no evidence resolved, no predicate flags — the honest picture after an
    # extraction failure with nothing to check against.
    d = decide("t-p3a", manifest["manifest_id"], action, claims, [], {}, manifest)

    assert d.verdict is not Verdict.VERIFIED
    cov = d.verification_ledger.coverage
    assert cov.value in (None, 0.0)  # never inflated to 1.0 by a silent failure


def test_successful_replayed_extraction_emits_no_failure_event(caplog):
    """The committed-fixture replay path (the default for the test suite) must
    stay quiet — the event is for real failures only."""
    caplog.set_level(logging.WARNING, logger="controlplane.data_quality")
    action = extract.extract_action(
        tool="issue_refund",
        tool_call_args=_ARGS,
        justification=(
            "The customer's order ORD-88461 was delivered on 2026-07-19. "
            "Per the current returns policy, this is within the refund "
            "window, so I'm issuing a full refund."
        ),
        retrieved_chunks=[
            "Refunds and returns. Customers may request a full refund "
            "within 7 days of the delivery date."
        ],
    )
    assert action.claimed_delivered_at is not None  # the fixture really replayed
    assert _failure_events(caplog) == []
