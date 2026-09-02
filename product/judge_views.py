"""PRODUCT-02 — Evidence Passport and Decision Inspector.

Both functions below are pure presentation: they read fields off an
already-built product.judge_presentation.PresentationModel (itself built,
with no governance work, from PRODUCT-01's real ScenarioResult) and group /
label / format them for a judge. Neither function queries a resolver,
evaluates a predicate, calls decide(), dispatches a tool, or signs a
receipt. Both consume the SAME model, so anything the two views show for a
given result is guaranteed identical (see tests/test_product02_judge_presentation.py's
Passport<->Inspector consistency test).
"""

from __future__ import annotations

from typing import Any

from product.judge_presentation import NOT_AVAILABLE, PresentationModel, is_stale_for_profile

NOT_APPLICABLE_FOR_PROFILE = "NOT APPLICABLE FOR PROFILE"

EVIDENCE_HEALTH_DISCLAIMER = "NOT A VALIDATED CONFIDENCE SCORE"


def _guard_profile(model: PresentationModel, expected_profile: str | None) -> dict[str, Any] | None:
    if expected_profile is not None and is_stale_for_profile(model, expected_profile):
        return {
            "status": NOT_APPLICABLE_FOR_PROFILE,
            "requested_profile": expected_profile,
            "result_profile": model.profile,
            "note": "this result was produced under a different profile; re-run the "
                    "scenario under the requested profile rather than reusing this one",
        }
    return None


def evidence_passport(model: PresentationModel, *, expected_profile: str | None = None) -> dict[str, Any]:
    guard = _guard_profile(model, expected_profile)
    if guard is not None:
        return guard

    if not model.available:
        return {
            "kind": "EVIDENCE_PASSPORT",
            "scenario": model.scenario,
            "status": NOT_AVAILABLE,
            "reason": model.unavailable_reason,
        }

    return {
        "kind": "EVIDENCE_PASSPORT",
        "scenario": model.scenario,
        "profile": model.profile,
        "trace_id": model.trace_id,
        "ai_intent": model.ai_intent,
        "proposed_action": model.proposed_action,
        "evidence": [
            {
                "source": e.source,
                "field": e.field,
                "query": e.query,
                "value": e.value,
                "reliability": e.reliability,
                "freshness_ms": e.freshness_ms,
                "origin": model.evidence_origin,
            }
            for e in model.evidence
        ] or NOT_AVAILABLE,
        "policy_version": model.policy_version,
        "verdict": model.verdict,
        "intervention": model.intervention,
        "execution_state": model.execution_state,
        "idempotency_key": model.idempotency_key,
        "receipt_reference": model.receipt_reference,
        "receipt_verification": model.receipt_verification,
        "runtime_latency_ms": model.runtime_latency_ms,
        "evidence_origin": model.evidence_origin,
        "unavailable_fields": sorted(model.unavailable_fields),
    }


# Decision explanation hierarchy — Section 12: when multiple structured
# reasons exist, present the most fundamental one first. This only orders
# ALREADY-PRESENT structured reasons; it never invents one.
_HIERARCHY = (
    "predicate_contradiction",
    "evidence_reliability_failure",
    "missing_evidence",
    "policy_ambiguity",
    "authorization_failure",
)

_ROOT_CAUSE_TO_HIERARCHY = {
    "ambiguous_current_policy_state": "policy_ambiguity",
    "authoritative_source_unavailable": "missing_evidence",
}


def _explanation_rank(comparison_result: str, root_cause: str) -> str:
    if comparison_result == "CONFLICT":
        return "predicate_contradiction"
    if comparison_result == "UNAVAILABLE":
        return "missing_evidence"
    return _ROOT_CAUSE_TO_HIERARCHY.get(root_cause, "other_runtime_reason")


def decision_inspector(model: PresentationModel, *, expected_profile: str | None = None) -> dict[str, Any]:
    guard = _guard_profile(model, expected_profile)
    if guard is not None:
        return guard

    if not model.available:
        return {
            "kind": "DECISION_INSPECTOR",
            "scenario": model.scenario,
            "status": NOT_AVAILABLE,
            "reason": model.unavailable_reason,
        }

    chain = []
    for comparison in model.claim_evidence_comparisons:
        chain.append({
            "claim_field": comparison.claim_field,
            "evidence_field": comparison.evidence_field,
            "comparison_rule": comparison.comparison_rule,
            "comparison_result": comparison.comparison_result,
            "explanation_rank": _explanation_rank(comparison.comparison_result, model.root_cause),
        })
    # Present the structured chain ordered by the explanation hierarchy —
    # the first entry is the most fundamental existing reason, never a
    # fabricated one.
    rank_index = {name: i for i, name in enumerate(_HIERARCHY)}
    chain.sort(key=lambda item: rank_index.get(item["explanation_rank"], len(_HIERARCHY)))

    return {
        "kind": "DECISION_INSPECTOR",
        "scenario": model.scenario,
        "profile": model.profile,
        "trace_id": model.trace_id,
        "ai_claim": model.ai_intent,
        "claims": model.claims,
        "claim_evidence_chain": chain,
        "policy_version": model.policy_version,
        "predicate_result": model.predicate_result,
        "verdict": model.verdict,
        "intervention": model.intervention,
        "root_cause": model.root_cause,
        "execution_state": model.execution_state,
        "idempotency_key": model.idempotency_key,
        "receipt_reference": model.receipt_reference,
        "receipt_verification": model.receipt_verification,
        "unavailable_fields": sorted(model.unavailable_fields),
    }


def evidence_health_disclaimer() -> str:
    """The interface must display this exact statement wherever descriptive
    evidence-state labels (COMPLETE/STALE/CORROBORATED/...) appear, so they
    are never mistaken for a validated confidence score."""
    return EVIDENCE_HEALTH_DISCLAIMER
