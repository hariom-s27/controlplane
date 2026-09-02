"""MASTER-11-15 product views (Evidence Health / Passport / Decision
Inspector / Timeline / Verification Policy / Cost-Assurance) — run over the
real bench/gold_set.jsonl cases through the real ControlPlane pipeline.

These tests assert the views are honestly grounded in the underlying
Decision/Evidence objects, not that any particular case gets a particular
verdict (P04/P05 own that). In particular:

  - claim/evidence "conflict" must never fire on a claim kind whose
    asserted_value is a structurally different fact by design (regression
    test for the false-positive bug caught while building this: comparing
    ORDER_BELONGS_TO_CUSTOMER's asserted order_id against its evidence
    customer_id looked like a "conflict" on every single case, including
    gold-ALLOW ones).
  - the verification-policy panel is descriptive only — it must never be
    reachable from the real decide()/receipt path.
  - the cost/assurance view only ever reads reports/summary.json, never
    computes a new latency number.
"""

from __future__ import annotations

import os

os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("CP_MODEL", "Qwen/Qwen3-8B")

import pytest

from controlplane.schema import ClaimKind
from product.pipeline import all_case_ids, case_by_id, run_decision, run_with_replay_demo
from product import views

_ALL_IDS = all_case_ids()
_SAMPLE_IDS = _ALL_IDS[::15]  # every 15th case: cheap, still covers every slice at least once


@pytest.fixture(scope="module")
def bundles():
    return {cid: run_decision(case_by_id(cid)) for cid in _SAMPLE_IDS}


def test_gold_set_has_cases():
    assert len(_ALL_IDS) == 150


def test_evidence_health_shape(bundles):
    for cid, b in bundles.items():
        eh = views.evidence_health(b)
        assert eh["kind"] == "EVIDENCE_HEALTH"
        assert "not a validated confidence score" in eh["disclaimer"]
        comp = eh["evidence_completeness"]
        assert 0 <= comp["resolved"] <= comp["total"]
        assert eh["trace_freshness"]["state"] in {"CURRENT", "STALE", "MISSING"}
        assert eh["predicate_margin"]["overall"] in {"OK", "NEAR BOUNDARY", "EXCEEDED"}
        assert eh["claim_evidence_conflict"]["state"] in {"NONE", "CONTRADICTED"}


def test_evidence_health_no_scalar_confidence_field(bundles):
    """Section 6D/7: never a bare `confidence = 0.xx` — every field must be
    a labelled state or a raw count, not a fitted score."""
    for b in bundles.values():
        eh = views.evidence_health(b)
        flat = str(eh)
        assert "confidence_score" not in flat.lower()


def test_conflict_only_fires_on_the_two_comparable_claim_kinds(bundles):
    """Regression test for the asserted_value/evidence.value category-error
    bug: ORDER_BELONGS_TO_CUSTOMER, AMOUNT_NOT_EXCEEDING_ORDER,
    AMOUNT_WITHIN_AUTHORITY, CLAUSE_SEMANTICS_MATCH, and
    ORDER_ATTRIBUTES_MATCH must never appear in a reported conflict — their
    asserted_value is a different field by construction
    (controlplane/extract.py::_ASSERTED_VALUE_FIELD), not the same fact
    from two sources."""
    allowed = {ClaimKind.POLICY_CLAUSE_CURRENT.value, ClaimKind.WITHIN_REFUND_WINDOW.value}
    for b in bundles.values():
        eh = views.evidence_health(b)
        for c in eh["claim_evidence_conflict"]["conflicts"]:
            assert c["claim"] in allowed, f"unexpected conflict on {c['claim']}"


def test_evidence_passport_fields_are_real(bundles):
    for cid, b in bundles.items():
        ep = views.evidence_passport(b)
        assert ep["trace_id"] == cid
        assert ep["receipt_signature_valid"] is True
        assert ep["intervention"] == b.decision.intervention.value
        assert ep["idempotency_key"] == b.decision.idempotency_key
        assert set(ep["evidence_sources"]) <= {"orders.db", "policy_store.db", "manifest:servicing", "entitlements.db"}


def test_decision_inspector_never_fabricates_a_confidence_score(bundles):
    for b in bundles.values():
        di = views.decision_inspector(b)
        assert di["no_confidence_score_fabricated"] is True
        assert di["verdict"] == b.decision.verdict.value
        assert di["receipt_signature_valid"] is True
        # every claim line traces back to a real Claim object, not synthesized
        kinds_in_view = {c["kind"] for c in di["claims"]}
        kinds_in_decision = {c.kind.value for c in b.decision.claims}
        assert kinds_in_view == kinds_in_decision


def test_decision_timeline_marks_execution_correctly(bundles):
    for b in bundles.values():
        dt = views.decision_timeline(b)
        would_execute = b.decision.intervention.value in ("ALLOW", "MODIFY")
        if would_execute:
            assert dt["status"]["EXECUTION"] in {"EXECUTED", "REPLAYED"}
        else:
            assert dt["status"]["EXECUTION"] == "NOT_EXECUTED"
        # verification is never marked complete for a stage that didn't run
        assert dt["status"]["VERIFICATION_DECISION"] == "DONE"


def test_idempotent_replay_is_a_real_replay():
    """Uses the real ExecutionLedger; the second call must not re-decide."""
    case_id = _ALL_IDS[0]
    bundle, replayed = run_with_replay_demo(case_id)
    assert replayed is True
    dt = views.decision_timeline(bundle, replayed=replayed)
    if bundle.decision.intervention.value in ("ALLOW", "MODIFY"):
        assert dt["status"]["EXECUTION"] == "REPLAYED"


def test_verification_policy_is_labelled_as_a_prototype():
    assert "CONFIGURABLE PROTOTYPE" in views.VERIFICATION_POLICY_PROTOTYPE["label"]
    for word in ("OPTIMAL", "VALIDATED", "LEARNED"):
        assert word not in views.VERIFICATION_POLICY_PROTOTYPE["label"]


def test_verification_policy_evaluation_is_display_only_never_gates_the_real_decision(bundles):
    """The prototype table's own action must have zero influence on the
    real Decision object already computed by run_decision — it is
    evaluated from the finished bundle, strictly downstream, read-only."""
    for b in bundles.values():
        before = b.decision.intervention.value
        views.verification_policy_evaluation(b)
        assert b.decision.intervention.value == before


def test_cost_assurance_reads_committed_report_only():
    ca = views.cost_assurance_view()
    assert ca["available"] is True
    assert ca["source"].startswith("reports/summary.json")
    assert len(ca["configurations"]) == 4
    for row in ca["configurations"]:
        assert row["p50_ms"] is not None
        assert row["p95_ms"] >= row["p50_ms"]


def test_cost_assurance_excludes_external_benchmark_numbers():
    """Section 20 firewall: external comparators (AEGIS/OAP) must never be
    presented as ControlPlane measurements."""
    ca = views.cost_assurance_view()
    flat = str(ca)
    assert "aegis" not in flat.lower() or "excluded" in flat.lower()
    assert "8.3 ms" not in flat  # the external AEGIS figure, never smuggled in as our own
