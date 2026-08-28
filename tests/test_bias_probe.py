"""S14 checkpoint. decide() has no protected-attribute input at all; the
probe's own synthetic group label is assigned independently of every fact
decide() reads. This must come back "no detectable difference" — and with
a stated, quantified minimum detectable effect, not just a bare p-value.
"""

from __future__ import annotations

from controlplane.bias_probe import run_probe


def test_probe_finds_no_detectable_difference_with_a_quantified_mde():
    result = run_probe(n_pairs=200, seed=20260814)
    assert result.conclusion == "no detectable difference"
    assert result.p_value >= result.alpha
    assert 0 < result.mde_at_80pct_power < 1  # a real, finite, quantified effect size


def test_probe_is_reproducible_given_the_same_seed():
    r1 = run_probe(n_pairs=200, seed=20260814)
    r2 = run_probe(n_pairs=200, seed=20260814)
    assert r1.group_a_block_rate == r2.group_a_block_rate
    assert r1.group_b_block_rate == r2.group_b_block_rate
    assert r1.p_value == r2.p_value
