"""S12 — the policy manifest loader and validator.

A manifest is the whole per-use-case configuration: policy thresholds
(window, authority ceiling, reliability floor, verdict handling, fail
posture), the compensability of its action, which predicate graph runs, and
— since P02 — the *evidence bindings* that used to be Python in
intercept.py's ``_EVIDENCE_BUILDERS``.

The engine (everything under ``controlplane/``) is use-case agnostic. Adding
a use case is a new file in ``manifests/`` and nothing else. This loader is
the gate that keeps a broken manifest from ever reaching the pipeline: an
unknown resolver, an unknown claim kind, a malformed reference, or a
reference to a ``claimed_*`` field fails loudly here, with a message that
says which binding and why.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import jsonschema
import yaml

from controlplane.bindings import ManifestBindingError, validate_ref
from controlplane.registry import RESOLVER_BY_NAME
from controlplane.schema import ClaimKind

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = ROOT / "manifests"
AGENTS_DIR = ROOT / "agents"
SCHEMA_PATH = ROOT / "schemas" / "manifest.schema.json"

_VALID_CLAIM_KINDS = {k.name for k in ClaimKind}
_VALID_COMPENSABILITY = {"fully", "partially", "not"}
_VALID_FAIL_POSTURES = {"open", "closed"}
SUPPORTED_SCHEMA_VERSIONS = {1}

_json_schema_cache: dict | None = None


def _json_schema() -> dict:
    """The structural contract (schemas/manifest.schema.json), loaded once.
    STRUCTURAL only — see the schema's own $description. Semantic validation
    (does this resolver/claim_kind/graph actually exist) stays in _validate."""
    global _json_schema_cache
    if _json_schema_cache is None:
        _json_schema_cache = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _json_schema_cache


def _validate_structural(data: dict, name: str) -> None:
    instance = {k: v for k, v in data.items() if k != "_name"}
    try:
        jsonschema.validate(instance=instance, schema=_json_schema())
    except jsonschema.ValidationError as e:
        raise ManifestBindingError(
            f"manifests/{name}.yaml: structural schema violation at "
            f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        ) from e


def _validate(data: dict, name: str) -> None:
    def fail(msg: str) -> None:
        raise ManifestBindingError(f"manifests/{name}.yaml: {msg}")

    version = data.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        fail(f"unsupported schema_version {version!r} "
             f"(supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)})")

    _validate_structural(data, name)

    graph = data.get("predicate_graph")
    if not graph:
        fail("missing 'predicate_graph'")
    elif not (MANIFESTS_DIR / graph).is_file():
        fail(f"predicate_graph {graph!r} not found under manifests/")

    comp = data.get("compensation")
    if not isinstance(comp, dict) or comp.get("compensability") not in _VALID_COMPENSABILITY:
        fail(f"'compensation.compensability' must be one of {sorted(_VALID_COMPENSABILITY)}")

    risk_tier = data.get("risk_tier_default")
    if risk_tier not in {0, 1, 2}:
        fail("'risk_tier_default' must be 0, 1, or 2")
    fail_posture = data.get("fail_posture")
    tier_key = f"tier_{risk_tier}"
    if not isinstance(fail_posture, dict) or fail_posture.get(tier_key) not in _VALID_FAIL_POSTURES:
        fail(f"'fail_posture.{tier_key}' must be one of {sorted(_VALID_FAIL_POSTURES)}")

    bindings = data.get("claim_bindings")
    if not isinstance(bindings, list) or not bindings:
        fail("'claim_bindings' must be a non-empty list")

    for i, b in enumerate(bindings):
        where = f"claim_bindings[{i}]"
        if b.get("claim_kind") not in _VALID_CLAIM_KINDS:
            fail(f"{where}: unknown claim_kind {b.get('claim_kind')!r} "
                 f"(known: {sorted(_VALID_CLAIM_KINDS)})")
        if b.get("resolver") not in RESOLVER_BY_NAME:
            fail(f"{where}: unknown resolver {b.get('resolver')!r} "
                 f"(registered: {sorted(RESOLVER_BY_NAME)})")
        if "subject" in b and b["subject"] is not None:
            try:
                validate_ref(b["subject"], where=f"{name}.yaml {where}.subject")
            except ManifestBindingError as e:
                fail(str(e))
        pk = b.get("predicate_key")
        if not (pk is None or isinstance(pk, str) or (isinstance(pk, dict)
                and all(isinstance(v, str) for v in pk.values()))):
            fail(f"{where}: predicate_key must be null, a dotted string, or a str->str map")

    for dotted, ref in (data.get("predicate_payload") or {}).items():
        try:
            validate_ref(ref, where=f"{name}.yaml predicate_payload[{dotted!r}]")
        except ManifestBindingError as e:
            fail(str(e))


def load_manifest(name: str) -> dict:
    path = MANIFESTS_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["_name"] = name
    _validate(data, name)
    return data


def active_fail_posture(manifest: dict) -> tuple[int, str]:
    """Return the validated posture for the manifest's active risk tier.

    No default is permitted here: a missing posture is a configuration error,
    not an outage outcome that may be guessed at runtime.
    """

    risk_tier = int(manifest["risk_tier_default"])
    posture = manifest["fail_posture"][f"tier_{risk_tier}"]
    if posture not in _VALID_FAIL_POSTURES:
        raise ValueError(f"unsupported fail posture {posture!r} for tier_{risk_tier}")
    return risk_tier, posture


# --------------------------------------------------------------------------
# P02 hardening: read-only lint/explain. No file, DB, or network write; no
# manifest-named tool is ever called. Static only — see each report field's
# own "not statically checkable" fallback rather than overclaiming proof.
# --------------------------------------------------------------------------


def _tool_schemas() -> dict[str, dict]:
    """{tool_name: parameters JSON-schema-like dict}, discovered by AST
    ``literal_eval`` over every ``agents/*.py`` module-level tool-definition
    list (the OpenAI-style ``[{"type": "function", "function": {...}}]``
    literal each agent defines). No agent module is imported or executed."""
    out: dict[str, dict] = {}
    for py in sorted(AGENTS_DIR.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.List)):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            for entry in value:
                if isinstance(entry, dict) and entry.get("type") == "function":
                    fn = entry.get("function") or {}
                    if fn.get("name"):
                        out[fn["name"]] = fn.get("parameters") or {}
    return out


def _tool_contract_check(manifest: dict) -> str:
    schema = _tool_schemas().get(manifest.get("tool"))
    if schema is None:
        return "not statically checkable — no tool schema literal found under agents/"
    props = set(schema.get("properties", {}))
    subjects = {
        b["subject"].split(".", 1)[1]
        for b in manifest.get("claim_bindings", [])
        if isinstance(b.get("subject"), str) and b["subject"].startswith("action.")
    }
    unknown = sorted(subjects - props)
    if unknown:
        return f"INVALID — binding subject(s) not in {manifest['tool']}'s tool schema: {unknown}"
    return f"OK — {manifest['tool']} tool schema found, {len(props)} declared parameter(s)"


def _dead_binding_report(manifest: dict) -> list[str]:
    """Bindings with a predicate_key that never appears as ``evidence.<path>``
    text in the referenced Zen graph. A textual scan, not JS execution — a
    graph could reference the path dynamically, so a miss is reported as
    "not statically checkable", never asserted as proven-unused."""
    graph_path = MANIFESTS_DIR / manifest["predicate_graph"]
    if not graph_path.is_file():
        return ["not statically checkable — predicate_graph file missing"]
    graph_text = graph_path.read_text(encoding="utf-8")
    lines = []
    for b in manifest.get("claim_bindings", []):
        key = b.get("predicate_key")
        if key is None:
            continue
        paths = list(key.values()) if isinstance(key, dict) else [key]
        if all(f"evidence.{p}" in graph_text for p in paths):
            lines.append(f"{b['claim_kind']}: referenced in graph text")
        else:
            lines.append(
                f"{b['claim_kind']}: not found as 'evidence.<path>' in the graph text "
                "— not statically checkable beyond this substring scan"
            )
    return lines


def lint(name_or_path: str) -> dict:
    """Read-only report on one manifest. Never calls dispatch_tool, resolves
    no claim against a live system of record, writes nothing."""
    name = Path(name_or_path).stem
    report: dict = {"manifest": name, "ready": False}
    path = MANIFESTS_DIR / f"{name}.yaml"
    if not path.is_file():
        report["error"] = f"manifests/{name}.yaml not found"
        return report
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["_name"] = name
        _validate(data, name)
    except ManifestBindingError as e:
        report["error"] = str(e)
        return report

    report.update({
        "ready": True,
        "schema_version": data.get("schema_version"),
        "manifest_id": data["manifest_id"],
        "tool": data["tool"],
        "predicate_graph": data["predicate_graph"],
        "policy_config": {
            k: data.get(k) for k in (
                "window_days", "authority_ceiling_paise", "reliability_floor",
                "risk_tier_default", "fail_posture", "verdict_handling",
            )
        },
        "claim_bindings": [
            {"claim_kind": b["claim_kind"], "resolver": b["resolver"]}
            for b in data["claim_bindings"]
        ],
        "tool_contract": _tool_contract_check(data),
        "dead_binding_scan": _dead_binding_report(data),
    })
    return report


def _print_lint_report(report: dict) -> None:
    print(f"manifest: {report['manifest']}")
    if not report["ready"]:
        print(f"  INVALID — {report['error']}")
        return
    print(f"  schema_version: {report['schema_version']}")
    print(f"  manifest_id:    {report['manifest_id']}")
    print(f"  governed tool:  {report['tool']}")
    print(f"  predicate_graph: {report['predicate_graph']}")
    print("  claims:")
    for b in report["claim_bindings"]:
        print(f"    - {b['claim_kind']:<32} resolver={b['resolver']}")
    print(f"  policy config: {report['policy_config']}")
    print(f"  tool contract: {report['tool_contract']}")
    print("  dead-binding scan:")
    for line in report["dead_binding_scan"] or ["  (no predicate_key bindings)"]:
        print(f"    - {line}")
    print("  RESULT: READY")


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m controlplane.manifest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    lint_p = sub.add_parser("lint", help="read-only manifest lint/explain")
    lint_p.add_argument("manifest", help="manifest name or manifests/<name>.yaml path")
    args = parser.parse_args(argv)

    if args.cmd == "lint":
        report = lint(args.manifest)
        _print_lint_report(report)
        return 0 if report["ready"] else 1
    return 2


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))


__all__ = ["load_manifest", "active_fail_posture", "lint", "SUPPORTED_SCHEMA_VERSIONS"]
