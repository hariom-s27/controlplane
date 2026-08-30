#!/usr/bin/env python3
"""SEB-1 Exp 3 — corpus builder. Owns the construction-time ground truth.

This module is the ONLY place that knows, for each case, which order the
customer actually meant. It writes two files:

  bench/exp3_cases.jsonl         what a checker legitimately sees: the
                                 order the agent resolved to, that order's
                                 real attributes, the attributes the
                                 customer described, and the other facts.

  bench/exp3_ground_truth.jsonl  HELD OUT. The true order id recorded at
                                 construction time, plus the resolved id and
                                 the distractor kind. bench/exp3_checker.py
                                 must never read this file or import this
                                 module — tests/test_seb1_experiments.py
                                 asserts it.

Why this split exists: the previous Exp 3 defined the gold label as
"resolves to the distractor" and used the attributes_match predicate — which
detects resolving to the distractor — as the detector. Label and detector
were the same boolean over the same fields, so accuracy was 100% by
identity. See docs/experiment-audit.md. The gold label now comes only from
comparing two independently-recorded order ids.

The corpus also contains distractors the attribute check CANNOT see (same
colour and category as the true order, differing only on size, which the
check does not read). A wrong-order resolution onto one of those is a real
miss for the check — which is what lets this experiment produce a verdict
accuracy below 1.0, i.e. lets it fail.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "bench" / "exp3_cases.jsonl"
GROUND_TRUTH_PATH = ROOT / "bench" / "exp3_ground_truth.jsonl"

COLOURS = ["blue", "red", "grey", "black"]
CATEGORIES = ["shoes", "shorts", "jacket", "t-shirt"]
SIZES = ["S", "M", "L", "XL"]

# Fraction of cases in which a distractor order exists for the same customer.
P_DISTRACTOR_PRESENT = 0.5
# Of those distractors, the fraction that share colour AND category with the
# true order (differing only on size) — invisible to attributes_match.
P_DISTRACTOR_HIDDEN = 0.4
# When a distractor exists, the fraction of cases where the simulated agent
# resolves to it instead of the true order.
P_AGENT_RESOLVES_WRONG = 0.5

AUTHORITY_CEILING_PAISE = 2_500_000


def _order_id(rng: random.Random) -> str:
    return f"ORD-{rng.randint(10000, 99999)}"


def _build_one(rng: random.Random, idx: int) -> tuple[dict, dict]:
    true_colour = rng.choice(COLOURS)
    true_category = rng.choice(CATEGORIES)
    true_size = rng.choice(SIZES)
    true_id = _order_id(rng)

    has_distractor = rng.random() < P_DISTRACTOR_PRESENT
    distractor_kind = None
    distractor_id = None
    distractor_attrs = None
    if has_distractor:
        distractor_id = _order_id(rng)
        if rng.random() < P_DISTRACTOR_HIDDEN:
            distractor_kind = "hidden"  # same colour+category, different size
            distractor_attrs = {
                "colour": true_colour,
                "category": true_category,
                "size": rng.choice([s for s in SIZES if s != true_size]),
            }
        else:
            distractor_kind = "visible"  # same colour, different category
            distractor_attrs = {
                "colour": true_colour,
                "category": rng.choice([c for c in CATEGORIES if c != true_category]),
                "size": rng.choice(SIZES),
            }

    wrong_order_resolved = has_distractor and rng.random() < P_AGENT_RESOLVES_WRONG
    if wrong_order_resolved:
        resolved_id = distractor_id
        resolved_attrs = distractor_attrs
    else:
        resolved_id = true_id
        resolved_attrs = {"colour": true_colour, "category": true_category, "size": true_size}

    case_id = f"exp3-{idx:04d}"

    # Otherwise-clean case: window, authority and customer identity all pass,
    # so attributes_match is the only check that can catch a wrong-order pick.
    case = {
        "id": case_id,
        "resolved_order_id": resolved_id,
        "resolved_colour": resolved_attrs["colour"],
        "resolved_category": resolved_attrs["category"],
        # what the customer described == the true order's colour/category
        "claimed_colour": true_colour,
        "claimed_category": true_category,
        "days_ago": rng.randint(0, 7),
        "amount_paise": rng.randint(50_000, 2_000_000),
    }
    ground_truth = {
        "id": case_id,
        "true_order_id": true_id,
        "resolved_order_id": resolved_id,
        "distractor_present": has_distractor,
        "distractor_kind": distractor_kind,
        "wrong_order_resolved": wrong_order_resolved,
    }
    return case, ground_truth


def build_corpus(n: int = 200, seed: int = 20260814) -> dict:
    """Writes exp3_cases.jsonl and exp3_ground_truth.jsonl. Returns a small
    summary of the corpus composition (not the experiment result)."""
    rng = random.Random(seed)
    cases, truths = [], []
    for i in range(n):
        case, truth = _build_one(rng, i)
        cases.append(case)
        truths.append(truth)

    CASES_PATH.write_text("\n".join(json.dumps(c, sort_keys=True) for c in cases) + "\n", encoding="utf-8")
    GROUND_TRUTH_PATH.write_text("\n".join(json.dumps(t, sort_keys=True) for t in truths) + "\n", encoding="utf-8")

    return {
        "n": n,
        "seed": seed,
        "n_distractor_present": sum(t["distractor_present"] for t in truths),
        "n_distractor_hidden": sum(t["distractor_kind"] == "hidden" for t in truths),
        "n_distractor_visible": sum(t["distractor_kind"] == "visible" for t in truths),
        "n_wrong_order_resolved": sum(t["wrong_order_resolved"] for t in truths),
    }


def load_ground_truth() -> dict[str, dict]:
    """For the scorer only. The checker must not call this."""
    out = {}
    for line in GROUND_TRUTH_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


if __name__ == "__main__":
    print(json.dumps(build_corpus(), indent=2))
