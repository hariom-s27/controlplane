"""S15 checkpoint. ~200 mutants, one operator per docs/invariants.md's
table. A 1.0 score here means each of these six specific corruptions has a
dedicated check catching it — not that the gate catches every conceivable
real fault (see the Just & Ernst caveat in docs/invariants.md).
"""

from __future__ import annotations

from controlplane.mutation import run_mutation_testing


def test_mutation_score_is_high_and_every_operator_is_exercised():
    result = run_mutation_testing(n=200, seed=20260814)
    assert result["n"] == 200
    assert result["mutation_score"] >= 0.9
    for operator, score in result["per_operator"].items():
        assert score is not None, f"operator {operator} was never sampled — increase n or check MUTATORS"
        assert score >= 0.9, f"operator {operator} only caught {score:.2f}"
