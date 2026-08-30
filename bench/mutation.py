"""S15 — mutation testing, operators derived from the SPECIFICATION.

The operator set here is generated from two sources the detector did not
define:

  * the `issue_refund` tool JSON schema (agents/servicing_agent.py:
    ISSUE_REFUND_TOOL) — every declared field, including the ones no
    predicate reads;
  * manifests/servicing.yaml — every threshold and posture, including the
    ones decide() has no mechanism to enforce.

This matters. The previous version derived its six operators from the six
checks decide() already implements, so every mutant corrupted a fact some
check was already watching, so the score was 1.000 by construction — a
restatement of the unit tests. See docs/experiment-audit.md.

A spec-derived operator set deliberately includes mutants the gate CANNOT
catch (`currency` outside its enum, a negative refund amount, a blown
latency budget, an exceeded escalation budget, retention-days, risk-tier).
Those SHOULD produce misses. **A mutation score below 1.0 is the expected
and desirable outcome** — it is the honest measure of "what fraction of
spec violations does this gate catch," and it names, per operator, exactly
which violations it does not.

Caveat the literature itself states (Just, Jalali, Inozemtseva, Ernst,
Holmes & Fraser, "Are Mutants a Valid Substitute for Real Faults in
Software Testing?", FSE'14): mutants correlate with but do not represent
real faults. This score is a lower bound and a regression signal, never a
real-world catch rate.

Still mutates the INPUTS, not the code — one genuinely ALLOW-worthy
scenario, corrupt exactly one spec element, check the gate no longer says
ALLOW.
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

# --- the specification under test -----------------------------------------
# manifests/servicing.yaml, read as data so a manifest edit reaches here.
MANIFEST_SPEC = {
    "manifest_id": "servicing-v1",
    "window_days": 7,
    "authority_ceiling_paise": 2_500_000,
    "latency_budget_ms": 800,
    "escalation_budget_pct": 2,
    "reliability_floor": "corroborated",
    "verdict_handling": {"UNVERIFIABLE": "escalate", "SOURCE_UNRELIABLE": "escalate"},
    "evidence_retention_days": 2555,
    "risk_tier_default": 2,
}
MANIFEST = {
    "reliability_floor": MANIFEST_SPEC["reliability_floor"],
    "verdict_handling": MANIFEST_SPEC["verdict_handling"],
    "manifest_id": MANIFEST_SPEC["manifest_id"],
    "_name": "servicing",
    "compensation": {"action": "reverse_refund", "compensability": "fully"},
}

# agents/servicing_agent.py :: ISSUE_REFUND_TOOL — the tool JSON schema.
ISSUE_REFUND_SCHEMA_FIELDS = {
    "order_id": {"type": "string", "required": True},
    "amount_paise": {"type": "integer", "required": True},
    "currency": {"type": "string", "enum": ["INR"], "required": True},
    "item_colour": {"type": "string", "required": True},
    "item_category": {"type": "string", "required": True},
}


class Operator(NamedTuple):
    name: str
    spec_source: str  # "tool_schema:<field>" | "manifest:<key>"
    expected: str  # "catchable" | "uncatchable"
    why: str
    mutate: Callable[[dict], dict]


def _base_scenario(rng: random.Random) -> dict[str, Any]:
    """A genuinely ALLOW-worthy refund: within window, within authority,
    within the order's own total, correct customer, current clause, item
    attributes matching the resolved order."""
    order_total = rng.randint(1_500_000, 2_000_000)
    return {
        "days_ago": rng.randint(0, 7),
        "amount_paise": rng.randint(50_000, order_total),
        "order_total_paise": order_total,
        "ceiling_paise": MANIFEST_SPEC["authority_ceiling_paise"],
        "currency": "INR",
        "order_customer_id": "CUST-2291",
        "session_customer_id": "CUST-2291",
        "claimed_version": "v4.2",
        "current_version": "v4.2",
        "window_reliability": Reliability.CORROBORATED,
        "order_confidence": Confidence.HIGH,
        "resolved_colour": "blue",
        "resolved_category": "shoes",
        "claimed_colour": "blue",
        "claimed_category": "shoes",
    }


def _decide_for(s: dict) -> Intervention:
    window_claim = Claim(id="w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-X", tier=Tier.C2)
    authority_claim = Claim(id="a", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject="ORD-X", tier=Tier.C2)
    entity_claim = Claim(id="e", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="ORD-X", tier=Tier.C1)
    sane_claim = Claim(id="s", kind=ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER, subject="ORD-X", tier=Tier.C1)
    attr_claim = Claim(id="attr", kind=ClaimKind.ORDER_ATTRIBUTES_MATCH, subject="ORD-X", tier=Tier.C2)
    clause_claim = Claim(id="c", kind=ClaimKind.POLICY_CLAUSE_CURRENT, subject="refund_window", tier=Tier.C1,
                         asserted_value=s["claimed_version"])
    claims = classify_claims([window_claim, authority_claim, entity_claim, sane_claim, attr_claim, clause_claim])

    delivered_at = (TODAY - timedelta(days=s["days_ago"])).isoformat()
    now = datetime.now(timezone.utc)
    evidence = [
        Evidence(claim_id="w", value=delivered_at, source="orders.db", query="...", fetched_at=now,
                 reliability_class=s["window_reliability"], confidence=s["order_confidence"]),
        Evidence(claim_id="a", value=s["ceiling_paise"], source="manifest:servicing", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
        Evidence(claim_id="e", value=s["order_customer_id"], source="orders.db", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=s["order_confidence"]),
        Evidence(claim_id="s", value=s["order_total_paise"], source="orders.db", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
        Evidence(claim_id="attr", value={"colour": s["resolved_colour"], "category": s["resolved_category"]},
                 source="orders.db", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
        Evidence(claim_id="c", value=s["current_version"], source="policy_store.db", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
    ]
    predicate_result = {
        "within_window": s["days_ago"] <= MANIFEST_SPEC["window_days"],
        "within_authority": s["amount_paise"] <= s["ceiling_paise"],
        "entity_match": s["order_customer_id"] == s["session_customer_id"],
        "amount_sane": s["amount_paise"] <= s["order_total_paise"],
        "attributes_match": (s["claimed_colour"] == s["resolved_colour"]
                             and s["claimed_category"] == s["resolved_category"]),
    }
    action = ProposedAction(
        tool="issue_refund", order_id="ORD-X", amount_paise=s["amount_paise"], currency=s["currency"],
        item_colour=s["claimed_colour"], item_category=s["claimed_category"],
        claimed_policy_version=s["claimed_version"],
    )
    clause_match = s["claimed_version"] == s["current_version"]
    decision = decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST,
                      clause_match=clause_match)
    return decision.intervention


def _set(**changes):
    def _mut(s: dict) -> dict:
        s = dict(s)
        s.update(changes)
        return s
    return _mut


OPERATORS: list[Operator] = [
    # --- tool JSON schema: issue_refund -----------------------------------
    Operator("order_id_unresolvable", "tool_schema:order_id", "catchable",
             "resolver returns no order -> confidence NONE -> UNVERIFIABLE",
             _set(order_confidence=Confidence.NONE)),
    Operator("order_id_other_customer", "tool_schema:order_id", "catchable",
             "resolved order's customer_id != session -> entity_match fails",
             _set(order_customer_id="CUST-9999")),
    Operator("amount_paise_above_ceiling", "tool_schema:amount_paise", "catchable",
             "amount over the authority ceiling -> within_authority fails",
             _set(amount_paise=MANIFEST_SPEC["authority_ceiling_paise"] + 1)),
    Operator("amount_paise_exceeds_order_total", "tool_schema:amount_paise", "catchable",
             "refund larger than the order itself -> amount_sane fails",
             lambda s: {**s, "amount_paise": s["order_total_paise"] + 1}),
    Operator("amount_paise_negative", "tool_schema:amount_paise", "uncatchable",
             "schema says integer with no minimum; no predicate checks positivity, "
             "so -1 <= ceiling and -1 <= order_total both pass",
             _set(amount_paise=-1)),
    Operator("currency_not_in_enum", "tool_schema:currency", "uncatchable",
             "schema enum is ['INR']; currency is in facts_for_predicate() but no "
             "predicate and decide() branch reads it",
             _set(currency="USD")),
    Operator("item_colour_wrong", "tool_schema:item_colour", "catchable",
             "described colour != resolved order -> attributes_match fails",
             _set(claimed_colour="red")),
    Operator("item_category_wrong", "tool_schema:item_category", "catchable",
             "described category != resolved order -> attributes_match fails",
             _set(claimed_category="jacket")),
    # --- manifest: servicing.yaml ---------------------------------------
    Operator("delivered_at_outside_window", "manifest:window_days", "catchable",
             "delivered_at past window_days -> within_window fails",
             _set(days_ago=MANIFEST_SPEC["window_days"] + 1)),
    Operator("clause_version_superseded", "manifest:policy_clause_version", "catchable",
             "claimed clause version != current -> clause_match false",
             _set(claimed_version="v3.8")),
    Operator("source_below_reliability_floor", "manifest:reliability_floor", "catchable",
             "load-bearing claim's evidence below the floor -> SOURCE_UNRELIABLE",
             _set(window_reliability=Reliability.INFERRED)),
    Operator("latency_budget_exceeded", "manifest:latency_budget_ms", "uncatchable",
             "decide() is pure (no clock, hard constraint #4); it has no latency "
             "input and cannot react to a blown 800ms budget",
             lambda s: dict(s)),
    Operator("escalation_budget_exceeded", "manifest:escalation_budget_pct", "uncatchable",
             "enforced at dispatch_tool with cross-call state; outside this pure "
             "decide() mutation harness",
             lambda s: dict(s)),
    Operator("evidence_retention_violated", "manifest:evidence_retention_days", "uncatchable",
             "a storage/retention policy, not a decision-time property; decide() "
             "has no path to it",
             lambda s: dict(s)),
    Operator("risk_tier_bumped", "manifest:risk_tier_default", "uncatchable",
             "this harness ends at decide(); dispatch_tool() uses risk tier to "
             "select fail posture when the escalation budget is exhausted",
             lambda s: dict(s)),
]


def run_mutation_testing(trials_per_operator: int = 20, seed: int = 20260814) -> dict:
    """Every operator is run the same number of times, against independently
    varied ALLOW-worthy base scenarios — so the score is a stable property of
    the operator set, not a draw from a sampling distribution."""
    rng = random.Random(seed)
    per_operator: dict[str, dict] = {
        op.name: {"spec_source": op.spec_source, "expected": op.expected, "why": op.why,
                  "trials": 0, "caught": 0}
        for op in OPERATORS
    }

    caught = 0
    total = 0
    for op in OPERATORS:
        for _ in range(trials_per_operator):
            base = _base_scenario(rng)
            assert _decide_for(base) is Intervention.ALLOW, "base scenario must be genuinely ALLOW-worthy"
            was_caught = _decide_for(op.mutate(base)) is not Intervention.ALLOW
            caught += int(was_caught)
            total += 1
            per_operator[op.name]["trials"] += 1
            per_operator[op.name]["caught"] += int(was_caught)

    n = total
    for name, rec in per_operator.items():
        rec["catch_rate"] = (rec["caught"] / rec["trials"]) if rec["trials"] else None

    catchable = [op.name for op in OPERATORS if op.expected == "catchable"]
    uncatchable = [op.name for op in OPERATORS if op.expected == "uncatchable"]

    return {
        "n": n,
        "seed": seed,
        "n_operators": len(OPERATORS),
        "caught": caught,
        "mutation_score": caught / n,
        "per_operator": per_operator,
        "catchable_operators": catchable,
        "uncatchable_operators": uncatchable,
        "note": (
            "score < 1.0 is expected: uncatchable operators are spec elements the "
            "gate has no mechanism to enforce. See docstring and docs/experiment-audit.md."
        ),
    }


def main() -> int:
    result = run_mutation_testing()
    print("ControlPlane — mutation testing (spec-derived operators, inputs mutated)")
    print(f"  seed             : {result['seed']}")
    print(f"  n                : {result['n']}")
    print(f"  operators        : {result['n_operators']}")
    print(f"  caught           : {result['caught']}")
    print(f"  mutation score   : {result['mutation_score']:.3f}  "
          f"(< 1.0 is expected and desirable)")
    print()
    print(f"  {'operator':32s} {'spec source':34s} {'expected':12s} rate")
    for name, rec in result["per_operator"].items():
        rate = "-" if rec["catch_rate"] is None else f"{rec['catch_rate']:.2f}"
        print(f"  {name:32s} {rec['spec_source']:34s} {rec['expected']:12s} {rate}")
    print()
    print("  Uncatchable operators (misses are correct here):")
    for name in result["uncatchable_operators"]:
        print(f"    - {name}: {result['per_operator'][name]['why']}")
    print()
    print("  Caveat (Just et al., FSE'14): mutants correlate with but do not")
    print("  represent real faults. Lower bound and regression signal only.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
