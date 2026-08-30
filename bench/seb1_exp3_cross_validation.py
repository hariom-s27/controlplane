#!/usr/bin/env python3
"""SEB-1, Experiment 3 — order_id cross-validation (D52).

D52's own measurement says this is the highest-value unbuilt check, because
tool-call interception concentrates the ENTIRE verification burden onto
order_id: resolve it wrong and everything downstream is confidently wrong
about the wrong order. This experiment measures verdict accuracy WITH and
WITHOUT the ORDER_ATTRIBUTES_MATCH check on cases where the agent's
resolution goes to a distractor order (same customer, one or more
overlapping attributes — the real ORD-88461/ORD-88472 shoes/shorts pair,
generalized).

WHAT CHANGED, and why (see docs/experiment-audit.md):

The previous version defined the gold label as "resolves to the distractor"
and used attributes_match — the check that detects resolving to the
distractor — as the detector. Same boolean, same fields: 100% agreement by
identity, and a 75% baseline that was just `1 - P(wrong resolution)` read
back off the generator's coin flips.

Now:
  * bench/exp3_corpus.py records the TRUE order id at construction time and
    writes it to a held-out file. The gold verdict is derived only as
    `resolved_order_id != true_order_id`.
  * bench/exp3_checker.py produces the predicted verdict from the case file
    alone. It has no access to the gold label — asserted by AST inspection
    in tests/test_seb1_experiments.py.
  * The corpus contains "hidden" distractors (same colour and category as
    the true order, differing only on size) that attributes_match cannot
    see. A wrong-order resolution onto one of those is a genuine miss, so
    accuracy WITH the check is below 1.0 and this experiment can fail.

Reproducible at CP_SEED=20260814. Distractor presence and wrong-order
resolution are reported as separate rates, and misses are broken out by
distractor kind.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import dateparser  # noqa: F401
except ImportError:
    raise SystemExit("FATAL: dateparser missing. Results are invalid without it.")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

from exp3_checker import predict_all  # noqa: E402
from exp3_corpus import build_corpus, load_ground_truth  # noqa: E402


def _gold_verdict(truth: dict) -> str:
    return "CONTRADICTED" if truth["resolved_order_id"] != truth["true_order_id"] else "VERIFIED"


def run(n: int = 200, seed: int = 20260814) -> dict:
    composition = build_corpus(n=n, seed=seed)
    predictions = {row["id"]: row for row in predict_all()}
    ground_truth = load_ground_truth()

    correct_with = correct_without = 0
    wrong_res_total = 0
    caught_with = caught_without = 0
    misses_with_by_kind: dict[str, int] = {"hidden": 0, "visible": 0}
    wrong_res_by_kind: dict[str, int] = {"hidden": 0, "visible": 0}

    for case_id, truth in ground_truth.items():
        gold = _gold_verdict(truth)
        pred = predictions[case_id]
        pred_with = pred["verdict_with_attributes_check"]
        pred_without = pred["verdict_without_attributes_check"]

        correct_with += int(pred_with == gold)
        correct_without += int(pred_without == gold)

        if truth["wrong_order_resolved"]:
            wrong_res_total += 1
            kind = truth["distractor_kind"]
            wrong_res_by_kind[kind] += 1
            if pred_with == "CONTRADICTED":
                caught_with += 1
            else:
                misses_with_by_kind[kind] += 1
            if pred_without == "CONTRADICTED":
                caught_without += 1

    return {
        "n": n,
        "seed": seed,
        "n_distractor_present": composition["n_distractor_present"],
        "n_distractor_hidden": composition["n_distractor_hidden"],
        "n_distractor_visible": composition["n_distractor_visible"],
        "n_wrong_order_resolved": wrong_res_total,
        "wrong_order_resolved_by_kind": wrong_res_by_kind,
        "accuracy_with_attributes_check": correct_with / n,
        "accuracy_without_attributes_check": correct_without / n,
        "wrong_resolutions_caught_with_check": caught_with,
        "wrong_resolutions_caught_without_check": caught_without,
        "wrong_resolutions_missed_with_check_by_kind": misses_with_by_kind,
    }


def main() -> int:
    r = run()
    print("SEB-1 Exp 3 — order_id cross-validation (D52)")
    print(f"  seed                                     : {r['seed']}")
    print(f"  n                                        : {r['n']}")
    print(f"  distractor present                       : {r['n_distractor_present']} "
          f"(hidden={r['n_distractor_hidden']}, visible={r['n_distractor_visible']})")
    print(f"  wrong order actually resolved            : {r['n_wrong_order_resolved']} "
          f"({r['wrong_order_resolved_by_kind']})")
    print(f"  verdict accuracy WITH attributes_match   : {r['accuracy_with_attributes_check']:.3f}")
    print(f"  verdict accuracy WITHOUT attributes_match: {r['accuracy_without_attributes_check']:.3f}")
    print(f"  wrong resolutions caught  WITH check     : {r['wrong_resolutions_caught_with_check']} / {r['n_wrong_order_resolved']}")
    print(f"  wrong resolutions caught  WITHOUT check  : {r['wrong_resolutions_caught_without_check']} / {r['n_wrong_order_resolved']}")
    print(f"  wrong resolutions MISSED  WITH check     : {r['wrong_resolutions_missed_with_check_by_kind']} "
          f"(the check reads colour+category only, so hidden distractors get through)")
    print()
    print("  Gold verdict is `resolved_order_id != true_order_id`, derived from")
    print("  bench/exp3_ground_truth.jsonl — a file bench/exp3_checker.py never opens.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
