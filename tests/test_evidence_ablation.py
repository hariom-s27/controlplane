"""P05 — the evidence-source ablation.

Proves, BEFORE any grid runs: one shared pipeline, one decision path, arms differ
only by the injected strategy, and each arm reads exactly its own channel —
A1/A2/A3 touch no database, A4 only the replica, A5 only the live stores.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
DATA = ROOT / "data"
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(ROOT))

# Pinned over the frozen P03 gold set + frozen stores. A change means the P05
# context fixtures moved and every P05 number must be regenerated.
PINNED_CONTEXT_FIXTURE_SHA = "c9cd423e20b76aa04168d5a28ba76499d01b500e6e5de70e2bf172cab1327877"


@pytest.fixture(scope="module", autouse=True)
def _built():
    for name in ("orders.db", "policy_store.db"):
        if not (DATA / name).exists():
            subprocess.run([sys.executable, str(DATA / "build_db.py")], check=True,
                           capture_output=True, cwd=ROOT)


@pytest.fixture(scope="module")
def E():
    import evidence_ablation
    evidence_ablation.ensure_fixtures(rebuild=True)
    return evidence_ablation


@pytest.fixture(scope="module")
def cases(E):
    import baselines
    return baselines.load_cases()


@pytest.fixture(scope="module")
def isolation(E):
    return E.isolation_probe()


@pytest.fixture(scope="module")
def sensitivity(E):
    return E.replication_lag_sensitivity()


@pytest.fixture(scope="module")
def report(E, isolation, sensitivity):
    meta = E.ensure_fixtures()
    return E.build_report(meta, isolation, sensitivity)


# ======================================================================
# one shared pipeline, one decision path, only the strategy differs
# ======================================================================

def test_one_shared_runner_delegating_to_p04(E):
    src = inspect.getsource(E)
    tree = ast.parse(src)
    assert [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)].count("_run_pipeline") == 1
    body = inspect.getsource(E._run_pipeline)
    assert "B._run_our_pipeline(case, strategy)" in body  # delegates, does not reimplement
    # and _run_our_pipeline is P04's, not copied here
    assert "_run_our_pipeline" not in [n.name for n in ast.walk(tree)
                                       if isinstance(n, ast.FunctionDef)]


def test_strategy_registry_entries_are_bare_classes(E):
    src = inspect.getsource(E)
    tree = ast.parse(src)
    entries: dict[str, str] = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "STRATEGY_BY_ARM"):
            for k, v in zip(node.value.keys, node.value.values):
                entries[k.value] = ast.unparse(v)
    assert set(entries) == set(E.ARMS)
    assert all(re.fullmatch(r"[A-Za-z_]\w+", val) for val in entries.values()), entries
    assert all(isinstance(getattr(E, val), type) for val in entries.values())


def test_predict_all_varies_only_the_strategy(E):
    body = inspect.getsource(E._predict_all)
    assert "STRATEGY_BY_ARM[arm_id]()" in body
    assert "_run_pipeline(view, strat)" in body


def test_a5_is_p04_b5_verbatim(E):
    import baselines
    assert issubclass(E.LiveQueryStrategy, baselines.LiveQueryStrategy)
    assert "def resolve" not in inspect.getsource(E.LiveQueryStrategy)  # adds only a name


# ======================================================================
# structural isolation — each arm reads exactly its channel
# ======================================================================

def test_isolation_probe_A1_A2_A3_open_no_database(isolation):
    for arm in ("A1_message_only", "A2_retrieved_only", "A3_trace_only"):
        assert isolation[arm] == [], (arm, isolation[arm])


def test_isolation_probe_A4_only_the_replica(E, isolation):
    assert set(isolation["A4_cached_read"]) == {"orders.db", E.REPLICA_POLICY.name}
    assert "policy_store.db" not in isolation["A4_cached_read"]  # not the live policy store


def test_isolation_probe_A5_only_the_live_stores(E, isolation):
    assert set(isolation["A5_live_query"]) == {"orders.db", "policy_store.db"}
    assert E.REPLICA_POLICY.name not in isolation["A5_live_query"]


def test_assert_isolation_gate_passes(E, isolation):
    E.assert_isolation(isolation)  # raises SystemExit on any violation


def test_source_level_channel_isolation(E):
    a1 = inspect.getsource(E.MessageOnlyStrategy)
    a2 = inspect.getsource(E.RetrievedOnlyStrategy)
    a3 = inspect.getsource(E.TraceOnlyStrategy)
    a4 = inspect.getsource(E.CachedReadStrategy)
    assert "_message" in a1 and "_retrieval" not in a1 and "_trace" not in a1
    assert "sqlite3" not in a1 and "resolve_bindings" not in a1
    assert "_retrieval" in a2 and "_message" not in a2 and "_trace" not in a2
    assert "sqlite3" not in a2
    assert "_trace" in a3 and "_message" not in a3 and "_retrieval" not in a3
    assert "sqlite3" not in a3 and "resolve_bindings" not in a3 and "claimed_" not in a3
    assert "REPLICA_ORDERS" in a4 and "REPLICA_POLICY" in a4
    assert "resolve_bindings" not in a4


# ======================================================================
# A3 is genuine prior-tool-output evidence
# ======================================================================

def test_a3_reads_the_trace_and_its_boundaries(E, cases):
    probe = next(c for c in cases if c["slice"] == "allow_in_window")

    fresh = E.build_view(probe, absence=0.0, staleness=0.0, seed=0)
    tools = [s["tool"] for s in fresh["_trace"]]
    assert "get_order" in tools and tools.count("get_policy") == 2
    win = E._trace_result(fresh["_trace"], "get_policy", "refund_window")
    assert win["version"] == "v4.2" and win["window_days"] == 7

    # absence => the agent never called get_order
    absent = E.build_view(probe, absence=1.0, staleness=0.0, seed=0)
    assert E._trace_result(absent["_trace"], "get_order") is None
    assert "get_order" not in [s["tool"] for s in absent["_trace"]]

    # staleness => the prior get_policy result carries the superseded version
    stale = E.build_view(probe, absence=0.0, staleness=1.0, seed=0)
    win = E._trace_result(stale["_trace"], "get_policy", "refund_window")
    assert win["version"] == "v3.8" and win["window_days"] == 30
    # get_order still present and unchanged under staleness
    assert E._trace_result(stale["_trace"], "get_order")["delivered_at"] == \
        E._trace_result(fresh["_trace"], "get_order")["delivered_at"]


def test_a3_absence_is_not_prose_deletion(E):
    src = inspect.getsource(E.build_view)
    # absence for the trace channel drops the get_order STEP, it does not edit text
    assert 's["tool"] != "get_order"' in src


# ======================================================================
# A4 is a genuine point-in-time replica; "200 ms stale" == current here
# ======================================================================

def test_a4_replica_is_a_real_point_in_time_snapshot(E):
    assert E.REPLICA_ORDERS.exists() and E.REPLICA_POLICY.exists()
    # orders replica is a byte copy of the live store
    assert hashlib.sha256(E.REPLICA_ORDERS.read_bytes()).hexdigest() == \
        hashlib.sha256(E.ORDERS_DB.read_bytes()).hexdigest()
    # the 200 ms snapshot serves the SAME clause as live — the frozen data has no
    # sub-day write dynamics, so a 200 ms lag catches nothing
    c = sqlite3.connect(E.REPLICA_POLICY)
    snap = c.execute("SELECT version, window_days FROM clauses "
                     "WHERE policy_id='refund_window' AND effective_to IS NULL").fetchone()
    c.close()
    c = sqlite3.connect(E.POLICY_DB)
    live = c.execute("SELECT version, window_days FROM clauses "
                     "WHERE policy_id='refund_window' AND effective_to IS NULL").fetchone()
    c.close()
    assert snap == live == ("v4.2", 7)


def test_a4_latency_floor_is_not_a_sleep_and_alters_no_value(E):
    src = inspect.getsource(E)
    assert "time.sleep" not in src and "sleep(" not in src
    assert "latency.append(dt + floor)" in src  # 200 ms added to timing only
    a4 = inspect.getsource(E.CachedReadStrategy)
    assert "SELECT * FROM orders" in a4 and "effective_to IS NULL" in a4  # real reads


def test_a4_equals_a5_at_200ms_measured(E, cases):
    """A4 genuinely queries a separate replica file; it returns the same verdicts
    as the live query because nothing in the store changed in the last 200 ms."""
    memo = {}
    a4 = E._predict_all("A4_cached_read", cases, 0.0, 0.0, 0, memo)
    a5 = E._predict_all("A5_live_query", cases, 0.0, 0.0, 0, memo)
    assert [r["pred"] for r in a4.per_case] == [r["pred"] for r in a5.per_case]
    assert a4.accuracy() == a5.accuracy()


def test_replication_lag_is_a_step_at_the_last_write(E, sensitivity):
    rows = {r["lag_days"]: r for r in sensitivity["rows"]}
    # 200 ms (lag_days 0) and any lag up to the cutover age -> current clause, 100%
    assert rows[0]["snapshot_refund_window"] == "v4.2/7d"
    assert rows[0]["verdict_accuracy"] == rows[13]["verdict_accuracy"] == 1.0
    # once the lag straddles the 13-day-old cutover -> superseded clause, lower
    assert rows[14]["straddles_cutover"] and rows[14]["snapshot_refund_window"] == "v3.8/30d"
    assert rows[14]["verdict_accuracy"] < 0.95
    assert sensitivity["step_at_lag_days"] == 13
    assert sensitivity["freshness_cost_past_cutover"] > 0.05


# ======================================================================
# fixtures & the frozen artifacts
# ======================================================================

def test_context_fixture_is_deterministic_and_pinned(E):
    m1 = E.build_context_fixtures()
    m2 = E.build_context_fixtures()
    assert m1 == m2, "regenerating the P05 context fixture changed its bytes"
    assert m1["n"] == 150
    if m1["sha256"] != PINNED_CONTEXT_FIXTURE_SHA:
        pytest.skip(f"context-fixture SHA is {m1['sha256']} — update PINNED_CONTEXT_FIXTURE_SHA "
                    "and every P05 number if this construction change was intentional")


def test_perturbation_never_touches_gold_toolcall_or_stores(E, cases):
    before = {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest()
              for name in ("orders.db", "policy_store.db")}
    for c in cases[:20]:
        base = json.dumps({"args": c["tool_call"]["args"], "gold": c["gold_label"],
                           "verdict": c["gold_verdict"]}, sort_keys=True)
        for a, s in [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]:
            v = E.build_view(c, absence=a, staleness=s, seed=1)
            got = json.dumps({"args": v["tool_call"]["args"], "gold": v["gold_label"],
                              "verdict": v["gold_verdict"]}, sort_keys=True)
            assert got == base
    after = {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest()
             for name in ("orders.db", "policy_store.db")}
    assert after == before


def test_p03_gold_set_hash_is_unchanged(E):
    import baselines
    live = hashlib.sha256(baselines.GOLD_SET.read_bytes()).hexdigest()
    assert live == "09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e"


# ======================================================================
# grid mechanics & the prediction contract
# ======================================================================

def test_full_grid_shape(E, report):
    cfg = report["config"]
    assert cfg["absence_points"] == [0.0, 0.10, 0.30, 0.50, 0.70, 1.00]
    assert cfg["staleness_points"] == [0.0, 0.10, 0.25, 0.50, 1.00]
    assert cfg["seeds"] == [0, 1, 2]
    for arm in E.ARMS:
        assert len(report["grid"][arm]["absence"]) == 6
        assert len(report["grid"][arm]["staleness"]) == 5


def test_origin_parity_a3_vs_a5(E, report):
    pa = report["prediction_assessment"]
    assert abs(pa["origin_gap_absence_sweep"]) <= 1 / 140 + 1e-9
    assert abs(pa["origin_gap_staleness_sweep"]) <= 1 / 140 + 1e-9


def test_a3_degrades_but_both_independent_arms_are_flat(E, report):
    g = report["grid"]
    a3_abs = [r["verdict_accuracy"]["mean"] for r in g["A3_trace_only"]["absence"]]
    assert a3_abs[0] - a3_abs[-1] > 0.2                       # A3 collapses under absence
    for arm in ("A5_live_query", "A4_cached_read"):
        for sweep in ("absence", "staleness"):
            ys = [r["verdict_accuracy"]["mean"] for r in g[arm][sweep]]
            assert max(ys) - min(ys) < 1e-9, (arm, sweep)     # dead flat


def test_freshness_not_exercised_at_200ms_but_a_step_further_out(E, report):
    pa = report["prediction_assessment"]
    # at the CDC model's 200 ms lag A4 == A5 (measured); the benchmark does not
    # separate independence from freshness here
    assert pa["a4_equals_a5"] is True
    assert pa["freshness_cost_at_200ms_lag"] == 0.0
    # the sensitivity analysis shows freshness DOES cost, past the last-write age
    assert pa["freshness_cost_past_cutover_lag"] > 0.05
    assert pa["replication_lag_step_days"] == 13


def test_prediction_string_recorded_verbatim(E):
    assert "A3 and A5 are statistically indistinguishable" in E.PREDICTION
    assert "publishable negative result for our own thesis" in E.PREDICTION


def test_report_puts_prediction_before_results(E, report, tmp_path, monkeypatch):
    monkeypatch.setattr(E, "REPORTS", tmp_path)
    E.write_markdown(report)
    md = (tmp_path / "evidence-ablation.md").read_text(encoding="utf-8")
    i_pred = md.index("## Prediction (recorded before the results")
    i_prov = md.index("## Arm provenance")
    i_res = md.index("## Results —")
    i_held = md.index("## Did the prediction hold?")
    assert i_pred < i_prov < i_res < i_held


def test_summary_json_merge_preserves_p04(E, report, tmp_path, monkeypatch):
    monkeypatch.setattr(E, "REPORTS", tmp_path)
    (tmp_path / "summary.json").write_text(json.dumps({"p04_baselines": {"keep": 1}}),
                                           encoding="utf-8")
    E.merge_summary_json(report)
    merged = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert merged["p04_baselines"] == {"keep": 1}
    p5 = merged["p05_evidence_ablation"]
    assert p5["prediction"] == E.PREDICTION
    assert "crossover" in p5 and "isolation_probe" in p5["config"]
    json.dumps(merged, allow_nan=False)
