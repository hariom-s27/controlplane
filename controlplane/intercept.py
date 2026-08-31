"""S3 — the interception boundary, now wired to S4-S11 (S10's own milestone
line: `python -m agents.servicing_agent` with CP_GATE=on prints a verdict
and decisions.jsonl gains a signed receipt).

D2/D27: a Python function boundary is a legitimate interception point —
Portkey and LiteLLM only hook LLM-request lifecycles, neither fires on a
structured tool call.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from controlplane.decide import decide
from controlplane.errors import SourceUnavailable
from controlplane.extract import build_claims, extract_action
from controlplane.idempotency import execute_once
from controlplane.ladder import classify_claims
from controlplane.manifest import load_manifest
from controlplane.registry import resolve_all
from controlplane.schema import ClaimKind, Compensability, Decision, Intervention, Reason, SessionContext, Verdict
from controlplane.telemetry import record

REGISTRY: dict[str, Callable[..., Any]] = {}


class Blocked(Exception):
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        super().__init__(f"BLOCK: {decision.verdict.value} — {[r.rule for r in decision.reasons if not r.passed]}")


class Pending(Exception):
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        super().__init__(f"ESCALATE: {decision.verdict.value}")


def register_tool(name: str, impl: Callable[..., Any]) -> None:
    REGISTRY[name] = impl


def _build_predicate_evidence_servicing(evidence: list, session: SessionContext) -> dict:
    """Assembles the shape controlplane/predicates/graphs/servicing.json
    expects from the flat Evidence list resolve_all() returns. This
    mapping — which ClaimKind's resolved value becomes which evidence key —
    is the one place that knowledge lives."""
    by_kind = {}
    for claim, e in evidence:
        by_kind[claim.kind] = e

    out: dict[str, Any] = {"session": {"customer_id": session.customer_id}}
    if ClaimKind.WITHIN_REFUND_WINDOW in by_kind:
        out["delivered_at"] = by_kind[ClaimKind.WITHIN_REFUND_WINDOW].value
    if ClaimKind.AMOUNT_WITHIN_AUTHORITY in by_kind:
        out["authority_ceiling_paise"] = by_kind[ClaimKind.AMOUNT_WITHIN_AUTHORITY].value
    order: dict[str, Any] = {}
    if ClaimKind.ORDER_BELONGS_TO_CUSTOMER in by_kind:
        order["customer_id"] = by_kind[ClaimKind.ORDER_BELONGS_TO_CUSTOMER].value
    if ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER in by_kind:
        order["amount_paise"] = by_kind[ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER].value
    if ClaimKind.ORDER_ATTRIBUTES_MATCH in by_kind:
        attrs = by_kind[ClaimKind.ORDER_ATTRIBUTES_MATCH].value or {}
        order["item_colour"] = attrs.get("colour")
        order["item_category"] = attrs.get("category")
    out["order"] = order
    from controlplane.registry.clock import today

    out["clock"] = {"today": today().isoformat()}
    return out


def _build_predicate_evidence_knowledge_assistant(evidence: list, session: SessionContext) -> dict:
    """Assembles the shape controlplane/predicates/graphs/knowledge_assistant.json
    expects. Both fields are already-resolved booleans from
    controlplane/registry/entitlements.py — the predicate here mostly names
    them, it doesn't derive anything new, unlike servicing's date arithmetic."""
    by_kind = {c.kind: e for c, e in evidence}
    out: dict[str, Any] = {}
    if ClaimKind.DOC_CLASSIFICATION_PERMITTED in by_kind:
        out["classification_permitted"] = by_kind[ClaimKind.DOC_CLASSIFICATION_PERMITTED].value
    if ClaimKind.RECIPIENT_ENTITLED_TO_DOC in by_kind:
        out["recipient_entitled"] = by_kind[ClaimKind.RECIPIENT_ENTITLED_TO_DOC].value
    return out


_EVIDENCE_BUILDER_FOR_MANIFEST = {
    "servicing": _build_predicate_evidence_servicing,
    "knowledge_assistant": _build_predicate_evidence_knowledge_assistant,
}


def _source_unavailable_decision(action, claims: list, session: SessionContext, manifest: dict) -> Decision:
    """Translate a typed resolver outage through the manifest's fail posture."""

    decision = decide(
        trace_id=session.trace_id,
        manifest_id=manifest["manifest_id"],
        action=action,
        claims=claims,
        evidence=[],
        predicate_result={},
        manifest=manifest,
    )
    posture_key = (
        "non_compensable"
        if decision.compensation.compensability is Compensability.NOT
        else "compensable"
    )
    posture = manifest.get("fail_posture", {}).get(posture_key, "closed")
    decision.verdict = Verdict.UNVERIFIABLE
    decision.intervention = Intervention.ALLOW if posture == "open" else Intervention.BLOCK
    decision.reasons = [
        Reason(
            rule="authoritative_source_available",
            expected=True,
            observed=False,
            passed=False,
            policy_version=manifest["manifest_id"],
        )
    ]
    decision.root_cause = "authoritative_source_unavailable"
    return decision


def _run_gate(name: str, args: dict[str, Any], session: SessionContext, justification: str, retrieved_chunks: list[str]) -> tuple[Decision, dict[str, float]]:
    latency_ms: dict[str, float] = {}

    t0 = time.perf_counter()
    action = extract_action(tool=name, tool_call_args=args, justification=justification, retrieved_chunks=retrieved_chunks)
    latency_ms["extract"] = round((time.perf_counter() - t0) * 1000, 2)

    t0 = time.perf_counter()
    claims = classify_claims(build_claims(action))
    latency_ms["classify"] = round((time.perf_counter() - t0) * 1000, 2)

    manifest = load_manifest(os.environ.get("CP_MANIFEST", "servicing"))

    t0 = time.perf_counter()
    try:
        resolved = [(c, e) for c, e in zip(claims, resolve_all(claims, session, manifest, action))]
    except SourceUnavailable:
        latency_ms["resolve"] = round((time.perf_counter() - t0) * 1000, 2)
        decision = _source_unavailable_decision(action, claims, session, manifest)
        record(decision, action.facts_for_predicate(), latency_ms)
        return decision, latency_ms
    latency_ms["resolve"] = round((time.perf_counter() - t0) * 1000, 2)
    evidence = [e for _, e in resolved]

    t0 = time.perf_counter()
    build_evidence = _EVIDENCE_BUILDER_FOR_MANIFEST[manifest["_name"]]
    predicate_evidence = build_evidence(resolved, session)
    predicate_out = evaluate_predicates(predicate_evidence, action, manifest)
    latency_ms["predicate"] = round((time.perf_counter() - t0) * 1000, 2)

    clause_match = None
    for claim, e in resolved:
        if claim.kind is ClaimKind.POLICY_CLAUSE_CURRENT:
            from controlplane.predicates import clause_matches_claim

            clause_match = clause_matches_claim(claim, e)

    grounding_score = None
    if os.environ.get("CP_GROUNDING", "off") == "on":
        t0 = time.perf_counter()
        try:
            from controlplane import ground

            for claim, e in resolved:
                if claim.kind is ClaimKind.CLAUSE_SEMANTICS_MATCH and action.claimed_clause_text:
                    grounding_score = ground.score(premise=str(e.value), hypothesis=action.claimed_clause_text)
        except ImportError:
            pass  # torch/transformers not installed — decide() treats this as "no C3 signal"
        ground_ms = round((time.perf_counter() - t0) * 1000, 2)
        if grounding_score is not None:
            latency_ms["ground"] = ground_ms

    t0 = time.perf_counter()
    decision = decide(
        trace_id=session.trace_id,
        manifest_id=manifest["manifest_id"],
        action=action,
        claims=claims,
        evidence=evidence,
        predicate_result=predicate_out["result"],
        manifest=manifest,
        clause_match=clause_match,
        grounding_score=grounding_score,
    )
    latency_ms["decide"] = round((time.perf_counter() - t0) * 1000, 2)

    record(decision, action.facts_for_predicate(), latency_ms)
    return decision, latency_ms


def evaluate_predicates(evidence: dict, action, manifest: dict) -> dict:
    from controlplane.predicates import evaluate

    return evaluate(evidence, action, manifest)


def _execute_governed_once(impl: Callable[..., Any], call_args: dict[str, Any], decision: Decision) -> Any:
    outcome = execute_once(decision.idempotency_key, lambda: impl(**call_args))
    return outcome.result


def dispatch_tool(name: str, args: dict[str, Any], session: SessionContext, justification: str = "", retrieved_chunks: list[str] | None = None) -> Any:
    impl = REGISTRY[name]
    if not session.gate_enabled:
        return impl(**args)

    decision, _ = _run_gate(name, args, session, justification, retrieved_chunks or [])

    if decision.intervention is Intervention.ALLOW:
        return _execute_governed_once(impl, args, decision)
    if decision.intervention is Intervention.MODIFY:
        if decision.modified_args is None:
            raise Pending(decision)
        return _execute_governed_once(impl, decision.modified_args, decision)
    if decision.intervention is Intervention.BLOCK:
        raise Blocked(decision)
    if decision.intervention is Intervention.ESCALATE:
        raise Pending(decision)
    raise AssertionError(f"unhandled intervention {decision.intervention!r}")  # OBSERVE_ONLY: not used by this demo


__all__ = ["REGISTRY", "register_tool", "dispatch_tool", "Blocked", "Pending"]
