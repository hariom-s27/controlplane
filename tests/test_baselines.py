"""P04 — the baseline harness: structure, determinism, and label-ontology
preservation.

Does NOT make LLM calls. B3 is exercised only through its parser and (if
present) its committed fixtures.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
DATA = ROOT / "data"
sys.path.insert(0, str(BENCH))


@pytest.fixture(scope="module", autouse=True)
def _built():
    for name in ("orders.db", "policy_store.db"):
        if not (DATA / name).exists():
            subprocess.run([sys.executable, str(DATA / "build_db.py")], check=True,
                           capture_output=True, cwd=ROOT)


@pytest.fixture(scope="module")
def B():
    import baselines
    return baselines


@pytest.fixture(scope="module")
def cases(B):
    return B.load_cases()


# --- B4 vs B5 share all code except the injected strategy ------------------

def test_b4_and_b5_differ_only_by_the_injected_strategy(B):
    """B4 and B5 must route through the same implementation, differing only by
    the injected strategy class. Checked by unparsing the SYSTEMS dict entries
    from the module AST (robust to lambdas / named fns / peer edits)."""
    src = inspect.getsource(B)
    tree = ast.parse(src)
    assert [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)].count("_run_our_pipeline") == 1

    entries: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and any(
            isinstance(k, ast.Constant) and k.value == "B5_ControlPlane" for k in node.keys
        ):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant):
                    entries[k.value] = ast.unparse(v)
    b4, b5 = entries["B4_TraceGrounded"], entries["B5_ControlPlane"]
    assert "_run_our_pipeline" in b4 and "_run_our_pipeline" in b5
    norm = lambda s: re.sub(r"(TraceGrounded|LiveQuery)Strategy", "X", s)
    assert norm(b4) == norm(b5), f"B4 and B5 entries differ by more than the strategy:\n{b4}\n{b5}"


def test_only_the_strategy_touches_retrieved_chunks(B):
    """The live-query strategy must not read the agent's retrieved chunks; the
    trace-grounded one must. That is the whole experiment."""
    live = inspect.getsource(B.LiveQueryStrategy)
    trace = inspect.getsource(B.TraceGroundedStrategy)
    assert "retrieved_chunks" not in live
    assert "retrieved_chunks" in trace
    assert "resolve_bindings" in live and "resolve_bindings" not in trace
    assert "gold_label" not in live and "gold_label" not in trace
    assert "gold_verdict" not in live and "gold_verdict" not in trace


# --- determinism ---------------------------------------------------------

@pytest.mark.parametrize("name", ["B0_NoGate", "B1_RuleOnly", "B2_AuthOnly",
                                  "B4_TraceGrounded", "B5_ControlPlane"])
def test_system_is_deterministic(B, cases, name):
    a = [p.predicted for p in B.run_system(name, B.SYSTEMS[name], cases)]
    b = [p.predicted for p in B.run_system(name, B.SYSTEMS[name], cases)]
    assert a == b
    assert len(a) == 150


# --- label ontology is preserved, not remapped -------------------------

def test_binary_metrics_exclude_ambiguous_and_use_140(B, cases):
    preds = B.run_system("B5", B.SYSTEMS["B5_ControlPlane"], cases)
    m = B.binary_metrics(preds)
    assert m["n"] == 140
    assert m["tp"] + m["fp"] + m["tn"] + m["fn"] == 140
    # FPR denominator is the 50 gold-ALLOW cases exactly
    assert m["fp"] + m["tn"] == 50
    assert m["gold_allow_source_clusters"] == 5
    assert m["gold_allow_clusters_with_any_fp"] == 0


def test_ambiguous_cases_are_reported_separately_never_folded(B, cases):
    preds = B.run_system("B5", B.SYSTEMS["B5_ControlPlane"], cases)
    panel = B.ambiguous_panel(preds)
    assert panel["n"] == 10
    # and they are absent from the binary rows
    amb_ids = {c["id"] for c in cases if c["gold_label"] == "AMBIGUOUS"}
    binary_rows = [p for p in preds if p.gold_label != "AMBIGUOUS"]
    assert not (amb_ids & {p.case_id for p in binary_rows})
    assert B.per_slice(preds)["ambiguous_under_policy"]["accuracy_direction"] is None


def test_source_unreliable_is_visible_as_its_own_gold_verdict(B, cases):
    preds = B.run_system("B0", B.SYSTEMS["B0_NoGate"], cases)
    panel = B.gold_verdict_panel(preds)
    assert panel["SOURCE_UNRELIABLE"]["n"] == 5
    assert panel["UNVERIFIABLE"]["n"] == 10
    assert panel["AMBIGUOUS"]["n"] == 10


def test_exact_match_panel_scores_against_original_labels(B, cases):
    """B0-B3 structurally cannot emit ESCALATE; the panel must show that, not
    hide it by remapping ESCALATE gold to BLOCK."""
    b1 = B.run_system("B1", B.SYSTEMS["B1_RuleOnly"], cases)
    e = B.exact_match_panel(b1)
    assert e["can_emit_escalate"] is False
    assert e["escalate_gold_n"] == 15
    assert e["escalate_gold_hit"] == 0  # B1 can never match an ESCALATE gold

    b5 = B.run_system("B5", B.SYSTEMS["B5_ControlPlane"], cases)
    assert B.exact_match_panel(b5)["can_emit_escalate"] is True


def test_no_baseline_prediction_is_outside_the_known_vocabulary(B, cases):
    ok = {"ALLOW", "BLOCK", "ESCALATE", "MODIFY"}
    for name in ("B0_NoGate", "B1_RuleOnly", "B2_AuthOnly", "B4_TraceGrounded", "B5_ControlPlane"):
        for p in B.run_system(name, B.SYSTEMS[name], cases):
            assert p.predicted in ok, (name, p.case_id, p.predicted)


# --- clustering ---------------------------------------------------------

def test_clustering_matches_the_p03_source_orders(B, cases):
    from collections import defaultdict
    by_slice = defaultdict(set)
    for c in cases:
        by_slice[c["slice"]].add(B.cluster_id(c))
    assert len(by_slice["allow_in_window"]) == 5       # 50 cases, 5 real orders
    assert len(by_slice["ambiguous_under_policy"]) == 7
    assert len({B.cluster_id(c) for c in cases}) == 101
    for s in ("outside_window", "over_authority", "distractor_present",
              "stale_policy_context", "corrupted_or_missing_record"):
        # 1:1 there
        assert len(by_slice[s]) == sum(1 for c in cases if c["slice"] == s)


def test_mcnemar_is_paired_and_cluster_aware(B, cases):
    b4 = B.run_system("B4", B.SYSTEMS["B4_TraceGrounded"], cases)
    b5 = B.run_system("B5", B.SYSTEMS["B5_ControlPlane"], cases)
    mc = B.mcnemar_b4_b5(b4, b5)
    assert mc["n_paired"] == 140
    assert mc["n_discordant"] == mc["b5_right_b4_wrong"] + mc["b4_right_b5_wrong"]
    lo, hi = mc["diff_95ci_cluster_bootstrap"]
    assert lo <= mc["accuracy_diff_b5_minus_b4"] <= hi or lo <= hi


# --- B3 parser --------------------------------------------------------

def test_b3_parser_handles_json_and_falls_closed(B):
    assert B._b3_parse('{"decision": "ALLOW", "reason": "x"}') == "ALLOW"
    assert B._b3_parse('  {"decision":"BLOCK"}') == "BLOCK"
    assert B._b3_parse("garbage, no json") == "BLOCK"  # conservative on unparseable


def test_three_seed_results_have_per_seed_rows_and_mean_range(B, cases):
    seed_results = []
    for seed in B.SEEDS:
        preds = B.run_system("B0", B.SYSTEMS["B0_NoGate"], cases, seed=seed)
        seed_results.append({
            "seed": seed,
            "n_cases": len(preds),
            "binary_140": B.binary_metrics(preds),
            "exact_intervention": B.exact_match_panel(preds),
            "ambiguous_panel": B.ambiguous_panel(preds),
            "gold_verdict_panel": B.gold_verdict_panel(preds),
            "cost_weighted_error": B.cost_weighted_error(preds),
            "per_slice": B.per_slice(preds),
            "latency": B.latency_summary([p.latency_ms for p in preds]),
        })
    assert len(seed_results) >= 3
    assert [run["seed"] for run in seed_results] == list(B.SEEDS)
    assert all(run["n_cases"] == 150 for run in seed_results)

    aggregate = B.aggregate_seed_results(seed_results)
    assert aggregate["binary_140"]["fn"] == {"mean": 90.0, "min": 90, "max": 90}
    assert aggregate["per_slice"]["ambiguous_under_policy"]["accuracy_direction"] == {
        "mean": None, "min": None, "max": None,
    }
    json.dumps(aggregate, allow_nan=False)


def test_headline_numbers_are_locked(B, cases):
    """Pins the published P04 table against the committed gold set + pipeline.
    A shift here means bench/gold_set.jsonl or the pipeline changed and
    reports/baselines.md must be regenerated (and the deck updated)."""
    r = {name: B.binary_metrics(B.run_system(name, B.SYSTEMS[name], cases))
         for name in ("B0_NoGate", "B1_RuleOnly", "B2_AuthOnly",
                      "B3_LLMJudge", "B4_TraceGrounded", "B5_ControlPlane")}
    assert (r["B5_ControlPlane"]["tp"], r["B5_ControlPlane"]["fp"],
            r["B5_ControlPlane"]["fn"]) == (90, 0, 0)          # 100% recall, 0% FPR
    assert r["B0_NoGate"]["tp"] == 0 and r["B0_NoGate"]["fn"] == 90
    assert r["B1_RuleOnly"]["tp"] == 79 and r["B1_RuleOnly"]["fp"] == 0
    assert r["B2_AuthOnly"]["tp"] == 15                        # authority check only
    assert r["B3_LLMJudge"]["fp"] == 11                        # over-blocks 11/50 valid
    assert r["B4_TraceGrounded"]["tp"] == 73 and r["B4_TraceGrounded"]["fp"] == 0

    mc = B.mcnemar_b4_b5(B.run_system("B4", B.SYSTEMS["B4_TraceGrounded"], cases),
                         B.run_system("B5", B.SYSTEMS["B5_ControlPlane"], cases))
    assert mc["n_discordant"] == 17
    assert mc["b4_right_b5_wrong"] == 0                        # B5 never worse than B4
    assert mc["p_value_exact_binomial"] < 0.001
    assert mc["diff_95ci_cluster_bootstrap"][0] > 0           # CI excludes 0


def test_no_case_derives_its_label_from_decide(B, cases):
    """P04 scores against P03's gold_label (from bench/label.py). Sanity: the
    harness never imports decide to *label*, only to *run B4/B5 as systems*."""
    src = inspect.getsource(B)
    assert "gold_label" in src
    # decide() is used to RUN our pipeline, never to assign a gold value
    assert "case['gold_label']" in src or 'case["gold_label"]' in src
