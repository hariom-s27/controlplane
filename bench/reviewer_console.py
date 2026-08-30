#!/usr/bin/env python3
"""S17 — the reviewer console. Terminal version (the roadmap's own sanctioned
alternative to FastAPI+HTMX: "same experiment, less pretty, still produces
the measurement"). Chosen here to spend the time budget on the pipeline
this console MEASURES rather than on a web UI for it.

D12, a cognitive forcing function: the reviewer sees the receipt with the
verdict, reasons, and root_cause stripped out, commits APPROVE or BLOCK,
and only then sees what the gate actually decided.
Revealing the verdict first would measure compliance with an explanation,
not independent judgement — explanations increase acceptance regardless of
correctness.

    python bench/reviewer_console.py                  # interactive

Consumes pending_actions.jsonl and writes the review decision and agreement
back to that queue. It also writes reports/reviewer_agreement.json.
That file needs a real human running this interactively.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "reports" / "reviewer_agreement.json"
from controlplane.escalation import PENDING_QUEUE, pending_items, record_review


def _present_case(receipt: dict) -> None:
    print("-" * 72)
    print(f"trace_id: {receipt['trace_id']}")
    print(f"action  : {receipt['action']['tool']}({receipt['action']['args']})")
    print("claims:")
    for c in receipt["claims"]:
        print(f"  - {c['kind']:32s} tier={c['tier']}  load_bearing={c['load_bearing']}  asserted={c['asserted']!r}")
    print("evidence:")
    for e in receipt["evidence"]:
        print(f"  - {e['claim_id']:40s} value={e['value']!r}  source={e['source']}  "
              f"reliability={e['reliability_class']}  confidence={e['confidence']}")
        print(f"      query: {e['query']}")
    print()


def _reveal(receipt: dict) -> None:
    print(f"actual verdict     : {receipt['verdict']}")
    print(f"actual intervention: {receipt['intervention']}")
    print(f"root_cause         : {receipt['root_cause']}")
    for r in receipt["reasons"]:
        print(f"  reason: {r['rule']} expected={r['expected']!r} observed={r['observed']!r}")
    print("-" * 72)
    print()


def run() -> dict:
    items = pending_items()
    if not items:
        print(f"No pending actions found at {PENDING_QUEUE}.")
        return {"n": 0, "agreement_rate": None}

    agreements = 0
    rows = []
    for item in items:
        receipt = item["receipt"]
        print(f"queue_id: {item['queue_id']}")
        _present_case(receipt)
        human_call = ""
        while human_call not in ("A", "B"):
            human_call = input("Your call?  [A]PPROVE / [B]LOCK  ").strip().upper()
        human_call = {"A": "APPROVE", "B": "BLOCK"}[human_call]

        _reveal(receipt)
        reviewed = record_review(item["queue_id"], human_call)
        gate_call = reviewed["review"]["gate_decision"]
        agree = reviewed["review"]["agreement"]
        agreements += int(agree)
        rows.append({"queue_id": item["queue_id"], "trace_id": receipt["trace_id"], "human_call": human_call, "gate_call": gate_call, "agree": agree})
        print(f"{'AGREE' if agree else 'DISAGREE'} — human said {human_call}, gate said {gate_call}\n")

    result = {
        "n": len(items),
        "agreements": agreements,
        "agreement_rate": agreements / len(items),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    return result


def main() -> int:
    argparse.ArgumentParser(description="Review pending actions").parse_args()
    result = run()
    if result["agreement_rate"] is not None:
        print(f"\nhuman-gate agreement rate: {result['agreement_rate']:.1%} (n={result['n']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
