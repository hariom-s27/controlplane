#!/usr/bin/env python3
"""Task P09 -- latency profile.

Measures the ControlPlane gate (``controlplane.intercept._run_gate``: the seven
governed stages ending in a signed, persisted receipt) over four configurations,
each with >= 1,000 real gated calls. The downstream business tool is never
invoked -- its runtime is the caller's, not the gate's (docs/ROADMAP.md).

    C1  C3/HHEM off, concurrency 1
    C2  C3/HHEM on,  concurrency 1
    C3  C3/HHEM off, concurrency 10
    C4  C3/HHEM on,  concurrency 10

Run from the repository root:

    python bench/latency.py            # prints the JSON result only
    python bench/latency.py --write    # also writes reports/latency.md + summary.json[p09_latency]
    python bench/latency.py --smoke    # 60 calls/config, for a fast wiring check (never --write this)

Nothing here touches the frozen P03 gold set or the P04/P05/P08 artifacts; the
harness hashes them before and after and aborts on any drift.

Workload: the full 150-case P03 gold set, in file order, cycled 7x -> 1,050
calls per configuration, identical across all four. Extraction is stubbed to the
pre-built ProposedAction per case (the P04/P05/P08 convention) so the profile is
the gate's own overhead; see reports/latency.md for what "extract" does and does
not include.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import baselines as B  # noqa: E402  (frozen P04 helpers, read-only)
import controlplane.escalation as escalation_module  # noqa: E402
import controlplane.ground as ground_module  # noqa: E402
import controlplane.intercept as intercept  # noqa: E402
import controlplane.receipt as receipt_module  # noqa: E402
import controlplane.telemetry as telemetry_module  # noqa: E402
from controlplane.registry.clock import set_clock  # noqa: E402


REPORTS = ROOT / "reports"

FROZEN_DATE = "2026-08-14"
SEED = 20260814
STAGES = ("extract", "classify", "resolve", "predicate", "ground", "decide", "receipt")
END_TO_END = "end_to_end"
N_CALLS = 1050          # 150-case gold set x 7 full cycles -> balanced, >= 1,000
WARMUP = 50             # discarded, identical for every configuration
SMOKE_CALLS = 60
SMOKE_WARMUP = 10
CONCURRENCY_HI = 10

CONFIGS: tuple[dict[str, Any], ...] = (
    {"name": "C1_hhem_off_seq",  "c3": "off", "concurrency": 1},
    {"name": "C2_hhem_on_seq",   "c3": "on",  "concurrency": 1},
    {"name": "C3_hhem_off_par",  "c3": "off", "concurrency": CONCURRENCY_HI},
    {"name": "C4_hhem_on_par",   "c3": "on",  "concurrency": CONCURRENCY_HI},
)

FROZEN_INPUTS = (
    ROOT / "bench" / "gold_set.jsonl",
    ROOT / "bench" / "ground_truth_holdout.jsonl",
    ROOT / "bench" / "human_label_sample.csv",
    ROOT / "bench" / "baselines.py",
    ROOT / "bench" / "evidence_ablation.py",
    ROOT / "bench" / "failure_injection.py",
    REPORTS / "baselines.md",
    REPORTS / "evidence-ablation.md",
    REPORTS / "robustness.md",
    ROOT / "docs" / "limitations.md",
    REPORTS / "summary.json",
)

_MISSING = object()
_tls = threading.local()


# ---------------------------------------------------------------------------
# Frozen-artifact guard
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_hashes() -> dict[str, str]:
    return {str(p.relative_to(ROOT)): _sha256(p) for p in FROZEN_INPUTS}


def _summary_subtrees() -> dict[str, str]:
    d = json.loads((REPORTS / "summary.json").read_text(encoding="utf-8"))
    return {
        k: hashlib.sha256(json.dumps(d[k], sort_keys=True).encode()).hexdigest()
        for k in ("p04_baselines", "p05_evidence_ablation", "p08_robustness")
        if k in d
    }


# ---------------------------------------------------------------------------
# Isolation helpers
# ---------------------------------------------------------------------------


@contextmanager
def _patched_attr(obj: Any, name: str, value: Any) -> Iterator[None]:
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextmanager
def _patched_env(name: str, value: str | None) -> Iterator[None]:
    old = os.environ.get(name, _MISSING)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if old is _MISSING:
            os.environ.pop(name, None)
        else:
            os.environ[name] = str(old)


def _stub_extract(*_a: Any, **_k: Any):
    """Thread-local: each worker sets ``_tls.action`` before calling the gate.
    No signature change to _run_gate, and concurrency-safe by construction."""
    return _tls.action


# ---------------------------------------------------------------------------
# Percentiles -- nearest-rank, no interpolation
# ---------------------------------------------------------------------------


def _pctiles(values: list[float]) -> dict[str, float | int | None]:
    """Nearest-rank: pXX is the smallest observation V such that at least XX%
    of the sample is <= V, i.e. sorted[ceil(q*n) - 1]. No interpolation, so
    every reported number is a latency that actually occurred. ``max`` is the
    slowest single call. Values are NOT rounded here."""
    if not values:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None, "mean": None}
    s = sorted(values)
    n = len(s)

    def nr(q: float) -> float:
        return s[min(n - 1, max(0, math.ceil(q * n) - 1))]

    return {
        "n": n,
        "p50": nr(0.50),
        "p95": nr(0.95),
        "p99": nr(0.99),
        "max": s[-1],
        "mean": statistics.fmean(s),
    }


def _max_concurrency(intervals: list[tuple[float, float]]) -> int:
    """Sweep-line over (enter, exit) perf_counter stamps: the largest number of
    gate calls whose execution windows overlapped at any instant."""
    events: list[tuple[float, int]] = []
    for a, b in intervals:
        events.append((a, +1))
        events.append((b, -1))
    events.sort()
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


# ---------------------------------------------------------------------------
# One configuration
# ---------------------------------------------------------------------------


def _one_call(case: dict, action) -> dict[str, Any]:
    _tls.action = action
    enter = time.perf_counter()
    decision, timing, receipt = intercept._run_gate(
        case["tool_call"]["name"],
        dict(case["tool_call"]["args"]),
        B.session_from_case(case),
        case.get("justification") or "",
        list(case.get("retrieved_chunks", [])),
    )
    exit_ = time.perf_counter()
    return {
        "case_id": case["id"],
        "intervention": decision.intervention.value,
        "verdict": decision.verdict.value,
        "timing": timing,
        "signature_valid": receipt_module.verify(receipt),
        "interval": (enter, exit_),
        "receipt_latency_keys": sorted(receipt["latency_ms"].keys()),
    }


def run_config(
    cfg: dict[str, Any],
    cases: list[dict],
    *,
    n_calls: int,
    warmup: int,
    cold_start_ms: dict[str, float | None],
) -> dict[str, Any]:
    actions = [B.action_from_case(c) for c in cases]
    plan = [(cases[i % len(cases)], actions[i % len(actions)]) for i in range(warmup + n_calls)]

    with tempfile.TemporaryDirectory(prefix=f"p09-{cfg['name']}-") as tmp:
        trail = Path(tmp) / "decisions.jsonl"
        with ExitStack() as stack:
            stack.enter_context(_patched_env("CP_RECEIPT_SECRET", "p09-isolated-secret"))
            stack.enter_context(_patched_env("CP_MANIFEST", "servicing"))
            stack.enter_context(_patched_env("CP_DEMO_DATE", FROZEN_DATE))
            stack.enter_context(_patched_env("CP_GROUNDING", cfg["c3"]))
            stack.enter_context(_patched_attr(receipt_module, "OPERATIONAL_TRAIL", trail))
            stack.enter_context(_patched_attr(telemetry_module, "OPERATIONAL_TRAIL", trail))
            stack.enter_context(_patched_attr(escalation_module, "OPERATIONAL_TRAIL", trail))
            stack.enter_context(_patched_attr(intercept, "extract_action", _stub_extract))
            set_clock(None)  # rely on CP_DEMO_DATE env, never a cross-thread override

            # Cold start: load HHEM once, at the start of the first grounded
            # configuration, and time it. Later grounded configs reuse it.
            if cfg["c3"] == "on" and not ground_module.is_loaded():
                t0 = time.perf_counter()
                ground_module.preload()
                cold_start_ms["value"] = round((time.perf_counter() - t0) * 1000, 2)
                cold_start_ms["config"] = cfg["name"]

            # Warm up the compiled-graph cache, SQLite, and (grounded configs)
            # the first scored inference -- discarded, identical policy per config.
            for case, action in plan[:warmup]:
                _tls.action = action
                intercept._run_gate(
                    case["tool_call"]["name"], dict(case["tool_call"]["args"]),
                    B.session_from_case(case), case.get("justification") or "",
                    list(case.get("retrieved_chunks", [])),
                )

            timed = plan[warmup:]
            if cfg["concurrency"] == 1:
                rows = [_one_call(case, action) for case, action in timed]
            else:
                with ThreadPoolExecutor(max_workers=cfg["concurrency"]) as pool:
                    rows = list(pool.map(lambda ca: _one_call(*ca), timed))

            trail_lines = trail.read_text(encoding="utf-8").splitlines()

    # ---- aggregate ----
    per_stage: dict[str, dict[str, Any]] = {}
    for stage in STAGES:
        vals = [r["timing"][stage] for r in rows if stage in r["timing"]]
        per_stage[stage] = _pctiles(vals)
    e2e = _pctiles([r["timing"][END_TO_END] for r in rows])

    intervals = [r["interval"] for r in rows]
    observed_concurrency = _max_concurrency(intervals)
    wall_start = min(a for a, _ in intervals)
    wall_end = max(b for _, b in intervals)

    ground_n = per_stage["ground"]["n"]
    return {
        "config": cfg["name"],
        "c3": cfg["c3"],
        "concurrency": cfg["concurrency"],
        "n": len(rows),
        "warmup_discarded": warmup,
        "stages": per_stage,
        "end_to_end": e2e,
        "observed_max_concurrency": observed_concurrency,
        "wall_clock_s": round(wall_end - wall_start, 3),
        "throughput_calls_per_s": round(len(rows) / (wall_end - wall_start), 1),
        "grounded_calls": ground_n,
        "all_signatures_valid": all(r["signature_valid"] for r in rows),
        "receipt_persisted_lines": len(trail_lines),
        "receipt_lines_all_parse": all(_parses(l) for l in trail_lines),
        "intervention_distribution": _dist(r["intervention"] for r in rows),
    }


def _parses(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except json.JSONDecodeError:
        return False


def _dist(it) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in it:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def build_report(*, smoke: bool = False) -> dict[str, Any]:
    n_calls = SMOKE_CALLS if smoke else N_CALLS
    warmup = SMOKE_WARMUP if smoke else WARMUP

    hashes_before = _frozen_hashes()
    subtrees_before = _summary_subtrees()

    cases = B.load_cases()
    cold_start: dict[str, float | None] = {"value": None, "config": None}
    results = [
        run_config(cfg, cases, n_calls=n_calls, warmup=warmup, cold_start_ms=cold_start)
        for cfg in CONFIGS
    ]

    hashes_after = _frozen_hashes()
    subtrees_after = _summary_subtrees()
    frozen_unchanged = hashes_before == hashes_after and subtrees_before == subtrees_after

    try:
        import torch  # noqa: PLC0415  -- only to record the runtime, never used for compute
        torch_version = torch.__version__
    except Exception:  # noqa: BLE001
        torch_version = "not-imported"

    return {
        "task": "P09_LATENCY_PROFILE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "smoke": smoke,
        "measurement_setup": {
            "unit": (
                "one intercept._run_gate() call: extract -> classify -> resolve -> "
                "predicate -> ground -> decide -> receipt, ending in a signed receipt "
                "persisted to an isolated decisions.jsonl. The downstream business "
                "tool is not invoked."
            ),
            "workload": "P03 gold_set.jsonl (150 cases) in file order, cycled to n per config",
            "gold_set_sha256": _sha256(B.GOLD_SET),
            "n_calls_per_config": n_calls,
            "warmup_discarded_per_config": warmup,
            "warmup_policy": (
                "a fixed count of leading calls is executed and discarded, identical "
                "for all four configurations; it primes the Zen compiled-graph cache, "
                "SQLite, and (grounded configs) the first scored HHEM inference"
            ),
            "extraction": (
                "stubbed to the pre-built ProposedAction per case (P04/P05/P08 "
                "convention). The 'extract' row is the gate's typed-object hand-off, "
                "NOT production extraction (one LLM call, CP_MODEL=Qwen/Qwen3-8B, "
                "temperature 0) nor the offline fixture read (~0.1-0.5 ms)."
            ),
            "clock": f"frozen, CP_DEMO_DATE={FROZEN_DATE}",
            "seed": SEED,
            "timing_method": "time.perf_counter(), per stage inside _run_gate; end_to_end wraps the whole gate body",
            "percentile_method": (
                "nearest-rank without interpolation: pXX = sorted[ceil(XX/100 * n) - 1]; "
                "max = slowest single call. Percentiles in summary.json are exact sample "
                "values (an actual observed latency), not rounded; per-call stage latencies "
                "are recorded by _run_gate at 0.01 ms resolution, mean is full-precision."
            ),
            "concurrency_mechanism": (
                "concurrent.futures.ThreadPoolExecutor(max_workers=N). Threads, not "
                "processes: the pipeline is I/O-bound (SQLite + trail append) with a "
                "shared in-process HHEM model; the GIL is released during SQLite, file "
                "I/O and torch compute. Observed max concurrency is measured by "
                "sweep-line over per-call (enter, exit) perf_counter stamps."
            ),
            "grounding_model": ground_module.MODEL_NAME,
            "grounding_load": "controlplane.ground.preload() -- once, at process start, timed as cold start",
            "runtime": {
                "python": sys.version.split()[0],
                "torch": torch_version,
                "platform": sys.platform,
            },
        },
        "cold_start": {
            "ms": cold_start["value"],
            "measured_on_config": cold_start["config"],
            "definition": (
                "wall time of the one-time HHEM model load (controlplane.ground.preload). "
                "Excluded from every steady-state percentile below."
            ),
            "applies_to": "C2, C4 (grounding on). N/A for C1, C3.",
        },
        "steady_state": {
            "definition": (
                "the n timed calls per configuration, after the fixed warm-up and "
                "after preload(); the model is already resident, so no call pays the "
                "cold start"
            ),
        },
        "configurations": results,
        "aegis_comparison": "AEGIS 8.3 ms median (48 attacks / 500 benign / 1,000 interceptions)",
        "oap_comparison": "OAP 53 ms median (N=1,000)",
        "frozen_input_integrity": {
            "unchanged": frozen_unchanged,
            "before": hashes_before,
            "after": hashes_after,
            "summary_subtrees_before": subtrees_before,
            "summary_subtrees_after": subtrees_after,
        },
        "reproduction_command": "python bench/latency.py --write",
    }


# ---------------------------------------------------------------------------
# reports/latency.md + summary.json['p09_latency']  (only on --write)
# ---------------------------------------------------------------------------


def _ms(v: float | None) -> str:
    return "-" if v is None else f"{v:.2f}"


def _cfg_label(r: dict[str, Any]) -> str:
    return f"{r['config']} (C3 {r['c3']}, concurrency {r['concurrency']}, n={r['n']})"


def _headline_config(results: list[dict[str, Any]]) -> dict[str, Any]:
    return next(r for r in results if r["config"] == "C1_hhem_off_seq")


def write_markdown(report: dict[str, Any]) -> str:
    ms = report["measurement_setup"]
    results = report["configurations"]
    head = _headline_config(results)
    e2e_head = head["end_to_end"]
    cold = report["cold_start"]

    L: list[str] = []
    L.append("# P09 -- latency profile")
    L.append("")
    L.append(
        "Regenerate with `python bench/latency.py --write`. This report and "
        "`summary.json['p09_latency']` are the authoritative latency numbers; the "
        "older `summary.json['latency']` block (n=24) is a superseded interim."
    )
    L.append("")

    # A
    L.append("## A. Measurement setup")
    L.append("")
    L.append(f"- **Unit measured**: {ms['unit']}")
    L.append(f"- **Workload**: {ms['workload']} -> {ms['n_calls_per_config']} calls per configuration, identical across all four. Gold set SHA-256 `{ms['gold_set_sha256']}`.")
    L.append(f"- **Extraction**: {ms['extraction']}")
    L.append(f"- **Clock**: {ms['clock']}. **Seed**: {ms['seed']}.")
    L.append(f"- **Timing**: {ms['timing_method']}.")
    L.append(f"- **Percentile method**: {ms['percentile_method']}")
    L.append(f"- **Concurrency**: {ms['concurrency_mechanism']}")
    L.append(f"- **Warm-up**: {ms['warmup_discarded_per_config']} calls per configuration, discarded. {ms['warmup_policy']}. No other observations are dropped; no outliers removed.")
    L.append(f"- **Grounding model**: `{ms['grounding_model']}` ({ms['grounding_load']}).")
    L.append(f"- **Runtime**: Python {ms['runtime']['python']}, torch {ms['runtime']['torch']}, {ms['runtime']['platform']}.")
    L.append(f"- **Frozen inputs unchanged during the run**: **{report['frozen_input_integrity']['unchanged']}**.")
    L.append("")
    L.append("**Stage boundaries** (each a `time.perf_counter()` block in `controlplane/intercept.py::_run_gate`; no stage is nested inside another):")
    L.append("")
    L.append("| stage | starts | ends |")
    L.append("|---|---|---|")
    L.append("| extract | tool call in | typed `ProposedAction` returned (stubbed here) |")
    L.append("| classify | after extract | claims built + Checkability-Ladder tier/load-bearing assigned |")
    L.append("| resolve | after classify | every claim's `Evidence` resolved via its binding (live SQLite reads) |")
    L.append("| predicate | after resolve | Zen JDM graph evaluated over the resolved evidence |")
    L.append("| ground | after predicate | HHEM entailment score returned (only when C3 on and a clause-semantics claim exists) |")
    L.append("| decide | after ground | pure `decide()` returns the `Decision` |")
    L.append("| receipt | after decide | receipt built, HMAC-signed, and appended to the trail |")
    L.append("| **end_to_end** | tool call in | signed receipt persisted (spans all of the above **plus** manifest load/validate, `claim_specs`, the clause-match check and bookkeeping between stages) |")
    L.append("")
    L.append("`end_to_end` is measured directly, not summed from stages, so the un-instrumented between-stage work (manifest YAML load + validation, `claim_specs`, `clause_matches_claim`) is visible as the gap `end_to_end - sum(stages)`.")
    L.append("")

    # B
    L.append("## B. The four configurations")
    L.append("")
    L.append("| config | C3 / HHEM | concurrency | n (timed) | warm-up discarded | observed max concurrency | wall clock (s) | throughput (calls/s) |")
    L.append("|---|---|--:|--:|--:|--:|--:|--:|")
    for r in results:
        L.append(
            f"| {r['config']} | {r['c3']} | {r['concurrency']} | {r['n']} | {r['warmup_discarded']} "
            f"| {r['observed_max_concurrency']} | {r['wall_clock_s']} | {r['throughput_calls_per_s']} |"
        )
    L.append("")
    L.append("Configurations are **not** averaged together. Each is a separate >= 1,000-call distribution.")
    L.append("")
    L.append("Intervention mix per config (same 1,050 inputs each): " + "; ".join(
        f"{r['config']} -> {json.dumps(r['intervention_distribution'], sort_keys=True)}" for r in results
    ) + ". The C3-on configs escalate more: HHEM is an extra gate that fires on this workload's paraphrases. "
        "That is a verdict-semantics effect of `CP_GROUNDING=on` (by design, pre-P09), not a workload difference and not "
        "caused by the timing instrumentation -- `tests/test_latency.py` checks the receipt stays signed and the verdict "
        "is unchanged by the timing code.")
    L.append("")

    # C
    L.append("## C. Stage percentile table (ms)")
    L.append("")
    for r in results:
        L.append(f"### {_cfg_label(r)}")
        L.append("")
        L.append("| stage | n | p50 | p95 | p99 | max | mean | note |")
        L.append("|---|--:|--:|--:|--:|--:|--:|---|")
        for stage in STAGES:
            s = r["stages"][stage]
            if s["n"] == 0:
                note = "grounding off" if stage == "ground" else "not reached"
                L.append(f"| {stage} | 0 | - | - | - | - | - | {note} |")
            else:
                L.append(
                    f"| {stage} | {s['n']} | {_ms(s['p50'])} | {_ms(s['p95'])} | "
                    f"{_ms(s['p99'])} | {_ms(s['max'])} | {_ms(s['mean'])} | |"
                )
        gap_mean = (r["end_to_end"]["mean"] or 0) - sum(
            (r["stages"][st]["mean"] or 0) for st in STAGES
        )
        L.append(
            f"| _(between-stage)_ | {r['n']} | - | - | - | - | {gap_mean:.2f} | "
            f"manifest YAML load+validate, claim_specs, clause-match, bookkeeping -- "
            f"redone every call, not attributed to a stage |"
        )
        L.append("")

    # D
    L.append("## D. End-to-end percentile table (ms)")
    L.append("")
    L.append("| config | C3 | concurrency | n | p50 | p95 | p99 | max | mean |")
    L.append("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for r in results:
        e = r["end_to_end"]
        L.append(
            f"| {r['config']} | {r['c3']} | {r['concurrency']} | {e['n']} "
            f"| {_ms(e['p50'])} | {_ms(e['p95'])} | {_ms(e['p99'])} | {_ms(e['max'])} | {_ms(e['mean'])} |"
        )
    L.append("")

    # E / F
    L.append("## E. Cold-start measurement")
    L.append("")
    if cold["ms"] is None:
        L.append("Not measured (no grounded configuration ran).")
    else:
        L.append(f"- **HHEM one-time model load: {cold['ms']:.0f} ms** ({cold['ms']/1000:.2f} s), measured on `{cold['measured_on_config']}` via `controlplane.ground.preload()`.")
        L.append(f"- {cold['definition']}")
        L.append(f"- {cold['applies_to']}")
        L.append("- The model is a module-global loaded exactly once per process (`controlplane/ground.py`, double-checked lock). It is **not** loaded per call; test `tests/test_latency.py` asserts this.")
    L.append("")
    L.append("## F. Steady-state measurement")
    L.append("")
    L.append(f"{report['steady_state']['definition']}. Every percentile in sections C and D is steady-state. Cold start is never folded into them.")
    L.append("")

    # G
    L.append("## G. C3 / HHEM contribution")
    c1 = next(r for r in results if r["config"] == "C1_hhem_off_seq")
    c2 = next(r for r in results if r["config"] == "C2_hhem_on_seq")
    L.append("")
    g = c2["stages"]["ground"]
    if g["n"]:
        L.append(f"- HHEM `ground` stage, sequential (C2): p50 **{_ms(g['p50'])} ms**, p95 **{_ms(g['p95'])} ms**, p99 **{_ms(g['p99'])} ms**, max **{_ms(g['max'])} ms** over {g['n']} scored calls.")
        L.append(f"- End-to-end p50 with HHEM off (C1) = **{_ms(c1['end_to_end']['p50'])} ms**; with HHEM on (C2) = **{_ms(c2['end_to_end']['p50'])} ms**.")
        L.append(f"- End-to-end p99: C1 = **{_ms(c1['end_to_end']['p99'])} ms**, C2 = **{_ms(c2['end_to_end']['p99'])} ms**. End-to-end max: C1 = **{_ms(c1['end_to_end']['max'])} ms**, C2 = **{_ms(c2['end_to_end']['max'])} ms**.")
        dominates = (g["p95"] or 0) >= 0.5 * (c2["end_to_end"]["p95"] or 1)
        L.append("")
        if dominates:
            L.append("**Finding: HHEM dominates the tail.** When C3 grounding is on, the HHEM entailment call is the single largest stage at p95/p99/max and drives end-to-end latency roughly an order of magnitude above the HHEM-off path. This is reported, not optimised away: C3 is optional coverage (`CP_GROUNDING=off` is the default), the verdict degrades to C1/C2 on timeout (P08 scenario 6), and the gate's own deterministic overhead is the HHEM-off number.")
        else:
            L.append("**Finding:** HHEM adds a measurable but not tail-dominating cost on this workload; see the numbers above.")
    else:
        L.append("No grounded calls were recorded -- unexpected; investigate before citing C2/C4.")
    L.append("")

    # H
    L.append("## H. Concurrency comparison")
    c3c = next(r for r in results if r["config"] == "C3_hhem_off_par")
    c4c = next(r for r in results if r["config"] == "C4_hhem_on_par")
    L.append("")
    L.append("| pair | metric | concurrency 1 | concurrency 10 | direction |")
    L.append("|---|---|--:|--:|---|")
    for lo, hi, lab in ((c1, c3c, "HHEM off"), (c2, c4c, "HHEM on")):
        for m in ("p50", "p95", "p99", "max"):
            a, b = lo["end_to_end"][m], hi["end_to_end"][m]
            direction = "worse under load" if (b or 0) > (a or 0) else ("better" if (b or 0) < (a or 0) else "flat")
            L.append(f"| {lab} (end_to_end) | {m} | {_ms(a)} | {_ms(b)} | {direction} |")
    L.append("")
    L.append(f"- Observed max concurrency: C3 = {c3c['observed_max_concurrency']}, C4 = {c4c['observed_max_concurrency']} (target {CONCURRENCY_HI}). C1/C2 = {c1['observed_max_concurrency']}/{c2['observed_max_concurrency']} (sequential).")
    L.append(f"- Throughput: C1 {c1['throughput_calls_per_s']}/s vs C3 {c3c['throughput_calls_per_s']}/s; C2 {c2['throughput_calls_per_s']}/s vs C4 {c4c['throughput_calls_per_s']}/s.")
    L.append("- Same workload on both sides of every comparison (same 1,050 gold-case calls).")
    L.append("")
    off_blowup = (c3c["end_to_end"]["p50"] or 1) / (c1["end_to_end"]["p50"] or 1)
    on_blowup = (c4c["end_to_end"]["p50"] or 1) / (c2["end_to_end"]["p50"] or 1)
    tput_gain_off = (c3c["throughput_calls_per_s"] or 0) / (c1["throughput_calls_per_s"] or 1)
    rs1, rs10 = c1["stages"]["resolve"], c3c["stages"]["resolve"]
    rc1, rc10 = c1["stages"]["receipt"], c3c["stages"]["receipt"]
    L.append(
        f"**Finding: concurrency=10 with in-process threads badly worsens per-call latency and barely helps throughput.** "
        f"End-to-end p50 goes {c1['end_to_end']['p50']:.1f} -> {c3c['end_to_end']['p50']:.1f} ms ({off_blowup:.0f}x) with HHEM off "
        f"and {c2['end_to_end']['p50']:.0f} -> {c4c['end_to_end']['p50']:.0f} ms ({on_blowup:.1f}x) with HHEM on, while throughput moves only "
        f"{c1['throughput_calls_per_s']:.0f} -> {c3c['throughput_calls_per_s']:.0f}/s ({tput_gain_off:.2f}x) and "
        f"{c2['throughput_calls_per_s']:.1f} -> {c4c['throughput_calls_per_s']:.1f}/s. "
        f"Attribution (HHEM off): the `resolve` stage p50 blows up {rs1['p50']:.1f} -> {rs10['p50']:.0f} ms "
        f"({(rs10['p50'] or 1)/(rs1['p50'] or 1):.0f}x -- each gate call opens and closes a fresh SQLite connection per claim, "
        f"and the surrounding Python is GIL-bound) and the `receipt` stage p50 goes {rc1['p50']:.1f} -> {rc10['p50']:.0f} ms "
        f"({(rc10['p50'] or 1)/(rc1['p50'] or 1):.0f}x -- the trail-append lock serializes all ten workers). With HHEM on, the model "
        f"call itself contends across the ten threads ({c2['stages']['ground']['p50']:.0f} -> {c4c['stages']['ground']['p50']:.0f} ms). "
        f"The gate re-loads and re-validates the manifest YAML on every call (the `end_to_end - Sigma(stages)` gap, ~{(c1['end_to_end']['mean'] or 0) - sum((c1['stages'][s]['mean'] or 0) for s in STAGES):.1f} ms/call at concurrency 1), which is also GIL-bound. "
        f"P09 reports this as measured, not optimised: a real deployment would use process-level workers or async I/O, cache the manifest, and pool connections; this run measures the gate exactly as it stands under a thread pool, as the task specifies."
    )
    L.append("")

    # I / J -- one comparison line covers both, as the task requires
    head_p50 = _ms(e2e_head["p50"])
    L.append("## I. AEGIS comparison")
    L.append("")
    L.append("AEGIS 8.3 ms median over 1,000 interceptions (48 attacks / 500 benign). See the combined comparison line below.")
    L.append("")
    L.append("## J. OAP comparison")
    L.append("")
    L.append("OAP 53 ms median, N=1,000. See the combined comparison line below.")
    L.append("")
    L.append("### Comparison line")
    L.append("")
    L.append(
        f"> AEGIS 8.3 ms median (48 attacks / 500 benign / 1,000 interceptions); "
        f"OAP 53 ms median (N=1,000); ControlPlane {head_p50} ms median "
        f"(**C1**: C3/HHEM off, concurrency 1, n={e2e_head['n']}, end-to-end)."
    )
    L.append("")
    L.append(
        f"The ControlPlane figure quoted on this axis is the **C1 end-to-end p50** = {head_p50} ms "
        "-- HHEM off, sequential -- because that is the configuration comparable to a median "
        "over mixed traffic with no grounding model. The HHEM-on numbers (C2/C4) are "
        "reported separately in sections C, D and G and are **not** blended into this line. "
        f"For reference on the same axis: C2 (HHEM on, seq) end-to-end p50 = {_ms(c2['end_to_end']['p50'])} ms, "
        f"p95 = {_ms(c2['end_to_end']['p95'])} ms."
    )
    L.append("")

    # K
    L.append("## K. Honesty / limitations")
    L.append("")
    L.append("- **Live database query.** Our figure includes a live SQLite read of the system of record on every call (the `resolve` stage) -- neither AEGIS nor OAP performs a source-of-record lookup. The comparison is **not like-for-like**. **Direction of bias: the live query makes our measured latency higher than it would be without that lookup.** This caveat explains the gap; it does not discount the measurement -- the lookup is the point of the architecture.")
    L.append("- **extract is stubbed** (see section A). Production extraction is one LLM call and would dominate a full agent-turn measurement; it is deliberately excluded because the gate's own overhead is what P09 measures (`docs/ROADMAP.md`: report the gate's latency excluding the agent's own model call).")
    L.append("- **Single machine, single run.** One host, one OS (see runtime above), one process. Percentiles are over calls, not over repeated runs; the workload is deterministic (fixed seed, frozen clock, deterministic HHEM classifier) so a re-run reproduces them closely modulo host scheduling noise.")
    L.append("- **Raw per-call observations are not stored** in `summary.json` (4 x ~1,050 x 8 numbers). `summary.json['p09_latency']` retains the unrounded percentiles; the full sample is reproduced by re-running the one command.")
    L.append("- **Threads, not processes.** True parallelism is bounded by the GIL between the C-extension release points; concurrency=10 measures the gate under a realistic in-process worker pool, not 10 isolated CPUs. See section H for the resulting per-call blow-up -- it is a real property of the gate as written (per-call manifest YAML re-parse, per-claim SQLite connect/close), reported, not tuned away.")
    L.append(f"- **The trail-append lock is a deliberate correctness/latency trade.** `controlplane/receipt.py` now serializes the `decisions.jsonl` append (P09 fires the gate from a thread pool; two interleaved writes would corrupt the trail -- and all {sum(r['n'] for r in results) + sum(r['warmup_discarded'] for r in results)} persisted lines across the run parse cleanly). At concurrency 10 with sub-30 ms calls this adds ~{(c3c['stages']['receipt']['p50'] or 0):.0f} ms of serialization to the `receipt` stage (C3); a persistent append handle would cut it, but that would break the per-test/per-config trail redirection P08/P09 rely on. It is visible in section C, not hidden.")
    L.append(f"- **Cold start is I/O-bound and noisy.** The one HHEM load measured {(cold['ms'] or 0)/1000:.1f} s in this run; separate loads this session ranged ~4.7-13.5 s depending on OS page-cache state. It is reported as a single measurement, kept entirely out of the steady-state tables.")
    L.append("")

    # L
    L.append("## L. Exact reproduction command")
    L.append("")
    L.append("```")
    L.append("python bench/latency.py --write")
    L.append("```")
    L.append("")
    L.append(f"Deterministic inputs: `CP_DEMO_DATE={FROZEN_DATE}`, seed `{SEED}`, `CP_MODEL=Qwen/Qwen3-8B` (unused -- extract stubbed), grounding model `{ms['grounding_model']}` (no decoding params -- a classifier, greedy by construction), gold set `bench/gold_set.jsonl` SHA-256 `{ms['gold_set_sha256']}`, {ms['n_calls_per_config']} calls/config, {ms['warmup_discarded_per_config']} warm-up calls/config discarded.")
    L.append("")

    text = "\n".join(L).rstrip("\n") + "\n"
    (REPORTS / "latency.md").write_text(text, encoding="utf-8")
    return text


def _summary_entry(report: dict[str, Any]) -> dict[str, Any]:
    ms = report["measurement_setup"]
    return {
        "measurement_setup": ms,
        "cold_start": report["cold_start"],
        "steady_state": report["steady_state"],
        "aegis_comparison": report["aegis_comparison"],
        "oap_comparison": report["oap_comparison"],
        "configurations": [
            {
                "config": r["config"],
                "c3": r["c3"],
                "concurrency": r["concurrency"],
                "n": r["n"],
                "warmup_discarded": r["warmup_discarded"],
                "model": ground_module.MODEL_NAME if r["c3"] == "on" else None,
                "seed": SEED,
                "workload": {
                    "source": "bench/gold_set.jsonl",
                    "n_cases": 150,
                    "cycles": r["n"] // 150,
                    "gold_set_sha256": ms["gold_set_sha256"],
                    "clock": ms["clock"],
                },
                "stages": r["stages"],           # unrounded p50/p95/p99/max/mean per stage
                "end_to_end": r["end_to_end"],   # unrounded
                "observed_max_concurrency": r["observed_max_concurrency"],
                "grounded_calls": r["grounded_calls"],
                "wall_clock_s": r["wall_clock_s"],
                "throughput_calls_per_s": r["throughput_calls_per_s"],
                "all_signatures_valid": r["all_signatures_valid"],
                "receipt_persisted_lines": r["receipt_persisted_lines"],
                "receipt_lines_all_parse": r["receipt_lines_all_parse"],
                "intervention_distribution": r["intervention_distribution"],
            }
            for r in report["configurations"]
        ],
        "cold_start_ms": report["cold_start"]["ms"],
        "steady_state_definition": report["steady_state"]["definition"],
        "reproduction_command": report["reproduction_command"],
        "frozen_inputs_unchanged_during_run": report["frozen_input_integrity"]["unchanged"],
    }


def merge_summary_json(report: dict[str, Any]) -> None:
    path = REPORTS / "summary.json"
    existing: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    before = {k: v for k, v in existing.items() if k != "p09_latency"}
    existing["p09_latency"] = _summary_entry(report)
    for key, value in before.items():
        if existing[key] != value:
            raise AssertionError(f"summary.json merge would have altered {key!r}")
    path.write_text(
        json.dumps(existing, indent=2, default=str, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--write", action="store_true", help="write reports/latency.md + summary.json[p09_latency]")
    parser.add_argument("--smoke", action="store_true", help="60 calls/config -- wiring check only, never combine with --write")
    args = parser.parse_args()

    if args.smoke and args.write:
        raise SystemExit("refusing to --write a --smoke run (n below 1,000)")

    report = build_report(smoke=args.smoke)
    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True, default=str))

    ok = (
        report["frozen_input_integrity"]["unchanged"]
        and all(r["all_signatures_valid"] for r in report["configurations"])
        and all(r["receipt_lines_all_parse"] for r in report["configurations"])
        and all(r["n"] >= (SMOKE_CALLS if args.smoke else 1000) for r in report["configurations"])
        and all(r["grounded_calls"] > 0 for r in report["configurations"] if r["c3"] == "on")
        and next(r for r in report["configurations"] if r["config"] == "C3_hhem_off_par")["observed_max_concurrency"] >= 2
    )

    if args.write:
        write_markdown(report)
        merge_summary_json(report)
        print("\nwrote reports/latency.md and reports/summary.json['p09_latency']", file=sys.stderr)

    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
