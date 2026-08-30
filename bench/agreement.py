#!/usr/bin/env python3
"""Task P03 — human vs. bench/label.py agreement.

    python bench/agreement.py

Reads the human labels a person filled into ``bench/human_label_sample.csv``
and compares them, case by case, with the independent labeller
(``bench/label.py``, whose verdict is the ``gold_label`` in the *public*
``bench/gold_set.jsonl``). Reports Cohen's kappa and a per-case disagreement
list.

The human is doing the *same job* as bench/label.py — reading the policy text
and the order facts and deciding — so their agreement is a check on the
labeller, not on the gate. Low kappa means our policy interpretation is
contestable, and that belongs in docs/gold-set.md's limitations, not hidden.

Join key is the opaque ``case_id`` (never CSV row position):
``case_id`` -> ``bench/gold_set.jsonl`` -> ``gold_label``. The construction
holdout (``bench/ground_truth_holdout.jsonl``) is never opened, and no system
prediction is generated — this script never touches ``controlplane.decide``,
the predicates or ``intercept``.

Cohen's kappa is reported **only once every case in the sheet has a human
label**. Until then this prints how many labels are still outstanding and
exits 0 (no kappa, no partial number), so it is safe to wire into CI now.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUMAN_CSV = ROOT / "bench" / "human_label_sample.csv"
GOLD_SET = ROOT / "bench" / "gold_set.jsonl"

VALID = {"ALLOW", "BLOCK", "ESCALATE", "AMBIGUOUS"}


def _label_py_by_id() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in GOLD_SET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        # gold_label in gold_set.jsonl IS bench/label.py's verdict (see
        # gold_set_build.py) — not decide()'s.
        out[rec["id"]] = rec["gold_label"]
    return out


def _sheet_case_ids() -> list[str]:
    """Every case_id in the human sheet, in row order — the roster we expect a
    human to label in full before any kappa is reported. This is the join
    universe; row position is never used to align labels to gold."""
    if not HUMAN_CSV.exists():
        return []
    return [
        row["case_id"]
        for row in csv.DictReader(HUMAN_CSV.read_text(encoding="utf-8").splitlines())
        if (row.get("case_id") or "").strip()
    ]


def _human_labels() -> dict[str, str]:
    if not HUMAN_CSV.exists():
        return {}
    out: dict[str, str] = {}
    for row in csv.DictReader(HUMAN_CSV.read_text(encoding="utf-8").splitlines()):
        raw = (row.get("human_label") or "").strip().upper()
        if not raw:
            continue
        if raw not in VALID:
            raise SystemExit(
                f"{HUMAN_CSV.name}: case {row.get('case_id')!r} has human_label "
                f"{raw!r}; expected one of {sorted(VALID)}"
            )
        out[row["case_id"]] = raw
    return out


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Unweighted Cohen's kappa for two raters over a shared label set.
    Stdlib only — CLAUDE.md rule 5 (no dependency where arithmetic will do)."""
    n = len(pairs)
    if n == 0:
        return None
    labels = sorted({x for pair in pairs for x in pair})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for lab in labels:
        pa = sum(1 for a, _ in pairs if a == lab) / n
        pb = sum(1 for _, b in pairs if b == lab) / n
        pe += pa * pb
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def run() -> dict:
    label_py = _label_py_by_id()
    roster = _sheet_case_ids()
    human = _human_labels()

    missing = [cid for cid in roster if cid not in human]
    # kappa is defined only over a fully-labelled sheet — a partial fill would
    # let the reader (or CI) quote an early, unrepresentative number.
    complete = bool(roster) and not missing

    result: dict = {
        "n_expected": len(roster),
        "n_human_labels": len(human),
        "n_missing": len(missing),
        "missing_case_ids": missing,
        "complete": complete,
        "human_validation_available": complete,
    }
    if not complete:
        result.update({"cohens_kappa": None, "n_compared": 0, "n_agree": 0,
                       "percent_agreement": None, "disagreements": []})
        return result

    compared = sorted(cid for cid in human if cid in label_py)
    pairs = [(human[cid], label_py[cid]) for cid in compared]
    disagreements = [
        {"case_id": cid, "human": human[cid], "label_py": label_py[cid]}
        for cid in compared
        if human[cid] != label_py[cid]
    ]
    result.update({
        "n_compared": len(compared),
        "n_agree": len(compared) - len(disagreements),
        "cohens_kappa": cohens_kappa(pairs),
        "percent_agreement": (len(compared) - len(disagreements)) / len(compared)
        if compared
        else None,
        "disagreements": disagreements,
    })
    return result


def main() -> int:
    result = run()
    if not result["complete"]:
        if result["n_expected"] == 0:
            print(
                "bench/human_label_sample.csv not found or has no rows — nothing "
                "to compare."
            )
            return 0
        print(
            f"{result['n_human_labels']}/{result['n_expected']} human labels in "
            "bench/human_label_sample.csv — human agreement is NOT yet available.\n"
            f"{result['n_missing']} case(s) still unlabelled: "
            f"{', '.join(result['missing_case_ids'])}\n"
            "Fill every `human_label` cell (ALLOW / BLOCK / ESCALATE / AMBIGUOUS) "
            "before Cohen's kappa is computed."
        )
        return 0
    print(json.dumps(result, indent=2))
    k = result["cohens_kappa"]
    print()
    print(f"  Cohen's kappa (human vs bench/label.py): {k:.3f}" if k is not None else "  kappa: n/a")
    print(f"  agreement: {result['n_agree']}/{result['n_compared']}")
    if result["disagreements"]:
        print("  disagreements:")
        for d in result["disagreements"]:
            print(f"    {d['case_id']}: human={d['human']}  label.py={d['label_py']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
