"""S16 checkpoint — post-audit (docs/experiment-audit.md).

Exp 5 (confusion matrix) is BLOCKED: its generator was circular (cases built
by decide(), scored against decide()), so it now raises SystemExit until a
held-out gold set exists (task P03).

Exp 3 (D52 cross-validation) is rebuilt: the gold verdict comes only from
comparing two independently-recorded order ids in a held-out file that the
checker module never opens. The corpus contains distractors the attribute
check cannot see, so accuracy WITH the check is genuinely below 1.0 — the
experiment can fail.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parent.parent / "bench"
sys.path.insert(0, str(BENCH))

from seb1_exp3_cross_validation import run as run_exp3  # noqa: E402
from seb1_exp5_confusion_matrix import run as run_exp5  # noqa: E402


# --- Exp 5: blocked, not passing-but-meaningless -------------------------

def test_exp5_is_blocked_until_a_held_out_gold_set_exists():
    with pytest.raises(SystemExit) as excinfo:
        run_exp5()
    assert "BLOCKED" in str(excinfo.value)


# --- Exp 3: rebuilt against held-out labels ------------------------------

def test_exp3_attributes_check_helps_but_has_a_real_blind_spot():
    r = run_exp3(n=200, seed=20260814)
    assert r["n_distractor_present"] > 0
    assert r["n_wrong_order_resolved"] > 0
    # the check helps
    assert r["accuracy_with_attributes_check"] > r["accuracy_without_attributes_check"]
    # ...but it is NOT perfect — hidden distractors get through, so the
    # experiment is capable of producing a sub-1.0 number (i.e. it can fail)
    assert r["accuracy_with_attributes_check"] < 1.0
    assert r["wrong_resolutions_missed_with_check_by_kind"]["hidden"] > 0
    assert r["wrong_resolutions_missed_with_check_by_kind"]["visible"] == 0


def test_exp3_gold_label_is_independent_of_the_detector():
    """The circular version defined gold as 'resolves to distractor' and used
    attributes_match (which detects that) as the detector. Now the checker
    module must have no path to the ground truth at all."""
    checker_src = (BENCH / "exp3_checker.py").read_text(encoding="utf-8")
    tree = ast.parse(checker_src)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert "exp3_corpus" not in imported, "checker imports the ground-truth-owning module"
    assert not any("ground_truth" in m for m in imported)

    lowered = checker_src.lower()
    for forbidden in ("ground_truth", "true_order_id", "gold_verdict", "gold_label", "wrong_order_resolved"):
        assert forbidden not in lowered, f"checker references {forbidden!r} — it must be blind to the label"


def test_exp3_is_reproducible_given_seed():
    a = run_exp3(n=120, seed=20260814)
    b = run_exp3(n=120, seed=20260814)
    assert a["accuracy_with_attributes_check"] == b["accuracy_with_attributes_check"]
    assert a["accuracy_without_attributes_check"] == b["accuracy_without_attributes_check"]
