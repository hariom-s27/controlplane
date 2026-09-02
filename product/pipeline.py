"""Run one real case through the real ControlPlane pipeline and hand back the
full `Decision` + signed receipt (`bench/baselines.py::_run_our_pipeline`
only returns the intervention string, which loses everything a product view
needs). Every call below is imported unchanged from `controlplane/` — see
module docstring for the no-duplication rule this follows.

This mirrors `bench.baselines.LiveQueryStrategy` exactly (B5, the
ControlPlane arm): an independent live query against `orders.db` /
`policy_store.db`, never the agent's own trace. That is the arm the product
is actually shipping, so it is the only one wired here.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from bench.baselines import (
    GOLD_SET,
    POLICY_DB,
    action_from_case,
    cluster_id,
    load_cases,
    session_from_case,
)
from controlplane.bindings import build_predicate_payload, claim_specs
from controlplane.decide import decide
from controlplane.extract import build_claims
from controlplane.idempotency import ExecutionLedger
from controlplane.ladder import classify_claims
from controlplane.manifest import load_manifest
from controlplane.predicates import clause_matches_claim, evaluate
from controlplane.receipt import build_receipt, verify
from controlplane.registry import resolve_bindings
from controlplane.registry.clock import set_clock
from controlplane.schema import Claim, ClaimKind, Decision, Evidence, ProposedAction, SessionContext

ROOT = Path(__file__).resolve().parent.parent
FROZEN_TODAY = "2026-08-14"


@dataclass(frozen=True)
class DecisionBundle:
    case: dict
    action: ProposedAction
    session: SessionContext
    claims: list[Claim]
    evidence: list[Evidence]
    current_policy_version: str | None
    decision: Decision
    receipt: dict
    receipt_valid: bool


def _current_policy_version() -> str | None:
    conn = sqlite3.connect(POLICY_DB)
    try:
        row = conn.execute(
            "SELECT version FROM clauses WHERE policy_id='refund_window' "
            "AND effective_to IS NULL"
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def run_decision(case: dict) -> DecisionBundle:
    """The B5/ControlPlane arm, in full — same call sequence as
    `bench.baselines._run_our_pipeline(case, LiveQueryStrategy())`, just
    returning the whole `Decision` and its signed receipt instead of only
    `decision.intervention.value`."""
    set_clock(date.fromisoformat(FROZEN_TODAY))
    manifest = load_manifest("servicing")
    specs = claim_specs(manifest)
    action = action_from_case(case)
    session = session_from_case(case)

    claims = classify_claims(build_claims(action, manifest))
    evidence = resolve_bindings(claims, specs, session, manifest, action)
    resolved = list(zip(claims, evidence))
    current_version = _current_policy_version()

    payload = build_predicate_payload(manifest, resolved, action=action, session=session)
    payload["authority_ceiling_paise"] = int(manifest["authority_ceiling_paise"])

    try:
        predicate_out = evaluate(payload, action, manifest)["result"]
    except RuntimeError:
        predicate_out = {}

    clause_match = None
    for c, e in resolved:
        if c.kind is ClaimKind.POLICY_CLAUSE_CURRENT:
            clause_match = clause_matches_claim(c, e)

    decision = decide(
        trace_id=session.trace_id, manifest_id=manifest["manifest_id"], action=action,
        claims=claims, evidence=evidence, predicate_result=predicate_out, manifest=manifest,
        clause_match=clause_match, grounding_score=None,
    )
    receipt = build_receipt(decision, action.facts_for_predicate(), decision.latency_ms)
    return DecisionBundle(
        case=case, action=action, session=session, claims=claims, evidence=evidence,
        current_policy_version=current_version, decision=decision, receipt=receipt,
        receipt_valid=verify(receipt),
    )


_CASES_BY_ID: dict[str, dict] | None = None


def case_by_id(case_id: str) -> dict:
    global _CASES_BY_ID
    if _CASES_BY_ID is None:
        _CASES_BY_ID = {c["id"]: c for c in load_cases()}
    if case_id not in _CASES_BY_ID:
        raise KeyError(f"no such gold_set case: {case_id!r} (see bench/gold_set.jsonl)")
    return _CASES_BY_ID[case_id]


def all_case_ids() -> list[str]:
    return [c["id"] for c in load_cases()]


_LEDGER = ExecutionLedger()


def run_with_replay_demo(case_id: str) -> tuple[DecisionBundle, bool]:
    """Run the same case twice through a real `controlplane.idempotency.
    ExecutionLedger` (the identical class `controlplane.intercept` uses,
    same class not same process-global instance) keyed by the case's own
    idempotency_key, to show a genuine at-most-once replay: the second call
    to `execute_once` never re-invokes `_call` and hands back the exact
    first result. Returns (bundle, was_the_second_call_a_replay)."""
    case = case_by_id(case_id)
    first = run_decision(case)
    key = first.decision.idempotency_key or first.decision.trace_id

    def _call():
        return run_decision(case)

    outcome1 = _LEDGER.execute_once(key, _call)
    outcome2 = _LEDGER.execute_once(key, _call)
    return outcome1.result, outcome2.replayed
