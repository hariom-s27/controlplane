#!/usr/bin/env python3
"""S17 — the reviewer console. Terminal version (the roadmap's own sanctioned
alternative to FastAPI+HTMX: "same experiment, less pretty, still produces
the measurement"). Chosen here to spend the time budget on the pipeline
this console MEASURES rather than on a web UI for it.

D12, a cognitive forcing function: the reviewer sees the receipt with the
verdict, reasons, and root_cause stripped out, commits APPROVE / BLOCK /
ESCALATE FIRST, and only then sees what the gate actually decided.
Revealing the verdict first would measure compliance with an explanation,
not independent judgement — explanations increase acceptance regardless of
correctness.

    python bench/reviewer_console.py                  # interactive
    python bench/reviewer_console.py --auto-approve    # non-interactive smoke test only

Writes reports/reviewer_agreement.json: the human-gate agreement rate.
That file needs a REAL human running this interactively — --auto-approve
exists only to prove the mechanics don't crash, and is labelled as such in
its own output, never presented as a measurement.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DECISIONS = ROOT / "decisions.jsonl"
OUT = ROOT / "reports" / "reviewer_agreement.json"

_GATE_TO_HUMAN = {"ALLOW": "APPROVE", "BLOCK": "BLOCK", "ESCALATE": "ESCALATE", "MODIFY": "ESCALATE", "OBSERVE_ONLY": "APPROVE"}


def _load_decisions() -> list[dict]:
    if not DECISIONS.exists():
        return []
    lines = DECISIONS.read_text(encoding="utf-8").splitlines()
    out = []
    for raw in lines:
        entry = json.loads(raw)
        out.append(entry["receipt"] if "receipt" in entry else entry)
    return out


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


def run(auto_approve: bool = False) -> dict:
    receipts = _load_decisions()
    if not receipts:
        print(f"No decisions found at {DECISIONS}. Run `make demo` (or the knowledge assistant) first.")
        return {"n": 0, "agreement_rate": None}

    agreements = 0
    rows = []
    for receipt in receipts:
        _present_case(receipt)
        if auto_approve:
            human_call = "APPROVE"
            print("[--auto-approve] mechanical smoke test only, not a real reviewer call\n")
        else:
            human_call = ""
            while human_call not in ("A", "B", "E"):
                human_call = input("Your call?  [A]PPROVE / [B]LOCK / [E]SCALATE  ").strip().upper()
            human_call = {"A": "APPROVE", "B": "BLOCK", "E": "ESCALATE"}[human_call]

        _reveal(receipt)
        gate_call = _GATE_TO_HUMAN.get(receipt["intervention"], receipt["intervention"])
        agree = human_call == gate_call
        agreements += int(agree)
        rows.append({"trace_id": receipt["trace_id"], "human_call": human_call, "gate_call": gate_call, "agree": agree})
        print(f"{'AGREE' if agree else 'DISAGREE'} — human said {human_call}, gate said {gate_call}\n")

    result = {
        "n": len(receipts),
        "agreements": agreements,
        "agreement_rate": agreements / len(receipts),
        "auto_approve_smoke_test": auto_approve,
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-approve", action="store_true",
                         help="Non-interactive smoke test only — proves the console runs, is NOT a measurement.")
    args = parser.parse_args()
    result = run(auto_approve=args.auto_approve)
    if result["agreement_rate"] is not None:
        print(f"\nhuman-gate agreement rate: {result['agreement_rate']:.1%} (n={result['n']})")
        if args.auto_approve:
            print("(--auto-approve was used: this number is a smoke test artifact, not a real measurement.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
