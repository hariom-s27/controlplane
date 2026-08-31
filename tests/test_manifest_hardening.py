"""P02 hardening — the manifest as a governance contract.

Adds, on top of the existing P02 manifest/bindings architecture (unchanged):
schema_version support, a machine-readable JSON Schema for the STRUCTURAL
shape (schemas/manifest.schema.json — semantic validation stays authoritative
in controlplane/manifest.py::_validate), a read-only `lint` report, a static
(AST-only, no import/execution) tool-contract check, and a textual
dead-binding scan. These tests do not touch any P03/P04/P05/P07/P08/P09
artifact and never call dispatch_tool.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from controlplane import manifest as cm
from controlplane.bindings import ManifestBindingError
from controlplane.registry import RESOLVER_BY_NAME
from controlplane.schema import ClaimKind

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = ["servicing", "knowledge_assistant", "discount_approval"]


def _fresh(name: str) -> dict:
    data = yaml.safe_load((cm.MANIFESTS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    data["_name"] = name
    return data


# --------------------------------------------------------------------------
# Feature 1 — every shipped manifest validates against the JSON Schema
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", MANIFESTS)
def test_every_shipped_manifest_passes_json_schema(name):
    data = {k: v for k, v in _fresh(name).items() if k != "_name"}
    jsonschema.validate(instance=data, schema=cm._json_schema())


@pytest.mark.parametrize("name", MANIFESTS)
def test_every_shipped_manifest_loads_without_error(name):
    assert cm.load_manifest(name)["_name"] == name


def test_schema_enums_cover_builtins_and_declared_external_extensions():
    """The JSON Schema's claim_kind/resolver enums are a structural
    convenience (Section 5). Built-in resolvers must remain accepted, while
    an explicitly permitted external resolver name still has to pass the
    independent RESOLVER_BY_NAME check in manifest._validate."""
    props = cm._json_schema()["properties"]["claim_bindings"]["items"]["properties"]
    assert set(props["claim_kind"]["enum"]) == {k.name for k in ClaimKind}
    resolver_names = set(props["resolver"]["enum"])
    assert set(RESOLVER_BY_NAME) <= resolver_names
    assert resolver_names - set(RESOLVER_BY_NAME) == {"tau2_retail"}


def test_schema_forbids_raw_query_or_arbitrary_keys_on_a_binding():
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["query"] = "SELECT * FROM orders"
    instance = {k: v for k, v in data.items() if k != "_name"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=instance, schema=cm._json_schema())


# --------------------------------------------------------------------------
# Feature 3 / Section 11 — the required negative cases
# --------------------------------------------------------------------------


def test_unknown_resolver_fails():
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["resolver"] = "not_a_real_resolver"
    with pytest.raises(ManifestBindingError):
        cm._validate(data, "discount_approval")


def test_unknown_claim_kind_fails():
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["claim_kind"] = "NOT_A_REAL_CLAIM_KIND"
    with pytest.raises(ManifestBindingError):
        cm._validate(data, "discount_approval")


def test_claimed_star_reference_fails():
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["subject"] = "action.claimed_clause_text"
    with pytest.raises(ManifestBindingError, match="claimed_"):
        cm._validate(data, "discount_approval")


def test_malformed_reference_fails():
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["subject"] = "no_dot_here"
    with pytest.raises(ManifestBindingError):
        cm._validate(data, "discount_approval")


def test_arbitrary_python_reference_is_rejected():
    """A reference that LOOKS structurally valid (dotted) but names a root
    outside {action, manifest, session, clock} — e.g. reaching for a module —
    is rejected by the semantic validator, not silently accepted."""
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["subject"] = "os.system"
    with pytest.raises(ManifestBindingError, match="not in"):
        cm._validate(data, "discount_approval")


def test_missing_predicate_graph_fails():
    data = _fresh("discount_approval")
    data["predicate_graph"] = "graphs/does_not_exist.json"
    with pytest.raises(ManifestBindingError, match="not found"):
        cm._validate(data, "discount_approval")


def test_unsupported_schema_version_fails():
    data = _fresh("discount_approval")
    data["schema_version"] = 2
    with pytest.raises(ManifestBindingError, match="unsupported schema_version"):
        cm._validate(data, "discount_approval")


def test_missing_schema_version_fails():
    data = _fresh("discount_approval")
    del data["schema_version"]
    with pytest.raises(ManifestBindingError, match="unsupported schema_version"):
        cm._validate(data, "discount_approval")


# --------------------------------------------------------------------------
# Section 9 — manifest/tool contract (static, AST-only)
# --------------------------------------------------------------------------


def test_tool_contract_passes_for_every_shipped_manifest():
    for name in MANIFESTS:
        result = cm._tool_contract_check(_fresh(name))
        assert result.startswith("OK —"), f"{name}: {result}"


def test_tool_contract_flags_a_binding_subject_the_tool_schema_does_not_declare():
    """`action.doc_id` is a valid ENGINE structural field (ProposedAction) —
    controlplane.bindings.validate_ref would accept it — but approve_discount's
    own tool schema declares only order_id/amount_paise/currency. This is the
    gap the tool-contract check closes that validate_ref alone cannot see."""
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["subject"] = "action.doc_id"
    result = cm._tool_contract_check(data)
    assert result.startswith("INVALID —")
    assert "doc_id" in result


def test_tool_contract_reports_not_statically_checkable_for_an_unknown_tool():
    data = _fresh("discount_approval")
    data["tool"] = "some_tool_no_agent_declares"
    result = cm._tool_contract_check(data)
    assert result == "not statically checkable — no tool schema literal found under agents/"


# --------------------------------------------------------------------------
# Section 10 — dead/unused binding detection (textual, not Zen execution)
# --------------------------------------------------------------------------


def test_dead_binding_scan_finds_every_consumed_binding_in_shipped_manifests():
    for name in MANIFESTS:
        lines = cm._dead_binding_report(_fresh(name))
        unreferenced = [l for l in lines if "not found" in l]
        assert not unreferenced, f"{name}: {unreferenced}"


def test_dead_binding_scan_flags_a_predicate_key_the_graph_never_reads():
    data = _fresh("discount_approval")
    data["claim_bindings"][0]["predicate_key"] = "order.totally_unused_field"
    lines = cm._dead_binding_report(data)
    assert any("not found" in l for l in lines)


# --------------------------------------------------------------------------
# Feature 2 — lint/explain: read-only, reports dependencies, final verdict
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", MANIFESTS)
def test_lint_reports_ready_and_identifies_dependencies(name):
    report = cm.lint(name)
    assert report["ready"] is True
    assert report["manifest_id"]
    assert report["tool"]
    assert report["predicate_graph"]
    assert report["claim_bindings"], "lint must list every claim's resolver dependency"
    for b in report["claim_bindings"]:
        assert b["resolver"] in RESOLVER_BY_NAME
    assert report["tool_contract"].startswith("OK —")


def test_lint_accepts_a_yaml_path_not_just_a_bare_name():
    by_path = cm.lint(str(cm.MANIFESTS_DIR / "discount_approval.yaml"))
    by_name = cm.lint("discount_approval")
    assert by_path["manifest_id"] == by_name["manifest_id"]


def test_lint_reports_invalid_for_a_broken_manifest(tmp_path, monkeypatch):
    bad = _fresh("discount_approval")
    bad["schema_version"] = 99
    del bad["_name"]
    broken_dir = tmp_path
    (broken_dir / "broken.yaml").write_text(yaml.safe_dump(bad), encoding="utf-8")
    monkeypatch.setattr(cm, "MANIFESTS_DIR", broken_dir)
    report = cm.lint("broken")
    assert report["ready"] is False
    assert "schema_version" in report["error"]


def test_lint_is_read_only_no_execution_no_writes():
    """manifest.py never imports controlplane.intercept (where dispatch_tool
    and REGISTRY live) — lint() is structurally incapable of calling a
    business action, not just conventionally well-behaved."""
    src = (ROOT / "controlplane" / "manifest.py").read_text(encoding="utf-8")
    assert "controlplane.intercept" not in src
    assert "import dispatch_tool" not in src and "dispatch_tool(" not in src

    watched = [
        ROOT / "decisions.jsonl",
        *sorted((ROOT / "manifests").glob("*.yaml")),
    ]
    before = {p: (p.read_bytes() if p.is_file() else None) for p in watched}
    for name in MANIFESTS:
        cm.lint(name)
    after = {p: (p.read_bytes() if p.is_file() else None) for p in watched}
    assert before == after


def test_cli_lint_exit_code_reflects_readiness(capsys):
    assert cm._cli(["lint", "discount_approval"]) == 0
    out = capsys.readouterr().out
    assert "RESULT: READY" in out

    assert cm._cli(["lint", "no_such_manifest"]) == 1
    out = capsys.readouterr().out
    assert "INVALID" in out
