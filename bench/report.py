#!/usr/bin/env python3
"""S18 — one command that reads decisions.jsonl and regenerates every
number and chart in the submission. The alternative is copying numbers by
hand into a deck, and that is exactly how a stale figure survives — this
project has already caught four fabricated figures; the point of this
script is that a fifth can't get in through a transcription error.

    make report   ->   python bench/report.py

Writes reports/coverage.md, latency.md, confusion.md, noise_sweep.png,
and summary.json (every headline number, as a key).

promotion_curve.png is intentionally not generated: its model-load input was
a hand-typed value from a past session with no reproducible source in this
repository. Restore that chart only when every input comes from preserved,
logged measurements.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import dateparser  # noqa: F401
except ImportError:
    raise SystemExit("FATAL: dateparser missing. Results are invalid without it.")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DECISIONS = ROOT / "decisions.jsonl"
REPORTS = ROOT / "reports"
ACCENT = "#2563eb"

def _load_decisions() -> list[dict]:
    if not DECISIONS.exists():
        return []
    return [json.loads(line) for line in DECISIONS.read_text(encoding="utf-8").splitlines() if line.strip()]


def _coverage_report(lines: list[dict]) -> dict:
    if not lines:
        return {"n_decisions": 0, "note": "decisions.jsonl is empty — run `make demo` first"}
    totals = {"C1": 0, "C2": 0, "C3": 0, "C4": 0, "C5": 0}
    claims_total = 0
    for line in lines:
        cov = line.get("telemetry", {}).get("coverage", {})
        claims_total += cov.get("claims_total", 0)
        for t in totals:
            totals[t] += cov.get(f"{t.lower()}_n", 0)
    checkable = totals["C1"] + totals["C2"]
    return {
        "n_decisions": len(lines),
        "claims_total": claims_total,
        "by_tier": totals,
        "coverage_ratio_c1_c2": (checkable / claims_total) if claims_total else None,
    }


def _latency_report(lines: list[dict]) -> dict:
    stages = ["extract", "classify", "resolve", "predicate", "decide", "ground"]
    samples = {s: [] for s in stages}
    for line in lines:
        for s, ms in line.get("telemetry", {}).get("latency", {}).items():
            if s in samples:
                samples[s].append(ms)
    out = {}
    for s, vals in samples.items():
        if not vals:
            out[s] = None
            continue
        vals_sorted = sorted(vals)

        def pct(p):
            return vals_sorted[min(len(vals_sorted) - 1, int(round(p * (len(vals_sorted) - 1))))]

        out[s] = {"n": len(vals), "p50_ms": pct(0.5), "p95_ms": pct(0.95), "mean_ms": sum(vals) / len(vals)}
    return out


def _write_markdown_table(path: Path, title: str, rows: list[tuple], headers: tuple, note: str = "") -> None:
    lines = [f"# {title}", ""]
    if note:
        lines += [note, ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "---|" * len(headers))
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _exp3_chart(path: Path) -> dict:
    """Named noise_sweep.png per the roadmap's file list, but honestly
    titled for what this build actually measured: no noise-level sweep
    experiment exists in this repo (see README's Honest limitations) — this
    is Exp 3's real result, the closest thing that exists to it."""
    from seb1_exp3_cross_validation import run as run_exp3

    result = run_exp3(n=200, seed=20260814)
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["WITH attributes_match\n(R3 extended, D52)", "WITHOUT attributes_match"]
    values = [result["accuracy_with_attributes_check"], result["accuracy_without_attributes_check"]]
    bars = ax.bar(labels, values, color=[ACCENT, "#999"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("verdict accuracy")
    ax.set_title("SEB-1 Exp 3: D52 cross-validation accuracy\n"
                  "(labelled noise_sweep.png for file-list compatibility — no noise-level\n"
                  "sweep exists in this build; see README's Honest limitations)",
                  fontsize=9, loc="left")
    ax.text(0, 1.1, f"synthetic benchmark · CP_SEED=20260814 · n={result['n']}",
            transform=ax.transAxes, fontsize=8, color="#666")
    for bar, val in zip(bars, values):
        ax.annotate(f"{val:.1%}", (bar.get_x() + bar.get_width() / 2, val), ha="center", va="bottom", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return result


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    lines = _load_decisions()

    coverage = _coverage_report(lines)
    latency = _latency_report(lines)

    from seb1_exp5_confusion_matrix import run as run_exp5

    exp5 = run_exp5(n_per_class=50, seed=20260814)
    exp3 = _exp3_chart(REPORTS / "noise_sweep.png")

    from dataclasses import asdict

    from controlplane.bias_probe import run_probe
    from controlplane.mutation import run_mutation_testing

    bias = asdict(run_probe())
    mutation = run_mutation_testing()

    _write_markdown_table(
        REPORTS / "coverage.md", "Claim coverage by tier",
        [(t, n) for t, n in coverage.get("by_tier", {}).items()],
        ("tier", "count"),
        note=(f"n_decisions={coverage['n_decisions']}, claims_total={coverage.get('claims_total', 0)}, "
              f"C1+C2 coverage_ratio={coverage.get('coverage_ratio_c1_c2')}"
              if coverage.get("n_decisions") else coverage.get("note", "")),
    )
    _write_markdown_table(
        REPORTS / "latency.md", "Per-stage latency (from decisions.jsonl)",
        [(s, v["n"], f"{v['p50_ms']:.2f}", f"{v['p95_ms']:.2f}") if v else (s, 0, "-", "-")
         for s, v in latency.items()],
        ("stage", "n", "p50_ms", "p95_ms"),
        note="Real percentiles need many logged decisions — run `make demo` repeatedly to grow this.",
    )
    _write_markdown_table(
        REPORTS / "confusion.md", "SEB-1 Exp 5 — gold vs predicted (4x4)",
        [(g, *[exp5["matrix"][g][p] for p in ["ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"]])
         for g in ["ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"]],
        ("gold \\ pred", "ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"),
        note=f"n={exp5['total']}, accuracy={exp5['accuracy']:.3f}, CP_SEED=20260814. Cost-weighted: {exp5['cost_weighted']}",
    )

    summary = {
        "coverage": coverage,
        "latency": latency,
        "confusion_matrix": exp5,
        "seb1_exp3_cross_validation": exp3,
        "bias_probe": bias,
        "mutation_testing": mutation,
        "seed": 20260814,
        "demo_date": "2026-08-14",
    }
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("wrote reports/coverage.md, latency.md, confusion.md, noise_sweep.png, summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
