"""P02 — the payoff. A third use case (goodwill discount / store-credit
approval) added with ZERO changes to anything under controlplane/.

It reuses the `orders` resolver and existing ClaimKinds; the only new
artifacts are manifests/discount_approval.yaml, its predicate graph, and a
demo agent. This file proves it runs through the real gate, and
test_engine_is_use_case_agnostic.py proves controlplane/ carries no string
that names it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.discount_agent import _approve_discount_impl  # noqa: E402 (registers the tool)
from controlplane.intercept import Blocked, dispatch_tool, register_tool
from controlplane.manifest import load_manifest
from controlplane.registry.clock import set_clock
from controlplane.schema import ProposedAction, SessionContext

register_tool("approve_discount", _approve_discount_impl)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CP_MANIFEST", "discount_approval")
    monkeypatch.setenv("CP_RECEIPT_SECRET", "test-secret-not-for-production")
    set_clock(__import__("datetime").date(2026, 8, 14))
    yield
    set_clock(None)


def _dispatch(order_id: str, amount_paise: int, monkeypatch):
    """Drive the real gate. extract_action is stubbed (no LLM in the unit
    suite) — this use case declares no claimed_* claim, so a bare
    ProposedAction is a faithful stand-in for what the extractor returns."""
    monkeypatch.setattr(
        "controlplane.intercept.extract_action",
        lambda **kw: ProposedAction(tool=kw["tool"], **kw["tool_call_args"]),
    )
    session = SessionContext(
        trace_id="t-disc", customer_id="CUST-2291", agent_role="discount_agent",
        manifest_id="discount_approval-v1", gate_enabled=True,
    )
    return dispatch_tool("approve_discount", {"order_id": order_id, "amount_paise": amount_paise, "currency": "INR"}, session)


def test_manifest_loads_and_is_valid():
    m = load_manifest("discount_approval")
    assert m["tool"] == "approve_discount"
    assert m["window_days"] == 14
    assert m["authority_ceiling_paise"] == 500000
    assert [b["claim_kind"] for b in m["claim_bindings"]] == [
        "ORDER_BELONGS_TO_CUSTOMER", "WITHIN_REFUND_WINDOW", "AMOUNT_WITHIN_AUTHORITY"
    ]


def test_gate_blocks_a_discount_outside_the_window_and_over_the_ceiling(monkeypatch):
    # ORD-88461: delivered 2026-07-19 (26 days before the frozen clock) → outside
    # the 14-day discount window; INR 8,000 → over the INR 5,000 ceiling.
    with pytest.raises(Blocked) as e:
        _dispatch("ORD-88461", 800000, monkeypatch)
    reasons = {r.rule for r in e.value.decision.reasons if not r.passed}
    assert "within_window" in reasons
    assert "within_authority" in reasons
    assert e.value.decision.manifest_id == "discount_approval-v1"


def test_gate_allows_a_clean_discount(monkeypatch):
    # ORD-90233: delivered 2026-08-11 (3 days) → inside the window;
    # INR 2,000 → under the ceiling; right customer.
    result = _dispatch("ORD-90233", 200000, monkeypatch)
    assert result["status"] == "approved"


def test_same_input_different_manifest_different_ceiling(monkeypatch):
    """The governance claim, made concrete: INR 8,000 on a 3-day-old order.
    Under discount_approval (ceiling 5,000) it is over authority; under
    servicing (ceiling 25,000) the same amount would be within it. Same
    engine, same code path — only the manifest differs."""
    with pytest.raises(Blocked) as e:
        _dispatch("ORD-90233", 800000, monkeypatch)  # in window, but over the 5k discount ceiling
    reasons = {r.rule for r in e.value.decision.reasons if not r.passed}
    assert reasons == {"within_authority"}
