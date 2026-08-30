"""P03 / task M4 — the human label sheet is genuinely blind, and the repaired
second-pass instrument.

``bench/human_label_sample.csv`` goes in front of a person who re-does
``bench/label.py``'s job from the policy and the facts. If the sheet leaks the
construction ``slice`` (whose name states the intended class for five of seven
slices), the gold label, ``label.py``'s rationale, or anything from the
construction holdout, the resulting Cohen's kappa is not measuring independent
human judgement.

Lifecycle:
  * PASS 1 — complete, archived, superseded. 30/30 labels, kappa
    0.5454545454545454, 10 disagreements, all human-BLOCK vs label.py
    ESCALATE/AMBIGUOUS. Preserved IMMUTABLY at
    ``bench/human_label_sample_pass1.csv``.
  * Instrument repair (task M4) — added ``record_lookup_status`` (FOUND /
    NO_MATCH); NO_MATCH rows no longer show any order-record column (the
    pass-1 audit found that a complete-looking order block was shown even when
    the tool-call order id resolved to nothing). Rubric:
    ``docs/gold-set-annotation.md``.
  * PASS 2 — complete. FINAL M4 result: 30/30 labels, kappa
    0.7321428571428572, 24/30 (80.0%) exact agreement, 6 disagreements
    (``gs-145``..``gs-150``, all human-BLOCK vs label.py AMBIGUOUS — the
    documented supervisor-discretion band; see docs/gold-set.md §6). Pass-1
    labels were not copied forward; the four corrupted-record disagreements
    from pass 1 are gone (both sides now ESCALATE).

These tests pin: exactly 30 cases, all 10 ambiguous + the same 20 others, the
``case_id`` set *and order* unchanged, no answer-bearing column, NO_MATCH
presentation, pass-1 preserved and not copied into pass-2, and that
``bench/agreement.py`` joins on ``case_id`` (not row position), never reads the
holdout, withholds kappa until fully labelled, and is UTF-8-BOM tolerant.
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
PASS1_CSV = BENCH / "human_label_sample_pass1.csv"
GOLD_SET = BENCH / "gold_set.jsonl"
HOLDOUT = BENCH / "ground_truth_holdout.jsonl"
DATA = ROOT / "data"
sys.path.insert(0, str(BENCH))

# tool-call order ids in the 30-case sample that do NOT resolve to any
# orders.db row (the corrupted_or_missing_record slice, transcription kind).
NO_MATCH_CASE_IDS = ["gs-129", "gs-130", "gs-133", "gs-134"]

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

VALID_LABELS = {"ALLOW", "BLOCK", "ESCALATE", "AMBIGUOUS"}

# The repaired blank reviewer template (pass-2 instrument, pre-labeling).
# Deterministic generator output; also pinned in tests/test_gold_set_determinism.py.
PINNED_BLANK_CSV_SHA256 = "7a41fc7b0c462ee4f66216551aa9fdb4da11484c45add7bdbc7f1139d7f52da6"
# The completed pass-2 sheet: 30/30 human labels under the repaired
# instrument, entered manually. This is the FINAL M4 human-validation sheet.
PINNED_PASS2_CSV_SHA256 = "ccf356a53088c4ae68562364cade01f0b02b2da6ab7daf1f206b943027c22d91"
# The immutable pass-1 artifact: 30/30 human labels, entered manually, saved
# with a UTF-8 BOM. Historical evidence only — never an active sheet.
PINNED_PASS1_CSV_SHA256 = "919627b0e3ec1b6fc5d5e71f46561ed767a7aea4fd2961717cf5684e5c0ab729"

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
    # utf-8-sig: the annotator's editor re-saved the sheet with a UTF-8 BOM.
    text = HUMAN_CSV.read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


@pytest.fixture(scope="module")
def header() -> list[str]:
    with HUMAN_CSV.open(encoding="utf-8-sig") as fh:
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
        "case_id", "session_customer_id", "call_order_id", "record_lookup_status",
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
    order_ids = {o["order_id"] for o in orders}
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
        if r["record_lookup_status"] == "NO_MATCH":
            # the tool-call order id genuinely does not resolve, and the sheet
            # must not fill in the hidden real record behind it
            assert r["call_order_id"] not in order_ids
            assert r["order_total_paise"] == r["order_customer_id"] == r["order_delivered_at"] == ""
            continue
        assert r["record_lookup_status"] == "FOUND"
        # order-record columns must be a real, public orders.db row
        assert any(
            str(o["amount_paise"]) == r["order_total_paise"]
            and o["customer_id"] == r["order_customer_id"]
            and o["delivered_at"] == r["order_delivered_at"]
            for o in orders
        ), f"{r['case_id']}: order facts match no public orders.db row"


# --------------------------------------------------------------------------
# label columns — filled only by the human, only with the label vocabulary
# --------------------------------------------------------------------------


def test_human_label_is_blank_or_a_valid_vocabulary_term(rows):
    """The agent never machine-populates this column. A human may fill it, and
    only with the 4-class vocabulary — anything else means a leaked gold value
    or a typo."""
    for r in rows:
        v = (r.get("human_label") or "").strip().upper()
        assert v == "" or v in VALID_LABELS, f"{r['case_id']}: human_label {v!r}"


def test_label_column_is_all_or_nothing(rows):
    """Either an untouched sheet (all blank) or a completed one (all 30 filled)
    — a half-filled sheet is not a valid state to report from."""
    filled = [r for r in rows if (r.get("human_label") or "").strip()]
    assert len(filled) in (0, 30), f"{len(filled)}/30 labels filled"


def test_human_notes_do_not_leak_construction_metadata(rows):
    """Notes are the annotator's free text; they must still not contain the
    builder's machine tokens (a paste of gold/holdout data)."""
    for r in rows:
        low = (r.get("human_notes") or "").lower()
        for tok in FORBIDDEN_CELL_TOKENS:
            assert tok not in low, f"{r['case_id']}/human_notes contains {tok!r}"


# --------------------------------------------------------------------------
# determinism / byte-stability
# --------------------------------------------------------------------------


def test_sheet_is_byte_stable():
    """The sheet on disk matches its pinned hash. Pass 2 (the final,
    repaired-instrument human validation) is now complete and pinned; the
    blank-template hash remains valid only for a freshly regenerated sheet."""
    actual = hashlib.sha256(HUMAN_CSV.read_bytes()).hexdigest()
    assert actual in (PINNED_PASS2_CSV_SHA256, PINNED_BLANK_CSV_SHA256), actual


def test_pass1_artifact_is_immutable_and_pinned():
    """The historical pass-1 sheet (30/30 labels, kappa 0.5454545454545454)
    must never be touched by the M4 instrument repair."""
    actual = hashlib.sha256(PASS1_CSV.read_bytes()).hexdigest()
    assert actual == PINNED_PASS1_CSV_SHA256, actual


def test_pass1_has_the_same_case_ids_in_the_same_order():
    text = PASS1_CSV.read_text(encoding="utf-8-sig")
    pass1_rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["case_id"] for r in pass1_rows] == EXPECTED_CASE_IDS


def test_pass2_is_independent_of_pass1_not_a_copy(rows):
    """Pass 2 was NOT produced by silently carrying pass-1's labels forward.
    Direct evidence: the instrument repair changed what a reviewer sees for
    the four corrupted/unresolvable-record cases (NO_MATCH -> no fabricated
    order block), and the pass-2 label for all four moved from pass-1's BLOCK
    to ESCALATE — a copy of pass-1 would still read BLOCK here."""
    text = PASS1_CSV.read_text(encoding="utf-8-sig")
    pass1_by_id = {r["case_id"]: r for r in csv.DictReader(io.StringIO(text))}
    pass2_by_id = {r["case_id"]: r for r in rows}
    for cid in NO_MATCH_CASE_IDS:
        assert pass1_by_id[cid]["human_label"].strip() == "BLOCK"
        assert pass2_by_id[cid]["human_label"].strip() == "ESCALATE"
    # pass-2 notes are overwhelmingly the annotator's own fresh wording, not a
    # bulk verbatim copy of pass-1's notes column (a short coincidental match
    # on an unambiguous case is expected and not itself evidence of copying;
    # a copy-paste of the whole sheet would show near-100% identity, not one)
    identical_notes = sum(
        1 for cid in EXPECTED_CASE_IDS
        if pass1_by_id[cid]["human_notes"].strip()
        and pass1_by_id[cid]["human_notes"].strip() == pass2_by_id[cid]["human_notes"].strip()
    )
    assert identical_notes <= 2, (
        f"{identical_notes}/30 notes are byte-identical to pass-1 — looks like "
        "a bulk copy rather than independent re-annotation"
    )


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


_HEADER = (
    "case_id,session_customer_id,call_order_id,refund_amount_paise,"
    "order_total_paise,order_customer_id,order_delivered_at,frozen_today,"
    "agent_cited_policy_version,current_refund_policy_text,authority_policy_text,"
    "agent_justification,human_label,human_notes"
)


def _write_sheet(path: Path, labels: dict[str, str], *, bom: bool = False) -> None:
    """A minimal sheet with the real 30 case_ids and the given human_label
    values (missing ids -> blank). Only case_id and human_label matter to
    agreement.py; the other columns are padded."""
    lines = [_HEADER]
    for cid in EXPECTED_CASE_IDS:
        lab = labels.get(cid, "")
        lines.append(f"{cid},C,O,1,1,C,2026-08-01,2026-08-14,v4.2,p,a,j,{lab},")
    data = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(b"\xef\xbb\xbf" + data if bom else data)


def test_agreement_withholds_kappa_until_all_30_labels(monkeypatch, tmp_path):
    import agreement

    sheet = tmp_path / "sheet.csv"
    monkeypatch.setattr(agreement, "HUMAN_CSV", sheet)

    # nothing filled: not complete, no kappa
    _write_sheet(sheet, {})
    result = agreement.run()
    assert result["complete"] is False
    assert result["human_validation_available"] is False
    assert result["cohens_kappa"] is None
    assert result["n_expected"] == 30
    assert result["n_missing"] == 30

    # 29/30 filled: still withholds kappa, names the gap
    _write_sheet(sheet, {cid: "ALLOW" for cid in EXPECTED_CASE_IDS[:29]})
    result = agreement.run()
    assert result["complete"] is False
    assert result["cohens_kappa"] is None
    assert result["missing_case_ids"] == ["gs-150"]

    # 30/30 filled: kappa is computed over all 30
    _write_sheet(sheet, {cid: "AMBIGUOUS" for cid in EXPECTED_CASE_IDS})
    result = agreement.run()
    assert result["complete"] is True
    assert result["cohens_kappa"] is not None
    assert result["n_compared"] == 30


def test_agreement_main_is_safe_with_zero_labels(monkeypatch, tmp_path, capsys):
    import agreement

    sheet = tmp_path / "sheet.csv"
    _write_sheet(sheet, {})
    monkeypatch.setattr(agreement, "HUMAN_CSV", sheet)

    rc = agreement.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "NOT yet available" in out
    assert '"cohens_kappa"' not in out       # the JSON result block is not printed
    assert "Cohen's kappa (human vs" not in out  # nor the computed-kappa line


def test_agreement_tolerates_a_utf8_bom_in_the_sheet_header(monkeypatch, tmp_path):
    """Regression (M4 BOM fix): a sheet re-saved with a UTF-8 BOM must still be
    read with 'case_id' as the first key, not '\\ufeffcase_id'."""
    # raw csv on a BOM-prefixed file, read as plain utf-8: the bug reproduces
    bom_sheet = tmp_path / "bom.csv"
    _write_sheet(bom_sheet, {cid: "BLOCK" for cid in EXPECTED_CASE_IDS}, bom=True)
    naive = next(csv.reader(io.StringIO(bom_sheet.read_text(encoding="utf-8"))))
    assert naive[0] == "﻿case_id"          # the failure mode
    fixed = next(csv.reader(io.StringIO(bom_sheet.read_text(encoding="utf-8-sig"))))
    assert fixed[0] == "case_id"                 # the fix

    # and agreement.py, pointed at the BOM sheet, joins cleanly by case_id
    import agreement
    monkeypatch.setattr(agreement, "HUMAN_CSV", bom_sheet)
    assert agreement._sheet_case_ids() == EXPECTED_CASE_IDS
    labels = agreement._human_labels()
    assert set(labels) == set(EXPECTED_CASE_IDS)
    assert "﻿case_id" not in labels and "﻿gs-005" not in labels
    result = agreement.run()
    assert result["complete"] is True
    assert result["n_compared"] == 30
    assert result["cohens_kappa"] is not None


def test_agreement_processes_the_completed_real_sheet():
    """Acceptance: with the real 30/30 human-labelled sheet on disk (BOM and
    all), agreement.py joins every case by case_id and produces the kappa."""
    import agreement

    result = agreement.run()
    if result["n_human_labels"] == 0:
        pytest.skip("real sheet is unlabelled in this checkout")
    assert result["complete"] is True
    assert result["n_expected"] == 30
    assert result["n_human_labels"] == 30
    assert result["n_compared"] == 30
    assert result["cohens_kappa"] is not None
    # every disagreement is keyed by a real case_id, never a BOM-mangled one
    for d in result["disagreements"]:
        assert d["case_id"] in EXPECTED_CASE_IDS
        assert d["human"] in VALID_LABELS and d["label_py"] in VALID_LABELS
