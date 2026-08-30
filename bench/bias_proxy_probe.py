#!/usr/bin/env python3
"""PROXY ANALYSIS — not a bias measurement. Read this before citing it.

The deleted counterfactual-twin probe (controlplane/bias_probe.py) drew a
group label independent of every fact decide() reads, so it had zero power
to detect anything and reported "no detectable difference" by construction.
See docs/experiment-audit.md.

This script is the opposite demonstration: it makes the group label
*correlated with an input decide() actually uses* (group A gets
systematically lower refund amounts, group B systematically higher, some
above the authority ceiling), then measures the block-rate gap. The gap is
real and the test detects it — which is the only claim being made here:
**the statistical machinery has power when an effect exists.**

What this is NOT:
  * NOT evidence of bias in decide(). `group` is not a protected attribute,
    is not passed to decide(), and the disparity is a mechanical consequence
    of the amount correlation the script itself injects.
  * NOT a substitute for the structural guarantee in
    tests/test_no_protected_attributes.py, which is the actual argument that
    decide() cannot discriminate: it has no protected-attribute input.

Stdlib only (statistics.NormalDist for the two-proportion z-test).
"""

from __future__ import annotations

import random
import statistics
import sys
from dataclasses import dataclass
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

MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {}, "manifest_id": "servicing-v1", "_name": "servicing",
            "compensation": {"action": "reverse_refund", "compensability": "fully"}}
TODAY = date(2026, 8, 14)
CEILING_PAISE = 2_500_000


@dataclass
class ProxyResult:
    n: int
    group_a_block_rate: float
    group_b_block_rate: float
    observed_gap: float
    p_value: float
    alpha: float
    detected: bool
    caveat: str


def _decide_one(days_ago: int, amount_paise: int) -> Intervention:
    window_claim = Claim(id="w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-X", tier=Tier.C2)
    authority_claim = Claim(id="a", kind=ClaimKind.AMOUNT_WITHIN_AUTHORITY, subject="ORD-X", tier=Tier.C2)
    claims = classify_claims([window_claim, authority_claim])
    delivered_at = (TODAY - timedelta(days=days_ago)).isoformat()
    now = datetime.now(timezone.utc)
    evidence = [
        Evidence(claim_id="w", value=delivered_at, source="orders.db", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
        Evidence(claim_id="a", value=CEILING_PAISE, source="manifest:servicing", query="...", fetched_at=now,
                 reliability_class=Reliability.CORROBORATED, confidence=Confidence.CERTAIN),
    ]
    predicate_result = {"within_window": days_ago <= 7, "within_authority": amount_paise <= CEILING_PAISE}
    action = ProposedAction(tool="issue_refund", order_id="ORD-X", amount_paise=amount_paise, currency="INR")
    return decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST).intervention


def run_proxy_probe(n: int = 400, seed: int = 20260814, alpha: float = 0.05) -> ProxyResult:
    rng = random.Random(seed)
    a_blocks = a_n = b_blocks = b_n = 0
    for _ in range(n):
        group = rng.choice(["A", "B"])
        days_ago = rng.randint(0, 7)  # keep the window clean; isolate the amount effect
        if group == "A":
            amount = rng.randint(50_000, 1_500_000)          # all within ceiling
            a_n += 1
        else:
            amount = rng.randint(1_500_000, 4_000_000)        # ~40% above ceiling
            b_n += 1
        blocked = _decide_one(days_ago, amount) in (Intervention.BLOCK, Intervention.ESCALATE, Intervention.MODIFY)
        if group == "A":
            a_blocks += int(blocked)
        else:
            b_blocks += int(blocked)

    p_a = a_blocks / a_n if a_n else 0.0
    p_b = b_blocks / b_n if b_n else 0.0
    p_pool = (a_blocks + b_blocks) / (a_n + b_n)
    se = (p_pool * (1 - p_pool) * (1 / a_n + 1 / b_n)) ** 0.5 if 0 < p_pool < 1 else 0.0
    z = (p_a - p_b) / se if se > 0 else 0.0
    normal = statistics.NormalDist()
    p_value = 2 * (1 - normal.cdf(abs(z))) if se > 0 else 1.0

    return ProxyResult(
        n=n, group_a_block_rate=p_a, group_b_block_rate=p_b, observed_gap=abs(p_a - p_b),
        p_value=p_value, alpha=alpha, detected=p_value < alpha,
        caveat=("group is a PROXY correlated with amount_paise, not a protected attribute; "
                "the gap is injected by this script, not produced by decide()"),
    )


def main() -> int:
    r = run_proxy_probe()
    print("ControlPlane — bias PROXY probe (NOT a bias measurement)")
    print(f"  n                 : {r.n}")
    print(f"  group A block rate : {r.group_a_block_rate:.3f}   (amounts within ceiling)")
    print(f"  group B block rate : {r.group_b_block_rate:.3f}   (amounts skew above ceiling)")
    print(f"  observed gap       : {r.observed_gap:.3f}")
    print(f"  p-value            : {r.p_value:.4g}  (alpha={r.alpha})")
    print(f"  difference detected: {r.detected}")
    print(f"  CAVEAT: {r.caveat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
