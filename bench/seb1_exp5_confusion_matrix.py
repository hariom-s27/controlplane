#!/usr/bin/env python3
"""SEB-1, Experiment 5 — a per-verdict confusion matrix.

STATUS: BLOCKED. See docs/experiment-audit.md.

The brief asks for false-positive and false-negative rates explicitly under
"Metrics & monitoring" — a single accuracy number can't answer that, because
a false ALLOW and a false BLOCK have completely different costs. That ask is
still valid. The way this experiment used to answer it was not.

The previous implementation generated every "gold" case by calling decide()
with arguments chosen to force a known verdict, then scored decide() on those
same inputs. Label and prediction were the same function call, so accuracy
was exactly 1.000 for every seed and every n — a restatement of "decide() is
deterministic," not a measurement. The generator has been deleted.

An honest confusion matrix needs a gold set whose labels are assigned
independently of decide() and whose facts are resolved by the real registry +
predicate pipeline, not chosen to hit a target. That artifact is
`bench/gold_set.jsonl`, built in task P03 — it now EXISTS (150 cases, labels
from bench/label.py, an independent re-implementation). What is still missing
is the non-executing pipeline driver `_predict_class()` needs; until that
lands, run() raises SystemExit rather than emit a passing-but-meaningless
number. See docs/gold-set.md.

Expected `bench/gold_set.jsonl` schema (one JSON object per line), so this
file is ready to score the moment P03 lands:

    {
      "id": "gs-001",
      "tool_call": {"name": "issue_refund", "args": {...}},
      "session": {"trace_id": "...", "customer_id": "...", "gate_enabled": true},
      "justification": "<agent prose, verbatim>",
      "retrieved_chunks": ["<chunk text>", ...],
      "gold_intervention": "ALLOW|BLOCK|ESCALATE|MODIFY",
      "gold_verdict": "VERIFIED|CONTRADICTED|UNVERIFIABLE|SOURCE_UNRELIABLE",
      "label_source": "<who/what assigned this, and how>",
      "note": "<why this case is in the set>"
    }

`gold_intervention` / `gold_verdict` MUST NOT be produced by decide(). P03 is
responsible for that guarantee; this file only consumes the result.
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

GOLD_SET = ROOT / "bench" / "gold_set.jsonl"

# SOURCE_UNRELIABLE is a verdict, not an Intervention; it is surfaced as its
# own confusion-matrix class because a reviewer cares whether an escalation
# means "the evidence itself is shaky" versus any other reason to escalate.
CLASSES = ["ALLOW", "BLOCK", "ESCALATE", "SOURCE_UNRELIABLE"]

_BLOCKED_MESSAGE = (
    "\n".join(
        [
            "SEB-1 Exp 5 is BLOCKED — no honest number is available.",
            "",
            f"  bench/gold_set.jsonl not found at: {GOLD_SET}",
            "",
            "  The previous confusion matrix was circular: cases were generated",
            "  by calling decide() with parameters chosen to force a verdict, then",
            "  scored against decide() on the same inputs. Accuracy was 1.000 by",
            "  construction. The generator has been deleted.",
            "",
            "  This experiment resumes when task P03 delivers a held-out gold set",
            "  whose labels are assigned independently of decide(). See",
            "  docs/experiment-audit.md and docs/retired-figures.md.",
        ]
    )
)


def _load_gold_set(path: Path = GOLD_SET) -> list[dict]:
    if not path.exists():
        raise SystemExit(_BLOCKED_MESSAGE)
    records = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        for required in ("id", "tool_call", "gold_intervention", "gold_verdict", "label_source"):
            if required not in rec:
                raise SystemExit(f"gold_set.jsonl line {i}: missing required key {required!r}")
        records.append(rec)
    if not records:
        raise SystemExit(_BLOCKED_MESSAGE)
    return records


def _gold_class(rec: dict) -> str:
    if rec["gold_verdict"] == "SOURCE_UNRELIABLE":
        return "SOURCE_UNRELIABLE"
    return rec["gold_intervention"]


def _predict_class(rec: dict) -> str:
    """Run the REAL gate on the gold case and read its verdict/intervention.

    P03 must land the plumbing this needs: a way to drive
    controlplane/intercept.py's pipeline for a recorded tool call without
    executing the tool. Deliberately not stubbed with a decide() shortcut —
    that shortcut is exactly what made the old version circular.
    """
    raise NotImplementedError(
        "Exp 5 scoring path is not wired until P03 provides the held-out gold "
        "set and the non-executing pipeline driver. See docs/experiment-audit.md."
    )


def _confusion(records: list[dict]) -> dict:
    matrix = {g: {p: 0 for p in CLASSES} for g in CLASSES}
    for rec in records:
        gold = _gold_class(rec)
        predicted = _predict_class(rec)
        if gold not in CLASSES:
            raise SystemExit(f"gold_set.jsonl {rec['id']}: gold class {gold!r} not in {CLASSES}")
        if predicted not in CLASSES:
            matrix[gold].setdefault("OTHER", 0)
            matrix[gold]["OTHER"] += 1
        else:
            matrix[gold][predicted] += 1

    per_class = {}
    for cls in CLASSES:
        tp = matrix[cls][cls]
        fn = sum(v for p, v in matrix[cls].items() if p != cls)
        fp = sum(matrix[g][cls] for g in CLASSES if g != cls)
        per_class[cls] = {
            "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
            "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    total = len(records)
    correct = sum(matrix[g][g] for g in CLASSES)
    return {"total": total, "accuracy": correct / total if total else float("nan"),
            "matrix": matrix, "per_class": per_class}


_DRIVER_MISSING_MESSAGE = "\n".join(
    [
        "SEB-1 Exp 5 is BLOCKED — no honest number is available yet.",
        "",
        "  Task P03 has landed the held-out gold set (bench/gold_set.jsonl,",
        f"  {GOLD_SET.name}) with labels assigned independently of decide() by",
        "  bench/label.py. That was the first of two things this experiment",
        "  needs.",
        "",
        "  Still missing: the non-executing pipeline driver — a way to run",
        "  controlplane/intercept.py's gate for each recorded tool call WITHOUT",
        "  executing the refund, so _predict_class() can read a real verdict.",
        "  It is deliberately not stubbed with a decide() shortcut; that",
        "  shortcut is what made the previous confusion matrix circular.",
        "",
        "  This experiment resumes when that driver exists. See",
        "  docs/experiment-audit.md and docs/gold-set.md.",
    ]
)


def run() -> dict:
    """Blocked. Until P03 (done: gold set) *and* the non-executing pipeline
    driver (pending) both exist, this raises SystemExit rather than emit a
    meaningless number."""
    records = _load_gold_set()
    # The gold set is here; the scoring driver is not. Fail loudly and
    # specifically rather than let _predict_class()'s NotImplementedError
    # surface as an opaque crash.
    raise SystemExit(_DRIVER_MISSING_MESSAGE)
    return _confusion(records)  # noqa: unreachable — kept for when the driver lands


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
