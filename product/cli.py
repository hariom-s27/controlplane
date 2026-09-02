"""Product demo CLI — renders the MASTER-11-15 product views against one
real gold_set case, run through the real ControlPlane pipeline. Every value
printed comes from `product.pipeline.run_decision` / `reports/summary.json`;
nothing here is fabricated.

    python -m product.cli gs-001
    python -m product.cli gs-001 --replay     # also show the idempotency replay
    python -m product.cli --list              # list all 150 case ids
    python -m product.cli --random             # pick one at random
"""

from __future__ import annotations

import argparse
import json
import random
import sys

from product.pipeline import all_case_ids, case_by_id, run_decision, run_with_replay_demo
from product import views


def _hr(title: str) -> None:
    print()
    print(f"── {title} " + "─" * max(0, 60 - len(title)))


def render(case_id: str, show_replay: bool) -> None:
    case = case_by_id(case_id)
    bundle = run_decision(case)
    replayed = None
    if show_replay:
        bundle, replayed = run_with_replay_demo(case_id)

    print(f"CASE {case_id}  ({case.get('slice')})  gold={case.get('gold_label')}")
    print(f"verdict={bundle.decision.verdict.value}  intervention={bundle.decision.intervention.value}")

    _hr("EVIDENCE HEALTH")
    eh = views.evidence_health(bundle)
    print(f"  disclaimer: {eh['disclaimer']}")
    print(f"  evidence completeness   {eh['evidence_completeness']['label']}")
    print(f"  trace freshness         {eh['trace_freshness']['state']} "
          f"(max {eh['trace_freshness']['max_freshness_ms']} ms)")
    print(f"  predicate margin        {eh['predicate_margin']['overall']}")
    for e in eh["predicate_margin"]["per_claim"]:
        print(f"    - {e['claim']}: {e.get('state')} "
              f"({ {k: v for k, v in e.items() if k not in ('claim', 'state')} })")
    print(f"  claim/evidence conflict {eh['claim_evidence_conflict']['state']}")
    for c in eh["claim_evidence_conflict"]["conflicts"]:
        print(f"    - {c['claim']}: asserted={c['asserted']!r} observed={c['observed']!r}")

    _hr("EVIDENCE PASSPORT")
    ep = views.evidence_passport(bundle)
    for k in ("trace_id", "evidence_sources", "policy_version", "verification_state",
              "intervention", "execution_status", "idempotency_key",
              "receipt_id", "receipt_signature_valid"):
        print(f"  {k:24} {ep[k]}")

    _hr("DECISION INSPECTOR — why did ControlPlane decide this?")
    di = views.decision_inspector(bundle)
    for c in di["claims"]:
        print(f"  [{c['tier'] or '?'}] {c['kind']:28} load_bearing={c['load_bearing']!s:5} "
              f"asserted={c['asserted_value']!r} evidence={c['evidence_value']!r} "
              f"({c['reliability_class']}/{c['confidence']})")
    print("  reasons:")
    for r in di["policy_outcome"]:
        mark = "OK" if r["passed"] else "FAIL"
        print(f"    [{mark}] {r['rule']}: expected={r['expected']!r} observed={r['observed']!r}")
    print(f"  root_cause: {di['root_cause']}")
    print(f"  compensation: {di['compensation']}")

    _hr("DECISION TIMELINE")
    dt = views.decision_timeline(bundle, replayed=replayed)
    for stage in dt["stages"]:
        print(f"  {stage:22} {dt['status'][stage]}")

    _hr("VERIFICATION POLICY (configurable prototype)")
    vp = views.verification_policy_evaluation(bundle)
    print(f"  {views.VERIFICATION_POLICY_PROTOTYPE['label']}")
    print(f"  matched_rule={vp['matched_rule']}  prototype_action={vp['prototype_action']}  "
          f"actual={vp['actual_controlplane_intervention']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case_id", nargs="?", help="a bench/gold_set.jsonl case id, e.g. gs-001")
    p.add_argument("--list", action="store_true", help="list all case ids and exit")
    p.add_argument("--random", action="store_true", help="pick a random case id")
    p.add_argument("--replay", action="store_true", help="also demonstrate an idempotent replay")
    p.add_argument("--json", action="store_true", help="dump the raw view dicts as JSON instead of the text report")
    p.add_argument("--cost", action="store_true", help="print the Cost/Assurance view (already-measured latency) and exit")
    args = p.parse_args(argv)

    if args.list:
        for cid in all_case_ids():
            print(cid)
        return 0

    if args.cost:
        ca = views.cost_assurance_view()
        if not ca["available"]:
            print(f"COST/ASSURANCE unavailable: {ca['reason']}")
            return 1
        print(f"COST / ASSURANCE — {ca['source']}")
        print(f"{'config':22} {'C3':5} {'conc':5} {'n':6} {'p50 ms':>10} {'p95 ms':>10} {'p99 ms':>10}")
        for row in ca["configurations"]:
            print(f"{row['config']:22} {row['grounding_c3']:5} {row['concurrency']:<5} "
                  f"{row['n']:<6} {row['p50_ms']:>10} {row['p95_ms']:>10} {row['p99_ms']:>10}")
        print(f"\n{ca['qualitative_control']}")
        return 0

    case_id = args.case_id
    if args.random or case_id is None:
        case_id = random.choice(all_case_ids())

    if args.json:
        bundle = run_decision(case_by_id(case_id))
        out = {
            "evidence_health": views.evidence_health(bundle),
            "evidence_passport": views.evidence_passport(bundle),
            "decision_inspector": views.decision_inspector(bundle),
            "decision_timeline": views.decision_timeline(bundle),
            "verification_policy": views.verification_policy_evaluation(bundle),
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    render(case_id, args.replay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
