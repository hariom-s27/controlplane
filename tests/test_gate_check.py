"""Focused regression tests for the gate-check return-shape defect."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_gate_check():
    spec = importlib.util.spec_from_file_location(
        "gate_check_under_test", ROOT / "scripts" / "gate_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(call):
    return call, {"content": ""}, "context", ["chunk"]


def test_valid_majority_passes(monkeypatch, capsys):
    gate_check = _load_gate_check()
    call = {"name": "issue_refund", "args": {"order_id": "ORD-1"}}
    monkeypatch.setattr(gate_check, "propose", lambda phrasing: _result(call))

    assert gate_check.main() == 0
    assert "5/5" in capsys.readouterr().out


def test_minority_proposals_fail(monkeypatch, capsys):
    gate_check = _load_gate_check()
    call = {"name": "issue_refund", "args": {"order_id": "ORD-1"}}
    results = iter([_result(call), _result(call), _result(None), _result(None), _result(None)])
    monkeypatch.setattr(gate_check, "propose", lambda phrasing: next(results))

    assert gate_check.main() == 1
    assert "2/5" in capsys.readouterr().out


def test_malformed_propose_result_is_not_ignored(monkeypatch):
    gate_check = _load_gate_check()
    monkeypatch.setattr(gate_check, "propose", lambda phrasing: (None, {"content": ""}, "context"))

    with pytest.raises(ValueError):
        gate_check.main()
