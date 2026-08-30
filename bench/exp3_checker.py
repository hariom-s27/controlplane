#!/usr/bin/env python3
"""SEB-1 Exp 3 — the checker. Reads bench/exp3_cases.jsonl and nothing else.

This module deliberately has no path to the reference labels. It does not
import the corpus builder and never opens the held-out reference file.
tests/test_seb1_experiments.py parses this file's AST and asserts that.

For each case it runs decide() twice — with and without the
ORDER_ATTRIBUTES_MATCH claim (the R3 extension, D52) — and records the
resulting verdict. Whether that verdict is right is not this module's
concern; scoring happens in seb1_exp3_cross_validation.py.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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

CASES_PATH = ROOT / "bench" / "exp3_cases.jsonl"
PREDICTIONS_PATH = ROOT / "bench" / "exp3_predictions.jsonl"

TODAY = date(2026, 8, 14)
NOW = datetime.now(timezone.utc)
MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {}, "manifest_id": "servicing-v1", "_name": "servicing",
            "compensation": {"action": "reverse_refund", "compensability": "fully"}}
AUTHORITY_CEILING_PAISE = 2_500_000


def load_cases() -> list[dict]:
    out = []
    for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def predict_verdict(case: dict, *, use_attributes_check: bool) -> str:
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
        Evidence(claim_id="a", value=AUTHORITY_CEILING_PAISE, source="manifest:servicing", query="...", fetched_at=NOW,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
        # entity_match is customer-level only — a distractor order from the
        # SAME customer passes it by construction. That is D52's whole point.
        Evidence(claim_id="e", value="CUST-SAME", source="orders.db", query="...", fetched_at=NOW,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
    ]
    predicate_result = {
        "within_window": case["days_ago"] <= 7,
        "within_authority": case["amount_paise"] <= AUTHORITY_CEILING_PAISE,
        "entity_match": True,
    }
    if use_attributes_check:
        evidence.append(Evidence(
            claim_id="attr",
            value={"colour": case["resolved_colour"], "category": case["resolved_category"]},
            source="orders.db", query="...", fetched_at=NOW,
            reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
        ))
        # attributes_match reads colour and category only. A hidden distractor
        # (same colour+category, different size) passes this even though it is
        # the wrong order — the check's real blind spot.
        predicate_result["attributes_match"] = (
            case["claimed_colour"] == case["resolved_colour"]
            and case["claimed_category"] == case["resolved_category"]
        )

    action = ProposedAction(
        tool="issue_refund", order_id="ORD-X", amount_paise=case["amount_paise"], currency="INR",
        item_colour=case["claimed_colour"], item_category=case["claimed_category"],
    )
    decision = decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST)
    return "VERIFIED" if decision.intervention is Intervention.ALLOW else "CONTRADICTED"


def predict_all() -> list[dict]:
    rows = []
    for case in load_cases():
        rows.append({
            "id": case["id"],
            "verdict_with_attributes_check": predict_verdict(case, use_attributes_check=True),
            "verdict_without_attributes_check": predict_verdict(case, use_attributes_check=False),
        })
    PREDICTIONS_PATH.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")
    return rows


if __name__ == "__main__":
    for row in predict_all():
        print(row)
