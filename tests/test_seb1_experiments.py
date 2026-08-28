"""S16 checkpoint — Exp 3 (D52 cross-validation) and Exp 5 (confusion matrix)
run and produce sane, honestly-labelled results."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from seb1_exp3_cross_validation import run as run_exp3  # noqa: E402
from seb1_exp5_confusion_matrix import run as run_exp5  # noqa: E402


def test_exp3_attributes_check_improves_accuracy_on_distractor_cases():
    result = run_exp3(n=200, seed=20260814)
    assert result["n_with_distractor_present"] > 0
    assert result["n_with_wrong_order_actually_resolved"] > 0
    assert result["accuracy_with_attributes_check"] == 1.0
    assert result["accuracy_without_attributes_check"] < result["accuracy_with_attributes_check"]


def test_exp5_confusion_matrix_diagonal_and_cost_fields_present():
    result = run_exp5(n_per_class=50, seed=20260814)
    assert result["total"] == 200
    for cls, m in result["per_class"].items():
        assert 0.0 <= m["precision"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0
    cw = result["cost_weighted"]
    assert "false_allow_total_paise" in cw
    assert "false_block_review_count" in cw
