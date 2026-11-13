"""Recompute the latency summary of this evidence pack from its run files.

Python standard library only; runs on Linux, macOS and Windows.

    python summarise.py           # writes summary.json and summary.md next to this file
    python summarise.py --check   # writes nothing; exits 1 if either file differs

Reads runs/<E>_r<round>_<cond>.json (end-to-end latency, intervention mix) and
runs/<same>.gate.txt (power overlay, RAM, CPU) for the 12 counted runs, and lists
runs/incomplete/*.json separately (never used in any median).

Exits 1 if a counted run file is missing, if any counted run's mix is not
ALLOW 378 / BLOCK 602 / ESCALATE 70, or if a run's configuration, n, warm-up,
signatures, machine gate or power overlay differs from PROTOCOL_E.md.

Numbers are sequential per-call service time in one process (concurrency 1),
not response time under load. The median of 3 runs is reported together with
all 3 values; no statistical test is made.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PHASES = {
    "E1": {"overlay": "ded574b5-45a0-4f42-8737-46345c09c238", "power_mode": "Best performance",
           "role": "official"},
    "E2": {"overlay": "961cc777-2547-4f9d-8174-7d86181b8a7a", "power_mode": "Best power efficiency",
           "role": "report-only"},
}
CONDITIONS = {"old": "880d5c9", "new": "356ec58"}
ROUNDS = (1, 2, 3)
EXPECTED_MIX = {"ALLOW": 378, "BLOCK": 602, "ESCALATE": 70}
PCTS = ("p50", "p95", "p99", "max")
GATE_RE = re.compile(r"free_GB=(?P<free>[\d.]+) avail_GB=(?P<avail>[\d.]+) .*"
                     r"cpu_avg=(?P<cpu>[\d.]+) .*pass=(?P<passed>\w+)")
OVERLAY_RE = re.compile(r"^overlay=(?P<reg>\S+) api=(?P<api>\S+)", re.MULTILINE)


class PackError(Exception):
    pass


def _read_run(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    e2e = data["end_to_end"]
    return {
        "label": data["label"],
        "config": data["config"],
        "concurrency": data["concurrency"],
        "n": data["n"],
        "warmup_discarded": data["warmup_discarded"],
        "all_signatures_valid": data["all_signatures_valid"],
        "mix": dict(data["intervention_distribution"]),
        **{k: e2e[k] for k in PCTS},
    }


def _read_gate(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    g, o = GATE_RE.search(text), OVERLAY_RE.search(text)
    if not g or not o:
        raise PackError(f"{path.name}: gate or overlay line not found")
    return {
        "gate_pass": g["passed"] == "True",
        "free_ram_gb": float(g["free"]),
        "available_ram_gb": float(g["avail"]),
        "cpu_avg_pct": float(g["cpu"]),
        "overlay_registry": o["reg"],
        "overlay_api": o["api"],
    }


def build() -> dict:
    errors: list[str] = []
    runs: list[dict] = []
    for phase, spec in PHASES.items():
        for rnd in ROUNDS:
            for cond in CONDITIONS:
                label = f"{phase}_r{rnd}_{cond}"
                files = {x: RUNS / f"{label}.{x}" for x in ("json", "gate.txt", "stdout.txt")}
                missing = [p.name for p in files.values() if not p.is_file()]
                if missing:
                    errors.append(f"missing: {', '.join(missing)}")
                    continue
                run = {"phase": phase, "round": rnd, "condition": cond,
                       "commit": CONDITIONS[cond], **_read_run(files["json"]),
                       **_read_gate(files["gate.txt"])}
                checks = {
                    "label": run["label"] == label,
                    "mix": run["mix"] == EXPECTED_MIX,
                    "config": run["config"] == "C1_hhem_off_seq" and run["concurrency"] == 1,
                    "n/warm-up": run["n"] == 1050 and run["warmup_discarded"] == 50,
                    "signatures": run["all_signatures_valid"] is True,
                    "machine gate": run["gate_pass"],
                    "overlay": run["overlay_registry"] == run["overlay_api"] == spec["overlay"],
                }
                errors += [f"{label}: {name} check failed" for name, ok in checks.items() if not ok]
                runs.append(run)
    if errors:
        raise PackError("\n".join(errors))

    conditions = []
    for phase, spec in PHASES.items():
        for cond, commit in CONDITIONS.items():
            sel = sorted((r for r in runs if r["phase"] == phase and r["condition"] == cond),
                         key=lambda r: r["round"])
            p50s, p99s = [r["p50"] for r in sel], [r["p99"] for r in sel]
            conditions.append({
                "phase": phase, "role": spec["role"], "power_mode": spec["power_mode"],
                "condition": cond, "commit": commit, "runs": len(sel),
                "median_p50_ms": statistics.median(p50s), "p50_ms_by_round": p50s,
                "median_p99_ms": statistics.median(p99s), "p99_ms_by_round": p99s,
            })

    incomplete = []
    for path in sorted((RUNS / "incomplete").glob("*.json")):
        run = _read_run(path)
        incomplete.append({"file": f"runs/incomplete/{path.name}", "label": run["label"],
                           "mix": run["mix"], **{k: run[k] for k in PCTS}})

    return {
        "unit": "ms",
        "metric": "end-to-end per-call service time, sequential, one process (concurrency 1); "
                  "not response time under load",
        "workload": "bench/latency.py C1_hhem_off_seq, n=1050 timed calls after 50 warm-up",
        "expected_mix": EXPECTED_MIX,
        "median_rule": "median of the 3 run values per condition; no statistical test",
        "conditions": conditions,
        "runs": runs,
        "incomplete_runs_not_used": incomplete,
    }


def _fmt(values: list[float]) -> str:
    return ", ".join(f"{v:.2f}" for v in values)


def render_md(s: dict) -> str:
    lines = [
        "# Latency summary (generated by summarise.py; do not edit)",
        "",
        f"Metric: {s['metric']}. Unit: ms. Workload: {s['workload']}.",
        "Median of 3 runs per condition, with all 3 values (rounds 1, 2, 3). No statistical test.",
        "",
        "| Phase | Power mode | Condition | Median p50 | p50 by round | Median p99 | p99 by round |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in s["conditions"]:
        lines.append(
            f"| {c['phase']} ({c['role']}) | {c['power_mode']} | {c['condition'].upper()} {c['commit']} "
            f"| {c['median_p50_ms']:.2f} | {_fmt(c['p50_ms_by_round'])} "
            f"| {c['median_p99_ms']:.2f} | {_fmt(c['p99_ms_by_round'])} |")
    lines += [
        "",
        "## Per run",
        "",
        "| Run | p50 | p95 | p99 | max | ALLOW/BLOCK/ESCALATE | Overlay | Avail. RAM GB | CPU avg % |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s["runs"]:
        m = r["mix"]
        lines.append(
            f"| {r['label']} | {r['p50']:.2f} | {r['p95']:.2f} | {r['p99']:.2f} | {r['max']:.2f} "
            f"| {m['ALLOW']}/{m['BLOCK']}/{m['ESCALATE']} | {r['overlay_registry'][:8]} "
            f"| {r['available_ram_gb']:.2f} | {r['cpu_avg_pct']:.1f} |")
    lines += ["", "## Incomplete runs (listed only; never used in a median)", ""]
    if s["incomplete_runs_not_used"]:
        lines += ["| File | p50 | p99 |", "|---|---|---|"]
        lines += [f"| {r['file']} | {r['p50']:.2f} | {r['p99']:.2f} |" for r in s["incomplete_runs_not_used"]]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    check = argv == ["--check"]
    if argv and not check:
        print(__doc__)
        return 2
    try:
        s = build()
    except (PackError, KeyError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    outputs = {HERE / "summary.json": json.dumps(s, indent=2, sort_keys=True) + "\n",
               HERE / "summary.md": render_md(s)}
    for c in s["conditions"]:
        print(f"{c['phase']} {c['condition'].upper()} {c['commit']}: median p50 {c['median_p50_ms']:.2f} "
              f"({_fmt(c['p50_ms_by_round'])}) | median p99 {c['median_p99_ms']:.2f} "
              f"({_fmt(c['p99_ms_by_round'])})")
    print(f"counted runs: {len(s['runs'])}, mix {s['expected_mix']} in every run; "
          f"incomplete runs listed (not used): {len(s['incomplete_runs_not_used'])}")
    if check:
        stale = [p.name for p, text in outputs.items()
                 if not p.is_file() or p.read_bytes() != text.encode("utf-8")]
        print("check:", "OK" if not stale else f"DIFFERS: {', '.join(stale)}")
        return 1 if stale else 0
    for path, text in outputs.items():
        path.write_bytes(text.encode("utf-8"))
    print("wrote summary.json, summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
