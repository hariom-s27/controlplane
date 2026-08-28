"""S15 — mutation testing. Mutates the INPUTS, not the code: each operator
takes a genuinely ALLOW-worthy scenario and corrupts exactly one fact, then
checks the gate no longer says ALLOW. See docs/invariants.md for the full
caveat (Just & Ernst, FSE'14) — this is a lower bound and a regression
signal, never a real-world catch rate.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from controlplane.decide import decide
from controlplane.ladder import classify_claims
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Intervention, ProposedAction, Reliability, Tier

TODAY = date(2026, 8, 14)
MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {}, "manifest_id": "servicing-v1", "_name": "servicing"}


def _base_scenario(rng: random.Random) -> dict[str, Any]:
    """A genuinely ALLOW-worthy refund: within window, within authority,
    correct customer, current clause version."""
    return {
        "days_ago": rng.randint(0, 7),
        "amount_paise": rng.randint(50_000, 2_000_000),
        "ceiling_paise": 2_500_000,
        "order_customer_id": "CUST-2291",
        "session_customer_id": "CUST-2291",
        "claimed_version": "v4.2",
        "current_version": "v4.2",
        "window_reliability": Reliability.CORROBORATED,
        "order_confidence": Confidence.HIGH,
    }


def _mutate_order_id_nonexistent(s: dict) -> dict:
    s = dict(s)
    s["order_confidence"] = Confidence.NONE  # the resolver's actual behavior for a missing order_id
    return s


def _mutate_amount_above_ceiling(s: dict) -> dict:
    s = dict(s)
    s["amount_paise"] = s["ceiling_paise"] + 1
    return s


def _mutate_delivered_at_outside_window(s: dict) -> dict:
    s = dict(s)
    s["days_ago"] = 8
    return s


def _mutate_clause_version_superseded(s: dict) -> dict:
    s = dict(s)
    s["claimed_version"] = "v3.8"  # superseded; current_version stays v4.2
    return s


def _mutate_customer_id_mismatched(s: dict) -> dict:
    s = dict(s)
    s["session_customer_id"] = "CUST-9999"
    return s


def _mutate_order_status_inconsistent(s: dict) -> dict:
    """order_status disagreeing with delivered_at is exactly D36's inferred-
    field case — modeled as degrading the window evidence's reliability,
    the same mechanism freshness.py uses for a real inferred order_status."""
    s = dict(s)
    s["window_reliability"] = Reliability.INFERRED
    return s


MUTATORS: dict[str, Callable[[dict], dict]] = {
    "order_id_nonexistent": _mutate_order_id_nonexistent,
    "amount_above_ceiling": _mutate_amount_above_ceiling,
    "delivered_at_outside_window": _mutate_delivered_at_outside_window,
    "clause_version_superseded": _mutate_clause_version_superseded,
    "customer_id_mismatched": _mutate_customer_id_mismatched,
    "order_status_inconsistent": _mutate_order_status_inconsistent,
}


def _decide_for(s: dict) -> Intervention:
    window_claim = Claim(id="w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-X", tier=Tier.C2)
    authority_claim = Claim(id="a", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject="ORD-X", tier=Tier.C2)
    entity_claim = Claim(id="e", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="ORD-X", tier=Tier.C1)
    clause_claim = Claim(id="c", kind=ClaimKind.POLICY_CLAUSE_CURRENT, subject="refund_window", tier=Tier.C1,
                          asserted_value=s["claimed_version"])
    claims = classify_claims([window_claim, authority_claim, entity_claim, clause_claim])

    delivered_at = (TODAY - timedelta(days=s["days_ago"])).isoformat()
    now = datetime.now(timezone.utc)
    evidence = [
        Evidence(claim_id="w", value=delivered_at, source="orders.db", query="...", fetched_at=now,
                  reliability_class=s["window_reliability"], confidence=s["order_confidence"]),
        Evidence(claim_id="a", value=s["ceiling_paise"], source="manifest:servicing", query="...", fetched_at=now,
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
        Evidence(claim_id="e", value=s["order_customer_id"], source="orders.db", query="...", fetched_at=now,
                  reliability_class=Reliability.CORROBORATED, confidence=s["order_confidence"]),
        Evidence(claim_id="c", value=s["current_version"], source="policy_store.db", query="...", fetched_at=now,
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
    ]
    predicate_result = {
        "within_window": s["days_ago"] <= 7,
        "within_authority": s["amount_paise"] <= s["ceiling_paise"],
        "entity_match": s["order_customer_id"] == s["session_customer_id"],
    }
    action = ProposedAction(
        tool="issue_refund", order_id="ORD-X", amount_paise=s["amount_paise"], currency="INR",
        claimed_policy_version=s["claimed_version"],
    )
    clause_match = s["claimed_version"] == s["current_version"]
    decision = decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST, clause_match=clause_match)
    return decision.intervention


def run_mutation_testing(n: int = 200, seed: int = 20260814) -> dict:
    rng = random.Random(seed)
    caught = 0
    per_operator: dict[str, list[bool]] = {name: [] for name in MUTATORS}

    for _ in range(n):
        base = _base_scenario(rng)
        assert _decide_for(base) is Intervention.ALLOW, "base scenario must be genuinely ALLOW-worthy"

        operator = rng.choice(list(MUTATORS))
        mutant = MUTATORS[operator](base)
        intervention = _decide_for(mutant)
        was_caught = intervention is not Intervention.ALLOW
        caught += int(was_caught)
        per_operator[operator].append(was_caught)

    return {
        "n": n,
        "caught": caught,
        "mutation_score": caught / n,
        "per_operator": {
            name: (sum(results) / len(results) if results else None) for name, results in per_operator.items()
        },
    }


def main() -> int:
    result = run_mutation_testing()
    print("ControlPlane — mutation testing (inputs mutated, not code)")
    print(f"  n                : {result['n']}")
    print(f"  caught           : {result['caught']}")
    print(f"  mutation score   : {result['mutation_score']:.3f}")
    print("  per operator:")
    for name, score in result["per_operator"].items():
        print(f"    {name:32s} {score if score is None else f'{score:.3f}'}")
    print()
    print("  Caveat (Just & Ernst, FSE'14): mutants correlate with but do not")
    print("  perfectly represent real faults. Reported as a lower bound and a")
    print("  regression signal, not a real-world catch rate.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
