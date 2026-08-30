"""P09 regression tests for the latency profile.

Fast by construction: the >=1,000-call measurement lives in bench/latency.py and
is not run here. These tests prove the instrumentation, the harness contract,
and that adding timing changed no decision semantics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import controlplane.ground as ground_module
import controlplane.intercept as intercept
import controlplane.receipt as receipt_module
import controlplane.telemetry as telemetry_module
from bench import baselines as B
from bench import latency as P09

ROOT = Path(__file__).resolve().parent.parent
IN_PIPELINE_STAGES = ("extract", "classify", "resolve", "predicate", "ground", "decide", "receipt")


@pytest.fixture
def gated_call(tmp_path, monkeypatch):
    """One real _run_gate() over a gold case, grounding on with a fake HHEM so
    the 'ground' stage is exercised without loading a 0.1B-param model."""
    trail = tmp_path / "decisions.jsonl"
    monkeypatch.setenv("CP_RECEIPT_SECRET", "p09-test-secret")
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    monkeypatch.setenv("CP_DEMO_DATE", "2026-08-14")
    monkeypatch.setenv("CP_GROUNDING", "on")
    monkeypatch.setattr(receipt_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(telemetry_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(ground_module, "score", lambda **_k: 0.87)

    case = B.load_cases()[0]
    action = B.action_from_case(case)
    monkeypatch.setattr(intercept, "extract_action", lambda **_k: action)

    def _run():
        return intercept._run_gate(
            case["tool_call"]["name"],
            dict(case["tool_call"]["args"]),
            B.session_from_case(case),
            case.get("justification") or "",
            list(case.get("retrieved_chunks", [])),
        )

    return _run


# --- 1 / 2 / 4 : every required stage is instrumented ----------------------


def test_all_seven_stages_and_end_to_end_are_instrumented(gated_call):
    _decision, timing, _receipt = gated_call()
    for stage in IN_PIPELINE_STAGES:
        assert stage in timing, f"stage {stage!r} missing from timing dict"
    assert "end_to_end" in timing


# --- 3 : timing values are numeric / non-negative / present ---------------


def test_timing_values_are_numeric_non_negative_and_not_missing(gated_call):
    _d, timing, _r = gated_call()
    for key in (*IN_PIPELINE_STAGES, "end_to_end"):
        v = timing[key]
        assert isinstance(v, (int, float)) and not isinstance(v, bool)
        assert v >= 0.0
        assert v == v  # not NaN


def test_end_to_end_is_at_least_the_sum_of_stages(gated_call):
    _d, timing, _r = gated_call()
    staged = sum(timing[s] for s in IN_PIPELINE_STAGES)
    # end_to_end additionally covers un-instrumented between-stage work
    assert timing["end_to_end"] + 0.5 >= staged


# --- 5 : grounding model loaded once, not once per call ------------------


def test_grounding_model_is_loaded_once_not_per_call(monkeypatch):
    loads: list[int] = []

    class _FakeHHEM:
        def predict(self, pairs):
            return [0.5] * len(pairs)

    class _Loader:
        @staticmethod
        def from_pretrained(*_a, **_k):
            loads.append(1)
            return _FakeHHEM()

    import transformers

    monkeypatch.setattr(transformers, "AutoModelForSequenceClassification", _Loader)
    monkeypatch.setattr(ground_module, "_model", None)

    ground_module.preload()
    for _ in range(6):
        ground_module.score("premise text", "hypothesis text")

    assert loads == [1], "HHEM was loaded more than once"
    assert ground_module.is_loaded()


def test_ground_module_exposes_a_single_preload_entrypoint():
    assert hasattr(ground_module, "preload") and callable(ground_module.preload)
    assert hasattr(ground_module, "is_loaded")
    src = (ROOT / "controlplane" / "ground.py").read_text(encoding="utf-8")
    assert "_load_lock" in src, "the one-time load must be guarded for the 10-worker pool"


# --- 6 : configurations are kept separate ------------------------------


def test_four_configurations_are_distinct_and_never_averaged():
    names = [c["name"] for c in P09.CONFIGS]
    keys = [(c["c3"], c["concurrency"]) for c in P09.CONFIGS]
    assert len(P09.CONFIGS) == 4
    assert sorted(keys) == [("off", 1), ("off", 10), ("on", 1), ("on", 10)]
    assert len(set(names)) == 4
    # the aggregator emits one distribution per config, not a pooled one
    report = _synthetic_report()
    entry = P09._summary_entry(report)
    assert len(entry["configurations"]) == 4
    assert {c["config"] for c in entry["configurations"]} == set(names)


# --- 7 : concurrency=10 actually executes concurrently -----------------


@pytest.mark.parametrize("cfg_name,expect_min", [("C1_hhem_off_seq", 1), ("C3_hhem_off_par", 2)])
def test_concurrency_is_real(cfg_name, expect_min):
    cfg = next(c for c in P09.CONFIGS if c["name"] == cfg_name)
    cases = B.load_cases()
    result = P09.run_config(
        cfg, cases, n_calls=30, warmup=0, cold_start_ms={"value": None, "config": None}
    )
    if cfg["concurrency"] == 1:
        assert result["observed_max_concurrency"] == 1
    else:
        assert result["observed_max_concurrency"] >= expect_min
    assert result["all_signatures_valid"]
    assert result["receipt_lines_all_parse"]
    assert result["n"] == 30


# --- 8 : all required percentile fields exist -------------------------


def test_percentile_fields_present_for_every_stage_and_end_to_end():
    entry = P09._summary_entry(_synthetic_report())
    for cfg in entry["configurations"]:
        for stage in IN_PIPELINE_STAGES:
            s = cfg["stages"][stage]
            assert {"p50", "p95", "p99", "max", "n"} <= set(s)
        e = cfg["end_to_end"]
        assert {"p50", "p95", "p99", "max", "n"} <= set(e)


def test_pctiles_helper_reports_p50_p95_p99_max():
    out = P09._pctiles([float(i) for i in range(1, 101)])
    assert out["p50"] == 50 and out["p95"] == 95 and out["p99"] == 99 and out["max"] == 100
    assert P09._pctiles([])["p50"] is None


# --- 9 : summary.json preserves prior P04 / P05 / P08 sections --------


def test_merge_preserves_frozen_summary_sections(tmp_path, monkeypatch):
    live = json.loads((ROOT / "reports" / "summary.json").read_text(encoding="utf-8"))
    before = {k: json.dumps(live[k], sort_keys=True) for k in
              ("p04_baselines", "p05_evidence_ablation", "p08_robustness") if k in live}
    assert before, "expected P04/P05/P08 sections to exist before P09"

    staging = tmp_path / "reports"
    staging.mkdir()
    (staging / "summary.json").write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(P09, "REPORTS", staging)

    P09.merge_summary_json(_synthetic_report())  # its own guard also raises on drift

    after_doc = json.loads((staging / "summary.json").read_text(encoding="utf-8"))
    assert "p09_latency" in after_doc
    for k, raw in before.items():
        assert json.dumps(after_doc[k], sort_keys=True) == raw, f"{k} changed"


# --- 10 : the old "75% in 1-20 ms" claim is absent as a current fact --


def test_old_latency_claim_is_not_a_current_factual_claim():
    label_words = ("retired", "historical", "design target", "unmeasured", "interim",
                   "superseded", "prior claim", "not a measurement", "modelled")
    pattern = re.compile(r"75\s*%[^\n]{0,60}1\s*[-–]\s*20\s*ms|1\s*[-–]\s*20\s*ms[^\n]{0,60}75\s*%",
                         re.IGNORECASE)
    roots = [ROOT / "README.md", ROOT / "docs", ROOT / "reports"]
    files: list[Path] = []
    for r in roots:
        files += [r] if r.is_file() else list(r.rglob("*.md"))
    offenders = []
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines()):
            if pattern.search(line):
                window = " ".join(
                    f.read_text(encoding="utf-8").splitlines()[max(0, i - 1): i + 2]
                ).lower()
                if not any(w in window for w in label_words):
                    offenders.append(f"{f.relative_to(ROOT)}:{i+1}: {line.strip()}")
    assert not offenders, "unlabelled '75% in 1-20 ms' claim still present:\n" + "\n".join(offenders)


# --- 11 : cold-start and steady-state are distinct -------------------


def test_cold_start_and_steady_state_are_reported_separately():
    report = _synthetic_report()
    entry = P09._summary_entry(report)
    assert "cold_start_ms" in entry
    assert "steady_state_definition" in entry
    assert report["cold_start"]["ms"] != report["steady_state"]  # different shapes entirely
    assert "load" in report["cold_start"]["definition"].lower()
    assert "preload" in report["steady_state"]["definition"].lower() or \
           "warm" in report["steady_state"]["definition"].lower()
    # cold start must not appear inside any per-config percentile table
    for cfg in entry["configurations"]:
        assert "cold_start" not in cfg["stages"]
        assert "cold_start_ms" not in cfg["end_to_end"]


# --- 12 : no timing code changed decision semantics ----------------


def test_with_totals_returns_a_fresh_dict_and_does_not_mutate_input():
    base = {"extract": 0.1, "classify": 0.2, "resolve": 1.0, "predicate": 1.0, "decide": 0.1}
    snapshot = dict(base)
    out = intercept._with_totals(base, 0.0, 0.0)
    assert base == snapshot, "_with_totals mutated its input (would corrupt the signed receipt)"
    assert out is not base
    assert set(out) == set(base) | {"receipt", "end_to_end"}


def test_timing_leaves_the_signed_receipt_consistent_and_verdict_unchanged(gated_call):
    decision, _timing, receipt = gated_call()
    assert receipt_module.verify(receipt) is True
    # the persisted receipt carries only the in-pipeline stages, never the
    # after-the-fact totals (which are not covered by its HMAC)
    assert "end_to_end" not in receipt["latency_ms"]
    assert "receipt" not in receipt["latency_ms"]
    assert decision.verdict.value and decision.intervention.value


def test_run_gate_still_returns_a_three_tuple(gated_call):
    out = gated_call()
    assert isinstance(out, tuple) and len(out) == 3
    decision, timing, receipt = out
    assert hasattr(decision, "verdict")
    assert isinstance(timing, dict) and isinstance(receipt, dict)


# --- helpers -------------------------------------------------------


def _synthetic_pctiles(base: float) -> dict:
    return {"n": 1050, "p50": base, "p95": base * 1.4, "p99": base * 1.8,
            "max": base * 2.2, "mean": base * 1.1}


def _synthetic_config(name: str, c3: str, concurrency: int) -> dict:
    return {
        "config": name, "c3": c3, "concurrency": concurrency, "n": 1050,
        "warmup_discarded": 50,
        "stages": {s: _synthetic_pctiles(0.5 + i) for i, s in enumerate(IN_PIPELINE_STAGES)},
        "end_to_end": _synthetic_pctiles(7.0),
        "observed_max_concurrency": concurrency,
        "wall_clock_s": 10.0, "throughput_calls_per_s": 105.0,
        "grounded_calls": 1050 if c3 == "on" else 0,
        "all_signatures_valid": True, "receipt_persisted_lines": 1100,
        "receipt_lines_all_parse": True,
        "intervention_distribution": {"ALLOW": 350, "BLOCK": 560, "ESCALATE": 140},
    }


def _synthetic_report() -> dict:
    return {
        "task": "P09_LATENCY_PROFILE",
        "measurement_setup": {
            "unit": "one intercept._run_gate() call",
            "workload": "P03 gold_set.jsonl", "gold_set_sha256": "deadbeef",
            "n_calls_per_config": 1050, "warmup_discarded_per_config": 50,
            "warmup_policy": "fixed leading calls discarded, identical per config",
            "extraction": "stubbed", "clock": "frozen CP_DEMO_DATE=2026-08-14", "seed": 20260814,
            "timing_method": "perf_counter", "percentile_method": "nearest-rank",
            "concurrency_mechanism": "ThreadPoolExecutor", "grounding_model": ground_module.MODEL_NAME,
            "grounding_load": "preload once", "runtime": {"python": "3.14", "torch": "x", "platform": "win32"},
        },
        "cold_start": {"ms": 6421.7, "measured_on_config": "C2_hhem_on_seq",
                       "definition": "wall time of the one-time HHEM model load",
                       "applies_to": "C2, C4"},
        "steady_state": {"definition": "the n timed calls after warm-up and after preload()"},
        "configurations": [
            _synthetic_config("C1_hhem_off_seq", "off", 1),
            _synthetic_config("C2_hhem_on_seq", "on", 1),
            _synthetic_config("C3_hhem_off_par", "off", 10),
            _synthetic_config("C4_hhem_on_par", "on", 10),
        ],
        "aegis_comparison": "AEGIS 8.3 ms median",
        "oap_comparison": "OAP 53 ms median",
        "frozen_input_integrity": {"unchanged": True, "before": {}, "after": {},
                                   "summary_subtrees_before": {}, "summary_subtrees_after": {}},
        "reproduction_command": "python bench/latency.py --write",
    }
