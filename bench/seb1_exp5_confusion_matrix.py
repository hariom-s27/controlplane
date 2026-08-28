#!/usr/bin/env python3
"""SEB-1, Experiment 5 — a per-verdict confusion matrix.

The brief asks for false-positive and false-negative rates explicitly
under "Metrics & monitoring" — a single accuracy number can't answer that,
because a false ALLOW and a false BLOCK have completely different costs
(D49's whole point, applied to measurement instead of intervention design).

Four gold categories, generated directly (not via the LLM agent — this
benchmarks the VERIFICATION layer's own accuracy on known-truth inputs,
the same scoping choice controlplane/bias_probe.py makes and for the same
reason: reproducible, labelled, and fast enough to run at n=200+):

  ALLOW              genuinely clean: in window, in authority, right customer
  BLOCK              genuinely bad: a reliable, real predicate violation
  ESCALATE           genuinely unresolvable: a load-bearing claim has no evidence
  SOURCE_UNRELIABLE  genuinely uncertain: reliable facts look fine, but the
                     evidence backing them is below the reliability floor
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
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Intervention, ProposedAction, Reliability, Tier, Verdict

TODAY = date(2026, 8, 14)
NOW = datetime.now(timezone.utc)
MANIFEST = {"reliability_floor": "corroborated", "verdict_handling": {"UNVERIFIABLE": "escalate", "SOURCE_UNRELIABLE": "escalate"},
            "manifest_id": "servicing-v1", "_name": "servicing"}
CLASSES = ["ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"]

# Illustrative, clearly-labelled ASSUMPTIONS, not measured figures — no
# published per-review or per-refund-reversal cost exists in this repo.
# Swap these for real numbers the moment finance/ops has them.
ASSUMED_COST_PER_HUMAN_REVIEW_PAISE = 50_000  # INR 500/review, assumed
ASSUMED_MEAN_REFUND_PAISE = 1_500_000  # INR 15,000, assumed


def _outcome_label(decision) -> str:
    """SOURCE_UNRELIABLE is a verdict in schema.py, not an Intervention —
    surfaced as its own confusion-matrix class because a human reviewer
    cares whether an escalation means "the evidence itself is shaky" versus
    any other reason to escalate."""
    if decision.verdict is Verdict.SOURCE_UNRELIABLE:
        return "SOURCE_UNRELIABLE"
    return decision.intervention.value


def _decide(days_ago: int, amount_paise: int, customer_ok: bool, reliability: Reliability, confidence: Confidence) -> object:
    claim = Claim(id="w", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-X", tier=Tier.C2)
    entity_claim = Claim(id="e", kind=ClaimKind.ORDER_BELONGS_TO_CUSTOMER, subject="ORD-X", tier=Tier.C1)
    claims = classify_claims([claim, entity_claim])
    delivered_at = (TODAY - timedelta(days=days_ago)).isoformat()
    evidence = [
        Evidence(claim_id="w", value=delivered_at, source="orders.db", query="...", fetched_at=NOW,
                  reliability_class=reliability, confidence=confidence),
        Evidence(claim_id="e", value="CUST-A" if customer_ok else "CUST-B", source="orders.db", query="...",
                  fetched_at=NOW, reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
    ]
    predicate_result = {"within_window": days_ago <= 7, "entity_match": customer_ok}
    action = ProposedAction(tool="issue_refund", order_id="ORD-X", amount_paise=amount_paise, currency="INR")
    return decide("t", "servicing-v1", action, claims, evidence, predicate_result, MANIFEST)


def _generate(rng: random.Random, gold: str) -> object:
    amount = rng.randint(50_000, 2_000_000)
    if gold == "ALLOW":
        return _decide(rng.randint(0, 7), amount, True, Reliability.CORROBORATED, Confidence.HIGH)
    if gold == "BLOCK":
        return _decide(rng.randint(8, 30), amount, True, Reliability.CORROBORATED, Confidence.HIGH)
    if gold == "ESCALATE":
        return _decide(rng.randint(0, 7), amount, True, Reliability.CORROBORATED, Confidence.NONE)
    if gold == "SOURCE_UNRELIABLE":
        return _decide(rng.randint(0, 7), amount, True, Reliability.INFERRED, Confidence.HIGH)
    raise ValueError(gold)


def run(n_per_class: int = 50, seed: int = 20260814) -> dict:
    rng = random.Random(seed)
    matrix = {g: {p: 0 for p in CLASSES} for g in CLASSES}

    for gold in CLASSES:
        for _ in range(n_per_class):
            decision = _generate(rng, gold)
            predicted = _outcome_label(decision)
            if predicted not in CLASSES:
                predicted = "OTHER"
                matrix[gold].setdefault("OTHER", 0)
                matrix[gold]["OTHER"] += 1
            else:
                matrix[gold][predicted] += 1

    per_class = {}
    total = n_per_class * len(CLASSES)
    correct = sum(matrix[g][g] for g in CLASSES)
    for cls in CLASSES:
        tp = matrix[cls][cls]
        fn = sum(matrix[cls][p] for p in CLASSES if p != cls)
        fp = sum(matrix[g][cls] for g in CLASSES if g != cls)
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        per_class[cls] = {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn}

    # Cost-weighted error: a false ALLOW (gold BLOCK/ESCALATE/SOURCE_UNRELIABLE,
    # predicted ALLOW) costs a refund; a false BLOCK (gold ALLOW, predicted
    # anything stricter) costs one human review. Assumed unit costs above.
    false_allow_paise = 0
    false_block_reviews = 0
    for gold in CLASSES:
        for predicted, count in matrix[gold].items():
            if predicted not in CLASSES or gold == predicted:
                continue
            if predicted == "ALLOW":
                false_allow_paise += count * ASSUMED_MEAN_REFUND_PAISE
            elif gold == "ALLOW":
                false_block_reviews += count

    return {
        "n_per_class": n_per_class,
        "total": total,
        "accuracy": correct / total,
        "matrix": matrix,
        "per_class": per_class,
        "cost_weighted": {
            "false_allow_total_paise": false_allow_paise,
            "false_block_review_count": false_block_reviews,
            "false_block_total_paise": false_block_reviews * ASSUMED_COST_PER_HUMAN_REVIEW_PAISE,
            "note": "costs use ASSUMED_* constants in this file, not measured figures",
        },
    }


def main() -> int:
    result = run()
    print("SEB-1 Exp 5 — confusion matrix (gold vs predicted)")
    print(f"  n per class: {result['n_per_class']}  ·  total: {result['total']}  ·  accuracy: {result['accuracy']:.3f}")
    print()
    header = "gold\\pred".ljust(20) + "".join(c.ljust(20) for c in CLASSES)
    print(header)
    for gold in CLASSES:
        row = gold.ljust(20) + "".join(str(result["matrix"][gold].get(p, 0)).ljust(20) for p in CLASSES)
        print(row)
    print()
    for cls, m in result["per_class"].items():
        print(f"  {cls:20s} precision={m['precision']:.3f}  recall={m['recall']:.3f}  (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
    print()
    cw = result["cost_weighted"]
    print(f"  false ALLOW cost (assumed INR {ASSUMED_MEAN_REFUND_PAISE // 100:,}/refund) : "
          f"INR {cw['false_allow_total_paise'] // 100:,}")
    print(f"  false BLOCK reviews (assumed INR {ASSUMED_COST_PER_HUMAN_REVIEW_PAISE // 100:,}/review): "
          f"{cw['false_block_review_count']} -> INR {cw['false_block_total_paise'] // 100:,}")
    print(f"  ({cw['note']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
