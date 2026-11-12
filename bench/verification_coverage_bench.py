#!/usr/bin/env python3
"""P1 — deterministic verification-coverage metric check.

This validates that the coverage NUMBER is computed correctly. It is not a
risk curve and makes no claim that coverage equals a probability of
correctness — coverage is "how much of the load-bearing claim set was
actually checked against authoritative evidence", nothing more
(docs/verification-coverage.md).

Every case is built by hand with a known expected coverage, run through the
real `controlplane.decide.decide()` (no reimplementation, no model call, no
database), and the ledger it produces is compared against the expectation.
Deterministic: same input, same output, every run.

    python bench/verification_coverage_bench.py            # prints JSON, exits non-zero on any mismatch
    python bench/verification_coverage_bench.py --write    # also regenerates the committed report

`--write` regenerates `reports/verification-coverage.md` only. It does not
touch `reports/summary.json` or any other committed artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Benchmark-only: lets `python bench/verification_coverage_bench.py` run without
# the caller exporting CP_RECEIPT_SECRET. Clearly non-production, only set if the
# environment does not already provide one, and does not affect receipt security
# or any P1 verification semantics.
os.environ.setdefault("CP_RECEIPT_SECRET", "coverage-bench-secret-not-for-production")

from controlplane.decide import decide  # noqa: E402
from controlplane.ladder import classify_claims  # noqa: E402
from controlplane.registry.clock import now  # noqa: E402
from controlplane.receipt import build_receipt, verify  # noqa: E402
from controlplane.schema import (  # noqa: E402
    Claim,
    ClaimKind,
    Confidence,
    Evidence,
    ProposedAction,
    Reliability,
)

REPORTS = ROOT / "reports"

MANIFEST = {
    "reliability_floor": "corroborated",
    "verdict_handling": {"UNVERIFIABLE": "escalate", "SOURCE_UNRELIABLE": "escalate"},
    "manifest_id": "coverage-bench-v1",
    "_name": "coverage_bench",
    "compensation": {"compensability": "fully", "action": "reverse_it"},
}

# One load-bearing, verification-eligible ClaimKind per Zen predicate flag, so
# a decision's coverage can be dialled to any k/5 by flipping flags.
FIVE = [
    (ClaimKind.ORDER_BELONGS_TO_CUSTOMER, "entity_match"),
    (ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER, "amount_sane"),
    (ClaimKind.WITHIN_REFUND_WINDOW, "within_window"),
    (ClaimKind.AMOUNT_WITHIN_AUTHORITY, "within_authority"),
    (ClaimKind.ORDER_ATTRIBUTES_MATCH, "attributes_match"),
]

ACTION = ProposedAction(tool="issue_refund", order_id="ORD-BENCH", amount_paise=100_000, currency="INR")


def _ev(claim_id: str, *, reliability=Reliability.CORROBORATED, confidence=Confidence.HIGH, value="x") -> Evidence:
    return Evidence(
        claim_id=claim_id, value=value, source="orders.db", query="SELECT ...",
        fetched_at=now(), reliability_class=reliability, confidence=confidence,
    )


def _decision(outcomes, *, extra_claims=None, reliabilities=None):
    """outcomes[i] in {verified, contradicted, unverified, unavailable} for the
    i-th of the FIVE load-bearing eligible claims. extra_claims: list of
    (Claim, Evidence|None) appended verbatim (for unmodelled / not-eligible)."""
    n = len(outcomes)
    reliabilities = reliabilities or [Reliability.CORROBORATED] * n
    claims = classify_claims([
        Claim(id=f"ORD-BENCH:{k.value}", kind=k, subject="ORD-BENCH") for k, _ in FIVE[:n]
    ])
    evidence, predicate_result = [], {}
    for (kind, field), outcome, rel in zip(FIVE[:n], outcomes, reliabilities):
        cid = f"ORD-BENCH:{kind.value}"
        if outcome == "unavailable":
            continue
        evidence.append(_ev(cid, reliability=rel))
        if outcome == "verified":
            predicate_result[field] = True
        elif outcome == "contradicted":
            predicate_result[field] = False
        elif outcome == "unverified":
            pass
        else:
            raise ValueError(outcome)
    for claim, ev in (extra_claims or []):
        claims.append(claim)
        if ev is not None:
            evidence.append(ev)
    return decide("t-bench", "coverage-bench-v1", ACTION, claims, evidence, predicate_result, MANIFEST)


# --------------------------------------------------------------------------
# Cases: (name, decision, expected)
# --------------------------------------------------------------------------


def _pct_cases():
    grid = {
        "coverage_100pct": (["verified"] * 5, 5, 5, 1.0),
        "coverage_80pct":  (["verified"] * 4 + ["contradicted"], 4, 5, 0.8),
        "coverage_60pct":  (["verified"] * 3 + ["contradicted", "unverified"], 3, 5, 0.6),
        "coverage_40pct":  (["verified"] * 2 + ["contradicted", "unavailable", "unverified"], 2, 5, 0.4),
        "coverage_20pct":  (["verified"] + ["contradicted", "unavailable", "unverified", "contradicted"], 1, 5, 0.2),
        "coverage_0pct":   (["contradicted", "unavailable", "unverified", "contradicted", "unavailable"], 0, 5, 0.0),
    }
    for name, (outcomes, verified, eligible, value) in grid.items():
        yield name, _decision(outcomes), {"verified": verified, "eligible": eligible, "value": value, "n_a": False}


def _edge_cases():
    # missing evidence -> UNAVAILABLE, not verified
    yield ("missing_evidence",
           _decision(["verified", "unavailable", "verified", "verified", "verified"]),
           {"verified": 4, "eligible": 5, "value": 0.8, "n_a": False,
            "expect_status": ("ORD-BENCH:amount_not_exceeding_order", "unavailable")})

    # contradiction -> CONTRADICTED, not verified
    yield ("contradiction",
           _decision(["verified", "verified", "contradicted", "verified", "verified"]),
           {"verified": 4, "eligible": 5, "value": 0.8, "n_a": False,
            "expect_status": ("ORD-BENCH:within_refund_window", "contradicted")})

    # source unavailable across the board -> 0 / N
    yield ("source_unavailable_all",
           _decision(["unavailable"] * 5),
           {"verified": 0, "eligible": 5, "value": 0.0, "n_a": False})

    # sub-reliability-floor evidence that would pass -> UNVERIFIED, not verified
    yield ("below_reliability_floor",
           _decision(["verified"], reliabilities=[Reliability.INFERRED]),
           {"verified": 0, "eligible": 1, "value": 0.0, "n_a": False,
            "expect_status": ("ORD-BENCH:order_belongs_to_customer", "unverified")})

    # unmodelled claim -> UNMODELLED, not dropped, does not inflate coverage
    unmodelled = Claim(id="ORD-BENCH:mystery", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-BENCH")
    yield ("unmodelled_claim",
           _decision(["verified", "verified"], extra_claims=[(unmodelled, None)]),
           {"verified": 2, "eligible": 2, "value": 1.0, "n_a": False,
            "expect_extracted": 3, "expect_modelled": 2, "expect_unmodelled": 1,
            "expect_status": ("ORD-BENCH:mystery", "not_eligible")})

    # mixed states -> every counter correct at once
    yield ("mixed_states",
           _decision(["verified", "contradicted", "unverified", "unavailable", "verified"]),
           {"verified": 2, "eligible": 5, "value": 0.4, "n_a": False,
            "expect_counts": {"contradicted": 1, "unverified": 1, "unavailable": 1}})

    # zero eligible claims -> N/A, never 100%
    intent = classify_claims([Claim(id="ORD-BENCH:intent", kind=ClaimKind.CUSTOMER_INTENT, subject="ORD-BENCH")])[0]
    yield ("zero_eligible",
           decide("t-bench", "coverage-bench-v1", ACTION, [intent], [], {}, MANIFEST),
           {"verified": 0, "eligible": 0, "value": None, "n_a": True})


def _check(name, decision, expected) -> dict:
    L = decision.verification_ledger
    cov = L.coverage
    problems = []

    if cov.verified != expected["verified"]:
        problems.append(f"verified {cov.verified} != {expected['verified']}")
    if cov.eligible != expected["eligible"]:
        problems.append(f"eligible {cov.eligible} != {expected['eligible']}")
    if expected["value"] is None:
        if cov.value is not None:
            problems.append(f"value {cov.value} != None")
    elif cov.value != expected["value"]:
        problems.append(f"value {cov.value} != {expected['value']}")
    if cov.n_a != expected["n_a"]:
        problems.append(f"n_a {cov.n_a} != {expected['n_a']}")

    # invariants (PART 8)
    if L.claims_modelled + L.claims_unmodelled != L.claims_extracted:
        problems.append("MODELLED + UNMODELLED != EXTRACTED")
    status_total = L.verified_claims + L.contradicted_claims + L.unverified_claims + L.unavailable_claims
    if status_total > L.verification_eligible_claims:
        problems.append("status counts exceed VERIFICATION_ELIGIBLE")
    lb_elig = [r for r in L.claims if r.load_bearing and r.verification_eligible]
    recomputed = (round(sum(1 for r in lb_elig if r.verification_status.value == "verified") / len(lb_elig), 6)
                  if lb_elig else None)
    if recomputed != cov.value:
        problems.append(f"coverage {cov.value} != recomputed {recomputed}")

    if "expect_extracted" in expected and L.claims_extracted != expected["expect_extracted"]:
        problems.append(f"extracted {L.claims_extracted} != {expected['expect_extracted']}")
    if "expect_modelled" in expected and L.claims_modelled != expected["expect_modelled"]:
        problems.append(f"modelled {L.claims_modelled} != {expected['expect_modelled']}")
    if "expect_unmodelled" in expected and L.claims_unmodelled != expected["expect_unmodelled"]:
        problems.append(f"unmodelled {L.claims_unmodelled} != {expected['expect_unmodelled']}")
    if "expect_status" in expected:
        cid, want = expected["expect_status"]
        got = next((r.verification_status.value for r in L.claims if r.claim_id == cid), None)
        if got != want:
            problems.append(f"{cid} status {got} != {want}")
    for k, want in expected.get("expect_counts", {}).items():
        got = getattr(L, f"{k}_claims")
        if got != want:
            problems.append(f"{k}_claims {got} != {want}")

    # the signed receipt must carry a reconstructable block
    receipt = build_receipt(decision, {"tool": "issue_refund", "order_id": "ORD-BENCH"}, {"decide": 0.1})
    block = receipt["verification_coverage"]
    if not verify(receipt):
        problems.append("receipt signature invalid")
    if block is None or block["coverage"] != cov.value or block["verified"] != cov.verified:
        problems.append("receipt block does not match ledger")

    return {
        "case": name,
        "verdict": decision.verdict.value,
        "intervention": decision.intervention.value,
        "coverage": {
            "verified": cov.verified, "eligible": cov.eligible,
            "value": cov.value, "basis": cov.basis, "n_a": cov.n_a,
        },
        "counts": {
            "extracted": L.claims_extracted, "modelled": L.claims_modelled,
            "unmodelled": L.claims_unmodelled, "load_bearing": L.load_bearing_claims,
            "verification_eligible": L.verification_eligible_claims,
            "verified": L.verified_claims, "contradicted": L.contradicted_claims,
            "unverified": L.unverified_claims, "unavailable": L.unavailable_claims,
        },
        "receipt_block_matches": block is not None and block["coverage"] == cov.value,
        "pass": not problems,
        "problems": problems,
    }


def build_report() -> dict:
    results = [_check(n, d, e) for n, d, e in list(_pct_cases()) + list(_edge_cases())]
    return {
        "task": "P1_VERIFICATION_COVERAGE_METRIC_CHECK",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "what_this_is": (
            "A deterministic check that the verification-coverage number is computed "
            "correctly for a spread of known claim mixes. NOT a risk curve; coverage is "
            "not a probability of correctness."
        ),
        "coverage_basis": "load_bearing_verification_eligible_claims",
        "cases": results,
        "all_pass": all(r["pass"] for r in results),
    }


def write_markdown(report: dict) -> str:
    lines = [
        "# P1 — verification coverage: metric check",
        "",
        "Harness: `bench/verification_coverage_bench.py` (regenerate with "
        "`python bench/verification_coverage_bench.py --write`). Every row is built by "
        "hand with a known expected coverage, run through the real "
        "`controlplane.decide.decide()`, and the ledger it produces is compared against "
        "the expectation. No model call, no database, fully deterministic.",
        "",
        "**What coverage is:** verified load-bearing verification-eligible claims / "
        "load-bearing verification-eligible claims. A claim only counts as *verified* if "
        "authoritative evidence was resolved, was at or above the manifest reliability "
        "floor, and actually supported the claim's check on this decision. "
        "`CONTRADICTED`, `UNVERIFIED`, `UNAVAILABLE`, `NOT_ELIGIBLE` and `UNMODELLED` are "
        "all explicitly *not* verified. See `docs/verification-coverage.md`.",
        "",
        "**What it is not:** a probability that the action is correct, and not a "
        "risk-coverage curve. The denominator is the load-bearing claims that had an "
        "authoritative check path — not \"every claim that should have existed\".",
        "",
        "| case | verdict | intervention | verified / eligible | coverage | extracted / modelled / unmodelled | v / c / u / na | pass |",
        "|---|---|---|--:|--:|--:|--:|:--:|",
    ]
    for r in report["cases"]:
        c, n = r["coverage"], r["counts"]
        val = "N/A" if c["value"] is None else f"{c['value'] * 100:.0f}%"
        lines.append(
            f"| `{r['case']}` | {r['verdict']} | {r['intervention']} | "
            f"{c['verified']} / {c['eligible']} | {val} | "
            f"{n['extracted']} / {n['modelled']} / {n['unmodelled']} | "
            f"{n['verified']} / {n['contradicted']} / {n['unverified']} / {n['unavailable']} | "
            f"{'pass' if r['pass'] else '**FAIL**'} |"
        )
    lines += [
        "",
        f"All cases pass: **{report['all_pass']}**.",
        "",
        "Invariants checked on every case (PART 8):",
        "",
        "- `MODELLED + UNMODELLED == EXTRACTED` — no claim is dropped without a state.",
        "- `VERIFIED + CONTRADICTED + UNVERIFIED + UNAVAILABLE <= VERIFICATION_ELIGIBLE`.",
        "- `coverage == verified / eligible` recomputed from the per-claim rows.",
        "- `0 / 0` is reported as `N/A` (value `null`), never `100%` (PART 7).",
        "- the signed Decision Receipt carries a `verification_coverage` block whose "
        "`verified`/`eligible`/`coverage` match the ledger (PART 9 / PART 11 case 10).",
        "",
    ]
    text = "\n".join(lines) + "\n"
    # LF explicitly: committed reports/*.md are LF and git here has
    # core.autocrlf=false, so text-mode translation would dirty the file.
    (REPORTS / "verification-coverage.md").write_text(text, encoding="utf-8", newline="\n")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="regenerate reports/verification-coverage.md")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args()

    report = build_report()
    print(json.dumps(report, indent=None if args.compact else 2, default=str))
    if args.write:
        write_markdown(report)
        print("\nwrote reports/verification-coverage.md", file=sys.stderr)
    if not report["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
