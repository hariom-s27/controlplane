"""PRODUCT-02 — focused tests for the Evidence Passport / Decision Inspector
presentation layer (product/judge_presentation.py, product/judge_views.py).

These tests do not re-test controlplane/* or scripts/judge_demo.py's own
correctness (see tests/test_judge_demo.py for that). They lock in that the
presentation layer:
  - builds one shared model consumed identically by both views;
  - never re-derives evidence/claims/policy/verdict independently;
  - never triggers a second dispatch/decide/receipt-generation;
  - renders NOT AVAILABLE rather than guessing, for every missing field;
  - only reports MATCH/CONFLICT/UNAVAILABLE for the two ClaimKinds where
    that comparison is semantically valid, and NO DIRECT COMPARISON for
    every other kind;
  - classifies receipt verification for real (VERIFIED/TAMPERED/etc), using
    controlplane.receipt.verify(), not a second verifier;
  - keeps verdict / intervention / execution_state as distinct fields.
"""

from __future__ import annotations

import copy
import json

import pytest

from controlplane.idempotency import reset_execution_ledger
from product.judge_presentation import (
    CONFLICT,
    MATCH,
    NO_DIRECT_COMPARISON,
    NOT_AVAILABLE,
    UNAVAILABLE,
    build_presentation_model,
    classify_receipt,
    is_stale_for_profile,
)
from product.judge_views import (
    NOT_APPLICABLE_FOR_PROFILE,
    decision_inspector,
    evidence_health_disclaimer,
    evidence_passport,
)
from scripts import judge_demo as demo


@pytest.fixture(autouse=True)
def _isolated_ledger():
    reset_execution_ledger()
    demo._call_log.clear()
    yield
    reset_execution_ledger()
    demo._call_log.clear()


# ---------------------------------------------------------------------------
# 1/2/3 — shared presentation model; Passport and Inspector consume it
# ---------------------------------------------------------------------------


def test_shared_model_feeds_both_views_identically():
    result = demo.scenario_1_allow()
    model = build_presentation_model(result)

    passport = evidence_passport(model)
    inspector = decision_inspector(model)

    assert passport["verdict"] == inspector["verdict"] == model.verdict
    assert passport["intervention"] == inspector["intervention"] == model.intervention
    assert passport["execution_state"] == inspector["execution_state"] == model.execution_state
    assert passport["receipt_verification"] == inspector["receipt_verification"]
    assert passport["trace_id"] == inspector["trace_id"] == model.trace_id
    assert passport["policy_version"] == inspector["policy_version"]


def test_no_duplicated_independent_extraction():
    """Passport and Inspector must both read from the same model object,
    not recompute evidence/claims themselves."""
    result = demo.scenario_3_contradiction()
    model = build_presentation_model(result)

    assert evidence_passport(model)["evidence"] != NOT_AVAILABLE
    # Inspector's claims list is model.claims verbatim, not a re-derivation.
    assert decision_inspector(model)["claims"] is model.claims


# ---------------------------------------------------------------------------
# 4/5 — semantic claim -> evidence mapping
# ---------------------------------------------------------------------------


def test_within_refund_window_gets_a_real_semantic_comparison():
    """The one comparable claim in judge_demo's scenarios: WITHIN_REFUND_WINDOW
    is asserted with no asserted_value in scenario 2 -> UNAVAILABLE, never a
    fabricated MATCH/CONFLICT."""
    result = demo.scenario_2_source_unreliable()
    model = build_presentation_model(result)

    comparisons = model.claim_evidence_comparisons
    assert len(comparisons) == 1
    c = comparisons[0]
    assert c.claim_kind == "within_refund_window"
    assert c.comparison_rule == "exact-date comparison"
    assert c.comparison_result == UNAVAILABLE


def test_unrelated_claim_kinds_never_manufacture_a_comparison():
    """Entitlement-shaped claims (DOC_CLASSIFICATION_PERMITTED,
    RECIPIENT_ENTITLED_TO_DOC) must never be scored MATCH/CONFLICT — their
    asserted_value is a different fact by construction (CLAUDE.md's own
    category-error example)."""
    result = demo.scenario_1_allow()
    model = build_presentation_model(result)

    assert model.claim_evidence_comparisons, "scenario 1 has claims to check"
    for c in model.claim_evidence_comparisons:
        assert c.claim_kind in (
            "doc_classification_permitted", "recipient_entitled_to_doc",
            "excerpt_contains_third_party_pii",
        )
        assert c.comparison_rule == NO_DIRECT_COMPARISON
        assert c.comparison_result == NO_DIRECT_COMPARISON


def test_explicit_match_and_conflict_are_reachable():
    """Construct the exact-match rule's two positive outcomes directly
    (not via a scenario) to prove MATCH/CONFLICT are real, reachable
    classifications, not dead code."""
    from product.judge_presentation import _compare_claim_to_evidence

    claim = {"kind": "within_refund_window", "asserted": "2026-08-11"}
    matching_evidence = {"claim_id": "c1", "value": "2026-08-11"}
    conflicting_evidence = {"claim_id": "c1", "value": "2026-08-01"}

    assert _compare_claim_to_evidence(claim, matching_evidence).comparison_result == MATCH
    assert _compare_claim_to_evidence(claim, conflicting_evidence).comparison_result == CONFLICT


# ---------------------------------------------------------------------------
# 6 — NOT AVAILABLE rendering
# ---------------------------------------------------------------------------


def test_unavailable_scenario_renders_not_available_everywhere():
    """No current judge_demo scenario is genuinely unavailable (see
    tests/test_judge_demo.py::test_full_catalog_has_no_unavailable_scenarios),
    so this exercises build_presentation_model's own NOT_AVAILABLE branch
    directly against a synthetic unavailable ScenarioResult — the same
    dataclass shape a genuinely-unsupported future scenario would use."""
    result = demo.ScenarioResult(
        number=99, key="synthetic_unavailable", title="SYNTHETIC UNAVAILABLE",
        evidence_source="N/A", available=False,
        unavailable_reason="synthetic: exercises the NOT AVAILABLE rendering path only.",
    )
    model = build_presentation_model(result)

    assert model.available is False
    assert model.verdict == NOT_AVAILABLE
    assert model.receipt_verification == NOT_AVAILABLE
    assert model.evidence == []

    passport = evidence_passport(model)
    inspector = decision_inspector(model)
    assert passport["status"] == NOT_AVAILABLE
    assert inspector["status"] == NOT_AVAILABLE
    assert "exercises the NOT AVAILABLE rendering path" in passport["reason"]


def test_missing_runtime_latency_is_not_available_not_inferred():
    """Scenario 2 builds its receipt with an empty latency_ms dict (it does
    not go through _run_dispatch's timed path) — this must render as
    NOT AVAILABLE, never a fabricated 0 or omitted silently."""
    result = demo.scenario_2_source_unreliable()
    model = build_presentation_model(result)

    assert model.runtime_latency_ms == NOT_AVAILABLE
    assert "runtime_latency_ms" in model.unavailable_fields


# ---------------------------------------------------------------------------
# 7 — evidence origin
# ---------------------------------------------------------------------------


def test_evidence_origin_is_preserved_not_invented():
    runtime_model = build_presentation_model(demo.scenario_1_allow())
    fixture_model = build_presentation_model(demo.scenario_2_source_unreliable())

    assert runtime_model.evidence_origin == "RUNTIME"
    assert fixture_model.evidence_origin == "FIXTURE"


# ---------------------------------------------------------------------------
# 8/9/10 — receipt verification: VERIFIED / TAMPERED / mismatch
# ---------------------------------------------------------------------------


def test_receipt_verified_uses_the_real_verifier():
    model = build_presentation_model(demo.scenario_1_allow())
    assert model.receipt_verification == "VERIFIED"


def test_receipt_tamper_is_detected_via_a_temporary_copy(tmp_path):
    """Copies one demo receipt to a tmp_path file, flips one byte, and runs
    it back through the real classify_receipt()/controlplane.receipt.verify()
    path. Never touches a canonical repository artifact."""
    result = demo.scenario_1_allow()
    receipt = copy.deepcopy(result.receipt)

    raw = json.dumps(receipt).encode("utf-8")
    tampered_path = tmp_path / "tampered_receipt.json"
    # Flip exactly one byte inside the signed payload (the verdict string).
    idx = raw.index(b"VERIFIED")
    tampered = bytearray(raw)
    tampered[idx] ^= 0x01
    tampered_path.write_bytes(bytes(tampered))

    tampered_receipt = json.loads(tampered_path.read_text(encoding="utf-8"))
    status = classify_receipt(
        tampered_receipt, expected_verdict=receipt["verdict"], expected_intervention=receipt["intervention"]
    )
    assert status == "TAMPERED"

    # The canonical in-memory receipt must remain untouched and still verify.
    assert classify_receipt(
        receipt, expected_verdict=receipt["verdict"], expected_intervention=receipt["intervention"]
    ) == "VERIFIED"


def test_receipt_result_mismatch_is_surfaced_not_silently_resolved():
    result = demo.scenario_1_allow()
    # A receipt whose own verdict genuinely disagrees with the result's
    # claimed verdict must surface as a mismatch, not silently pick one.
    status = classify_receipt(result.receipt, expected_verdict="CONTRADICTED", expected_intervention="ALLOW")
    assert status == "RECEIPT / RESULT MISMATCH"


def test_missing_receipt_is_not_available():
    assert classify_receipt(None, expected_verdict=None, expected_intervention=None) == NOT_AVAILABLE


# ---------------------------------------------------------------------------
# 11/12 — no hidden rerun / no additional implementation call
# ---------------------------------------------------------------------------


def test_rendering_never_triggers_a_second_dispatch_or_decide(monkeypatch):
    result = demo.scenario_1_allow()
    model = build_presentation_model(result)

    def _explode(*_a, **_k):
        raise AssertionError("presentation layer must never call this")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    monkeypatch.setattr("controlplane.extract.extract_action", _explode)
    monkeypatch.setattr("controlplane.receipt.build_receipt", _explode)

    # Render both views, twice each, purely from the already-built model.
    evidence_passport(model)
    decision_inspector(model)
    evidence_passport(model)
    decision_inspector(model)


def test_rendering_does_not_increment_the_real_implementation_call_count():
    result = demo.scenario_1_allow()
    calls_after_run = len(demo._call_log)
    model = build_presentation_model(result)

    evidence_passport(model)
    decision_inspector(model)
    evidence_passport(model)

    assert len(demo._call_log) == calls_after_run


def test_rendering_generates_no_additional_receipt():
    result = demo.scenario_1_allow()
    original_receipt_id = result.receipt["receipt_id"]
    model = build_presentation_model(result)

    evidence_passport(model)
    decision_inspector(model)

    assert model.receipt_reference == original_receipt_id


# ---------------------------------------------------------------------------
# 13 — profile / result mismatch, 14 — unsupported profile/scenario
# ---------------------------------------------------------------------------


def test_profile_mismatch_invalidates_the_stale_result():
    model = build_presentation_model(demo.scenario_1_allow())
    assert model.profile == "knowledge_assistant-v1"
    assert is_stale_for_profile(model, "servicing-v1") is True
    assert is_stale_for_profile(model, "knowledge_assistant-v1") is False


def test_rendering_under_the_wrong_profile_returns_not_applicable():
    model = build_presentation_model(demo.scenario_1_allow())

    passport = evidence_passport(model, expected_profile="servicing-v1")
    inspector = decision_inspector(model, expected_profile="servicing-v1")

    assert passport["status"] == NOT_APPLICABLE_FOR_PROFILE
    assert inspector["status"] == NOT_APPLICABLE_FOR_PROFILE
    # Must not fabricate an alternate result under the requested profile.
    assert "verdict" not in passport
    assert "verdict" not in inspector


def test_rendering_under_the_matching_profile_is_unaffected():
    model = build_presentation_model(demo.scenario_1_allow())
    passport = evidence_passport(model, expected_profile="knowledge_assistant-v1")
    assert passport.get("status") != NOT_APPLICABLE_FOR_PROFILE
    assert passport["verdict"] == "VERIFIED"


# ---------------------------------------------------------------------------
# 15 — Product-01 result preservation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_fn", demo.SCENARIOS)
def test_product01_result_is_preserved_exactly(scenario_fn):
    """For every scenario, the presentation model's verdict/intervention/
    execution-derived state must match what scripts/judge_demo.py itself
    already asserts as the real outcome (see tests/test_judge_demo.py) —
    Product-02 must not reinterpret it."""
    result = scenario_fn()
    model = build_presentation_model(result)

    if not result.available:
        assert model.available is False
        return

    assert model.verdict == result.verdict
    assert model.intervention == result.intervention
    assert model.receipt_reference == result.receipt["receipt_id"]
    assert model.idempotency_key == result.receipt["idempotency_key"]


# ---------------------------------------------------------------------------
# Evidence Health disclaimer — never a confidence score
# ---------------------------------------------------------------------------


def test_evidence_health_disclaimer_is_the_required_text():
    assert evidence_health_disclaimer() == "NOT A VALIDATED CONFIDENCE SCORE"


# ---------------------------------------------------------------------------
# 16 — repeated rendering is deterministic (double-render check)
# ---------------------------------------------------------------------------


def test_repeated_rendering_is_substantively_deterministic():
    result = demo.scenario_3_contradiction()
    model = build_presentation_model(result)

    first_passport = evidence_passport(model)
    second_passport = evidence_passport(model)
    first_inspector = decision_inspector(model)
    second_inspector = decision_inspector(model)

    assert first_passport == second_passport
    assert first_inspector == second_inspector
