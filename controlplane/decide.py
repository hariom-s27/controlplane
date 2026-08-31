"""S9 — verdict + intervention. Pure function: no I/O, no clock, no logging
(hard constraint #4). S15's metamorphic invariants and the mutation harness
call this thousands of times, which only works if it has no side effects and
no hidden inputs — every fact it uses is a parameter. That same property is
what tests/test_no_protected_attributes.py checks structurally: decide() has
no protected-attribute parameter, so it cannot discriminate on one.

Verdict precedence, per-claim not global: a hard (C1/C2) contradiction from
evidence that WAS above the reliability floor always wins the verdict
label, because "you cannot trust a contradiction derived from a source you
do not trust" only ever describes a claim whose OWN evidence is unreliable
— it was never meant to let one claim's degraded source suppress a
different, independently reliable claim's solid contradiction. Absent a
hard contradiction: SOURCE_UNRELIABLE > CONTRADICTED (C3-only) >
UNVERIFIABLE > VERIFIED.

Verdict label and intervention severity are deliberately decoupled for one
case: a claim that is BOTH below the reliability floor AND would itself
fail its own check still gets labeled SOURCE_UNRELIABLE (honest — we can't
fully trust that specific finding), but the INTERVENTION is floored at
whatever a hard CONTRADICTED would have produced. Without that floor,
degrading a claim's OWN evidence could turn its own would-be BLOCK into a
strictly more permissive ESCALATE — S15's M5 invariant
(docs/invariants.md, tests/test_invariants.py) is what caught this, twice,
at two different scenarios, before the fix above (per-claim precedence)
and the floor below (this paragraph) were both in place. Kept as a
Hypothesis-generated regression test so neither regresses silently.
See docs/compensability.md for how compensability then drives intervention.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from controlplane.compensation import compensation_for
from controlplane.schema import (
    Claim,
    ClaimKind,
    Compensability,
    Confidence,
    Decision,
    Evidence,
    Intervention,
    ProposedAction,
    Reason,
    Reliability,
    Verdict,
)

# Which Zen-resolved predicate flag backs each load-bearing ClaimKind.
# POLICY_CLAUSE_CURRENT and CLAUSE_SEMANTICS_MATCH are handled separately
# below — see controlplane/predicates/__init__.py for why they're not Zen
# predicates.
_PREDICATE_FOR_KIND: dict[ClaimKind, str] = {
    ClaimKind.WITHIN_REFUND_WINDOW: "within_window",
    ClaimKind.AMOUNT_WITHIN_AUTHORITY: "within_authority",
    ClaimKind.ORDER_BELONGS_TO_CUSTOMER: "entity_match",
    ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: "amount_sane",
    ClaimKind.ORDER_ATTRIBUTES_MATCH: "attributes_match",  # R3 extended, D52
    ClaimKind.ORDER_STATUS_SUPPORTS_ACTION: "status_supports_action",
    ClaimKind.DOC_CLASSIFICATION_PERMITTED: "classification_permitted",  # S13, use case 2
    ClaimKind.RECIPIENT_ENTITLED_TO_DOC: "recipient_entitled",  # the cross-tenant check
}

_RELIABILITY_RANK: dict[Reliability, int] = {
    Reliability.UNVERIFIED: 0,
    Reliability.INFERRED: 1,
    Reliability.CORROBORATED: 2,
}


def idempotency_key_for(trace_id: str, action: ProposedAction) -> str:
    """Deterministic, not random — decide() is pure. The same trace_id and
    action must always mint the same key, so a retried caller can be
    recognized and refused a double-execution."""
    payload = json.dumps({"trace_id": trace_id, "action": action.facts_for_predicate()}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def decide(
    trace_id: str,
    manifest_id: str,
    action: ProposedAction,
    claims: list[Claim],
    evidence: list[Evidence],
    predicate_result: dict[str, bool],
    manifest: dict[str, Any],
    clause_match: bool | None = None,
    grounding_score: float | None = None,
    grounding_threshold: float = 0.5,
) -> Decision:
    evidence_by_claim = {e.claim_id: e for e in evidence}
    reasons: list[Reason] = []

    reliability_floor = Reliability(manifest.get("reliability_floor", "corroborated"))
    floor_rank = _RELIABILITY_RANK[reliability_floor]

    source_unreliable = False
    hard_contradiction = False  # a real C1/C2 predicate or clause-version failure, on reliable evidence
    c3_contradiction = False  # a grounding-driven (C3) failure only
    unverifiable = False
    # A claim that is BOTH below the reliability floor AND would itself have
    # failed its own check. The verdict LABEL for this is still
    # SOURCE_UNRELIABLE (we can't confidently call it CONTRADICTED off shaky
    # evidence) — but M5 (docs/invariants.md) requires that the INTERVENTION
    # never relax below what treating it as a hard contradiction would give.
    # Verdict-label and intervention-severity are deliberately decoupled
    # below for exactly this reason.
    unreliable_and_would_violate = False

    for claim in claims:
        if not claim.load_bearing:
            continue  # a non-load-bearing claim's reliability can't taint the verdict either

        ev = evidence_by_claim.get(claim.id)

        is_unreliable = ev is not None and _RELIABILITY_RANK.get(ev.reliability_class, 0) < floor_rank
        if is_unreliable:
            source_unreliable = True
            reasons.append(
                Reason(
                    rule="reliability_floor",
                    expected=reliability_floor.value,
                    observed=ev.reliability_class.value,
                    passed=False,
                    policy_version=manifest_id,
                )
            )

        if ev is not None and ev.confidence == Confidence.NONE:
            unverifiable = True
            reasons.append(
                Reason(rule=f"{claim.kind.value}_resolved", expected="a value", observed=None, passed=False)
            )
            continue

        # Evaluated regardless of is_unreliable: whether the underlying
        # check WOULD fail is exactly what M5 needs to know, even when we
        # can't fully trust the answer.
        violated = False
        rule_name: str | None = None
        expected: Any = None
        observed: Any = None
        is_c3 = False

        predicate_field = _PREDICATE_FOR_KIND.get(claim.kind)
        if predicate_field is not None:
            passed = predicate_result.get(predicate_field)
            violated = passed is False
            rule_name, expected, observed = predicate_field, True, passed
        elif claim.kind is ClaimKind.POLICY_CLAUSE_CURRENT and clause_match is not None:
            violated = clause_match is False
            rule_name, expected, observed = "clause_current", claim.asserted_value, (ev.value if ev else None)
        elif claim.kind is ClaimKind.CLAUSE_SEMANTICS_MATCH and grounding_score is not None:
            # C3, moderate confidence per D3: a low score here is real
            # evidence of a problem, but never certainty the way a failed
            # C1/C2 predicate is.
            is_c3 = True
            violated = grounding_score < grounding_threshold
            rule_name, expected, observed = "clause_semantics_match", f">= {grounding_threshold}", grounding_score

        if violated and rule_name is not None:
            reasons.append(
                Reason(rule=rule_name, expected=expected, observed=observed, passed=False, policy_version=manifest_id)
            )
            if is_unreliable:
                unreliable_and_would_violate = True
            elif is_c3:
                c3_contradiction = True
            else:
                hard_contradiction = True

    # Precedence, refined by M5 (docs/invariants.md): a hard (C1/C2,
    # reliable-evidence) contradiction from ANY claim wins outright — by
    # construction it only ever comes from a claim whose OWN evidence was
    # above the reliability floor, so degrading a DIFFERENT, unrelated
    # claim's source must never suppress it. Absent that, SOURCE_UNRELIABLE >
    # CONTRADICTED(C3-only) > UNVERIFIABLE > VERIFIED, matching "you cannot
    # trust a contradiction derived from a source you do not trust" for the
    # case that phrase actually describes: a soft signal sitting alongside
    # an unrelated reliability problem, not a same-claim conflation.
    if hard_contradiction:
        verdict = Verdict.CONTRADICTED
    elif source_unreliable:
        verdict = Verdict.SOURCE_UNRELIABLE
    elif c3_contradiction:
        verdict = Verdict.CONTRADICTED
    elif unverifiable:
        verdict = Verdict.UNVERIFIABLE
    else:
        verdict = Verdict.VERIFIED

    comp = compensation_for(manifest)
    verdict_handling = manifest.get("verdict_handling", {})

    def _intervention_for(v: Verdict, c3_only: bool) -> Intervention:
        if v is Verdict.VERIFIED:
            return Intervention.ALLOW
        if comp.compensability is Compensability.NOT:
            # D49: no undo for this class. Irreversibility dominates
            # severity, regardless of how the verdict was reached.
            return Intervention.BLOCK
        if v is Verdict.CONTRADICTED and c3_only:
            # D3: low confidence never blocks. A C3-only contradiction escalates.
            return Intervention.ESCALATE
        if v is Verdict.CONTRADICTED:
            return Intervention.BLOCK
        handling = verdict_handling.get(v.value, "escalate")
        return Intervention.MODIFY if handling == "allow_with_caveat" else Intervention.ESCALATE

    intervention = _intervention_for(verdict, c3_contradiction and not hard_contradiction)

    if unreliable_and_would_violate:
        # The verdict stays SOURCE_UNRELIABLE-labeled for honest reporting,
        # but the response must be at least as strict as a hard contradiction
        # would have earned — never weaker just because the evidence backing
        # an apparent violation happens to be shaky.
        floor = _intervention_for(Verdict.CONTRADICTED, False)
        if floor.rank > intervention.rank:
            intervention = floor

    return Decision(
        trace_id=trace_id,
        manifest_id=manifest_id,
        verdict=verdict,
        intervention=intervention,
        reasons=reasons,
        claims=claims,
        evidence=evidence,
        predicate_trace={**predicate_result, "clause_match": clause_match, "grounding_score": grounding_score},
        compensation=comp,
        idempotency_key=idempotency_key_for(trace_id, action),
        verification_state=(
            "unverified"
            if verdict in {Verdict.UNVERIFIABLE, Verdict.SOURCE_UNRELIABLE}
            else "verified"
        ),
    )


__all__ = ["decide", "idempotency_key_for"]
