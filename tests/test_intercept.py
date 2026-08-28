"""S3 checkpoint — the product's core guarantee, tested explicitly.

Gate ON now runs the real S4-S9 pipeline (see test_intercept_gate_on.py for
the end-to-end ALLOW/BLOCK cases against real order data). What this file
locks in is narrower but just as load-bearing: a tool with no row in
extract.py's claim-kind table must fail loudly, never silently sail through
as VERIFIED/ALLOW — that would be a real bypass of the gate, not a safe
default.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from controlplane.intercept import dispatch_tool, register_tool
from controlplane.schema import SessionContext

ROOT = Path(__file__).resolve().parent.parent
_SKIP_DIRS = {".venv", "node_modules", "__pycache__", ".git"}


def test_gate_off_calls_impl_exactly_once():
    calls = []
    register_tool("noop_off", lambda **kw: calls.append(kw) or "ok")
    session = SessionContext(trace_id="t1", gate_enabled=False)

    result = dispatch_tool("noop_off", {"x": 1}, session)

    assert result == "ok"
    assert calls == [{"x": 1}]


def test_gate_on_unmodeled_tool_fails_loudly_never_calls_impl(monkeypatch):
    """extract_action() is mocked out here on purpose: the property under
    test is extract.py's own claim-kind check propagating up through
    dispatch_tool without impl ever running, not the (already fixture-
    tested, see test_extract.py) extraction call itself."""
    from controlplane.schema import ProposedAction

    monkeypatch.setattr(
        "controlplane.intercept.extract_action",
        lambda **kw: ProposedAction(tool=kw["tool"]),
    )

    calls = []
    register_tool("noop_on", lambda **kw: calls.append(kw) or "ok")
    session = SessionContext(trace_id="t2", gate_enabled=True)

    with pytest.raises(KeyError):
        dispatch_tool("noop_on", {"x": 1}, session)

    assert calls == []


def test_unregistered_tool_raises_keyerror():
    session = SessionContext(trace_id="t3", gate_enabled=False)
    with pytest.raises(KeyError):
        dispatch_tool("does_not_exist", {}, session)


def test_issue_refund_impl_is_never_called_outside_the_registry():
    """S3's own warning: naming the impl `_issue_refund_impl` only guards
    against bypass if nothing actually calls it directly. A plain substring
    search for `_issue_refund_impl(` only matches an invocation — the
    registration line passes the function by name, with no trailing `(`."""
    offenders = []
    this_file = Path(__file__).resolve()
    for p in ROOT.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in p.parts) or p.resolve() == this_file:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "_issue_refund_impl(" in line and not line.strip().startswith("def "):
                offenders.append(f"{p.relative_to(ROOT)}:{lineno}: {line.strip()}")

    assert offenders == [], (
        "_issue_refund_impl called directly, bypassing dispatch_tool:\n" + "\n".join(offenders)
    )
