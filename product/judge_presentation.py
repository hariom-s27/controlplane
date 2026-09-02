"""PRODUCT-02 — the shared presentation model for the Evidence Passport and
Decision Inspector, built over PRODUCT-01's actual result
(scripts/judge_demo.py::ScenarioResult / ScenarioResult.receipt).

This module performs NO governance work. It reads fields already computed by
the real engine (controlplane/intercept.py::dispatch_tool -> decide() ->
controlplane/receipt.py::build_receipt) off an already-produced
ScenarioResult and reshapes them into one structured, judge-readable
representation. Evidence Passport and Decision Inspector
(product/judge_views.py) both consume this SAME representation — neither
re-derives evidence, claims, policy, or the verdict independently.

Where a field is genuinely absent from the underlying result, this module
reports NOT_AVAILABLE. It never infers, guesses, or defaults a value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from controlplane.receipt import verify as verify_receipt

NOT_AVAILABLE = "NOT AVAILABLE"

# ---------------------------------------------------------------------------
# Claim -> evidence semantic comparison
# ---------------------------------------------------------------------------
#
# Only these two ClaimKinds have a claim.asserted_value and an evidence.value
# that are the same fact observed from two sources (the agent's assertion vs.
# the system of record) — see CLAUDE.md's own example ("for every other
# kind, e.g. ORDER_BELONGS_TO_CUSTOMER, asserted_value is a different field
# by design") and controlplane/predicates/__init__.py::clause_matches_claim's
# docstring. The POLICY_CLAUSE_CURRENT rule below is the exact rule
# clause_matches_claim implements (re-derived here from the receipt's plain
# dict fields, since clause_matches_claim itself takes live Claim/Evidence
# objects this module does not reconstruct) — not a second, different rule.
NO_DIRECT_COMPARISON = "NO DIRECT COMPARISON"
MATCH = "MATCH"
CONFLICT = "CONFLICT"
UNAVAILABLE = "UNAVAILABLE"

_EXACT_MATCH_KINDS = {"within_refund_window", "policy_clause_current"}


@dataclass(frozen=True)
class ClaimEvidenceComparison:
    claim_kind: str
    claim_field: str
    evidence_field: str
    comparison_rule: str
    comparison_result: str
    asserted_value: Any
    evidence_value: Any


def _compare_claim_to_evidence(claim: dict, evidence: dict | None) -> ClaimEvidenceComparison:
    kind = claim.get("kind", NOT_AVAILABLE)
    asserted = claim.get("asserted")
    ev_value = evidence.get("value") if evidence is not None else None
    claim_field = f"{kind}.asserted"
    evidence_field = f"{evidence.get('claim_id')}.value" if evidence is not None else NOT_AVAILABLE

    if kind not in _EXACT_MATCH_KINDS:
        return ClaimEvidenceComparison(
            claim_kind=kind, claim_field=claim_field, evidence_field=evidence_field,
            comparison_rule=NO_DIRECT_COMPARISON, comparison_result=NO_DIRECT_COMPARISON,
            asserted_value=asserted, evidence_value=ev_value,
        )

    rule = "exact-date comparison" if kind == "within_refund_window" else "clause-version match"
    if evidence is None:
        result = UNAVAILABLE
    elif asserted is None:
        # No assertion was made — clause_matches_claim's own contract:
        # nothing to contradict, not a mismatch.
        result = UNAVAILABLE
    elif str(asserted) == str(ev_value):
        result = MATCH
    else:
        result = CONFLICT
    return ClaimEvidenceComparison(
        claim_kind=kind, claim_field=claim_field, evidence_field=evidence_field,
        comparison_rule=rule, comparison_result=result,
        asserted_value=asserted, evidence_value=ev_value,
    )


# ---------------------------------------------------------------------------
# Evidence item
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    claim_id: str
    source: str
    field: str  # the evidence's own claim_id, doubling as the payload field name
    query: str
    value: Any
    reliability: str
    freshness_ms: Any  # int, or NOT_AVAILABLE


def _evidence_item(e: dict) -> EvidenceItem:
    return EvidenceItem(
        claim_id=e.get("claim_id", NOT_AVAILABLE),
        source=e.get("source") or NOT_AVAILABLE,
        field=e.get("claim_id", NOT_AVAILABLE),
        query=e.get("query") or NOT_AVAILABLE,
        value=e.get("value"),
        reliability=e.get("reliability_class") or NOT_AVAILABLE,
        freshness_ms=e.get("freshness_ms", NOT_AVAILABLE),
    )


# ---------------------------------------------------------------------------
# Execution state
# ---------------------------------------------------------------------------
#
# Derived from the ALREADY-COMPUTED, real try/except outcome captured by
# scripts/judge_demo.py::_run_dispatch (status is set to "BLOCKED" only when
# dispatch_tool() actually raised Blocked, "PENDING" only when it actually
# raised Pending — see that function). Never inferred from verdict alone.

EXECUTED = "EXECUTED"
PREVENTED = "PREVENTED"
REFUSED = "REFUSED"
REPLAYED = "REPLAYED"
NOT_EXECUTED = "NOT_EXECUTED"


def _execution_state(execution_status: str, call_count: str) -> str:
    if execution_status == "BLOCKED":
        return PREVENTED
    if execution_status.startswith("REFUSED"):
        return REFUSED
    if execution_status == "EXECUTED":
        return EXECUTED if call_count not in ("0", "") else NOT_EXECUTED
    if execution_status == "PENDING":
        return NOT_EXECUTED
    if "executed=True" in execution_status and "executed=False" in execution_status:
        # scenario 6's two-call replay: first call actually executed, the
        # second was suppressed by the real idempotency ledger.
        return REPLAYED
    return execution_status or NOT_AVAILABLE


# ---------------------------------------------------------------------------
# Receipt verification
# ---------------------------------------------------------------------------

VERIFIED = "VERIFIED"
TAMPERED = "TAMPERED"
VERIFICATION_ERROR = "VERIFICATION ERROR"
MISMATCH = "RECEIPT / RESULT MISMATCH"


def classify_receipt(receipt: dict | None, *, expected_verdict: str | None,
                      expected_intervention: str | None) -> str:
    """Uses controlplane.receipt.verify() — the existing, real verifier.
    Never treats a receipt as VERIFIED merely because it exists."""
    if receipt is None:
        return NOT_AVAILABLE
    try:
        signature_ok = verify_receipt(receipt)
    except Exception:
        return VERIFICATION_ERROR
    if not signature_ok:
        return TAMPERED
    if expected_verdict is not None and receipt.get("verdict") != expected_verdict:
        return MISMATCH
    if expected_intervention is not None and receipt.get("intervention") != expected_intervention:
        return MISMATCH
    return VERIFIED


# ---------------------------------------------------------------------------
# The shared presentation model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PresentationModel:
    scenario: str
    profile: str
    available: bool
    unavailable_reason: str
    ai_intent: str
    proposed_action: Any
    claims: list[dict]
    evidence: list[EvidenceItem]
    claim_evidence_comparisons: list[ClaimEvidenceComparison]
    policy_version: str
    predicate_result: Any
    verdict: str
    intervention: str
    root_cause: str
    execution_state: str
    execution_status_raw: str
    idempotency_key: str
    receipt_reference: str
    receipt_verification: str
    runtime_latency_ms: Any
    evidence_origin: str
    trace_id: str
    unavailable_fields: frozenset[str] = field(default_factory=frozenset)


_ORIGIN_MAP = {"RUNTIME": "RUNTIME", "FIXTURE": "FIXTURE", "N/A": NOT_AVAILABLE}


def build_presentation_model(result: Any) -> PresentationModel:
    """Build the shared presentation model from an already-produced
    scripts.judge_demo.ScenarioResult. Performs no dispatch, no decide(),
    no evidence resolution, no receipt generation — pure reshaping of
    fields the real engine already computed."""
    unavailable: set[str] = set()

    if not result.available:
        return PresentationModel(
            scenario=result.title, profile=NOT_AVAILABLE, available=False,
            unavailable_reason=result.unavailable_reason, ai_intent=NOT_AVAILABLE,
            proposed_action=NOT_AVAILABLE, claims=[], evidence=[],
            claim_evidence_comparisons=[], policy_version=NOT_AVAILABLE,
            predicate_result=NOT_AVAILABLE, verdict=NOT_AVAILABLE, intervention=NOT_AVAILABLE,
            root_cause=NOT_AVAILABLE, execution_state=NOT_AVAILABLE, execution_status_raw=NOT_AVAILABLE,
            idempotency_key=NOT_AVAILABLE, receipt_reference=NOT_AVAILABLE,
            receipt_verification=NOT_AVAILABLE, runtime_latency_ms=NOT_AVAILABLE,
            evidence_origin=NOT_AVAILABLE, trace_id=NOT_AVAILABLE,
            unavailable_fields=frozenset({
                "profile", "ai_intent", "proposed_action", "claims", "evidence", "policy_version",
                "predicate_result", "verdict", "intervention", "root_cause", "execution_state",
                "idempotency_key", "receipt_reference", "receipt_verification", "runtime_latency_ms",
                "evidence_origin", "trace_id",
            }),
        )

    receipt = result.receipt or {}
    if not receipt:
        unavailable.add("receipt")

    raw_claims = receipt.get("claims", [])
    raw_evidence = receipt.get("evidence", [])
    evidence_items = [_evidence_item(e) for e in raw_evidence]
    # Positional pairing: intercept.py's own real pipeline builds `claims`
    # and its resolved evidence in lockstep (`zip(claims, resolve_bindings(...))`)
    # and decide() receives both lists unchanged — the receipt's claims[i]
    # and evidence[i] are the same pairing the real engine already
    # established, not a name/label-based guess.
    comparisons = [
        _compare_claim_to_evidence(c, raw_evidence[i] if i < len(raw_evidence) else None)
        for i, c in enumerate(raw_claims)
    ]

    # The receipt's own latency_ms carries real per-stage timings (extract,
    # classify, resolve, predicate, decide) — record() persists the receipt
    # before the caller's end_to_end/receipt-signing totals exist
    # (controlplane/intercept.py::_run_gate computes those only in its
    # return tuple, after record() has already run), so "end_to_end" is
    # never present here. Report the real per-stage dict as-is rather than
    # fabricating a total that was never actually measured for this call.
    latency = receipt.get("latency_ms") or {}
    runtime_latency = dict(latency) if isinstance(latency, dict) and latency else None
    if runtime_latency is None:
        unavailable.add("runtime_latency_ms")

    policy_version = receipt.get("manifest_id") or NOT_AVAILABLE
    if policy_version == NOT_AVAILABLE:
        unavailable.add("policy_version")

    idempotency_key = receipt.get("idempotency_key") or NOT_AVAILABLE
    receipt_reference = receipt.get("receipt_id") or NOT_AVAILABLE
    root_cause = receipt.get("root_cause") or NOT_AVAILABLE
    trace_id = receipt.get("trace_id") or NOT_AVAILABLE

    verification = classify_receipt(
        result.receipt, expected_verdict=result.verdict, expected_intervention=result.intervention,
    )

    origin = _ORIGIN_MAP.get(result.evidence_source, NOT_AVAILABLE)
    if origin == NOT_AVAILABLE:
        unavailable.add("evidence_origin")

    return PresentationModel(
        scenario=result.title,
        profile=policy_version,
        available=True,
        unavailable_reason="",
        ai_intent=result.ai_intent or NOT_AVAILABLE,
        proposed_action=receipt.get("action", NOT_AVAILABLE),
        claims=raw_claims,
        evidence=evidence_items,
        claim_evidence_comparisons=comparisons,
        policy_version=policy_version,
        predicate_result=receipt.get("predicate_trace", NOT_AVAILABLE),
        verdict=result.verdict or NOT_AVAILABLE,
        intervention=result.intervention or NOT_AVAILABLE,
        root_cause=root_cause,
        execution_state=_execution_state(result.execution_status, result.call_count),
        execution_status_raw=result.execution_status,
        idempotency_key=idempotency_key,
        receipt_reference=receipt_reference,
        receipt_verification=verification,
        runtime_latency_ms=runtime_latency if runtime_latency is not None else NOT_AVAILABLE,
        evidence_origin=origin,
        trace_id=trace_id,
        unavailable_fields=frozenset(unavailable),
    )


def is_stale_for_profile(model: PresentationModel, expected_profile: str) -> bool:
    """True when a model produced under one profile (manifest) is being
    displayed as though it were the result for a different profile — the
    caller must re-RUN the scenario for `expected_profile`, never reuse
    this one."""
    return model.profile != expected_profile
