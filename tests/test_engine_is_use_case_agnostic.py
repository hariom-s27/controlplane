"""P02 CI check — controlplane/ must not name a use case.

The whole Governance claim is "same engine, different manifest, different
behaviour". This test fails if any file under controlplane/ contains a
use-case identifier as a string literal in executable code (docstrings and
comments are exempt — they explain, they don't dispatch). The forbidden
tokens are discovered from manifests/, so it also guards every use case
added later, not just the three that exist today.

If this fails: whatever you just wrote into controlplane/ belongs in a
manifest.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTROLPLANE = ROOT / "controlplane"
MANIFESTS = ROOT / "manifests"


def _forbidden_tokens() -> set[str]:
    tokens: set[str] = set()
    for mf in MANIFESTS.glob("*.yaml"):
        tokens.add(mf.stem)  # e.g. "servicing"
        data = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
        for key in ("tool", "manifest_id"):
            if data.get(key):
                tokens.add(str(data[key]))
    return tokens


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """id() of every string node that is a module/class/function docstring."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    return [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


CONTROLPLANE_PY = sorted(CONTROLPLANE.rglob("*.py"))


@pytest.mark.parametrize("path", CONTROLPLANE_PY, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_use_case_identifier_in_executable_code(path):
    forbidden = _forbidden_tokens()
    hits = sorted({tok for s in _string_literals(path) for tok in forbidden if tok in s})
    assert not hits, (
        f"{path.relative_to(ROOT)} names use case(s) {hits} in code. The engine must be "
        "use-case agnostic — move it to a manifest. (docstrings/comments are exempt.)"
    )


def test_forbidden_token_set_is_not_empty():
    """Guard against the check silently passing because it found no manifests."""
    assert len(_forbidden_tokens()) >= 6  # 3 manifests x (stem + tool) at least
