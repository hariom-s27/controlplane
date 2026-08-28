#!/usr/bin/env python3
"""SEB-1, Experiment 3 — order_id cross-validation (D52).

D52's own measurement says this is the highest-value unbuilt check, because
tool-call interception concentrates the ENTIRE verification burden onto
order_id: resolve it wrong and everything downstream is confidently wrong
about the wrong order. This experiment measures verdict accuracy WITH and
WITHOUT controlplane/predicates' R3 attributes_match check, on cases where
resolution goes to a distractor order (same customer, one overlapping
attribute — the real ORD-88461/ORD-88472 shoes/shorts pair, generalized).

Honesty note the roadmap explicitly asks for: a case only "actually had a
distractor" when the generator below places one AND the simulated agent
picks it. Distractor PRESENCE and RESOLUTION ERROR are reported as two
separate rates — collapsing them would overstate what's actually tested.
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import dateparser  # noqa: F401
except ImportError:
    raise SystemExit("FATAL: dateparser missing. Results are invalid without it.")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.decide import decide
from controlplane.ladder import classify_claims
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Intervention, ProposedAction, Reliability, Tier

TODAY = date(2026, 8, 14)
NOW = datetime.now(timezone.utc)
MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {}, "manifest_id": "servicing-v1", "_name": "servicing"}
COLOURS = ["blue", "red", "grey", "black"]
CATEGORIES = ["shoes", "shorts", "jacket", "t-shirt"]


def _make_case(rng: random.Random, place_distractor: bool, agent_picks_distractor: bool) -> dict:
    """Target: what the customer actually means. Distractor (if placed):
    same customer, same colour, DIFFERENT category — the actual shoes/shorts
    pattern in data/seed/orders.json, generalized."""
    colour = rng.choice(COLOURS)
    target_category = rng.choice(CATEGORIES)
    distractor_category = rng.choice([c for c in CATEGORIES if c != target_category])
    has_distractor = place_distractor
    resolves_to_distractor = has_distractor and agent_picks_distractor

    resolved_category = distractor_category if resolves_to_distractor else target_category
    days_ago = rng.randint(0, 7)  # otherwise-clean case: window/authority/customer all fine
    amount_paise = rng.randint(50_000, 2_000_000)

    return {
        "days_ago": days_ago,
        "amount_paise": amount_paise,
        "claimed_colour": colour,
        "claimed_category": target_category,  # what the customer actually described
        "resolved_colour": colour,  # the wrong order still shares the colour — that's the whole trap
        "resolved_category": resolved_category,  # what order attributes_match actually resolves to
        "has_distractor": has_distractor,
        "wrong_order_resolved": resolves_to_distractor,
        "gold_verdict": "CONTRADICTED" if resolves_to_distractor else "VERIFIED",
    }


def _decide_for(case: dict, *, use_attributes_check: bool) -> str:
    window_claim = Claim(id="w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-X", tier=Tier.C2)
    authority_claim = Claim(id="a", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject="ORD-X", tier=Tier.C2)
    entity_claim = Claim(id="e", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="ORD-X", tier=Tier.C1)
    claims = [window_claim, authority_claim, entity_claim]
    if use_attributes_check:
        claims.append(Claim(id="attr", kind=ClaimKind.ORDER_ATTRIBUTES_MATCH, subject="ORD-X", tier=Tier.C2))
    claims = classify_claims(claims)

    delivered_at = (TODAY - timedelta(days=case["days_ago"])).isoformat()
    evidence = [
        Evidence(claim_id="w", value=delivered_at, source="orders.db", query="...", fetched_at=NOW,
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
        Evidence(claim_id="a", value=2_500_000, source="manifest:servicing", query="...", fetched_at=NOW,
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
        # entity_match is customer-level only — a distractor order from the
        # SAME customer passes this by construction, which is D52's whole
        # point: identity alone cannot catch a wrong-order resolution.
        Evidence(claim_id="e", value="CUST-SAME", source="orders.db", query="...", fetched_at=NOW,
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
    ]
    predicate_result = {
        "within_window": case["days_ago"] <= 7,
        "within_authority": case["amount_paise"] <= 2_500_000,
        "entity_match": True,
    }
    if use_attributes_check:
        evidence.append(Evidence(
            claim_id="attr", value={"colour": case["resolved_colour"], "category": case["resolved_category"]},
            source="orders.db", query="...", fetched_at=NOW,
            reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
        ))
        predicate_result["attributes_match"] = (
            case["claimed_colour"] == case["resolved_colour"] and case["claimed_category"] == case["resolved_category"]
        )

    action = ProposedAction(
        tool="issue_refund", order_id="ORD-X", amount_paise=case["amount_paise"], currency="INR",
        item_colour=case["claimed_colour"], item_category=case["claimed_category"],
    )
    decision = decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST)
    return "VERIFIED" if decision.intervention is Intervention.ALLOW else "CONTRADICTED"


def run(n: int = 200, seed: int = 20260814) -> dict:
    rng = random.Random(seed)
    cases = []
    for _ in range(n):
        place_distractor = rng.random() < 0.5  # only ~half the corpus even has a distractor at all
        agent_picks_distractor = place_distractor and rng.random() < 0.5
        cases.append(_make_case(rng, place_distractor, agent_picks_distractor))

    n_with_distractor = sum(c["has_distractor"] for c in cases)
    n_wrong_resolution = sum(c["wrong_order_resolved"] for c in cases)

    correct_with_check = sum(_decide_for(c, use_attributes_check=True) == c["gold_verdict"] for c in cases)
    correct_without_check = sum(_decide_for(c, use_attributes_check=False) == c["gold_verdict"] for c in cases)

    return {
        "n": n,
        "n_with_distractor_present": n_with_distractor,
        "n_with_wrong_order_actually_resolved": n_wrong_resolution,
        "accuracy_with_attributes_check": correct_with_check / n,
        "accuracy_without_attributes_check": correct_without_check / n,
    }


def main() -> int:
    result = run()
    print("SEB-1 Exp 3 — order_id cross-validation (D52)")
    print(f"  n                                    : {result['n']}")
    print(f"  cases with a distractor present      : {result['n_with_distractor_present']} "
          f"({result['n_with_distractor_present'] / result['n']:.1%})")
    print(f"  cases where wrong order was resolved : {result['n_with_wrong_order_actually_resolved']} "
          f"({result['n_with_wrong_order_actually_resolved'] / result['n']:.1%})")
    print(f"  verdict accuracy WITH attributes_match   : {result['accuracy_with_attributes_check']:.3f}")
    print(f"  verdict accuracy WITHOUT attributes_match: {result['accuracy_without_attributes_check']:.3f}")
    print()
    print("  Distractor presence and wrong-order resolution are reported")
    print("  separately on purpose — this generator controls both explicitly,")
    print("  unlike phase 1's SEB-1 v1, which only ever created a distractor")
    print("  when a same-item order happened to exist, at uncontrolled density.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
