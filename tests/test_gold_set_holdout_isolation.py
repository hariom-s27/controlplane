"""P03 — the construction-time truth must be unreachable from any checker.

bench/ground_truth_holdout.jsonl records, per case, the real source order id,
whether a distractor exists, the true policy version and the construction
recipe. If the gate, the labeller, or a scorer could read it, the "held-out"
guarantee is a fiction.

This asserts that no module under controlplane/ and none of the checker-side
bench modules names that file, opens it, or imports the builder that owns it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROLPLANE = ROOT / "controlplane"
BENCH = ROOT / "bench"
HOLDOUT = BENCH / "ground_truth_holdout.jsonl"

HOLDOUT_NAME = "ground_truth_holdout"

# Modules that consume the gold set and therefore must be blind to the holdout.
CHECKER_SIDE = [
    BENCH / "label.py",
    BENCH / "agreement.py",
    BENCH / "baselines.py",
    BENCH / "seb1_exp5_confusion_matrix.py",
    BENCH / "exp3_checker.py",
]


def _all_controlplane_sources() -> list[Path]:
    return sorted(p for p in CONTROLPLANE.rglob("*.py") if "__pycache__" not in p.parts)


def _strip_docstrings_and_comments(src: str) -> str:
    """Round-trip the source through the AST with docstrings blanked. Comments
    are not in the AST, so ast.unparse drops them; a prose mention in a
    docstring ('this module does NOT read the holdout') is therefore not
    mistaken for a dependency."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body[0].value.value = ""
    return ast.unparse(tree).lower()


def test_no_controlplane_module_names_the_holdout_file():
    offenders = [
        str(p.relative_to(ROOT))
        for p in _all_controlplane_sources()
        if HOLDOUT_NAME in _strip_docstrings_and_comments(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"controlplane modules reference the holdout: {offenders}"


def test_checker_side_modules_are_blind_to_the_holdout():
    for path in CHECKER_SIDE:
        src = path.read_text(encoding="utf-8")
        code = _strip_docstrings_and_comments(src)
        assert HOLDOUT_NAME not in code, f"{path.name} references {HOLDOUT_NAME!r} in code"
        # and it must not import the builder module that holds the truth
        mods = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module)
        assert "gold_set_build" not in mods, (
            f"{path.name} imports gold_set_build — the module that knows each "
            "case's intended slice and source order"
        )


def test_label_py_only_opens_the_public_stores_and_gold_set():
    """bench/label.py may read orders.db, policy_store.db and gold_set.jsonl —
    the same things the gate sees — and nothing that reveals the label."""
    code = _strip_docstrings_and_comments(BENCH.joinpath("label.py").read_text(encoding="utf-8"))
    for forbidden in ("holdout", "true_order_id", "intended_slice",
                      "intended_label", "source_order_id", "distractor_order_id"):
        assert forbidden not in code, f"bench/label.py references {forbidden!r} in code"


def test_holdout_actually_carries_the_construction_truth():
    """Positive control — the file we are isolating is real and non-trivial."""
    records = [json.loads(l) for l in HOLDOUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(records) == 150
    for r in records:
        assert r["source_order_id"].startswith("ORD-")
        assert "intended_slice" in r and "true_policy_version" in r
    assert any(r["distractor_present"] for r in records)
