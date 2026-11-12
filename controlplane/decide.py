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
    ClaimVerification,
    Compensability,
    Confidence,
    Decision,
    Evidence,
    Intervention,
    ModellingState,
    ProposedAction,
    Reason,
    Reliability,
    Tier,
    VerificationCoverage,
    VerificationLedger,
    VerificationStatus,
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

# P1 — tiers that have an authoritative check path in this build. Mirrors
# controlplane/ladder._VERIFIABLE_TIERS; kept as a local literal so decide()
# stays a pure function of its arguments with no extra import.
_VERIFIABLE_TIERS = (Tier.C1, Tier.C2, Tier.C3)
_COVERAGE_BASIS = "load_bearing_verification_eligible_claims"


def _claim_check_outcome(
    claim: Claim,
    ev: Evidence,
    predicate_result: dict[str, bool],
    clause_match: bool | None,
    grounding_score: float | None,
    grounding_threshold: float,
) -> tuple[bool, bool | None, Any]:
    """Did a real check run for this claim, and did it pass? Mirrors the
    dispatch inside decide()'s own loop exactly, so the ledger can never
    disagree with the verdict. Returns (rule_ran, passed, observed_value)."""
    predicate_field = _PREDICATE_FOR_KIND.get(claim.kind)
    if predicate_field is not None:
        if predicate_field not in predicate_result:
            return False, None, None
        value = predicate_result[predicate_field]
        if type(value) is not bool:  # None / unavailable predicate
            return False, None, value
        return True, value, value
    if claim.kind is ClaimKind.POLICY_CLAUSE_CURRENT:
        if clause_match is None:
            return False, None, (ev.value if ev else None)
        return True, clause_match, (ev.value if ev else None)
    if claim.kind is ClaimKind.CLAUSE_SEMANTICS_MATCH:
        if grounding_score is None:
            return False, None, None
        return True, grounding_score >= grounding_threshold, grounding_score
    # An eligible kind with no rule wired in this build: honestly "not checked".
    return False, None, (ev.value if ev else None)


def _verify_one_claim(
    claim: Claim,
    ev: Evidence | None,
    predicate_result: dict[str, bool],
    clause_match: bool | None,
    grounding_score: float | None,
    grounding_threshold: float,
    floor_rank: int,
) -> ClaimVerification:
    modelled = claim.tier is not None
    eligible = modelled and claim.tier in _VERIFIABLE_TIERS

    row = ClaimVerification(
        claim_id=claim.id,
        kind=claim.kind,
        subject=claim.subject,
        modelling_state=ModellingState.MODELLED if modelled else ModellingState.UNMODELLED,
        tier=claim.tier,
        resolver=claim.resolver,
        load_bearing=claim.load_bearing,
        verification_eligible=eligible,
        verification_status=VerificationStatus.NOT_ELIGIBLE,
        asserted_value=claim.asserted_value,
        authoritative_source=ev.source if ev else None,
        evidence_ref=ev.claim_id if ev else None,
    )

    if not modelled:
        row.reason = "unmodelled_no_tier"
        return row
    if not eligible:
        row.reason = f"tier_{claim.tier.value}_no_checker"
        return row

    if ev is None:
        row.verification_status = VerificationStatus.UNAVAILABLE
        row.reason = "no_evidence_resolved"
        return row
    if ev.confidence == Confidence.NONE:
        row.verification_status = VerificationStatus.UNAVAILABLE
        row.reason = "authoritative_lookup_empty"
        return row

    below_floor = _RELIABILITY_RANK.get(ev.reliability_class, 0) < floor_rank
    rule_ran, passed, observed = _claim_check_outcome(
        claim, ev, predicate_result, clause_match, grounding_score, grounding_threshold
    )
    row.observed_value = observed if isinstance(observed, (str, int, float, bool)) or observed is None else str(observed)

    if not rule_ran:
        row.verification_status = VerificationStatus.UNVERIFIED
        row.reason = "no_conclusive_check_ran"
        return row
    if passed is False:
        row.verification_status = VerificationStatus.CONTRADICTED
        row.reason = "contradicted_on_subfloor_evidence" if below_floor else "contradicted"
        return row
    if below_floor:
        row.verification_status = VerificationStatus.UNVERIFIED
        row.reason = "source_below_reliability_floor"
        return row
    row.verification_status = VerificationStatus.VERIFIED
    return row


def build_verification_ledger(
    claims: list[Claim],
    evidence: list[Evidence],
    predicate_result: dict[str, bool],
    *,
    clause_match: bool | None = None,
    grounding_score: float | None = None,
    grounding_threshold: float = 0.5,
    reliability_floor: Reliability = Reliability.CORROBORATED,
) -> VerificationLedger:
    """P1 — the per-action verification ledger. Pure. Every claim that reaches
    here is recorded with an explicit modelling state and verification status;
    nothing is dropped. Coverage is verified / eligible over the LOAD-BEARING
    eligible population only (`_COVERAGE_BASIS`)."""
    evidence_by_claim = {e.claim_id: e for e in evidence}
    floor_rank = _RELIABILITY_RANK[reliability_floor]

    rows = [
        _verify_one_claim(
            c, evidence_by_claim.get(c.id), predicate_result,
            clause_match, grounding_score, grounding_threshold, floor_rank,
        )
        for c in claims
    ]

    def n(pred) -> int:
        return sum(1 for r in rows if pred(r))

    lb_eligible = [r for r in rows if r.load_bearing and r.verification_eligible]
    verified_lb = sum(1 for r in lb_eligible if r.verification_status is VerificationStatus.VERIFIED)
    denom = len(lb_eligible)
    coverage = VerificationCoverage(
        verified=verified_lb,
        eligible=denom,
        value=(round(verified_lb / denom, 6) if denom else None),
        basis=_COVERAGE_BASIS,
        n_a=(denom == 0),
    )

    return VerificationLedger(
        claims_extracted=len(rows),
        claims_modelled=n(lambda r: r.modelling_state is ModellingState.MODELLED),
        claims_unmodelled=n(lambda r: r.modelling_state is ModellingState.UNMODELLED),
        load_bearing_claims=n(lambda r: r.load_bearing),
        verification_eligible_claims=n(lambda r: r.verification_eligible),
        verified_claims=n(lambda r: r.verification_status is VerificationStatus.VERIFIED),
        contradicted_claims=n(lambda r: r.verification_status is VerificationStatus.CONTRADICTED),
        unverified_claims=n(lambda r: r.verification_status is VerificationStatus.UNVERIFIED),
        unavailable_claims=n(lambda r: r.verification_status is VerificationStatus.UNAVAILABLE),
        coverage=coverage,
        claims=rows,
    )


def resolved_verification_ledger(decision: Decision) -> VerificationLedger | None:
    """P1 — the ledger for a Decision, computed if `decide()` did not attach
    one. `decide()` fills `decision.verification_ledger` for the normal path;
    the operational-failure path in intercept.py (SourceUnavailable /
    AmbiguousPolicyState) builds a Decision directly with no evidence
    resolved — this reconstructs the all-UNAVAILABLE ledger from the facts
    that decision *did* record, without that path having to import anything.
    Returns None only when there is nothing to describe (no claims)."""
    if decision.verification_ledger is not None:
        return decision.verification_ledger
    if not decision.claims:
        return None
    trace = decision.predicate_trace or {}
    predicate_result = {k: v for k, v in trace.items() if type(v) is bool}
    return build_verification_ledger(
        decision.claims,
        decision.evidence,
        predicate_result,
        clause_match=trace.get("clause_match"),
        grounding_score=trace.get("grounding_score"),
    )


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

        if ev is None:
            unverifiable = True
            reasons.append(
                Reason(rule=f"{claim.kind.value}_resolved", expected="a value", observed=None, passed=False)
            )
            continue

        is_unreliable = _RELIABILITY_RANK.get(ev.reliability_class, 0) < floor_rank
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
            if predicate_field not in predicate_result or passed is None:
                unverifiable = True
                reasons.append(
                    Reason(
                        rule=f"{predicate_field}_available",
                        expected="boolean",
                        observed=None,
                        passed=False,
                        policy_version=manifest_id,
                    )
                )
                continue
            if type(passed) is not bool:
                unverifiable = True
                reasons.append(
                    Reason(
                        rule=f"{predicate_field}_available",
                        expected="boolean",
                        observed=type(passed).__name__,
                        passed=False,
                        policy_version=manifest_id,
                    )
                )
                continue
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

    # P1 — the explicit claim lifecycle + verification-coverage ledger.
    # Descriptive only: computed from the same facts the verdict used, it does
    # not feed back into verdict or intervention (docs/verification-coverage.md).
    ledger = build_verification_ledger(
        claims,
        evidence,
        predicate_result,
        clause_match=clause_match,
        grounding_score=grounding_score,
        grounding_threshold=grounding_threshold,
        reliability_floor=reliability_floor,
    )

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
        verification_ledger=ledger,
    )


__all__ = [
    "decide",
    "idempotency_key_for",
    "build_verification_ledger",
    "resolved_verification_ledger",
]
