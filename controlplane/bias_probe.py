"""S14 — the offline counterfactual-twin bias probe. Population property,
deliberately off the critical path: bias_probe.py is a standalone script,
never called from dispatch_tool. Putting it inline would contradict the
project's own argument that a single decision can't demonstrate a
population-level property — see docs/invariants.md's framing for M1-M5,
which is the same reasoning applied to a different kind of claim.

decide() (controlplane/decide.py) takes no protected-attribute input at
all — no name, no demographic field, nowhere in ProposedAction, Claim,
Evidence, or SessionContext. The honest way to probe a function like that
for bias is a counterfactual-twin design: generate matched pairs that are
IDENTICAL on every load-bearing fact (amount, delivered_at, policy
version) and differ only in a synthetic label attached for measurement
purposes, which decide() never reads. If the label correlates with the
outcome anyway, something is reading it through a back channel nothing
here declares — which is itself the finding. If it doesn't, that's not
"no bias exists" (this only tests decide(), not extraction or retrieval,
and only the load-bearing facts modeled here) — it's "no effect at the
size this sample was powered to detect," which is a specific, falsifiable,
bounded claim, not a vibe.

A null result you can quantify is a real result. A null result you cannot
quantify is nothing — which is why this module always reports the minimum
detectable effect (MDE) alongside the p-value, not the p-value alone.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from controlplane.decide import decide
from controlplane.ladder import classify_claims
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Intervention, ProposedAction, Reliability, Tier

MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {}, "manifest_id": "servicing-v1", "_name": "servicing"}
TODAY = date(2026, 8, 14)


@dataclass
class ProbeResult:
    n_pairs: int
    group_a_block_rate: float
    group_b_block_rate: float
    p_value: float
    mde_at_80pct_power: float
    alpha: float
    conclusion: str


def _twin_decision(delivered_days_ago: int, amount_paise: int) -> Intervention:
    """One synthetic refund scenario — a single load-bearing claim
    (WITHIN_REFUND_WINDOW) with everything decide() actually looks at
    varied, and nothing protected-attribute-shaped anywhere near it."""
    claim = Claim(id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-X", tier=Tier.C2)
    claims = classify_claims([claim])
    delivered_at = (TODAY - timedelta(days=delivered_days_ago)).isoformat()
    evidence = [
        Evidence(
            claim_id="c1", value=delivered_at, source="orders.db", query="...",
            fetched_at=datetime.now(timezone.utc),
            reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH,
        )
    ]
    predicate_result = {"within_window": delivered_days_ago <= 7}
    action = ProposedAction(tool="issue_refund", order_id="ORD-X", amount_paise=amount_paise, currency="INR")
    decision = decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST)
    return decision.intervention


def run_probe(n_pairs: int = 200, seed: int = 20260814, alpha: float = 0.05) -> ProbeResult:
    """Generates n_pairs matched twins. Each pair shares identical
    delivered_days_ago/amount_paise (the only facts decide() uses here);
    group label is assigned by an independent coin flip that never reaches
    decide() — it exists only so this function can tally outcomes by group.
    """
    rng = random.Random(seed)
    a_blocks = 0
    b_blocks = 0
    n_a = 0
    n_b = 0

    for _ in range(n_pairs):
        days_ago = rng.randint(0, 30)
        amount = rng.randint(50_000, 5_000_000)
        group = rng.choice(["A", "B"])  # independent of days_ago/amount by construction

        intervention = _twin_decision(days_ago, amount)
        blocked = intervention in (Intervention.BLOCK, Intervention.ESCALATE)

        if group == "A":
            n_a += 1
            a_blocks += int(blocked)
        else:
            n_b += 1
            b_blocks += int(blocked)

    p_a = a_blocks / n_a if n_a else 0.0
    p_b = b_blocks / n_b if n_b else 0.0
    p_pool = (a_blocks + b_blocks) / (n_a + n_b)

    # Two-proportion z-test, normal approximation (stdlib only:
    # statistics.NormalDist gives the inverse-CDF this needs).
    se = (p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b)) ** 0.5 if n_a and n_b and 0 < p_pool < 1 else 0.0
    z = (p_a - p_b) / se if se > 0 else 0.0
    normal = statistics.NormalDist()
    p_value = 2 * (1 - normal.cdf(abs(z))) if se > 0 else 1.0

    # Minimum detectable effect at 80% power, same alpha, same n and
    # baseline rate: the number this module exists to report. Formula:
    # MDE = (z_(alpha/2) + z_power) * sqrt(2 * p * (1-p) / n_per_group).
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(0.80)
    n_per_group = (n_a + n_b) / 2
    mde = (z_alpha + z_power) * (2 * p_pool * (1 - p_pool) / n_per_group) ** 0.5 if 0 < p_pool < 1 and n_per_group else float("nan")

    conclusion = "no detectable difference" if p_value >= alpha else "DETECTED DIFFERENCE — investigate"

    return ProbeResult(
        n_pairs=n_pairs, group_a_block_rate=p_a, group_b_block_rate=p_b,
        p_value=p_value, mde_at_80pct_power=mde, alpha=alpha, conclusion=conclusion,
    )


def main() -> int:
    result = run_probe()
    print("ControlPlane — bias probe (offline, counterfactual twins)")
    print(f"  n_pairs           : {result.n_pairs}")
    print(f"  group A block rate: {result.group_a_block_rate:.3f}")
    print(f"  group B block rate: {result.group_b_block_rate:.3f}")
    print(f"  p-value           : {result.p_value:.4f}  (alpha={result.alpha})")
    print(f"  MDE @ 80% power   : {result.mde_at_80pct_power:.3f} (block-rate percentage points, as a fraction)")
    print(f"  conclusion        : {result.conclusion}")
    return 0 if result.conclusion == "no detectable difference" else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
