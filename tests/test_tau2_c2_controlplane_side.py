"""P06 C2 — controlplane-side structural tests.

Runnable with ONLY controlplane's own dependencies (this repo's .venv).
Deliberately does NOT `import bench.tau2_adapter` so this structural subset
remains independent of the dedicated joint C2 environment. The actual C2
modules are imported separately from that isolated Python 3.12 environment.

These tests establish, for real and executed rather than by code-reading
alone:

  1. The two minimal P02 declarative-infrastructure repairs this integration needs
     (decide.py's _PREDICATE_FOR_KIND wiring; the manifest schema's closed
     resolver enum) -- both exercised through the real generic paths.
  2. The six tau2_*.yaml manifests and tau2_*.json graphs are well-formed
     and structurally consistent with bench/tau2_adapter.py's design
     (correct tool name, correct claim_kind, correct flat predicate_key,
     correct evidence.<path> reference in the graph text).
  3. RESOLVER_BY_NAME accepts a new, additive key from outside
     controlplane/, exactly as bench/tau2_adapter.py::register_tau2_resolver
     relies on.
  4. The one generic decision-map row adds no use-case-specific Python or
     decision branch under controlplane/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = ROOT / "manifests"
GRAPHS_DIR = MANIFESTS_DIR / "graphs"
BENCH = ROOT / "bench"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BENCH))

from controlplane.decide import _PREDICATE_FOR_KIND, decide  # noqa: E402
from controlplane.ladder import classify, is_load_bearing  # noqa: E402
from controlplane.manifest import ManifestBindingError, load_manifest  # noqa: E402
from controlplane.registry import RESOLVER_BY_NAME  # noqa: E402
from controlplane.registry.clock import now  # noqa: E402
from controlplane.schema import (  # noqa: E402
    Claim,
    ClaimKind,
    Confidence,
    Evidence,
    Intervention,
    ProposedAction,
    Reliability,
    Tier,
    Verdict,
)

GOVERNED_TOOLS = [
    "cancel_pending_order",
    "exchange_delivered_order_items",
    "modify_pending_order_address",
    "modify_pending_order_items",
    "modify_pending_order_payment",
    "return_delivered_order_items",
]

STRICT_PENDING_TOOLS = {"cancel_pending_order", "modify_pending_order_items"}
LOOSE_PENDING_TOOLS = {"modify_pending_order_address", "modify_pending_order_payment"}
DELIVERED_TOOLS = {"exchange_delivered_order_items", "return_delivered_order_items"}


# --------------------------------------------------------------------------
# 1. The two P02 repairs -- exercised through the generic engine paths.
# --------------------------------------------------------------------------


def test_decide_mapping_recognizes_order_status_without_changing_existing_mappings():
    expected = {
        ClaimKind.WITHIN_REFUND_WINDOW: "within_window",
        ClaimKind.AMOUNT_WITHIN_AUTHORITY: "within_authority",
        ClaimKind.ORDER_BELONGS_TO_CUSTOMER: "entity_match",
        ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: "amount_sane",
        ClaimKind.ORDER_ATTRIBUTES_MATCH: "attributes_match",
        ClaimKind.ORDER_STATUS_SUPPORTS_ACTION: "status_supports_action",
        ClaimKind.DOC_CLASSIFICATION_PERMITTED: "classification_permitted",
        ClaimKind.RECIPIENT_ENTITLED_TO_DOC: "recipient_entitled",
    }
    assert _PREDICATE_FOR_KIND == expected


def test_ladder_already_classifies_order_status_supports_action():
    """The OTHER half of the claim's plumbing (Tier + load-bearing) is
    already correct, pre-dating this integration (P08)."""
    assert classify(ClaimKind.ORDER_STATUS_SUPPORTS_ACTION) is Tier.C1
    assert is_load_bearing(ClaimKind.ORDER_STATUS_SUPPORTS_ACTION) is True


def _fake_tau2_retail_resolver(*args, **kwargs):  # pragma: no cover - validation never calls it
    raise AssertionError("manifest validation must not execute a resolver")


def _status_decision(status_supports_action: bool):
    claim = Claim(
        id="order:status",
        kind=ClaimKind.ORDER_STATUS_SUPPORTS_ACTION,
        subject="ORDER-1",
        tier=Tier.C1,
        load_bearing=True,
    )
    evidence = [Evidence(
        claim_id=claim.id,
        value="pending" if status_supports_action else "delivered",
        source="authoritative-store",
        query="read order status",
        fetched_at=now(),
        reliability_class=Reliability.CORROBORATED,
        confidence=Confidence.HIGH,
    )]
    action = ProposedAction(tool="generic_order_action", order_id="ORDER-1")
    manifest = {
        "reliability_floor": "corroborated",
        "verdict_handling": {
            "UNVERIFIABLE": "escalate",
            "SOURCE_UNRELIABLE": "escalate",
        },
        "compensation": {"compensability": "fully", "action": "undo"},
    }
    return decide(
        "trace-1",
        "generic-status-v1",
        action,
        [claim],
        evidence,
        {"status_supports_action": status_supports_action},
        manifest,
    )


@pytest.mark.parametrize(
    ("predicate_value", "expected_verdict", "expected_intervention"),
    [
        (True, Verdict.VERIFIED, Intervention.ALLOW),
        (False, Verdict.CONTRADICTED, Intervention.BLOCK),
    ],
)
def test_order_status_predicate_reaches_existing_generic_decision_path(
    predicate_value: bool,
    expected_verdict: Verdict,
    expected_intervention: Intervention,
):
    decision = _status_decision(predicate_value)
    assert decision.verdict is expected_verdict
    assert decision.intervention is expected_intervention
    assert decision.predicate_trace["status_supports_action"] is predicate_value
    if predicate_value is False:
        assert any(
            reason.rule == "status_supports_action"
            and reason.observed is False
            and reason.passed is False
            for reason in decision.reasons
        )


def test_schema_permission_does_not_make_unregistered_resolver_valid():
    assert "tau2_retail" not in RESOLVER_BY_NAME
    with pytest.raises(ManifestBindingError) as exc_info:
        load_manifest("tau2_cancel_pending_order")
    message = str(exc_info.value)
    assert "structural schema violation" not in message
    assert "unknown resolver 'tau2_retail'" in message


@pytest.mark.parametrize("tool", GOVERNED_TOOLS)
def test_registered_tau2_retail_resolver_allows_manifest_validation(tool: str):
    assert "tau2_retail" not in RESOLVER_BY_NAME
    try:
        RESOLVER_BY_NAME["tau2_retail"] = _fake_tau2_retail_resolver
        manifest = load_manifest(f"tau2_{tool}")
        assert manifest["claim_bindings"][0]["resolver"] == "tau2_retail"
    finally:
        RESOLVER_BY_NAME.pop("tau2_retail", None)


# --------------------------------------------------------------------------
# 2. The six manifests + graphs are well-formed.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tool", GOVERNED_TOOLS)
def test_manifest_file_structurally_sane(tool: str):
    path = MANIFESTS_DIR / f"tau2_{tool}.yaml"
    assert path.is_file(), f"missing {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["tool"] == tool
    assert data["predicate_graph"] == f"graphs/tau2_{tool}.json"
    assert (MANIFESTS_DIR / data["predicate_graph"]).is_file()

    assert data["compensation"]["compensability"] in {"fully", "partially", "not"}
    assert data["risk_tier_default"] in (0, 1, 2)
    tier_key = f"tier_{data['risk_tier_default']}"
    assert data["fail_posture"][tier_key] in ("open", "closed")
    assert data["reliability_floor"] == "corroborated"

    bindings = data["claim_bindings"]
    assert len(bindings) == 1, "exactly ORDER_STATUS_SUPPORTS_ACTION, per the report's evidence-honesty decision"
    binding = bindings[0]
    assert binding["claim_kind"] == "ORDER_STATUS_SUPPORTS_ACTION"
    assert binding["resolver"] == "tau2_retail"
    assert binding["subject"] == "action.order_id"
    assert binding["predicate_key"] == "order_status"
    assert "." not in binding["predicate_key"], (
        "predicate_key must stay FLAT (no dot) -- a nested 'order.status' key "
        "would trigger controlplane/predicates/__init__.py::evaluate()'s "
        "servicing-specific null-substitution block (it special-cases a "
        "top-level 'order' dict), silently injecting spurious "
        "entity_match/amount_sane/attributes_match=None keys into the "
        "predicate result for a manifest that never asked for them."
    )

    # No other manifest field smuggles a claimed_* reference or free-form
    # code -- the schema's own additionalProperties:false on claim_bindings
    # already forbids a 'query'/'exec' key structurally; this is a second,
    # independent check directly on our own file content.
    assert "claimed_" not in json.dumps(data)


@pytest.mark.parametrize("tool", GOVERNED_TOOLS)
def test_graph_file_well_formed_and_matches_tau2_business_rule(tool: str):
    path = GRAPHS_DIR / f"tau2_{tool}.json"
    assert path.is_file(), f"missing {path}"
    graph = json.loads(path.read_text(encoding="utf-8"))

    assert graph["contentType"] == "application/vnd.gorules.decision"
    node_types = {n["type"] for n in graph["nodes"]}
    assert node_types == {"inputNode", "expressionNode", "outputNode"}
    edges = graph["edges"]
    assert len(edges) == 2

    expr_node = next(n for n in graph["nodes"] if n["type"] == "expressionNode")
    expressions = expr_node["content"]["expressions"]
    keys = {e["key"] for e in expressions}
    assert "status_supports_action" in keys

    value = next(e["value"] for e in expressions if e["key"] == "status_supports_action")
    assert "evidence.order_status" in value, "dead-binding scan (controlplane/manifest.py) requires this exact substring"

    # Mirrors the REAL tau2 v1.0.1 business rule in
    # external/tau2-bench/src/tau2/domains/retail/tools.py, transcribed in
    # this test independently of the manifest's own header comment.
    if tool in STRICT_PENDING_TOOLS:
        assert value == 'evidence.order_status == "pending"'
    elif tool in LOOSE_PENDING_TOOLS:
        assert 'evidence.order_status == "pending"' in value
        assert 'evidence.order_status == "pending (item modified)"' in value
        assert " or " in value
    elif tool in DELIVERED_TOOLS:
        assert value == 'evidence.order_status == "delivered"'
    else:  # pragma: no cover - GOVERNED_TOOLS is closed and fully classified above
        raise AssertionError(f"tool {tool!r} not classified into a status-rule bucket")


_STATUS_CASES: dict[str, list[tuple[str, bool]]] = {
    "cancel_pending_order": [
        ("pending", True), ("cancelled", False), ("delivered", False), ("pending (item modified)", False),
    ],
    "modify_pending_order_items": [
        ("pending", True), ("pending (item modified)", False), ("delivered", False),
    ],
    "modify_pending_order_address": [
        ("pending", True), ("pending (item modified)", True), ("delivered", False), ("cancelled", False),
    ],
    "modify_pending_order_payment": [
        ("pending", True), ("pending (item modified)", True), ("delivered", False),
    ],
    "exchange_delivered_order_items": [
        ("delivered", True), ("pending", False), ("return requested", False),
    ],
    "return_delivered_order_items": [
        ("delivered", True), ("pending", False), ("exchange requested", False),
    ],
}


@pytest.mark.parametrize("tool", GOVERNED_TOOLS)
def test_graph_actually_executes_correctly_in_real_zen_engine(tool: str):
    """Not just well-formed JSON: this loads each graph through the REAL
    `zen` engine (the same `controlplane.predicates._decision_for` uses) and
    evaluates it against representative tau2 order statuses, confirming the
    computed `status_supports_action` matches tau2's own real business rule
    for every case in _STATUS_CASES. Proves the graphs are correct and
    execution-ready through the repaired generic P02 path."""
    zen = pytest.importorskip("zen")
    path = GRAPHS_DIR / f"tau2_{tool}.json"
    decision = zen.ZenEngine().create_decision(path.read_text(encoding="utf-8"))
    for status, expected in _STATUS_CASES[tool]:
        payload = {"evidence": {"order_status": status}, "action": {}, "manifest": {}}
        result = decision.evaluate(payload)
        got = result["result"]["status_supports_action"]
        assert got == expected, f"{tool}: order_status={status!r} expected {expected}, got {got}"


def test_governed_tool_set_matches_report_and_excludes_modify_user_address():
    from tau2_governed_scope import GOVERNED_TOOLS as governed  # stdlib-only, no tau2 needed

    assert governed == frozenset(GOVERNED_TOOLS)
    assert len(governed) == 6
    assert "modify_user_address" not in governed, (
        "modify_user_address is a documented representational scope boundary "
        "(section 6) -- it must never be forced into ActionSpec/governed scope."
    )


# --------------------------------------------------------------------------
# 3. RESOLVER_BY_NAME accepts a new, additive, bench-side key.
# --------------------------------------------------------------------------


def test_resolver_by_name_accepts_additive_bench_side_registration():
    """Exercises the EXACT mechanism bench/tau2_adapter.py::register_tau2_resolver
    relies on, without importing that module (it needs tau2). Confirms: (a)
    the dict accepts a brand-new key from outside controlplane/, (b) no
    EXISTING key's callable is disturbed, (c) re-registration is idempotent
    (matches register_tau2_resolver's use of setdefault)."""
    existing_snapshot = dict(RESOLVER_BY_NAME)

    def _fake_tau2_retail_resolver(claim, session, manifest, action):  # pragma: no cover - never invoked here
        raise AssertionError("not meant to be called by this test")

    try:
        assert "tau2_retail" not in RESOLVER_BY_NAME, (
            "a previous test run left 'tau2_retail' registered; RESOLVER_BY_NAME "
            "is process-global module state and this test needs a clean slate"
        )
        RESOLVER_BY_NAME.setdefault("tau2_retail", _fake_tau2_retail_resolver)
        assert RESOLVER_BY_NAME["tau2_retail"] is _fake_tau2_retail_resolver

        # idempotent: setdefault again must not clobber it
        RESOLVER_BY_NAME.setdefault("tau2_retail", lambda *a: None)
        assert RESOLVER_BY_NAME["tau2_retail"] is _fake_tau2_retail_resolver

        # no existing entry disturbed
        for k, v in existing_snapshot.items():
            assert RESOLVER_BY_NAME[k] is v
    finally:
        RESOLVER_BY_NAME.pop("tau2_retail", None)
        assert dict(RESOLVER_BY_NAME) == existing_snapshot


# --------------------------------------------------------------------------
# 4. The P02 repair remains use-case agnostic.
# --------------------------------------------------------------------------


def test_p02_repair_adds_no_use_case_specific_decision_branch():
    source = (ROOT / "controlplane" / "decide.py").read_text(encoding="utf-8").lower()
    forbidden = {"tau2", "retail", "tau2_retail", *GOVERNED_TOOLS}
    assert not {token for token in forbidden if token in source}


# --------------------------------------------------------------------------
# 5. Final-preflight records: exact evaluator identity and honest latency.
# --------------------------------------------------------------------------


def test_c2_evaluation_configuration_exactly_matches_frozen_c1_lock():
    config = json.loads((BENCH / "p06-c2-config.json").read_text(encoding="utf-8"))
    c1_lock = (ROOT / "reports" / "tau2-bench.md").read_text(encoding="utf-8")
    harness = (BENCH / "run_c2.py").read_text(encoding="utf-8")

    assert config["evaluation"] == {
        "type": "ALL_WITH_NL_ASSERTIONS",
        "tau2_enum_value": "all_with_nl_assertions",
        "c1_source": "reports/tau2-bench.md final locked protocol, Evaluation type (CLI)",
        "identical_to_c1": True,
    }
    assert "`ALL_WITH_NL_ASSERTIONS` for diagnostics" in c1_lock
    assert 'config["evaluation"]["type"]' in harness
    assert "evaluation_type=evaluation_type" in harness
    assert "evaluation_type=EvaluationType.ALL," not in harness
    assert "WORKSPACE_ROOT / config[\"output\"][\"path\"]" in harness


def test_latency_provenance_is_explicitly_unavailable_without_inference():
    config = json.loads((BENCH / "p06-c2-config.json").read_text(encoding="utf-8"))
    provenance = config["latency_provenance"]
    adapter = (BENCH / "tau2_adapter.py").read_text(encoding="utf-8")
    schema = (ROOT / "controlplane" / "schema.py").read_text(encoding="utf-8")

    assert provenance["status"] == "UNAVAILABLE"
    assert provenance["p50_p95_ready"] is False
    assert set(provenance["missing"]) == {
        "task_id at gate entry",
        "entry timestamp",
        "exit timestamp",
        "persisted end_to_end duration",
    }
    assert "task_id=" not in adapter
    session_block = schema[schema.index("class SessionContext"):schema.index("class ToolCall")]
    assert "task_id" not in session_block


def test_post_p02_integrity_record_accounts_for_one_authorized_change():
    record = ROOT / "docs" / "p06-post-p02-integrity.sha256"
    rows = [
        line.split(maxsplit=5)
        for line in record.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert len(rows) == 14
    changed = [row for row in rows if row[2] == "AUTHORIZED_CHANGE"]
    assert len(changed) == 1
    original_hash, current_hash, _, path, reason = changed[0]
    assert path == "tests/test_manifest_hardening.py"
    assert original_hash == "fb9dd57a2ccfdff03e0e199cead74e6f80a356ead3c60184b89b7c68c6479544"
    assert current_hash == "4a8c229df1bfd11cf7b163da8e6b4ac68b844af053184151f7fc8bf2108a741b"
    assert reason == "P02_minimal_repair_regression_coverage_authorized"

    for original_hash, current_hash, status, path, _reason in rows:
        live = __import__("hashlib").sha256((ROOT / path).read_bytes()).hexdigest()
        assert live == current_hash
        if status == "UNCHANGED":
            assert original_hash == current_hash
