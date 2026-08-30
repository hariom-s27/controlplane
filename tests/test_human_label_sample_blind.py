"""P03 / task M4 — the human label sheet is genuinely blind.

``bench/human_label_sample.csv`` goes in front of a person who re-does
``bench/label.py``'s job from the policy and the facts. If the sheet leaks the
construction ``slice`` (whose name states the intended class for five of seven
slices), the gold label, ``label.py``'s rationale, or anything from the
construction holdout, the resulting Cohen's kappa is not measuring independent
human judgement.

These tests pin: exactly 30 cases, all 10 ambiguous + the same 20 others, the
``case_id`` set *and order* unchanged, no answer-bearing column, blank label
columns, byte-determinism, and that ``bench/agreement.py`` joins on ``case_id``
(not row position), never reads the holdout, and withholds kappa until the
sheet is fully labelled.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
HUMAN_CSV = BENCH / "human_label_sample.csv"
GOLD_SET = BENCH / "gold_set.jsonl"
HOLDOUT = BENCH / "ground_truth_holdout.jsonl"
sys.path.insert(0, str(BENCH))

# The frozen P03 selection: all 10 ambiguous cases + the same 20 others, in
# case_id order. Task M4 removed the `slice` column; it did not touch which
# cases are in the sheet.
EXPECTED_CASE_IDS = [
    "gs-005", "gs-009", "gs-011", "gs-016", "gs-027", "gs-031", "gs-035",
    "gs-040", "gs-045", "gs-052", "gs-056", "gs-059", "gs-067", "gs-088",
    "gs-093", "gs-111", "gs-129", "gs-130", "gs-133", "gs-134", "gs-141",
    "gs-142", "gs-143", "gs-144", "gs-145", "gs-146", "gs-147", "gs-148",
    "gs-149", "gs-150",
]
EXPECTED_AMBIGUOUS = [f"gs-{n}" for n in range(141, 151)]
EXPECTED_OTHER_20 = [c for c in EXPECTED_CASE_IDS if c not in EXPECTED_AMBIGUOUS]

PINNED_CSV_SHA256 = "48f069133e63ef87fb7f6027e1b259ab5ae534016f41ca1640a375d74130d3c9"

# Columns that would hand the annotator the answer or the construction intent.
FORBIDDEN_COLUMNS = {
    "slice", "intended_slice", "intended_label",
    "gold_label", "gold_verdict", "gold_intervention", "gold_reason",
    "label_rationale", "label_source", "rationale", "note",
    "true_order_id", "distractor_order_id", "distractor_present",
    "corruption", "corruption_kind", "true_policy_version",
    "ambiguity_kind", "variation_index", "source_order_id", "source_row",
    "system_prediction", "decide_verdict", "prediction",
}

# Construction / answer vocabulary that must not appear anywhere in a data cell
# (legitimate policy prose containing "supervisor" / "refund" is fine — these
# are the machine tokens the builder uses for slices and recipes).
FORBIDDEN_CELL_TOKENS = (
    "allow_in_window", "outside_window", "over_authority", "stale_policy_context",
    "distractor_present", "corrupted_or_missing_record", "ambiguous_under_policy",
    "intended_slice", "intended_label", "true_order_id", "distractor_order_id",
    "order_id_transcription", "currency_field", "gold_label", "gold_verdict",
    "label_rationale", "label_source", "holdout",
)


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    text = HUMAN_CSV.read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


@pytest.fixture(scope="module")
def header() -> list[str]:
    with HUMAN_CSV.open(encoding="utf-8") as fh:
        return next(csv.reader(fh))


# --------------------------------------------------------------------------
# composition — 30 cases, exactly the frozen selection
# --------------------------------------------------------------------------


def test_exactly_30_rows(rows):
    assert len(rows) == 30


def test_case_id_set_is_unchanged(rows):
    assert {r["case_id"] for r in rows} == set(EXPECTED_CASE_IDS)


def test_case_id_order_is_unchanged(rows):
    assert [r["case_id"] for r in rows] == EXPECTED_CASE_IDS


def test_all_ten_ambiguous_cases_present(rows):
    present = {r["case_id"] for r in rows}
    assert set(EXPECTED_AMBIGUOUS).issubset(present)
    # and the gold set confirms these are the entire ambiguous slice
    gold = {json.loads(l)["id"]: json.loads(l) for l in
            GOLD_SET.read_text(encoding="utf-8").splitlines() if l.strip()}
    all_ambiguous = sorted(cid for cid, c in gold.items()
                           if c["slice"] == "ambiguous_under_policy")
    assert all_ambiguous == EXPECTED_AMBIGUOUS
    assert present.issuperset(all_ambiguous)


def test_same_20_other_cases_present(rows):
    others = [r["case_id"] for r in rows if r["case_id"] not in EXPECTED_AMBIGUOUS]
    assert others == EXPECTED_OTHER_20
    assert len(others) == 20


# --------------------------------------------------------------------------
# blindness — no leaking column, no leaking cell
# --------------------------------------------------------------------------


def test_no_slice_column(header):
    assert "slice" not in header


def test_no_gold_or_construction_columns(header):
    leaked = FORBIDDEN_COLUMNS.intersection(header)
    assert not leaked, f"human sheet exposes answer-bearing columns: {sorted(leaked)}"


def test_header_is_exactly_the_blind_schema(header):
    assert header == [
        "case_id", "session_customer_id", "call_order_id",
        "refund_amount_paise", "order_total_paise", "order_customer_id",
        "order_delivered_at", "frozen_today", "agent_cited_policy_version",
        "current_refund_policy_text", "authority_policy_text",
        "agent_justification", "human_label", "human_notes",
    ]


def test_no_construction_tokens_in_any_cell(rows):
    for r in rows:
        for col, val in r.items():
            low = (val or "").lower()
            for tok in FORBIDDEN_CELL_TOKENS:
                assert tok not in low, f"{r['case_id']}/{col} contains {tok!r}"


def test_every_cell_traces_to_a_public_source_not_the_holdout(rows):
    """Positive blindness check that never opens ground_truth_holdout.jsonl:
    every fact-bearing cell must reconcile with the PUBLIC gold_set.jsonl case
    or a real data/orders.db row. A value matching neither would be
    construction truth the sheet has no business showing."""
    gold = {json.loads(l)["id"]: json.loads(l) for l in
            GOLD_SET.read_text(encoding="utf-8").splitlines() if l.strip()}
    conn = sqlite3.connect(
        f"file:{(ROOT / 'data' / 'orders.db').as_posix()}?mode=ro", uri=True
    )
    conn.row_factory = sqlite3.Row
    orders = [dict(row) for row in conn.execute("SELECT * FROM orders")]
    conn.close()

    for r in rows:
        c = gold[r["case_id"]]
        args = c["tool_call"]["args"]
        # proposed-action columns come straight off the public tool call
        assert r["call_order_id"] == args["order_id"]
        assert int(r["refund_amount_paise"]) == args["amount_paise"]
        assert r["session_customer_id"] == c["session"]["customer_id"]
        assert r["agent_justification"] == c["justification"]
        assert (r["agent_cited_policy_version"] or None) == c.get("claimed_policy_version")
        # order-record columns must be a real, public orders.db row (for a
        # corrupted-id case the call id resolves to nothing, but the shown
        # facts still belong to a real underlying order)
        assert any(
            str(o["amount_paise"]) == r["order_total_paise"]
            and o["customer_id"] == r["order_customer_id"]
            and o["delivered_at"] == r["order_delivered_at"]
            for o in orders
        ), f"{r['case_id']}: order facts match no public orders.db row"


# --------------------------------------------------------------------------
# label columns start blank and are never auto-filled
# --------------------------------------------------------------------------


def test_human_label_blank_for_every_row(rows):
    assert all((r.get("human_label") or "") == "" for r in rows)


def test_human_notes_blank_for_every_row(rows):
    assert all((r.get("human_notes") or "") == "" for r in rows)


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------


def test_sheet_is_byte_deterministic():
    assert hashlib.sha256(HUMAN_CSV.read_bytes()).hexdigest() == PINNED_CSV_SHA256


def test_gold_set_and_holdout_are_untouched():
    """Integrity only — bytes -> SHA, no parse. M4 must not perturb either
    frozen P03 artifact; the human sheet is derived from the public case list."""
    assert hashlib.sha256(GOLD_SET.read_bytes()).hexdigest() == \
        "09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e"
    assert hashlib.sha256(HOLDOUT.read_bytes()).hexdigest() == \
        "204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb"


# --------------------------------------------------------------------------
# agreement.py — join key, holdout isolation, kappa gating
# --------------------------------------------------------------------------


def test_agreement_joins_on_case_id_not_row_position():
    import agreement

    # gold ids in a different order than the sheet — a row-position join would
    # mis-align; a case_id join would not. We only need the mapping shape here.
    by_id = agreement._label_py_by_id()
    assert set(EXPECTED_CASE_IDS).issubset(by_id)
    roster = agreement._sheet_case_ids()
    assert roster == EXPECTED_CASE_IDS  # sheet order, from the file, not sorted


def test_agreement_source_does_not_read_the_holdout():
    src = (BENCH / "agreement.py").read_text(encoding="utf-8")
    import ast
    tree = ast.parse(src)
    # blank docstrings (they legitimately explain what is NOT read)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body[0].value.value = ""
    code = ast.unparse(tree).lower()
    assert "ground_truth_holdout" not in code
    assert "holdout" not in code
    for banned in ("decide", "predicate", "intercept"):
        assert banned not in code, f"agreement.py references {banned!r}"


def test_agreement_withholds_kappa_until_all_30_labels(monkeypatch):
    import agreement

    # no labels yet (the shipped state): not complete, no kappa
    result = agreement.run()
    assert result["complete"] is False
    assert result["human_validation_available"] is False
    assert result["cohens_kappa"] is None
    assert result["n_expected"] == 30
    assert result["n_missing"] == 30

    # a partially filled sheet still withholds kappa
    partial = {cid: "ALLOW" for cid in EXPECTED_CASE_IDS[:29]}
    monkeypatch.setattr(agreement, "_human_labels", lambda: dict(partial))
    result = agreement.run()
    assert result["complete"] is False
    assert result["cohens_kappa"] is None
    assert result["missing_case_ids"] == ["gs-150"]

    # only a fully labelled sheet yields a kappa
    full = {cid: "AMBIGUOUS" for cid in EXPECTED_CASE_IDS}
    monkeypatch.setattr(agreement, "_human_labels", lambda: dict(full))
    result = agreement.run()
    assert result["complete"] is True
    assert result["cohens_kappa"] is not None
    assert result["n_compared"] == 30


def test_agreement_main_is_safe_with_zero_labels(capsys):
    import agreement

    rc = agreement.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "NOT yet available" in out
    assert '"cohens_kappa"' not in out       # the JSON result block is not printed
    assert "Cohen's kappa (human vs" not in out  # nor the computed-kappa line
