"""Claims registry check (docs/claims.yaml).

For every claim: its text is in its file, its value is in its text, its evidence
paths are tracked, and (kind fast / slow) its value is recomputed from committed
files and must match exactly. kind ci is checked for presence only.

Slow claims (recompute > ~5 s: the P04 baseline table and the P08 wrong-record
sweep) run in the normal suite; their test ids start with "slow:". No recompute
measures latency: the baseline recompute stubs the per-call timer.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLAIMS_FILE = ROOT / "docs" / "claims.yaml"
REQUIRED = ("id", "file", "text", "value", "definition", "n", "conditions", "evidence", "command", "kind")
KINDS = ("fast", "slow", "ci")


def _load_claims() -> list[dict]:
    return yaml.safe_load(CLAIMS_FILE.read_text(encoding="utf-8"))["claims"]


CLAIMS = _load_claims()


def _norm(text: str) -> str:
    return " ".join(text.split())


def _pid(claim: dict) -> str:
    return f"{claim.get('kind')}:{claim.get('id')}"


@functools.lru_cache(maxsize=None)
def _tracked() -> frozenset[str] | None:
    """Tracked paths, or None on an archive copy (no .git): `git archive`
    exports exactly the tracked files, so existence is the test there."""
    if not (ROOT / ".git").exists():
        return None
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
    return frozenset(p for p in out.stdout.decode("utf-8").split("\0") if p)


def _is_tracked(rel: str) -> bool:
    tracked = _tracked()
    if tracked is None:
        return (ROOT / rel).is_file()
    return rel in tracked


# --------------------------------------------------------------------------
# recompute hooks (each returns the value exactly as the public text states it)
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _p04() -> dict:
    """One P04 recompute per session, fixtures only, timer stubbed (no latency
    measured). Also runs bench/baselines.py's own check() against the committed
    reports and the committed per-case file."""
    from bench import baselines as B

    saved = (B._call_timer, B._FIXTURES_ONLY)
    B._call_timer = lambda: 0.0
    B._FIXTURES_ONLY = True
    try:
        report = B.build_report()
        m = report["mcnemar_b4_vs_b5"]
        rows = B.per_case_rows()
        stale = report["gold_set"]["slice_distribution"]["stale_policy_context"]
        values = {
            "b5_accuracy": f"{m['accuracy_b5'] * 100:.1f}%",
            "b4_accuracy": f"{m['accuracy_b4'] * 100:.1f}%",
            "accuracy_diff_points": f"{m['accuracy_diff_b5_minus_b4'] * 100:.1f}",
            "mcnemar_p": f"{m['p_value_exact_binomial']:.3g}",
            "diff_ci": "[{:.1f}%, {:.1f}%]".format(*(x * 100 for x in m["diff_95ci_cluster_bootstrap"])),
            "n_discordant": str(m["n_discordant"]),
            "n_discordant_stale": str(sum(d["slice"] == "stale_policy_context" for d in m["discordant_cases"])),
            "stale_slice_block_over_n": f"{stale['gold_labels'].get('BLOCK', 0)}/{stale['n']}",
        }
        problems = B.check(report)  # mutates report's latency fields; values read above
        return {"values": values, "problems": problems, "rows": rows}
    finally:
        B._call_timer, B._FIXTURES_ONLY = saved


@functools.lru_cache(maxsize=None)
def _p08() -> dict:
    from bench import failure_injection as FI

    observed = FI.scenario_wrong_record()["observed"]
    lo, hi = observed["crossover_uncertainty"]["interval_95"]
    return {
        "crossover": f"{observed['record_error_crossover'] * 100:.1f}%",
        "crossover_ci": f"[{lo * 100:.1f}%, {hi * 100:.1f}%]",
    }


@functools.lru_cache(maxsize=None)
def _exp3() -> dict:
    """Exp 3 writes three gitignored files under bench/; point them at a temp dir."""
    from bench import seb1_exp3_cross_validation as E

    corpus, checker = sys.modules["exp3_corpus"], sys.modules["exp3_checker"]
    saved = (corpus.CASES_PATH, corpus.GROUND_TRUTH_PATH, checker.CASES_PATH, checker.PREDICTIONS_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        corpus.CASES_PATH = checker.CASES_PATH = t / "exp3_cases.jsonl"
        corpus.GROUND_TRUTH_PATH = t / "exp3_ground_truth.jsonl"
        checker.PREDICTIONS_PATH = t / "exp3_predictions.jsonl"
        try:
            r = E.run(n=200, seed=20260814)
        finally:
            corpus.CASES_PATH, corpus.GROUND_TRUTH_PATH, checker.CASES_PATH, checker.PREDICTIONS_PATH = saved
    return {"accuracy_with": f"{r['accuracy_with_attributes_check']:.2f}",
            "accuracy_without": f"{r['accuracy_without_attributes_check']:.3f}"}


def _mutation_score() -> str:
    from bench import mutation as M

    return f"{M.run_mutation_testing()['mutation_score']:.2f}"


def _negative_control() -> str:
    lines = (ROOT / "docs" / "evidence" / "negative_control.txt").read_text(encoding="utf-8").splitlines()
    runs = [line for line in lines if re.match(r"^\[\d+\] ", line)]
    proposed = [line for line in runs if re.match(r"^\[\d+\] PROPOSED\b", line)]
    return f"{len(proposed)}/{len(runs)}"


def _seed_order(order_id: str) -> dict:
    data = json.loads((ROOT / "data" / "seed" / "orders.json").read_text(encoding="utf-8"))
    return next(o for o in data["demo_orders"] if o["order_id"] == order_id)


def _demo_date() -> date:
    text = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    return date.fromisoformat(re.search(r"CP_DEMO_DATE=(\d{4}-\d{2}-\d{2})", text).group(1))


RECOMPUTE = {
    **{f"p04.{k}": (lambda k=k: _p04()["values"][k]) for k in (
        "b5_accuracy", "b4_accuracy", "accuracy_diff_points", "mcnemar_p", "diff_ci",
        "n_discordant", "n_discordant_stale", "stale_slice_block_over_n")},
    "p08.crossover": lambda: _p08()["crossover"],
    "p08.crossover_ci": lambda: _p08()["crossover_ci"],
    "exp3.accuracy_with": lambda: _exp3()["accuracy_with"],
    "exp3.accuracy_without": lambda: _exp3()["accuracy_without"],
    "mutation.score": _mutation_score,
    "negctl.proposed_over_runs": _negative_control,
    "seed.ord88461_amount": lambda: f"₹{_seed_order('ORD-88461')['amount_paise'] // 100:,}",
    "seed.ord88461_days_elapsed": lambda: str(
        (_demo_date() - date.fromisoformat(_seed_order("ORD-88461")["delivered_at"])).days),
    "manifest.servicing_window": lambda: f"{yaml.safe_load((ROOT / 'manifests' / 'servicing.yaml').read_text(encoding='utf-8'))['window_days']} days",
}

RECOMPUTED = [c for c in CLAIMS if c.get("kind") in ("fast", "slow")]


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------


def test_registry_schema():
    ids = [c.get("id") for c in CLAIMS]
    assert len(ids) == len(set(ids)), "duplicate claim ids"
    for c in CLAIMS:
        missing = [f for f in REQUIRED if f not in c]
        assert not missing, f"{c.get('id')}: missing fields {missing}"
        assert c["kind"] in KINDS, f"{c['id']}: kind {c['kind']!r}"
        assert isinstance(c["evidence"], list) and c["evidence"], f"{c['id']}: evidence must be a non-empty list"
        if c["kind"] in ("fast", "slow"):
            assert c.get("recompute") in RECOMPUTE, f"{c['id']}: unknown recompute {c.get('recompute')!r}"
        else:
            assert "recompute" not in c, f"{c['id']}: ci claims are presence-only"


@pytest.mark.parametrize("claim", CLAIMS, ids=_pid)
def test_claim_text_is_in_its_file(claim):
    path = ROOT / claim["file"]
    assert path.is_file(), f"{claim['file']} does not exist"
    assert _norm(claim["text"]) in _norm(path.read_text(encoding="utf-8")), (
        f"{claim['id']}: text not found in {claim['file']}: {claim['text']!r}")
    assert str(claim["value"]) in _norm(claim["text"]), f"{claim['id']}: value not in text"


@pytest.mark.parametrize("claim", CLAIMS, ids=_pid)
def test_claim_evidence_is_tracked(claim):
    untracked = [p for p in claim["evidence"] if not _is_tracked(p)]
    assert not untracked, f"{claim['id']}: evidence not tracked: {untracked}"


@pytest.mark.parametrize("claim", RECOMPUTED, ids=_pid)
def test_claim_value_is_recomputed(claim):
    got = RECOMPUTE[claim["recompute"]]()
    assert got == str(claim["value"]), f"{claim['id']}: recomputed {got!r}, registry says {claim['value']!r}"


def test_slow_p04_reports_and_per_case_file_match_recompute():
    """bench/baselines.py --check, in-process: the committed baselines.md,
    summary.json['p04_baselines'] and bench/results/baselines-per-case-c240d87.jsonl
    equal a fresh recompute outside the wall-clock latency fields."""
    result = _p04()
    assert result["problems"] == []
    assert len(result["rows"]) == 150
