"""P03 — the labeller must not be a function of the system under test.

bench/label.py assigns the gold verdict for every gold-set case. If it could
import controlplane.decide / .predicates / .ladder / .ground, the "gold" label
would just be the gate's own output and the confusion matrix (SEB-1 Exp 5)
would be circular all over again — exactly the defect docs/experiment-audit.md
retired.

This parses bench/label.py's AST and fails if any controlplane import appears.
"""

from __future__ import annotations

import ast
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "bench"
LABEL_PY = BENCH / "label.py"

# The four the P03 spec names explicitly. The test below is stricter — it
# forbids *any* controlplane import — but these get a targeted message.
FORBIDDEN = (
    "controlplane.decide",
    "controlplane.predicates",
    "controlplane.ladder",
    "controlplane.ground",
)


def _imported_modules(src: str) -> set[str]:
    tree = ast.parse(src)
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # level > 0 is a relative import; module may be None for `from . import x`
            if node.module:
                mods.add(node.module)
    return mods


def test_label_py_imports_nothing_from_controlplane():
    mods = _imported_modules(LABEL_PY.read_text(encoding="utf-8"))

    named = sorted(m for m in mods if any(m == f or m.startswith(f + ".") for f in FORBIDDEN))
    assert not named, (
        f"bench/label.py imports {named} — the gold label must be independent "
        "of the system under test (P03 hard constraint)"
    )

    any_cp = sorted(m for m in mods if m == "controlplane" or m.startswith("controlplane."))
    assert not any_cp, (
        f"bench/label.py imports from controlplane ({any_cp}). The labeller is a "
        "second, independent implementation of the refund rules — it reads the "
        "policy prose and the order row directly and shares no code with the gate."
    )


def _code_only(src: str) -> str:
    """Source with docstrings blanked and comments dropped, so a prose mention
    ('must not import controlplane.decide') is not read as a dependency."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body[0].value.value = ""
    return ast.unparse(tree).lower()


def test_label_py_does_not_call_decide_by_any_name():
    """Belt and braces: even an importlib / __import__ / getattr dodge would
    still leave a string literal in the code."""
    code = _code_only(LABEL_PY.read_text(encoding="utf-8"))
    for needle in ("controlplane.decide", "controlplane.predicates",
                   "controlplane.ladder", "controlplane.ground",
                   "import decide", "from decide"):
        assert needle not in code, f"bench/label.py mentions {needle!r} in code"


def test_label_py_defines_the_labelling_entrypoint():
    tree = ast.parse(LABEL_PY.read_text(encoding="utf-8"))
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "label_case" in funcs
