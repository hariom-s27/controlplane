"""P3-A — the independent kind-level extraction reference.

`bench/extraction_reference.py` states, per governed tool, the load-bearing
ClaimKinds a correct verifier must check. If it could import `controlplane`
or read `manifests/`, it would just be a restatement of what the gate
already does — the same circularity `docs/experiment-audit.md` retired for
the P01 experiments and `tests/test_label_independence.py` guards for the
gold labeller. This suite parses the reference's AST and also checks it
names only real, load-bearing ClaimKinds.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
REF_PY = ROOT / "bench" / "extraction_reference.py"
MANIFESTS_DIR = ROOT / "manifests"

import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import extraction_reference as ref  # noqa: E402
from controlplane.ladder import is_load_bearing  # noqa: E402
from controlplane.schema import ClaimKind  # noqa: E402
from manifest_claim_coverage import ReferenceError, _assess_tool, _validate_reference  # noqa: E402


# --------------------------------------------------------------------------
# independence — mirrors tests/test_label_independence.py
# --------------------------------------------------------------------------


def _imported_modules(src: str) -> set[str]:
    tree = ast.parse(src)
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def _code_only(src: str) -> str:
    """Source with docstrings blanked, so a prose mention of 'claim_bindings'
    in the module docstring is not read as behaviour."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body[0].value.value = ""
    return ast.unparse(tree)


def test_reference_imports_nothing_from_controlplane():
    mods = _imported_modules(REF_PY.read_text(encoding="utf-8"))
    cp = sorted(m for m in mods if m == "controlplane" or m.startswith("controlplane."))
    assert not cp, (
        f"bench/extraction_reference.py imports {cp} — the reference must not be a "
        "function of the system it audits (see tests/test_label_independence.py)"
    )


def test_reference_only_imports_stdlib():
    mods = _imported_modules(REF_PY.read_text(encoding="utf-8"))
    allowed = {"__future__", "dataclasses", "typing"}
    assert mods <= allowed, f"unexpected imports in the reference: {sorted(mods - allowed)}"


def test_reference_does_no_file_io_and_does_not_read_manifests():
    code = _code_only(REF_PY.read_text(encoding="utf-8"))
    for needle in (
        "open(", "read_text", "read_bytes", "Path(", "glob(", "yaml", "json.load",
        "claim_bindings", "manifests/", ".yaml", "load_manifest",
    ):
        assert needle not in code, (
            f"bench/extraction_reference.py references {needle!r} in code — it must be "
            "static data authored from the tool schema, policy prose and threat model, "
            "never derived from the manifests it is compared against"
        )


# --------------------------------------------------------------------------
# the reference names only real, load-bearing ClaimKinds
# --------------------------------------------------------------------------


def test_validate_reference_passes_on_the_committed_reference():
    assert _validate_reference() == []


@pytest.mark.parametrize("tool", sorted(ref.REQUIRED))
def test_required_kinds_are_valid_and_load_bearing(tool):
    for rk in ref.REQUIRED[tool]:
        kind = ClaimKind[rk.kind]  # raises if not a real ClaimKind
        assert is_load_bearing(kind), f"{tool}: {rk.kind} is not load-bearing — cannot be 'required'"
        assert rk.rationale.strip()
        for token in rk.basis:
            assert token in ref.BASIS_VOCAB or token.startswith("threat-model:T"), token


def test_deliberately_not_required_names_real_claimkinds():
    for tool, entries in ref.DELIBERATELY_NOT_REQUIRED.items():
        assert tool in ref.REQUIRED
        for kind_name, why in entries:
            ClaimKind[kind_name]  # raises if bogus
            assert why.strip()


def test_every_governed_manifest_tool_has_a_reference_entry():
    missing = []
    for path in sorted(MANIFESTS_DIR.glob("*.yaml")):
        tool = yaml.safe_load(path.read_text(encoding="utf-8")).get("tool")
        if tool not in ref.REQUIRED:
            missing.append((path.name, tool))
    assert not missing, f"governed tools with no bench/extraction_reference.py entry: {missing}"


def test_governed_tools_matches_required_keys():
    assert ref.GOVERNED_TOOLS == frozenset(ref.REQUIRED)


def test_missing_reference_entry_fails_loudly():
    with pytest.raises(ReferenceError):
        _assess_tool("a_tool_with_no_reference_entry", "x", "x-v1", bound=[])
