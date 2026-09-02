"""PRODUCT-02 CLI — renders the Evidence Passport and Decision Inspector for
one of PRODUCT-01's six judge-demo scenarios.

This module does not modify scripts/judge_demo.py. It imports its unchanged
SCENARIOS list, runs the requested scenario exactly once (the same call
scripts.judge_demo.main() already makes), builds the shared presentation
model, and renders both views from it — text or JSON.

    python -m product.judge_cli --scenario 1
    python -m product.judge_cli --scenario 1 --json
    python -m product.judge_cli            (all six)
"""

from __future__ import annotations

import argparse
import json
import sys

from product.judge_presentation import PresentationModel, build_presentation_model
from product.judge_views import decision_inspector, evidence_health_disclaimer, evidence_passport
from scripts import judge_demo as demo


def _print_kv(label: str, value: object, width: int = 22) -> None:
    print(f"  {label:<{width}} {value}")


def render_text(model: PresentationModel) -> None:
    width = 70
    print("=" * width)
    print(f"EVIDENCE PASSPORT — {model.scenario}")
    print("=" * width)
    if not model.available:
        print("NOT AVAILABLE")
        print(f"  {model.unavailable_reason}")
        return

    passport = evidence_passport(model)
    _print_kv("Profile", passport["profile"])
    _print_kv("Trace ID", passport["trace_id"])
    _print_kv("AI intent", passport["ai_intent"])
    print()
    print("  Evidence:")
    for item in passport["evidence"]:
        print(f"    - source={item['source']}  field={item['field']}  origin={item['origin']}")
        print(f"      query: {item['query']}")
        print(f"      value={item['value']!r}  reliability={item['reliability']}  freshness_ms={item['freshness_ms']}")
    print()
    _print_kv("Policy version", passport["policy_version"])
    _print_kv("Verdict", passport["verdict"])
    _print_kv("Intervention", passport["intervention"])
    _print_kv("Execution state", passport["execution_state"])
    _print_kv("Idempotency key", passport["idempotency_key"])
    _print_kv("Receipt reference", passport["receipt_reference"])
    _print_kv("Receipt verification", passport["receipt_verification"])
    _print_kv("Runtime latency (ms)", passport["runtime_latency_ms"])
    if passport["unavailable_fields"]:
        _print_kv("Unavailable fields", ", ".join(passport["unavailable_fields"]))

    print()
    print("-" * width)
    print(f"WHY DID CONTROLPLANE DECIDE THIS? — {model.scenario}")
    print("-" * width)
    inspector = decision_inspector(model)
    print(f"  AI CLAIM: {inspector['ai_claim']}")
    print("    |")
    print("    v")
    for entry in inspector["claim_evidence_chain"]:
        print(f"  {entry['claim_field']}")
        print(f"    -> {entry['evidence_field']}")
        print(f"    -> {entry['comparison_rule']}")
        print(f"    -> {entry['comparison_result']}")
    print("    |")
    print(f"  POLICY: {inspector['policy_version']}")
    print("    |")
    print(f"  PREDICATE: {inspector['predicate_result']}")
    print("    |")
    print(f"  VERDICT: {inspector['verdict']}")
    print("    |")
    print(f"  INTERVENTION: {inspector['intervention']}")
    print("    |")
    print(f"  EXECUTION: {inspector['execution_state']}")
    print()
    _print_kv("Root cause", inspector["root_cause"])
    print()
    print(f"  Evidence Health labels are descriptive only — {evidence_health_disclaimer()}")
    print("=" * width)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PRODUCT-02 Evidence Passport / Decision Inspector")
    parser.add_argument("--scenario", type=int, choices=range(1, 7), default=None)
    parser.add_argument("--json", action="store_true", help="print the raw Passport/Inspector dicts instead")
    args = parser.parse_args(argv)

    demo._check_preconditions()
    to_run = [demo.SCENARIOS[args.scenario - 1]] if args.scenario else demo.SCENARIOS

    for fn in to_run:
        result = fn()
        model = build_presentation_model(result)
        if args.json:
            print(json.dumps(
                {"evidence_passport": evidence_passport(model), "decision_inspector": decision_inspector(model)},
                indent=2, default=str,
            ))
        else:
            render_text(model)
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
