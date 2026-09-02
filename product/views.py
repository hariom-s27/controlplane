"""Product views over a real `product.pipeline.DecisionBundle`.

Every field below is read off the actual `Decision`/`Evidence`/`Claim`/
receipt objects produced by the real engine (see `product/pipeline.py`).
Nothing here is a fitted score, a learned model, or a fabricated number —
per MASTER-11-15 section 6D/7: this is the "raw trace-derived signals"
Evidence Health view, explicitly NOT a validated confidence score, since
Task 11 (the research measurement that would validate such a score) was not
executed in this session.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from controlplane.manifest import load_manifest
from controlplane.predicates import clause_matches_claim
from controlplane.registry.clock import now
from controlplane.schema import ClaimKind, Confidence, Reliability

from product.pipeline import DecisionBundle

_MANIFEST = load_manifest("servicing")

# ---------------------------------------------------------------------------
# B. EVIDENCE HEALTH
# ---------------------------------------------------------------------------


def _completeness(bundle: DecisionBundle) -> dict[str, Any]:
    load_bearing = [c for c in bundle.claims if c.load_bearing]
    ev_by_claim = {e.claim_id: e for e in bundle.evidence}
    resolved = [
        c for c in load_bearing
        if (e := ev_by_claim.get(c.id)) is not None and e.confidence != Confidence.NONE
    ]
    return {"resolved": len(resolved), "total": len(load_bearing),
            "label": f"{len(resolved)} / {len(load_bearing)}"}


def _freshness(bundle: DecisionBundle) -> dict[str, Any]:
    """`Evidence.freshness_ms` on every claim here — 0 means the value was
    read from the live store in this same call (see docstring on
    `controlplane.schema.Evidence`), which is the actual freshness
    ControlPlane's live-query arm provides, not a fabricated "fresh" label."""
    values = [e.freshness_ms for e in bundle.evidence]
    max_ms = max(values) if values else None
    state = "CURRENT" if max_ms is not None and max_ms == 0 else (
        "STALE" if max_ms is not None else "MISSING")
    return {"max_freshness_ms": max_ms, "state": state}


_BOUNDARY_CLAIMS = {ClaimKind.WITHIN_REFUND_WINDOW, ClaimKind.AMOUNT_WITHIN_AUTHORITY}


def _predicate_margin(bundle: DecisionBundle) -> dict[str, Any]:
    """Numeric distance-to-boundary for the two claims where the manifest
    defines a numeric threshold (window_days, authority_ceiling_paise).
    Computed only from evidence resolved at decision time + the static
    manifest scalar — no gold label, no A5 verdict, no future information."""
    ev_by_claim = {e.claim_id: e for e in bundle.evidence}
    entries = []
    for c in bundle.claims:
        if c.kind not in _BOUNDARY_CLAIMS:
            continue
        e = ev_by_claim.get(c.id)
        if e is None or e.value is None:
            entries.append({"claim": c.kind.value, "margin": None, "state": "N/A"})
            continue
        if c.kind is ClaimKind.WITHIN_REFUND_WINDOW:
            try:
                delivered = date.fromisoformat(str(e.value))
            except ValueError:
                entries.append({"claim": c.kind.value, "margin": None, "state": "N/A"})
                continue
            elapsed_days = (now().date() - delivered).days
            margin = int(_MANIFEST["window_days"]) - elapsed_days
            state = "NEAR BOUNDARY" if abs(margin) <= 2 else ("EXCEEDED" if margin < 0 else "OK")
            entries.append({"claim": c.kind.value, "margin_days": margin, "state": state})
        elif c.kind is ClaimKind.AMOUNT_WITHIN_AUTHORITY:
            ceiling = int(e.value)
            amount = bundle.action.amount_paise or 0
            margin = ceiling - amount
            pct = margin / ceiling if ceiling else None
            state = "NEAR BOUNDARY" if pct is not None and 0 <= pct < 0.05 else (
                "EXCEEDED" if margin < 0 else "OK")
            entries.append({"claim": c.kind.value, "margin_paise": margin, "state": state})
    worst = "OK"
    for e in entries:
        if e["state"] == "EXCEEDED":
            worst = "EXCEEDED"
            break
        if e["state"] == "NEAR BOUNDARY":
            worst = "NEAR BOUNDARY"
    return {"per_claim": entries, "overall": worst}


def _claim_evidence_conflicts(bundle: DecisionBundle) -> dict[str, Any]:
    """A claim the agent asserted a value for, whose independently-resolved
    Evidence.value disagrees, restricted to the two `ClaimKind`s where
    `asserted_value` and `evidence.value` are actually the same fact from
    two sources (see `controlplane/extract.py::_ASSERTED_VALUE_FIELD`'s own
    docstring: for every other kind, e.g. ORDER_BELONGS_TO_CUSTOMER,
    asserted_value is a different field by design — comparing it to
    evidence.value there would be a category error, not a real signal).
    POLICY_CLAUSE_CURRENT reuses `clause_matches_claim`, the exact function
    `decide()` itself calls for this comparison — no second implementation."""
    ev_by_claim = {e.claim_id: e for e in bundle.evidence}
    conflicts = []
    for c in bundle.claims:
        if c.asserted_value is None:
            continue
        e = ev_by_claim.get(c.id)
        if e is None or e.value is None:
            continue
        if c.kind is ClaimKind.POLICY_CLAUSE_CURRENT:
            if not clause_matches_claim(c, e):
                conflicts.append({"claim": c.kind.value, "asserted": c.asserted_value, "observed": e.value})
        elif c.kind is ClaimKind.WITHIN_REFUND_WINDOW:
            if str(c.asserted_value) != str(e.value):
                conflicts.append({"claim": c.kind.value, "asserted": c.asserted_value, "observed": e.value})
    return {"conflicts": conflicts, "state": "CONTRADICTED" if conflicts else "NONE"}


def evidence_health(bundle: DecisionBundle) -> dict[str, Any]:
    completeness = _completeness(bundle)
    freshness = _freshness(bundle)
    margin = _predicate_margin(bundle)
    conflict = _claim_evidence_conflicts(bundle)
    return {
        "kind": "EVIDENCE_HEALTH",
        "disclaimer": "raw trace-derived signals — not a validated confidence score",
        "evidence_completeness": completeness,
        "trace_freshness": freshness,
        "predicate_margin": margin,
        "claim_evidence_conflict": conflict,
    }


# ---------------------------------------------------------------------------
# C. EVIDENCE PASSPORT
# ---------------------------------------------------------------------------


def evidence_passport(bundle: DecisionBundle) -> dict[str, Any]:
    d = bundle.decision
    r = bundle.receipt
    return {
        "kind": "EVIDENCE_PASSPORT",
        "trace_id": d.trace_id,
        "evidence_sources": sorted({e.source for e in bundle.evidence}),
        "evidence_freshness_ms": {e.claim_id: e.freshness_ms for e in bundle.evidence},
        "evidence_reliability": {e.claim_id: e.reliability_class.value for e in bundle.evidence},
        "policy_version": bundle.current_policy_version,
        "predicate_state": d.predicate_trace,
        "verification_state": d.verification_state,
        "decision": {"verdict": d.verdict.value, "intervention": d.intervention.value},
        "intervention": d.intervention.value,
        "execution_status": (
            "would_execute" if d.intervention.value in ("ALLOW", "MODIFY") else "not_executed"
        ),
        "idempotency_key": d.idempotency_key,
        "receipt_id": r["receipt_id"],
        "receipt_signature_valid": bundle.receipt_valid,
    }


# ---------------------------------------------------------------------------
# D. DECISION INSPECTOR — "why did ControlPlane decide this?"
# ---------------------------------------------------------------------------


def decision_inspector(bundle: DecisionBundle) -> dict[str, Any]:
    d = bundle.decision
    ev_by_claim = {e.claim_id: e for e in bundle.evidence}
    claims_view = []
    for c in bundle.claims:
        e = ev_by_claim.get(c.id)
        claims_view.append({
            "kind": c.kind.value, "tier": c.tier.value if c.tier else None,
            "load_bearing": c.load_bearing, "asserted_value": c.asserted_value,
            "evidence_value": e.value if e else None,
            "evidence_source": e.source if e else None,
            "reliability_class": e.reliability_class.value if e else None,
            "confidence": e.confidence.value if e else None,
        })
    return {
        "kind": "DECISION_INSPECTOR",
        "claims": claims_view,
        "evidence_freshness_summary": _freshness(bundle),
        "predicate_state": d.predicate_trace,
        "policy_outcome": [
            {"rule": r.rule, "expected": r.expected, "observed": r.observed,
             "passed": r.passed, "policy_version": r.policy_version}
            for r in d.reasons
        ],
        "verification_state": d.verification_state,
        "verdict": d.verdict.value,
        "root_cause": bundle.receipt.get("root_cause"),
        "intervention": d.intervention.value,
        "compensation": (
            {"action": d.compensation.action, "compensability": d.compensation.compensability.value}
            if d.compensation else None
        ),
        "execution": {
            "would_execute": d.intervention.value in ("ALLOW", "MODIFY"),
            "modified_args": d.modified_args,
        },
        "idempotency_key": d.idempotency_key,
        "receipt_id": bundle.receipt["receipt_id"],
        "receipt_signature_valid": bundle.receipt_valid,
        "component_status": d.component_status,
        "failure_context": (
            d.failure_context.model_dump(exclude_none=True) if d.failure_context else None
        ),
        "no_confidence_score_fabricated": True,
    }


# ---------------------------------------------------------------------------
# E. DECISION TIMELINE
# ---------------------------------------------------------------------------

_TIMELINE_STAGES = [
    "ACTION_RECEIVED", "EVIDENCE_RESOLVED", "POLICY_CHECKED",
    "VERIFICATION_DECISION", "CONTROLPLANE_VERDICT", "INTERVENTION",
    "EXECUTION", "SIGNED_RECEIPT",
]


def decision_timeline(bundle: DecisionBundle, replayed: bool | None = None) -> dict[str, Any]:
    d = bundle.decision
    would_execute = d.intervention.value in ("ALLOW", "MODIFY")
    stage_status = {
        "ACTION_RECEIVED": "DONE",
        "EVIDENCE_RESOLVED": "DONE" if bundle.evidence else "SKIPPED",
        "POLICY_CHECKED": "DONE" if bundle.current_policy_version else "SKIPPED",
        "VERIFICATION_DECISION": "DONE",
        "CONTROLPLANE_VERDICT": d.verdict.value,
        "INTERVENTION": d.intervention.value,
        "EXECUTION": (
            ("REPLAYED" if replayed else "EXECUTED") if would_execute else "NOT_EXECUTED"
        ),
        "SIGNED_RECEIPT": "SIGNED" if bundle.receipt_valid else "SIGNATURE_INVALID",
    }
    return {
        "kind": "DECISION_TIMELINE",
        "stages": _TIMELINE_STAGES,
        "status": stage_status,
        "note": (
            "verification is not marked complete unless VERIFICATION_DECISION "
            "actually ran (it always does here — the engine has no path that "
            "skips decide())"
        ),
    }


# ---------------------------------------------------------------------------
# F. CONFIGURABLE VERIFICATION POLICY (prototype, not learned/optimal)
# ---------------------------------------------------------------------------

VERIFICATION_POLICY_PROTOTYPE = {
    "kind": "CONFIGURABLE_PROTOTYPE_POLICY",
    "label": "CONFIGURABLE PROTOTYPE POLICY — not optimal, not validated, not learned",
    "rules": [
        {"condition": "missing_evidence", "action": "ESCALATE"},
        {"condition": "contradiction", "action": "BLOCK"},
        {"condition": "high_risk_action", "action": "VERIFY"},
        {"condition": "irreversible_action", "action": "VERIFY"},
        {"condition": "low_risk_action", "action": "ALLOW"},
    ],
}



# ---------------------------------------------------------------------------
# H. COST / ASSURANCE — reads already-measured latency only, no new run
# ---------------------------------------------------------------------------

def cost_assurance_view() -> dict[str, Any]:
    """Reads `reports/summary.json['p09_latency']['configurations']` — the
    real, already-committed P09 latency measurement (see docs/session-log-
    p08-p09.md). Generates nothing new; if that key is missing, says so
    rather than fabricating a number."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "reports" / "summary.json"
    if not path.exists():
        return {"kind": "COST_ASSURANCE", "available": False,
                "reason": "reports/summary.json not present in this worktree"}
    data = json.loads(path.read_text(encoding="utf-8"))
    p09 = data.get("p09_latency")
    if not p09:
        return {"kind": "COST_ASSURANCE", "available": False,
                "reason": "p09_latency not present in reports/summary.json"}
    rows = []
    for cfg in p09.get("configurations", []):
        e2e = cfg.get("end_to_end", {})
        rows.append({
            "config": cfg.get("config"),
            "grounding_c3": cfg.get("c3"),
            "concurrency": cfg.get("concurrency"),
            "n": cfg.get("n"),
            "p50_ms": e2e.get("p50"),
            "p95_ms": e2e.get("p95"),
            "p99_ms": e2e.get("p99"),
        })
    return {
        "kind": "COST_ASSURANCE",
        "available": True,
        "source": "reports/summary.json[p09_latency] (already measured, committed)",
        "configurations": rows,
        "qualitative_control": "LOWER COST ↔ HIGHER ASSURANCE (grounding C3 on/off trades latency for stronger verification; no optimal point claimed)",
        "external_references_excluded": (
            "aegis_comparison/oap_comparison exist in the source data but are "
            "external reference numbers, not ControlPlane measurements, and "
            "are intentionally omitted here per the external-reference firewall"
        ),
    }


def verification_policy_evaluation(bundle: DecisionBundle) -> dict[str, Any]:
    """Evaluate the same case against the toy prototype policy table above,
    purely for side-by-side display against what the real engine actually
    decided. This table is illustrative config, not a second decision
    engine wired into any execution path."""
    d = bundle.decision
    comp = bundle.decision.compensation
    conflict = _claim_evidence_conflicts(bundle)
    completeness = _completeness(bundle)
    missing = completeness["resolved"] < completeness["total"]
    irreversible = comp is not None and comp.compensability.value == "not"
    if missing:
        prototype_action = "ESCALATE"
        matched = "missing_evidence"
    elif conflict["state"] == "CONTRADICTED":
        prototype_action = "BLOCK"
        matched = "contradiction"
    elif irreversible:
        prototype_action = "VERIFY"
        matched = "irreversible_action"
    elif d.intervention.value in ("BLOCK", "ESCALATE"):
        prototype_action = "VERIFY"
        matched = "high_risk_action"
    else:
        prototype_action = "ALLOW"
        matched = "low_risk_action"
    return {
        "kind": "VERIFICATION_POLICY_EVALUATION",
        "matched_rule": matched,
        "prototype_action": prototype_action,
        "actual_controlplane_intervention": d.intervention.value,
        "note": "prototype table is descriptive config, evaluated for display only",
    }
