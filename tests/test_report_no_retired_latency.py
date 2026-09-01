"""Static release guard for the retired promotion-curve measurements."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "bench" / "report.py"
RETIRED_NAMES = {
    "MEASURED_GROUNDING_LOAD_MS",
    "MEASURED_GROUNDING_CALL_MS",
    "TYPICAL_PREDICATE_MS",
}


def _tree() -> ast.Module:
    return ast.parse(REPORT_PATH.read_text(encoding="utf-8"), filename=str(REPORT_PATH))


def test_retired_measurements_are_absent_from_executable_code():
    names = {node.id for node in ast.walk(_tree()) if isinstance(node, ast.Name)}
    assert names.isdisjoint(RETIRED_NAMES)


def test_retired_chart_is_neither_defined_nor_called():
    tree = _tree()
    definitions = {
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_promotion_curve_chart" not in definitions | calls


def test_retired_numeric_value_is_absent_from_executable_code():
    numeric_constants = {
        node.value
        for node in ast.walk(_tree())
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
    }
    assert 13_209.0 not in numeric_constants
