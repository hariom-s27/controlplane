"""S15 — the five metamorphic invariants over decide(), formally stated in
docs/invariants.md. hypothesis generates the scenarios; "more permissive"
and "stricter" are Intervention.rank comparisons, never a lookup table.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from hypothesis import given
from hypothesis import strategies as st

from controlplane.decide import decide
from controlplane.ladder import classify_claims
from controlplane.schema import (
    Claim,
    ClaimKind,
    Confidence,
    Evidence,
    Intervention,
    ProposedAction,
    Reliability,
    Tier,
)

TODAY = date(2026, 8, 14)
NOW = datetime.now(timezone.utc)
MANIFEST = {
    "reliability_floor": "corroborated", "verdict_handling": {},
    "manifest_id": "servicing-v1", "_name": "servicing",
    "compensation": {"action": "reverse_refund", "compensability": "fully"},
}


def _decide(
    days_ago: int,
    amount_paise: int,
    ceiling_paise: int = 2_500_000,
    window_reliability: Reliability = Reliability.CORROBORATED,
    claimed_version: str | None = None,
    current_version: str = "v4.2",
    order_id: str = "ORD-X",
):
    window_claim = Claim(id=f"{order_id}:w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject=order_id, tier=Tier.C2)
    authority_claim = Claim(id=f"{order_id}:a", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject=order_id, tier=Tier.C2)
    claims = classify_claims([window_claim, authority_claim])

    delivered_at = (TODAY - timedelta(days=days_ago)).isoformat()
    evidence = [
        Evidence(claim_id=window_claim.id, value=delivered_at, source="orders.db", query="...",
                  fetched_at=NOW, reliability_class=window_reliability, confidence=Confidence.HIGH),
        Evidence(claim_id=authority_claim.id, value=ceiling_paise, source="manifest:servicing", query="...",
                  fetched_at=NOW, reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
    ]
    predicate_result = {"within_window": days_ago <= 7, "within_authority": amount_paise <= ceiling_paise}
    action = ProposedAction(
        tool="issue_refund", order_id=order_id, amount_paise=amount_paise, currency="INR",
        claimed_policy_version=claimed_version,
    )
    clause_match = (claimed_version == current_version) if claimed_version is not None else None
    return decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST, clause_match=clause_match)


_days = st.integers(min_value=0, max_value=60)
_amount = st.integers(min_value=10_000, max_value=10_000_000)


@given(days_ago=_days, amount_paise=_amount, extra_days=st.integers(min_value=1, max_value=30))
def test_m1_strictness_monotonicity_on_window(days_ago, amount_paise, extra_days):
    """Making delivered_at strictly older (a strictly less favourable
    evidence value) must not make the intervention more permissive."""
    before = _decide(days_ago, amount_paise)
    after = _decide(days_ago + extra_days, amount_paise)
    assert not after.intervention.more_permissive_than(before.intervention), (
        f"days_ago {days_ago}->{days_ago + extra_days}: "
        f"{before.intervention} -> {after.intervention} got MORE permissive"
    )


@given(days_ago=_days, low=_amount, extra=st.integers(min_value=1, max_value=5_000_000))
def test_m2_amount_monotonicity(days_ago, low, extra):
    """Lower amount, all else equal, must not make the decision stricter."""
    high = low + extra
    lower_amount_decision = _decide(days_ago, low)
    higher_amount_decision = _decide(days_ago, high)
    assert lower_amount_decision.intervention.rank <= higher_amount_decision.intervention.rank, (
        f"amount {low} -> {high}: "
        f"{lower_amount_decision.intervention} -> {higher_amount_decision.intervention} got stricter for the LOWER amount"
    )


@given(days_ago=_days, amount_paise=_amount)
def test_m3_policy_equivalence(days_ago, amount_paise):
    """Two concrete scenarios that differ only in cosmetic details (order_id,
    claim/evidence identifiers) but are policy-identical in every fact
    decide() actually reads must get identical verdicts."""
    a = _decide(days_ago, amount_paise, order_id="ORD-AAAA")
    b = _decide(days_ago, amount_paise, order_id="ORD-ZZZZ")
    assert a.verdict == b.verdict
    assert a.intervention == b.intervention


@given(days_ago=_days, amount_paise=_amount)
def test_m4_idempotence(days_ago, amount_paise):
    """The same action re-submitted unchanged: same verdict, same
    intervention, same idempotency_key (decide() is pure, so this must
    hold exactly, not approximately)."""
    first = _decide(days_ago, amount_paise)
    second = _decide(days_ago, amount_paise)
    assert first.verdict == second.verdict
    assert first.intervention == second.intervention
    assert first.idempotency_key == second.idempotency_key


@given(days_ago=_days, amount_paise=_amount)
def test_m5_source_degradation_monotonicity(days_ago, amount_paise):
    """Swapping in a lower-reliability source for the same load-bearing
    claim must never make the verdict more permissive. It may become
    SOURCE_UNRELIABLE / ESCALATE; never ALLOW where it was BLOCK."""
    corroborated = _decide(days_ago, amount_paise, window_reliability=Reliability.CORROBORATED)
    inferred = _decide(days_ago, amount_paise, window_reliability=Reliability.INFERRED)
    assert not inferred.intervention.more_permissive_than(corroborated.intervention), (
        f"degrading reliability corroborated->inferred: "
        f"{corroborated.intervention} -> {inferred.intervention} got MORE permissive"
    )
    if corroborated.intervention is Intervention.BLOCK:
        assert inferred.intervention is not Intervention.ALLOW


# ---------------------------------------------------------------------------
# M6 — fail closed on missing evidence (D-M1-01, docs/invariants.md)
#
# "If any load-bearing evidence is missing, unavailable or failed, the
# intervention is never ALLOW and nothing executes." Two levels:
#   * decide(): any missing/failed load-bearing input -> never ALLOW;
#   * dispatch_tool(): over all 10 manifests x tier x posture (closed /
#     escalate) x escalation budget x fault, the governed tool is never
#     called; an `escalate` posture with budget available is queued, never
#     turned into execution, and an exhausted budget BLOCKs.
# Runtime files (trail, queue) are per-test tmp files via tests/conftest.py
# and are reset per Hypothesis example.
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

import pytest as _pytest  # noqa: E402
import yaml as _yaml  # noqa: E402
from hypothesis import HealthCheck, assume, settings  # noqa: E402

import controlplane.escalation as _escalation  # noqa: E402
import controlplane.ground as _ground  # noqa: E402
import controlplane.intercept as _intercept  # noqa: E402
import controlplane.predicates as _predicates  # noqa: E402
import controlplane.receipt as _receipt  # noqa: E402
from controlplane.decide import _PREDICATE_FOR_KIND  # noqa: E402
from controlplane.errors import SourceUnavailable  # noqa: E402
from controlplane.extract import build_claims  # noqa: E402
from controlplane.manifest import _validate_structural  # noqa: E402
from controlplane.schema import SessionContext, Verdict  # noqa: E402

_M6_ROOT = _Path(__file__).resolve().parent.parent
_M6_MANIFESTS = sorted(p.stem for p in (_M6_ROOT / "manifests").glob("*.yaml"))
_ALL_PREDICATES = sorted(set(_PREDICATE_FOR_KIND.values()))
_M6_ACTION_FIELDS = dict(
    order_id="ORD-1", amount_paise=100_000, currency="INR", recipient_id="EMP-1", doc_id="DOC-1",
    excerpt="x", item_colour="grey", item_category="shirt", claimed_delivered_at="2026-08-11",
    claimed_policy_version="v4.2", claimed_clause_text="clause text",
)


def _m6_manifest(name: str) -> dict:
    # structural validation only: tau2 manifests' resolver is registered by the
    # bench, and resolution is stubbed below anyway.
    data = _yaml.safe_load((_M6_ROOT / "manifests" / f"{name}.yaml").read_text(encoding="utf-8"))
    _validate_structural(data, name)
    data["_name"] = name
    return data


def _m6_claims(manifest: dict):
    action = ProposedAction(tool=manifest["tool"], **_M6_ACTION_FIELDS)
    return action, classify_claims(build_claims(action, manifest))


def _m6_good_evidence(claims, *, confidence_none_for=None, missing_for=None):
    out = []
    for c in claims:
        out.append(Evidence(
            claim_id=("missing-" + c.id) if c.id == missing_for else c.id,
            value="ok", source="test", query="q", fetched_at=NOW,
            reliability_class=Reliability.CORROBORATED,
            confidence=Confidence.NONE if c.id == confidence_none_for else Confidence.HIGH,
        ))
    return out


_M6_DECIDE_FAULTS = ("missing", "confidence_none", "predicate_unavailable", "clause_match_none", "c3_failed")


@given(name=st.sampled_from(_M6_MANIFESTS), fault=st.sampled_from(_M6_DECIDE_FAULTS),
       pick=st.integers(min_value=0, max_value=50))
@settings(max_examples=300, deadline=None)
def test_m6_decide_never_allows_on_missing_or_failed_load_bearing_input(name, fault, pick):
    manifest = _m6_manifest(name)
    action, claims = _m6_claims(manifest)
    lb = [c for c in claims if c.load_bearing]
    assume(lb)
    kinds = {c.kind for c in lb}
    predicates = {f: True for f in _ALL_PREDICATES}
    # grounding_state defaults to "off"; it is only passed for the c3_failed fault
    kwargs = {"clause_match": True, "grounding_score": None}
    evidence = _m6_good_evidence(claims)

    # the healthy baseline for this manifest is ALLOW, so a non-ALLOW below is the fault's doing
    healthy = decide("t", manifest["manifest_id"], action, claims, evidence, predicates, manifest, **kwargs)
    assert healthy.intervention is Intervention.ALLOW, (name, healthy.reasons)

    target = lb[pick % len(lb)]
    if fault == "missing":
        evidence = _m6_good_evidence(claims, missing_for=target.id)
    elif fault == "confidence_none":
        evidence = _m6_good_evidence(claims, confidence_none_for=target.id)
    elif fault == "predicate_unavailable":
        fields = [_PREDICATE_FOR_KIND[c.kind] for c in lb if c.kind in _PREDICATE_FOR_KIND]
        assume(fields)
        predicates = {**predicates, fields[pick % len(fields)]: None}
    elif fault == "clause_match_none":
        assume(ClaimKind.POLICY_CLAUSE_CURRENT in kinds)
        kwargs["clause_match"] = None
    else:
        assume(ClaimKind.CLAUSE_SEMANTICS_MATCH in kinds)
        kwargs["grounding_state"] = "failed"

    d = decide("t", manifest["manifest_id"], action, claims, evidence, predicates, manifest, **kwargs)
    assert d.intervention is not Intervention.ALLOW, (name, fault, target.kind)
    assert d.verdict is not Verdict.VERIFIED


_M6_DISPATCH_FAULTS = ("source_unavailable", "missing", "confidence_none", "predicate_unavailable",
                       "clause_match_none", "c3_failed")


@given(name=st.sampled_from(_M6_MANIFESTS), tier=st.sampled_from([0, 1, 2]),
       posture=st.sampled_from(["closed", "escalate", "manifest"]), budget=st.sampled_from([0, 2, 5, 100]),
       saturated=st.booleans(), fault=st.sampled_from(_M6_DISPATCH_FAULTS),
       pick=st.integers(min_value=0, max_value=50))
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_m6_dispatch_never_executes_on_missing_evidence(name, tier, posture, budget, saturated, fault, pick):
    manifest = _m6_manifest(name)
    manifest["risk_tier_default"] = tier
    if posture != "manifest":  # "manifest" keeps the file's own configured value for that tier
        manifest["fail_posture"] = {**manifest["fail_posture"], f"tier_{tier}": posture}
    posture = manifest["fail_posture"][f"tier_{tier}"]
    manifest["escalation_budget_pct"] = budget
    action, claims = _m6_claims(manifest)
    lb = [c for c in claims if c.load_bearing]
    assume(lb)
    kinds = {c.kind for c in lb}
    target = lb[pick % len(lb)]
    predicates = {f: True for f in _ALL_PREDICATES}
    if fault == "predicate_unavailable":
        fields = [_PREDICATE_FOR_KIND[c.kind] for c in lb if c.kind in _PREDICATE_FOR_KIND]
        assume(fields)
        predicates[fields[pick % len(fields)]] = None
    if fault == "clause_match_none":
        assume(ClaimKind.POLICY_CLAUSE_CURRENT in kinds)
    if fault == "c3_failed":
        assume(ClaimKind.CLAUSE_SEMANTICS_MATCH in kinds)

    # fresh runtime files for this example (conftest points the engine at them)
    trail, queue = _Path(_receipt.OPERATIONAL_TRAIL), _Path(_escalation.PENDING_QUEUE)
    for p in (trail, queue):
        p.unlink(missing_ok=True)
    if saturated:
        trail.write_text("".join(
            _json.dumps({"receipt": {"manifest_id": manifest["manifest_id"], "intervention": "ESCALATE"}}) + "\n"
            for _ in range(100)), encoding="utf-8")

    def resolve(*_a, **_k):
        if fault == "source_unavailable":
            raise SourceUnavailable(source="store.db", operation="connect")
        return _m6_good_evidence(
            claims,
            missing_for=target.id if fault == "missing" else None,
            confidence_none_for=target.id if fault == "confidence_none" else None,
        )

    calls = []
    with _pytest.MonkeyPatch.context() as mp:
        mp.setenv("CP_MANIFEST", name)
        mp.setenv("CP_RECEIPT_SECRET", "m6-secret")
        mp.setenv("CP_GROUNDING", "on" if fault == "c3_failed" else "off")
        mp.setattr(_intercept, "load_manifest", lambda _n: manifest)
        mp.setattr(_intercept, "extract_action", lambda **_k: action)
        mp.setattr(_intercept, "classify_claims", lambda _c: claims)
        mp.setattr(_intercept, "resolve_bindings", resolve)
        mp.setattr(_intercept, "build_predicate_payload", lambda *_a, **_k: {})
        mp.setattr(_intercept, "evaluate_predicates", lambda *_a, **_k: {"result": predicates, "trace": {}})
        if fault == "clause_match_none":
            mp.setattr(_predicates, "clause_matches_claim", lambda *_a: None)
        mp.setattr(_ground, "score", lambda **_k: (_ for _ in ()).throw(TimeoutError("m6")))
        mp.setitem(_intercept.REGISTRY, manifest["tool"], lambda **kw: calls.append(kw) or "EXECUTED")

        try:
            result = _intercept.dispatch_tool(manifest["tool"], {"x": 1}, SessionContext(trace_id="m6"))
            outcome = "pending" if isinstance(result, dict) and result.get("status") == "pending" else "other"
        except _intercept.Blocked:
            outcome = "blocked"
        except _intercept.Pending:
            outcome = "held"

    assert calls == [], (name, tier, posture, budget, saturated, fault)
    assert outcome in {"pending", "blocked", "held"}, (name, fault, outcome)
    entries = [_json.loads(line) for line in trail.read_text(encoding="utf-8").splitlines() if line.strip()]
    receipts = [e["receipt"] for e in entries if "receipt" in e and e["receipt"].get("trace_id") == "m6"]
    assert receipts and all(r["intervention"] != "ALLOW" for r in receipts)
    queued = [line for line in (queue.read_text(encoding="utf-8").splitlines() if queue.exists() else []) if line.strip()]
    assert len(queued) == (1 if outcome == "pending" else 0)

    if fault == "source_unavailable":
        if posture == "closed":
            assert outcome == "blocked"
        elif not saturated and budget > 0:
            assert outcome == "pending"  # escalate with budget available: queued, not Blocked, not executed
        elif saturated and budget < 100:
            assert outcome == "blocked"  # exhausted budget always BLOCKs (R2)
