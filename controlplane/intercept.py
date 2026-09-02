"""S3 — the interception boundary, wired to S4-S11: a governed tool call in
with CP_GATE=on, a verdict out, and decisions.jsonl gains a signed receipt.

D2/D27: a Python function boundary is a legitimate interception point —
Portkey and LiteLLM only hook LLM-request lifecycles, neither fires on a
structured tool call.

P02: this file is use-case agnostic. It loads whatever manifest CP_MANIFEST
names, builds claims and the predicate payload from that manifest's
``claim_bindings`` (controlplane/bindings.py), and never branches on which
use case is running. Adding a use case is a new file in ``manifests/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Callable

from controlplane.bindings import build_predicate_payload, claim_specs
from controlplane.compensation import compensation_for
from controlplane.decide import decide, idempotency_key_for
from controlplane.errors import AmbiguousPolicyState, SourceUnavailable
from controlplane.extract import build_claims, extract_action
from controlplane.escalation import enqueue_pending, escalation_budget_exhausted, record_budget_exhaustion
from controlplane.idempotency import execute_once
from controlplane.ladder import classify_claims
from controlplane.manifest import active_fail_posture, load_manifest
from controlplane.registry import resolve_bindings
from controlplane.schema import (
    ClaimKind,
    Decision,
    FailureContext,
    Intervention,
    ProposedAction,
    Reason,
    SessionContext,
    Verdict,
)
from controlplane.telemetry import record

REGISTRY: dict[str, Callable[..., Any]] = {}
_LOG = logging.getLogger("controlplane.data_quality")


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


def _active_manifest() -> dict:
    name = os.environ.get("CP_MANIFEST")
    if not name:
        raise RuntimeError(
            "CP_MANIFEST is not set. The gate does not assume a use case — the "
            "calling agent must name its manifest (see agents/*.py)."
        )
    return load_manifest(name)


def _operational_decision(
    *,
    action: ProposedAction,
    claims: list,
    session: SessionContext,
    manifest: dict,
    failure: SourceUnavailable | AmbiguousPolicyState,
    idempotency_key_override: str | None,
) -> Decision:
    """Build a signed, explicit decision for a typed operational failure."""

    comp = compensation_for(manifest)
    key = idempotency_key_override or idempotency_key_for(session.trace_id, action)

    if isinstance(failure, SourceUnavailable):
        risk_tier, posture = active_fail_posture(manifest)
        intervention = Intervention.ALLOW if posture == "open" else Intervention.BLOCK
        outcome = "permitted" if posture == "open" else "blocked"
        return Decision(
            trace_id=session.trace_id,
            manifest_id=manifest["manifest_id"],
            verdict=Verdict.UNVERIFIABLE,
            intervention=intervention,
            reasons=[Reason(
                rule="authoritative_source_available",
                expected=True,
                observed=False,
                passed=False,
                policy_version=manifest["manifest_id"],
            )],
            claims=claims,
            compensation=comp,
            idempotency_key=key,
            root_cause="authoritative_source_unavailable",
            verification_state="unverified",
            failure_context=FailureContext(
                kind="source_unavailable",
                source=failure.source,
                stage="resolve",
                risk_tier=risk_tier,
                fail_posture=posture,
                posture_outcome=outcome,
                detail=failure.operation,
            ),
            component_status={
                "authoritative_source": {
                    "status": "unavailable",
                    "source": failure.source,
                    "operation": failure.operation,
                },
                "execution": {"status": "permitted" if posture == "open" else "blocked"},
            },
        )

    _LOG.error(
        "data-quality event: policy_id=%s current_row_count=%s",
        failure.policy_id,
        failure.row_count,
    )
    risk_tier, _configured_posture = active_fail_posture(manifest)
    return Decision(
        trace_id=session.trace_id,
        manifest_id=manifest["manifest_id"],
        verdict=Verdict.SOURCE_UNRELIABLE,
        intervention=Intervention.BLOCK,
        reasons=[Reason(
            rule="current_policy_row_cardinality",
            expected=1,
            observed=failure.row_count,
            passed=False,
            policy_version=manifest["manifest_id"],
        )],
        claims=claims,
        compensation=comp,
        idempotency_key=key,
        root_cause="ambiguous_current_policy_state",
        verification_state="unverified",
        failure_context=FailureContext(
            kind="ambiguous_policy_state",
            source="policy_store.db",
            stage="resolve",
            risk_tier=risk_tier,
            fail_posture="closed",
            posture_outcome="blocked",
            detail=f"policy_id={failure.policy_id}; current_row_count={failure.row_count}",
        ),
        component_status={
            "data_quality": {
                "status": "detected",
                "policy_id": failure.policy_id,
                "current_row_count": failure.row_count,
                "expected_current_row_count": 1,
            },
            "execution": {"status": "blocked"},
        },
    )


def _run_gate(
    name: str,
    args: dict[str, Any],
    session: SessionContext,
    justification: str,
    retrieved_chunks: list[str],
    idempotency_key_override: str | None = None,
) -> tuple[Decision, dict[str, float], dict]:
    # P09: end_to_end spans every governed stage below (extract -> receipt),
    # started here so harness/agent per-call setup is not counted. The 6
    # in-pipeline stages are timed with their own perf_counter blocks; the
    # returned timing dict additionally carries "receipt" and "end_to_end",
    # which are only knowable after the signed receipt exists and so are
    # attached to a fresh dict — never mutated into the receipt's own copy.
    gate_t0 = time.perf_counter()
    latency_ms: dict[str, float] = {}

    t0 = time.perf_counter()
    action = extract_action(tool=name, tool_call_args=args, justification=justification, retrieved_chunks=retrieved_chunks)
    latency_ms["extract"] = round((time.perf_counter() - t0) * 1000, 2)

    manifest = _active_manifest()
    if action.tool != manifest.get("tool"):
        raise KeyError(
            f"tool {action.tool!r} is not governed by manifest {manifest['_name']!r} "
            f"(which governs {manifest.get('tool')!r}). A tool with no manifest must "
            "fail loudly, never sail through as VERIFIED/ALLOW."
        )
    specs = claim_specs(manifest)

    t0 = time.perf_counter()
    claims = classify_claims(build_claims(action, manifest))
    latency_ms["classify"] = round((time.perf_counter() - t0) * 1000, 2)

    t0 = time.perf_counter()
    try:
        resolved = list(zip(claims, resolve_bindings(claims, specs, session, manifest, action)))
    except (SourceUnavailable, AmbiguousPolicyState) as failure:
        latency_ms["resolve"] = round((time.perf_counter() - t0) * 1000, 2)
        decision = _operational_decision(
            action=action,
            claims=claims,
            session=session,
            manifest=manifest,
            failure=failure,
            idempotency_key_override=idempotency_key_override,
        )
        r0 = time.perf_counter()
        envelope = record(decision, action.facts_for_predicate(), latency_ms)
        return decision, _with_totals(latency_ms, r0, gate_t0), envelope["receipt"]
    latency_ms["resolve"] = round((time.perf_counter() - t0) * 1000, 2)
    evidence = [e for _, e in resolved]

    t0 = time.perf_counter()
    predicate_evidence = build_predicate_payload(manifest, resolved, action=action, session=session)
    predicate_out = evaluate_predicates(predicate_evidence, action, manifest)
    latency_ms["predicate"] = round((time.perf_counter() - t0) * 1000, 2)
    component_status: dict[str, Any] = {}
    unavailable_predicates = predicate_out.get("trace", {}).get("unavailable_predicates")
    if unavailable_predicates:
        component_status["predicate"] = {
            "status": "partial",
            "unavailable": unavailable_predicates,
        }

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
        except TimeoutError:
            # P08: C3 is optional coverage. Its timeout must not erase the
            # C1/C2 decision; unrelated grounding exceptions remain loud.
            component_status["C3"] = {
                "status": "unavailable",
                "reason": "timeout",
            }
        ground_ms = round((time.perf_counter() - t0) * 1000, 2)
        if grounding_score is not None:
            latency_ms["ground"] = ground_ms
            component_status["C3"] = {"status": "available"}
        elif "C3" in component_status:
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

    # decide() stays a pure function of record facts (hard constraint #4,
    # tests/test_no_protected_attributes.py). Operational context — which
    # components degraded, and any caller-supplied idempotency key — is
    # attached to the Decision here, at the I/O boundary, not passed through
    # the pure core.
    decision.component_status = component_status
    if idempotency_key_override:
        decision.idempotency_key = idempotency_key_override

    r0 = time.perf_counter()
    envelope = record(decision, action.facts_for_predicate(), latency_ms)
    return decision, _with_totals(latency_ms, r0, gate_t0), envelope["receipt"]


def _with_totals(
    latency_ms: dict[str, float], receipt_t0: float, gate_t0: float
) -> dict[str, float]:
    """Return a NEW timing dict = the per-stage timings plus ``receipt`` (build
    + sign + persist) and ``end_to_end``. A fresh dict is essential: the signed
    receipt holds a reference to ``latency_ms`` and its HMAC is already fixed,
    so these two after-the-fact totals must never land in that object."""
    now = time.perf_counter()
    return {
        **latency_ms,
        "receipt": round((now - receipt_t0) * 1000, 2),
        "end_to_end": round((now - gate_t0) * 1000, 2),
    }


def evaluate_predicates(evidence: dict, action, manifest: dict) -> dict:
    from controlplane.predicates import evaluate

    return evaluate(evidence, action, manifest)


def _fallback_execution_key(name: str, args: dict[str, Any], session: SessionContext) -> str:
    payload = json.dumps(
        {"trace_id": session.trace_id, "tool": name, "args": args},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _execute_governed_once(
    *,
    impl: Callable[..., Any],
    call_args: dict[str, Any],
    decision: Decision,
    name: str,
    session: SessionContext,
) -> Any:
    key = decision.idempotency_key or _fallback_execution_key(name, call_args, session)
    outcome = execute_once(key, lambda: impl(**call_args))
    if (
        not outcome.replayed
        and decision.failure_context is not None
        and decision.failure_context.kind == "source_unavailable"
    ):
        completed = decision.model_copy(deep=True)
        completed.failure_context = completed.failure_context.model_copy(
            update={"posture_outcome": "executed"}
        )
        completed.component_status = {
            **completed.component_status,
            "execution": {"status": "executed"},
        }
        record(completed, {"tool": name, **call_args}, {})
    if outcome.replayed:
        replay = decision.model_copy(deep=True)
        replay.idempotency_key = key
        replay.failure_context = FailureContext(
            kind="idempotent_replay",
            stage="execute",
            posture_outcome="replay",
            detail="completed result returned without re-executing the action",
        )
        replay.component_status = {
            **replay.component_status,
            "execution": {
                "status": "duplicate_suppressed",
                "reason": "completed_result_replayed",
            },
        }
        record(replay, {"tool": name, **call_args}, {})
    return outcome.result


def dispatch_tool(
    name: str,
    args: dict[str, Any],
    session: SessionContext,
    justification: str = "",
    retrieved_chunks: list[str] | None = None,
    idempotency_key: str | None = None,
) -> Any:
    impl = REGISTRY[name]
    if not session.gate_enabled:
        return impl(**args)

    if idempotency_key is None:
        decision, _, receipt = _run_gate(name, args, session, justification, retrieved_chunks or [])
    else:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty")
        decision, _, receipt = _run_gate(
            name,
            args,
            session,
            justification,
            retrieved_chunks or [],
            idempotency_key_override=idempotency_key,
        )

    if decision.intervention is Intervention.ALLOW:
        return _execute_governed_once(
            impl=impl, call_args=args, decision=decision, name=name, session=session
        )
    if decision.intervention is Intervention.MODIFY:
        # A MODIFY verdict whose modified_args never got populated (or was
        # corrupted into a non-mapping) must never silently fall back to the
        # original, unmodified args — that would execute exactly the call
        # MODIFY was raised to prevent. Hold it as Pending instead.
        if not isinstance(decision.modified_args, dict):
            raise Pending(decision)
        return _execute_governed_once(
            impl=impl,
            call_args=decision.modified_args,
            decision=decision,
            name=name,
            session=session,
        )
    if decision.intervention is Intervention.BLOCK:
        raise Blocked(decision)
    if decision.intervention is Intervention.ESCALATE:
        manifest = _active_manifest()
        if escalation_budget_exhausted(decision, manifest):
            risk_tier, posture = active_fail_posture(manifest)
            record_budget_exhaustion(
                decision, receipt, risk_tier=risk_tier, fail_posture=posture
            )
            if posture == "open":
                return _execute_governed_once(
                    impl=impl, call_args=args, decision=decision, name=name, session=session
                )
            raise Blocked(decision)
        queued = enqueue_pending(decision, receipt)
        return {"status": "pending", "queue_id": queued["queue_id"], "trace_id": decision.trace_id}
    raise AssertionError(f"unhandled intervention {decision.intervention!r}")  # OBSERVE_ONLY: not used by this demo


__all__ = ["REGISTRY", "register_tool", "dispatch_tool", "Blocked", "Pending"]
