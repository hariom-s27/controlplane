"""D-M1-01 — the gate never executes an action whose evidence is missing,
unavailable or failed (docs/decisions/D-M1-01-fail-closed.md).

Every test here pins a behaviour D-M1-01 changed, except the two marked
"kept guard", which pin protections that already existed and must not regress
(the receipt signature over `verification_coverage`, and MODIFY-without-args).
Runtime files go to tmp_path via tests/conftest.py.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import jsonschema
import pytest
import yaml

import controlplane.escalation as escalation_module
import controlplane.ground as ground_module
import controlplane.intercept as intercept
import controlplane.receipt as receipt_module
import controlplane.registry.orders as orders_registry
import controlplane.registry.policy as policy_registry
from controlplane.bindings import ManifestBindingError
from controlplane.decide import decide
from controlplane.errors import SourceUnavailable
from controlplane.extract import build_claims
from controlplane.idempotency import reset_execution_ledger
from controlplane.ladder import classify_claims
from controlplane.manifest import SCHEMA_PATH, _validate, load_manifest
from controlplane.receipt import verify
from controlplane.registry.clock import now
from controlplane.schema import (
    ClaimKind,
    Confidence,
    Decision,
    Evidence,
    FailureContext,
    Intervention,
    ProposedAction,
    Reliability,
    SessionContext,
    Verdict,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANIFEST_FILES = sorted((ROOT / "manifests").glob("*.yaml"))

CURRENT_CLAUSE = (
    "Customers may request a full refund within 7 days of the delivery date. "
    "Requests made after 7 days may be eligible for store credit at the "
    "discretion of a supervisor. Refunds are issued to the original payment "
    "method within 5-7 business days of approval."
)


@pytest.fixture(autouse=True)
def _clean_ledger(monkeypatch):
    monkeypatch.setenv("CP_RECEIPT_SECRET", "d-m1-01-test-secret")
    monkeypatch.setenv("CP_GROUNDING", "off")
    reset_execution_ledger()
    yield
    reset_execution_ledger()


def _queue_lines() -> list[dict]:
    q = Path(escalation_module.PENDING_QUEUE)
    if not q.exists():
        return []
    return [json.loads(l) for l in q.read_text(encoding="utf-8").splitlines() if l.strip()]


def _trail_lines() -> list[dict]:
    t = Path(receipt_module.OPERATIONAL_TRAIL)
    if not t.exists():
        return []
    return [json.loads(l) for l in t.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# (b) schema + loader reject the removed values; every manifest is migrated
# ---------------------------------------------------------------------------


def _raw(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("tier", ["tier_0", "tier_1", "tier_2"])
def test_schema_rejects_fail_posture_open(tier):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    data = _raw(ROOT / "manifests" / "servicing.yaml")
    data["fail_posture"][tier] = "open"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=data, schema=schema)


@pytest.mark.parametrize("tier", ["tier_0", "tier_1", "tier_2"])
def test_loader_rejects_fail_posture_open_with_d_m1_01_message(tier):
    data = _raw(ROOT / "manifests" / "servicing.yaml")
    data["fail_posture"][tier] = "open"
    with pytest.raises(ManifestBindingError, match=rf"fail_posture\.{tier}: open' was removed by decision D-M1-01"):
        _validate(data, "servicing")


@pytest.mark.parametrize("verdict", ["UNVERIFIABLE", "SOURCE_UNRELIABLE"])
def test_schema_and_loader_reject_allow_with_caveat(verdict):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    data = _raw(ROOT / "manifests" / "knowledge_assistant.yaml")
    data["verdict_handling"][verdict] = "allow_with_caveat"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=data, schema=schema)
    with pytest.raises(ManifestBindingError, match="allow_with_caveat' was removed by decision D-M1-01"):
        _validate(data, "knowledge_assistant")


def test_schema_accepts_closed_and_escalate_only():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    tiers = schema["properties"]["fail_posture"]["properties"]
    assert {t: sorted(v["enum"]) for t, v in tiers.items()} == {
        f"tier_{i}": ["closed", "escalate"] for i in range(3)
    }
    handling = schema["properties"]["verdict_handling"]["properties"]
    assert {v: d["enum"] for v, d in handling.items()} == {
        "UNVERIFIABLE": ["escalate"], "SOURCE_UNRELIABLE": ["escalate"]
    }


@pytest.mark.parametrize("path", MANIFEST_FILES, ids=lambda p: p.stem)
def test_every_manifest_is_migrated_and_schema_valid(path):
    assert len(MANIFEST_FILES) == 10
    data = _raw(path)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)
    assert set(data["fail_posture"].values()) <= {"closed", "escalate"}
    assert data["fail_posture"]["tier_0"] == "escalate"  # D-M1-01: every former `tier_0: open`
    assert set(data["verdict_handling"].values()) == {"escalate"}


def test_knowledge_assistant_active_posture_is_escalate():
    m = load_manifest("knowledge_assistant")
    assert m["risk_tier_default"] == 0 and m["fail_posture"]["tier_0"] == "escalate"
    assert m["verdict_handling"]["UNVERIFIABLE"] == "escalate"


# ---------------------------------------------------------------------------
# Servicing gate against copies of the real stores
# ---------------------------------------------------------------------------


def _servicing_action(**overrides) -> ProposedAction:
    fields = dict(
        tool="issue_refund", order_id="ORD-90233", amount_paise=849900, currency="INR",
        item_colour="grey", item_category="shirt", claimed_delivered_at="2026-08-11",
        claimed_policy_version="v4.2", claimed_clause_text=CURRENT_CLAUSE,
        claimed_reasoning="Current record and policy support the refund.",
    )
    fields.update(overrides)
    return ProposedAction(**fields)


def _args(action: ProposedAction) -> dict:
    return {k: v for k, v in action.facts_for_predicate().items() if k != "tool" and v is not None}


def _servicing_gate(monkeypatch, tmp_path, action: ProposedAction | None = None):
    for module, name in ((orders_registry, "orders.db"), (policy_registry, "policy_store.db")):
        target = tmp_path / name
        shutil.copy2(DATA / name, target)
        monkeypatch.setattr(module, "DB", target)
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    action = action or _servicing_action()
    monkeypatch.setattr(intercept, "extract_action", lambda **_kw: action)
    return intercept._run_gate(
        "issue_refund", _args(action),
        SessionContext(trace_id="d-m1-01-servicing", customer_id="CUST-2291"), "", [],
    )


def _csm_row(decision: Decision):
    rows = [r for r in decision.verification_ledger.claims if r.kind is ClaimKind.CLAUSE_SEMANTICS_MATCH]
    assert len(rows) == 1
    return rows[0]


def _receipt_csm_verification(receipt: dict):
    rows = [c for c in receipt["claims"] if c["kind"] == ClaimKind.CLAUSE_SEMANTICS_MATCH.value]
    assert len(rows) == 1
    return rows[0]["verification"]


# (d) grounding OFF by configuration: verdict unchanged, ledger says why
def test_grounding_off_keeps_verdict_and_ledger_says_c3_off_by_configuration(monkeypatch, tmp_path):
    decision, _lat, receipt = _servicing_gate(monkeypatch, tmp_path)
    assert decision.verdict is Verdict.VERIFIED  # unchanged by D-M1-01 (R6)
    assert decision.intervention is Intervention.ALLOW
    row = _csm_row(decision)
    assert row.modelling_state.value == "modelled" and row.verification_eligible is True
    assert row.verification_status.value == "unverified"
    assert row.reason == "c3_off_by_configuration"  # was "no_conclusive_check_ran"
    assert _receipt_csm_verification(receipt) == {"status": "unverified", "reason": "c3_off_by_configuration"}
    assert "C3" not in receipt["component_status"]
    assert verify(receipt) is True


# (e) grounding ON but failed -> UNVERIFIABLE
@pytest.mark.parametrize(
    ("case", "reason"),
    [("timeout", "timeout"), ("import_error", "import_error"), ("no_clause_text", "no_clause_text")],
)
def test_grounding_on_but_failed_is_unverifiable(monkeypatch, tmp_path, case, reason):
    monkeypatch.setenv("CP_GROUNDING", "on")
    action = _servicing_action(claimed_clause_text=None) if case == "no_clause_text" else _servicing_action()
    if case == "timeout":
        monkeypatch.setattr(ground_module, "score", lambda **_k: (_ for _ in ()).throw(TimeoutError("injected")))
    elif case == "import_error":
        monkeypatch.setattr(ground_module, "score", lambda **_k: (_ for _ in ()).throw(ImportError("no torch")))
    else:
        monkeypatch.setattr(ground_module, "score", lambda **_k: pytest.fail("no clause text: must not score"))

    decision, _lat, receipt = _servicing_gate(monkeypatch, tmp_path, action)

    assert decision.verdict is Verdict.UNVERIFIABLE
    assert decision.intervention is Intervention.ESCALATE
    assert any(r.rule == "clause_semantics_match_available" for r in decision.reasons)
    assert receipt["component_status"]["C3"] == {"status": "unavailable", "reason": reason}
    row = _csm_row(decision)
    assert (row.verification_status.value, row.reason) == ("unavailable", "c3_checker_failed")
    assert verify(receipt) is True


def test_grounding_failed_does_not_override_a_hard_contradiction(monkeypatch, tmp_path):
    # amount above the servicing authority ceiling (INR 25,000) -> C1/C2 contradiction
    monkeypatch.setenv("CP_GROUNDING", "on")
    monkeypatch.setattr(ground_module, "score", lambda **_k: (_ for _ in ()).throw(TimeoutError("injected")))
    decision, _lat, _receipt = _servicing_gate(monkeypatch, tmp_path, _servicing_action(amount_paise=2_600_000))
    assert decision.verdict is Verdict.CONTRADICTED
    assert decision.intervention is Intervention.BLOCK


def test_grounding_on_and_scored_is_still_honoured(monkeypatch, tmp_path):
    monkeypatch.setenv("CP_GROUNDING", "on")
    monkeypatch.setattr(ground_module, "score", lambda **_k: 0.97)
    decision, _lat, receipt = _servicing_gate(monkeypatch, tmp_path)
    assert decision.verdict is Verdict.VERIFIED and decision.intervention is Intervention.ALLOW
    assert receipt["component_status"]["C3"] == {"status": "available"}
    assert _csm_row(decision).verification_status.value == "verified"


# R3: POLICY_CLAUSE_CURRENT with no clause match is never a silent pass
def _servicing_decide(*, clause_match, grounding_score=None, grounding_state="off"):
    manifest = load_manifest("servicing")
    action = _servicing_action()
    claims = classify_claims(build_claims(action, manifest))
    evidence = [
        Evidence(claim_id=c.id, value="ok", source="test", query="q", fetched_at=now(),
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH)
        for c in claims
    ]
    predicates = {
        "within_window": True, "within_authority": True, "entity_match": True,
        "amount_sane": True, "attributes_match": True,
    }
    # grounding_state is passed only when not the default, so a missing-input
    # case exercises the verdict itself (not just the kwarg's existence).
    extra = {} if grounding_state == "off" else {"grounding_state": grounding_state}
    return decide("t", manifest["manifest_id"], action, claims, evidence, predicates, manifest,
                  clause_match=clause_match, grounding_score=grounding_score, **extra)


def test_policy_clause_current_with_no_clause_match_is_unverifiable():
    assert _servicing_decide(clause_match=True).intervention is Intervention.ALLOW  # healthy baseline
    d = _servicing_decide(clause_match=None)
    assert d.verdict is Verdict.UNVERIFIABLE
    assert d.intervention is Intervention.ESCALATE
    assert any(r.rule == "clause_current_available" and r.passed is False for r in d.reasons)


def test_decide_grounding_state_failed_without_score_is_unverifiable():
    assert _servicing_decide(clause_match=True, grounding_state="off").verdict is Verdict.VERIFIED
    d = _servicing_decide(clause_match=True, grounding_state="failed")
    assert d.verdict is Verdict.UNVERIFIABLE and d.intervention is Intervention.ESCALATE


# ---------------------------------------------------------------------------
# R1 / R2 at the dispatch boundary
# ---------------------------------------------------------------------------


def _outage_manifest(monkeypatch, name: str, *, posture: str | None = None, budget: float | None = None):
    manifest = load_manifest(name)
    if posture is not None:
        manifest["fail_posture"][f"tier_{manifest['risk_tier_default']}"] = posture
    if budget is not None:
        manifest["escalation_budget_pct"] = budget
    monkeypatch.setenv("CP_MANIFEST", name)
    monkeypatch.setattr(intercept, "load_manifest", lambda _n: manifest)
    monkeypatch.setattr(
        intercept, "resolve_bindings",
        lambda *_a, **_k: (_ for _ in ()).throw(SourceUnavailable(source="store.db", operation="connect")),
    )
    return manifest


_KNOWLEDGE_ARGS = {"recipient_id": "EMP-4410", "doc_id": "DOC-2277", "excerpt": "requested excerpt"}
_SERVICING_ARGS = {"order_id": "ORD-90233", "amount_paise": 849900}


@pytest.mark.parametrize(
    ("name", "tool", "args", "posture"),
    [
        ("knowledge_assistant", "send_document", _KNOWLEDGE_ARGS, None),   # its own tier_0 posture
        ("servicing", "issue_refund", _SERVICING_ARGS, "escalate"),        # escalate on tier_2
    ],
)
def test_outage_with_escalate_posture_queues_exactly_one_and_never_executes(monkeypatch, name, tool, args, posture):
    manifest = _outage_manifest(monkeypatch, name, posture=posture)
    assert manifest["fail_posture"][f"tier_{manifest['risk_tier_default']}"] == "escalate"
    action = ProposedAction(tool=tool, **args)
    monkeypatch.setattr(intercept, "extract_action", lambda **_kw: action)
    calls = []
    monkeypatch.setitem(intercept.REGISTRY, tool, lambda **kw: calls.append(kw) or {"executed": True})

    result = intercept.dispatch_tool(tool, dict(args), SessionContext(trace_id=f"d-m1-01-{name}"))

    # the source_unavailable execution guard must not turn `escalate` into Blocked
    assert result["status"] == "pending"
    queued = _queue_lines()
    assert len(queued) == 1 and queued[0]["queue_id"] == result["queue_id"]
    assert queued[0]["receipt"]["failure_context"]["posture_outcome"] == "escalated"
    assert calls == []


def test_outage_with_closed_posture_still_blocks(monkeypatch):
    _outage_manifest(monkeypatch, "servicing")  # tier_2: closed
    action = ProposedAction(tool="issue_refund", **_SERVICING_ARGS)
    monkeypatch.setattr(intercept, "extract_action", lambda **_kw: action)
    monkeypatch.setitem(intercept.REGISTRY, "issue_refund", lambda **kw: pytest.fail("executed"))
    with pytest.raises(intercept.Blocked):
        intercept.dispatch_tool("issue_refund", dict(_SERVICING_ARGS), SessionContext(trace_id="t"))
    assert _queue_lines() == []


def test_outage_with_escalate_posture_blocks_once_budget_is_exhausted(monkeypatch):
    manifest = _outage_manifest(monkeypatch, "knowledge_assistant")
    trail = Path(receipt_module.OPERATIONAL_TRAIL)
    trail.write_text("".join(
        json.dumps({"receipt": {"manifest_id": manifest["manifest_id"], "intervention": "ESCALATE"}}) + "\n"
        for _ in range(100)
    ), encoding="utf-8")
    action = ProposedAction(tool="send_document", **_KNOWLEDGE_ARGS)
    monkeypatch.setattr(intercept, "extract_action", lambda **_kw: action)
    monkeypatch.setitem(intercept.REGISTRY, "send_document", lambda **kw: pytest.fail("executed"))

    with pytest.raises(intercept.Blocked):
        intercept.dispatch_tool("send_document", dict(_KNOWLEDGE_ARGS), SessionContext(trace_id="t"))

    assert _queue_lines() == []
    events = [e for e in _trail_lines() if e.get("event") == "escalation_budget_exhausted"]
    assert len(events) == 1
    assert events[0]["outcome"] == "blocked" and events[0]["fail_posture"] == "escalate"


def test_record_budget_exhaustion_outcome_is_always_blocked(tmp_path):
    d = Decision(trace_id="t", manifest_id="m", verdict=Verdict.UNVERIFIABLE, intervention=Intervention.ESCALATE)
    for posture in ("open", "closed", "escalate", None):
        event = escalation_module.record_budget_exhaustion(
            d, {}, risk_tier=0, fail_posture=posture, trail_path=tmp_path / "t.jsonl")
        assert event["outcome"] == "blocked"


def test_source_unavailable_decision_never_reaches_execution(monkeypatch):
    # a hand-built ALLOW carrying a source_unavailable failure context
    decision = Decision(
        trace_id="t", manifest_id="m", verdict=Verdict.UNVERIFIABLE, intervention=Intervention.ALLOW,
        failure_context=FailureContext(kind="source_unavailable", stage="resolve", source="store.db"),
    )
    monkeypatch.setattr(intercept, "_run_gate", lambda *a, **k: (decision, {}, {}))
    intercept.register_tool("d_m1_01_guard", lambda **kw: pytest.fail("executed"))
    with pytest.raises(intercept.Blocked):
        intercept.dispatch_tool("d_m1_01_guard", {}, SessionContext(trace_id="t"))


# kept guard: MODIFY without modified_args never executes the original call
def test_modify_without_modified_args_never_executes(monkeypatch):
    decision = Decision(trace_id="t", manifest_id="m", verdict=Verdict.UNVERIFIABLE,
                        intervention=Intervention.MODIFY, modified_args=None)
    monkeypatch.setattr(intercept, "_run_gate", lambda *a, **k: (decision, {}, {}))
    intercept.register_tool("d_m1_01_modify", lambda **kw: pytest.fail("executed"))
    with pytest.raises(intercept.Pending):
        intercept.dispatch_tool("d_m1_01_modify", {"original": True}, SessionContext(trace_id="t"))


# ---------------------------------------------------------------------------
# (c) kept guard: verification_coverage is inside the signed bytes
# ---------------------------------------------------------------------------


def test_tampering_only_verification_coverage_fails_verify(monkeypatch, tmp_path):
    _decision, _lat, receipt = _servicing_gate(monkeypatch, tmp_path)
    assert verify(receipt) is True
    block = receipt["verification_coverage"]
    assert block is not None and block["eligible"] > block["verified"]
    tampered = copy.deepcopy(receipt)
    tampered["verification_coverage"]["verified"] = block["eligible"]
    tampered["verification_coverage"]["coverage"] = 1.0
    assert {k for k in receipt if receipt[k] != tampered[k]} == {"verification_coverage"}
    assert verify(tampered) is False
