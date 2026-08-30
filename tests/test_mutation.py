"""S15 checkpoint — spec-derived mutation testing.

Operators come from the issue_refund tool JSON schema and
manifests/servicing.yaml, NOT from the checks decide() implements. So the
score is expected to be BELOW 1.0: the operator set deliberately includes
spec elements the gate has no mechanism to enforce (currency enum, negative
amount, latency/escalation budgets, retention, risk tier), and those
mutants SHOULD go uncaught. See docs/experiment-audit.md.

A 1.0 score here would mean the operator set had drifted back to mirroring
the implementation — the exact defect this rewrite fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from mutation import OPERATORS, run_mutation_testing  # noqa: E402


def test_score_is_below_one_because_operators_come_from_the_spec():
    result = run_mutation_testing(trials_per_operator=20, seed=20260814)
    assert result["mutation_score"] < 1.0, (
        "mutation score is 1.0 — the operator set has drifted back to mirroring "
        "decide()'s own checks. Operators must come from the spec."
    )
    # sanity floor: the real checks must still be catching their mutants
    assert result["mutation_score"] >= 0.4


def test_every_operator_is_exercised_and_matches_its_expectation():
    result = run_mutation_testing(trials_per_operator=20, seed=20260814)
    for name, rec in result["per_operator"].items():
        assert rec["trials"] > 0, f"operator {name} never ran"
        if rec["expected"] == "catchable":
            assert rec["catch_rate"] == 1.0, f"{name} is spec-catchable but caught only {rec['catch_rate']:.2f}"
        else:
            assert rec["catch_rate"] == 0.0, (
                f"{name} is marked uncatchable but the gate caught it at {rec['catch_rate']:.2f} — "
                "either the gate gained a check (update the operator) or the operator is wrong"
            )


def test_operator_sources_are_declared_and_from_the_spec():
    for op in OPERATORS:
        assert op.spec_source.startswith(("tool_schema:", "manifest:")), op
        assert op.expected in ("catchable", "uncatchable")


def test_reproducible_given_seed():
    a = run_mutation_testing(trials_per_operator=15, seed=20260814)
    b = run_mutation_testing(trials_per_operator=15, seed=20260814)
    assert a["mutation_score"] == b["mutation_score"]
    assert a["caught"] == b["caught"]
