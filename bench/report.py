#!/usr/bin/env python3
"""S18 — one command that reads decisions.jsonl and regenerates every
number and chart in the submission. The alternative is copying numbers by
hand into a deck, and that is exactly how a stale figure survives — this
project has already caught circular figures in its own work; the point of
this script is that another can't get in through a transcription error.

    make report   ->   python bench/report.py

Writes reports/coverage.md, latency_trail.md, confusion.md, noise_sweep.png,
promotion_curve.png, and merges its own keys into summary.json. It does NOT
touch reports/latency.md (P09 owns it) or the p04/p05/p08/p09 summary sections.

Post-audit state (docs/experiment-audit.md):
  * confusion matrix (Exp 5) is BLOCKED until task P03 delivers a held-out
    gold set — this script records the blocked status, never a number;
  * the bias probe was retired (it could not fail) — no bias number is
    emitted; the structural guarantee is tests/test_no_protected_attributes.py;
  * coverage_ratio was retired (deterministically 1.0) — per-tier COUNTS
    remain, the ratio does not;
  * mutation score is now spec-derived and expected to be < 1.0.
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
from receipt_size import measure_receipt_sizes

DECISIONS = ROOT / "decisions.jsonl"
REPORTS = ROOT / "reports"
ACCENT = "#2563eb"

# Measured this session (README's S8 section) — not re-measured here to
# avoid a second ~13s model load every time `make report` runs.
MEASURED_GROUNDING_LOAD_MS = 13_209.0
MEASURED_GROUNDING_CALL_MS = 109.8
TYPICAL_PREDICATE_MS = 0.6


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
    # Per-tier COUNTS only. No ratio — see docs/experiment-audit.md.
    return {"n_decisions": len(lines), "claims_total": claims_total, "by_tier": totals}


def _latency_report(lines: list[dict]) -> dict:
    stages = ["extract", "classify", "resolve", "predicate", "decide", "ground", "end_to_end"]
    samples = {s: [] for s in stages}
    for line in lines:
        decision_latency = line.get("telemetry", {}).get("latency", {})
        for s, ms in decision_latency.items():
            if s in samples:
                samples[s].append(ms)
        if decision_latency:
            samples["end_to_end"].append(sum(decision_latency.values()))
    out = {}
    for s, vals in samples.items():
        if not vals:
            out[s] = None
            continue
        vals_sorted = sorted(vals)

        def pct(p):
            return vals_sorted[min(len(vals_sorted) - 1, int(round(p * (len(vals_sorted) - 1))))]

        out[s] = {"n": len(vals), "p50_ms": pct(0.5), "p95_ms": pct(0.95),
                  "p99_ms": pct(0.99), "mean_ms": sum(vals) / len(vals)}
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


def _promotion_curve_chart(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    stages = ["C1/C2\npredicate\n(Zen graph)", "C3\ngrounding\n(model load)", "C3\ngrounding\n(scored call)"]
    values_ms = [TYPICAL_PREDICATE_MS, MEASURED_GROUNDING_LOAD_MS, MEASURED_GROUNDING_CALL_MS]
    bars = ax.bar(stages, values_ms, color=ACCENT)
    ax.set_yscale("log")
    ax.set_ylabel("milliseconds (log scale)")
    ax.set_title("Rule promotion cost: C1/C2 predicate vs. C3 grounding (HHEM-2.1-Open)",
                 fontsize=10, loc="left")
    ax.text(0, 1.02, "measured this session, CP_SEED=20260814 · n=1 per bar — see README's S8 section",
            transform=ax.transAxes, fontsize=8, color="#666")
    for bar, val in zip(bars, values_ms):
        ax.annotate(f"{val:,.1f} ms", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _exp3_chart(path: Path) -> dict:
    """Named noise_sweep.png per the roadmap's file list, but honestly
    titled for what this build actually measured: no noise-level sweep
    experiment exists in this repo (see README's Honest limitations) — this
    is Exp 3's real result."""
    from seb1_exp3_cross_validation import run as run_exp3

    result = run_exp3(n=200, seed=20260814)
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["WITH attributes_match\n(R3 extended, D52)", "WITHOUT attributes_match"]
    values = [result["accuracy_with_attributes_check"], result["accuracy_without_attributes_check"]]
    bars = ax.bar(labels, values, color=[ACCENT, "#999"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("verdict accuracy (gold = resolved_order_id != true_order_id)")
    ax.set_title("SEB-1 Exp 3: D52 cross-validation accuracy\n"
                 "(labelled noise_sweep.png for file-list compatibility — no noise-level\n"
                 "sweep exists in this build; see README's Honest limitations)",
                 fontsize=9, loc="left")
    ax.text(0, 1.1,
            f"synthetic benchmark · CP_SEED=20260814 · n={result['n']} · "
            f"WITH-check misses {sum(result['wrong_resolutions_missed_with_check_by_kind'].values())} "
            f"hidden-distractor cases",
            transform=ax.transAxes, fontsize=8, color="#666")
    for bar, val in zip(bars, values):
        ax.annotate(f"{val:.1%}", (bar.get_x() + bar.get_width() / 2, val), ha="center", va="bottom", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return result


def _exp5_result() -> dict:
    """Exp 5 is BLOCKED (docs/experiment-audit.md). run() raises SystemExit
    until bench/gold_set.jsonl exists; record that, never a number."""
    from seb1_exp5_confusion_matrix import run as run_exp5

    try:
        return run_exp5()
    except SystemExit as e:
        return {"status": "BLOCKED", "reason": str(e).splitlines()[0] if str(e) else "no gold_set.jsonl",
                "detail": "held-out gold set (task P03) not yet available; see docs/experiment-audit.md"}


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    lines = _load_decisions()

    coverage = _coverage_report(lines)
    latency = _latency_report(lines)

    exp5 = _exp5_result()
    exp3 = _exp3_chart(REPORTS / "noise_sweep.png")
    _promotion_curve_chart(REPORTS / "promotion_curve.png")

    from mutation import run_mutation_testing

    mutation = run_mutation_testing()

    _write_markdown_table(
        REPORTS / "mutation.md", "Mutation testing — spec-derived operators",
        [(name, rec["spec_source"], rec["expected"],
          "-" if rec["catch_rate"] is None else f"{rec['catch_rate']:.2f}")
         for name, rec in mutation["per_operator"].items()],
        ("operator", "spec source", "expected", "catch rate"),
        note=(f"score = {mutation['mutation_score']:.3f} "
              f"({len(mutation['catchable_operators'])}/{mutation['n_operators']} operators catchable), "
              f"CP_SEED={mutation['seed']}. Operators come from the issue_refund tool JSON schema and "
              f"manifests/servicing.yaml, NOT from decide()'s checks — so a score below 1.0 is expected "
              f"and names what pure decide() does not catch; caller-level controls are labelled separately. See docs/experiment-audit.md."),
    )
    _write_markdown_table(
        REPORTS / "coverage.md", "Claim coverage by tier",
        [(t, n) for t, n in coverage.get("by_tier", {}).items()],
        ("tier", "count"),
        note=(f"n_decisions={coverage['n_decisions']}, claims_total={coverage.get('claims_total', 0)}. "
              f"Per-tier counts only — the C1+C2 'coverage ratio' was retired "
              f"(deterministically 1.0; see docs/retired-figures.md)."
              if coverage.get("n_decisions") else coverage.get("note", "")),
    )
    # reports/latency.md is owned by P09 (bench/latency.py --write): 4 configs x
    # >=1,000 gated calls. This script only keeps a quick trail-derived stat in
    # summary.json["latency"], written below, and does not touch latency.md.
    _write_markdown_table(
        REPORTS / "latency_trail.md", "Per-stage latency (quick stat from decisions.jsonl)",
        [(s, v["n"], f"{v['p50_ms']:.2f}", f"{v['p95_ms']:.2f}", f"{v['p99_ms']:.2f}") if v else (s, 0, "-", "-", "-")
         for s, v in latency.items()],
        ("stage", "n", "p50_ms", "p95_ms", "p99_ms"),
        note="Superseded by the P09 profile in reports/latency.md (4 configs x >=1,000 calls). "
             "This is a rolling stat over whatever is in decisions.jsonl.",
    )

    if exp5.get("status") == "BLOCKED":
        (REPORTS / "confusion.md").write_text(
            "# SEB-1 Exp 5 — confusion matrix\n\n"
            "**BLOCKED.** No honest number is available.\n\n"
            "The previous confusion matrix was circular: cases were generated by "
            "calling `decide()` with parameters chosen to force a verdict, then "
            "scored against `decide()` on the same inputs — accuracy 1.000 by "
            "construction. The generator has been deleted.\n\n"
            "This experiment resumes when task P03 delivers `bench/gold_set.jsonl`, "
            "a held-out set whose labels are assigned independently of `decide()`. "
            "See `docs/experiment-audit.md` and `docs/retired-figures.md`.\n",
            encoding="utf-8",
        )
    else:
        _write_markdown_table(
            REPORTS / "confusion.md", "SEB-1 Exp 5 — gold vs predicted (4x4)",
            [(g, *[exp5["matrix"][g].get(p, 0) for p in ["ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"]])
             for g in ["ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"]],
            ("gold \\ pred", "ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"),
            note=f"n={exp5['total']}, accuracy={exp5['accuracy']:.3f}, CP_SEED=20260814 "
                 f"(held-out gold set, labels independent of decide()).",
        )

    # Only the keys this script owns. P04/P05/P08/P09 each merge their own
    # section (bench/baselines.py, evidence_ablation.py, failure_injection.py,
    # latency.py) — this script must never clobber them.
    owned = {
        "coverage": coverage,
        "latency": latency,
        "receipt_size": measure_receipt_sizes(120),
        "confusion_matrix": exp5,
        "seb1_exp3_cross_validation": exp3,
        "bias": {
            "status": "retired",
            "reason": "the counterfactual-twin probe could not fail — group label never entered decide()",
            "replacement": "tests/test_no_protected_attributes.py (structural) + bench/bias_proxy_probe.py (labelled proxy)",
            "see": "docs/experiment-audit.md, docs/limitations.md",
        },
        "mutation_testing": mutation,
        "seed": 20260814,
        "demo_date": "2026-08-14",
        "audit": "docs/experiment-audit.md — 4 of 5 experiments were circular; see docs/retired-figures.md",
    }
    summary_path = REPORTS / "summary.json"
    summary: dict = {}
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = {}
    summary.update(owned)
    summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print("wrote reports/coverage.md, latency_trail.md, confusion.md, mutation.md, "
          "noise_sweep.png, promotion_curve.png, summary.json (merged; latency.md is P09's)")
    if exp5.get("status") == "BLOCKED":
        print("  note: Exp 5 (confusion matrix) is BLOCKED — see docs/experiment-audit.md")
    print(f"  mutation score: {mutation['mutation_score']:.3f} (spec-derived; < 1.0 expected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
