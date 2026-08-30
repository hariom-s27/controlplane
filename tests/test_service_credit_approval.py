"""Onboarding measurement — use case 4 (service credit approval), added with
ZERO changes to anything under controlplane/. It reuses the `orders` and
`authority` resolvers and existing ClaimKinds; the only new artifacts are
manifests/service_credit_approval.yaml, its predicate graph, and a demo
agent. This file proves it runs through the real gate, lints READY under the
P02-hardened manifest tooling, and test_engine_is_use_case_agnostic.py proves
controlplane/ carries no string that names it.

Real data (no fabrication): ORD-10200/CUST-1407 (order total 58,355 paise)
for the ALLOW case; ORD-10298/CUST-1629 (order total 8,829,529 paise) for
the over-authority BLOCK case — both genuine data/orders.db rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.service_credit_agent import _approve_service_credit_impl  # noqa: E402 (registers the tool)
from controlplane import manifest as cm  # noqa: E402
from controlplane.intercept import Blocked, dispatch_tool, register_tool  # noqa: E402
from controlplane.manifest import load_manifest  # noqa: E402
from controlplane.schema import ProposedAction, SessionContext  # noqa: E402

register_tool("approve_service_credit", _approve_service_credit_impl)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CP_MANIFEST", "service_credit_approval")
    monkeypatch.setenv("CP_RECEIPT_SECRET", "test-secret-not-for-production")
    yield


def _dispatch(order_id: str, amount_paise: int, customer_id: str, monkeypatch):
    monkeypatch.setattr(
        "controlplane.intercept.extract_action",
        lambda **kw: ProposedAction(tool=kw["tool"], **kw["tool_call_args"]),
    )
    session = SessionContext(
        trace_id="t-svccredit", customer_id=customer_id, agent_role="service_credit_agent",
        manifest_id="service_credit_approval-v1", gate_enabled=True,
    )
    return dispatch_tool(
        "approve_service_credit",
        {"order_id": order_id, "amount_paise": amount_paise, "currency": "INR"},
        session,
    )


# --------------------------------------------------------------------------
# acceptance 1-4: manifest loads, validates, and lints READY
# --------------------------------------------------------------------------


def test_manifest_loads_and_is_valid():
    m = load_manifest("service_credit_approval")
    assert m["tool"] == "approve_service_credit"
    assert m["window_days"] is None
    assert m["authority_ceiling_paise"] == 300000
    assert [b["claim_kind"] for b in m["claim_bindings"]] == [
        "ORDER_BELONGS_TO_CUSTOMER", "AMOUNT_NOT_EXCEEDING_ORDER", "AMOUNT_WITHIN_AUTHORITY"
    ]


def test_manifest_lints_ready():
    report = cm.lint("service_credit_approval")
    assert report["ready"] is True
    assert report["tool"] == "approve_service_credit"
    assert report["tool_contract"].startswith("OK —")
    assert not [l for l in report["dead_binding_scan"] if "not found" in l]


# --------------------------------------------------------------------------
# acceptance 5-8: evidence resolution + real ALLOW / BLOCK cases
# --------------------------------------------------------------------------


def test_gate_allows_a_clean_service_credit(monkeypatch):
    # ORD-10200/CUST-1407: order total 58,355 paise; requesting 50,000 paise
    # (INR 500) — within the 300,000-paise authority ceiling, within the
    # order total, correct customer, no window to fail.
    result = _dispatch("ORD-10200", 50000, "CUST-1407", monkeypatch)
    assert result["status"] == "approved"


def test_gate_blocks_a_credit_over_authority(monkeypatch):
    # ORD-10298/CUST-1629: order total 8,829,529 paise; requesting 500,000
    # paise (INR 5,000) — over the 300,000-paise (INR 3,000) ceiling.
    with pytest.raises(Blocked) as e:
        _dispatch("ORD-10298", 500000, "CUST-1629", monkeypatch)
    reasons = {r.rule for r in e.value.decision.reasons if not r.passed}
    assert reasons == {"within_authority"}
    assert e.value.decision.manifest_id == "service_credit_approval-v1"


def test_gate_blocks_a_credit_for_the_wrong_customer(monkeypatch):
    # ORD-10200 really belongs to CUST-1407, not CUST-1629.
    with pytest.raises(Blocked) as e:
        _dispatch("ORD-10200", 50000, "CUST-1629", monkeypatch)
    reasons = {r.rule for r in e.value.decision.reasons if not r.passed}
    assert "entity_match" in reasons


def test_same_input_different_manifest_different_ceiling(monkeypatch):
    """The governance claim, made concrete a third way: INR 5,000 on
    ORD-10298 is over service_credit_approval's INR 3,000 ceiling but would
    be within servicing's INR 25,000 or discount_approval's INR 5,000 (right
    at the edge) — same engine, same code path, only the manifest differs."""
    with pytest.raises(Blocked) as e:
        _dispatch("ORD-10298", 300001, "CUST-1629", monkeypatch)
    reasons = {r.rule for r in e.value.decision.reasons if not r.passed}
    assert reasons == {"within_authority"}
