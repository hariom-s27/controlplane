"""P3-C — the extraction-completeness benchmark.

`bench/extraction_completeness_bench.py` runs the ACTUAL ControlPlane
extraction layer (`controlplane.extract.build_claims` + the ladder) over the
30 frozen P3-B actions and measures recovery of the independently-required
claim set. The gold corpus is read-only; this suite pins its hash, checks the
benchmark is deterministic, and exercises the normalization / alignment /
taxonomy / metric machinery on hand-built inputs so each error type is
demonstrably detected.

Does not weaken or alter any existing test. The known pre-existing failure
(tests/test_tau2_c2_controlplane_side.py, stale P06 hash) is unrelated.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from bench import extraction_completeness_bench as X  # noqa: E402
from controlplane.schema import Claim, ClaimKind  # noqa: E402

PINNED_GOLD_SHA256 = "79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d"


# --------------------------------------------------------------------------
# gold corpus is untouched
# --------------------------------------------------------------------------
def test_frozen_gold_hash_is_unchanged():
    actual = hashlib.sha256((BENCH / "extraction_gold_v1.jsonl").read_bytes()).hexdigest()
    assert actual == PINNED_GOLD_SHA256
    assert X.PINNED_GOLD_SHA256 == PINNED_GOLD_SHA256
    assert X.gold_sha256() == PINNED_GOLD_SHA256


def test_benchmark_pins_and_verifies_the_gold_sha_in_build_report(monkeypatch):
    # build_report() aborts if the corpus moved — assert the guard exists
    src = (BENCH / "extraction_completeness_bench.py").read_text(encoding="utf-8")
    assert 'sha != PINNED_GOLD_SHA256' in src
    assert "STOP" in src


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------
def test_report_is_deterministic_across_two_builds():
    a = X.render_json(_report())
    b = X.render_json(_report())
    assert a == b


def test_committed_report_has_no_drift():
    r = subprocess.run(
        [sys.executable, str(BENCH / "extraction_completeness_bench.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, f"drift:\n{r.stdout}\n{r.stderr}"


_CACHED = {}


def _report():
    if "r" not in _CACHED:
        _CACHED["r"] = X.build_report()
    return _CACHED["r"]


# --------------------------------------------------------------------------
# normalization
# --------------------------------------------------------------------------
def test_normalize_claim_kind_accepts_enum_value_and_name():
    assert X.normalize_claim_kind(ClaimKind.WITHIN_REFUND_WINDOW) == "WITHIN_REFUND_WINDOW"
    assert X.normalize_claim_kind("within_refund_window") == "WITHIN_REFUND_WINDOW"
    assert X.normalize_claim_kind("WITHIN_REFUND_WINDOW") == "WITHIN_REFUND_WINDOW"


def test_normalize_claim_kind_rejects_unknown():
    with pytest.raises(ValueError):
        X.normalize_claim_kind("NOT_A_KIND")


def test_normalize_subject_strips_clause_prefix_and_is_symmetric():
    assert X.normalize_subject("clause:refund_window") == X.normalize_subject("refund_window")
    assert X.normalize_subject("clause:refund_window") == "refund_window"


def test_normalize_subject_is_idempotent_and_whitespace_stable():
    once = X.normalize_subject("  ORD-10227 ")
    assert once == X.normalize_subject(once) == "ord-10227"
    assert X.normalize_subject("clause:  refund_window") == "refund_window"


def test_claim_key_pairs_kind_and_subject():
    assert X.claim_key("policy_clause_current", "clause:refund_window") == (
        "POLICY_CLAUSE_CURRENT", "refund_window",
    )


# --------------------------------------------------------------------------
# alignment + error taxonomy — hand-built cases
# --------------------------------------------------------------------------
def _c(kind, subject):
    return Claim(id=f"{subject}:{kind.value}", kind=kind, subject=subject)


def _gold_claim(kind, subject, **kw):
    base = dict(
        claim_id=f"gs-000::{kind.lower()}", claim_kind=kind, subject=subject,
        required=True, load_bearing=True, expected_assertion="HOLDS",
        asserted_by_agent=True, rationale="x", source_basis=["csv:x"],
        decomposition_note="one claim", subject_note=None,
    )
    base.update(kw)
    return base


def _gold_rec(claims, foundational=None):
    return {
        "case_id": "gs-000", "gold_claims": claims,
        "foundational_requirements": foundational or [],
    }


def test_alignment_correct_claim():
    rec = _gold_rec([_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")])
    out = X.align_case(rec, [_c(ClaimKind.WITHIN_REFUND_WINDOW, "ORD-1")])
    assert out["per_gold"][0]["outcome"] == "CORRECT"
    assert out["spurious"] == []


def test_alignment_missed_claim():
    rec = _gold_rec([_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")])
    out = X.align_case(rec, [])
    assert out["per_gold"][0]["outcome"] == "MISSED_CLAIM"


def test_alignment_wrong_kind_same_subject():
    rec = _gold_rec([_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")])
    out = X.align_case(rec, [_c(ClaimKind.AMOUNT_WITHIN_AUTHORITY, "ORD-1")])
    assert out["per_gold"][0]["outcome"] == "WRONG_KIND"


def test_alignment_wrong_subject_same_kind():
    rec = _gold_rec([_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")])
    out = X.align_case(rec, [_c(ClaimKind.WITHIN_REFUND_WINDOW, "ORD-2")])
    assert out["per_gold"][0]["outcome"] == "WRONG_SUBJECT"


def test_alignment_split_claim_one_gold_many_extracted():
    rec = _gold_rec([_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")])
    dup = _c(ClaimKind.WITHIN_REFUND_WINDOW, "ORD-1")
    dup2 = Claim(id="ORD-1:within_refund_window#2", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1")
    out = X.align_case(rec, [dup, dup2])
    assert out["per_gold"][0]["outcome"] == "SPLIT_CLAIM"


def test_alignment_merged_claim_many_gold_one_extracted():
    rec = _gold_rec([
        _gold_claim("WITHIN_REFUND_WINDOW", "ORD-1", claim_id="gs-000::a"),
        _gold_claim("WITHIN_REFUND_WINDOW", "ORD-1", claim_id="gs-000::b"),
    ])
    out = X.align_case(rec, [_c(ClaimKind.WITHIN_REFUND_WINDOW, "ORD-1")])
    assert len(out["merged"]) == 1
    assert set(out["merged"][0]["gold_claim_ids"]) == {"gs-000::a", "gs-000::b"}


def test_alignment_spurious_claim():
    rec = _gold_rec([_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")])
    out = X.align_case(rec, [
        _c(ClaimKind.WITHIN_REFUND_WINDOW, "ORD-1"),
        _c(ClaimKind.CUSTOMER_INTENT, "ORD-1"),
    ])
    assert [s["claim_kind"] for s in out["spurious"]] == ["customer_intent"]


def test_alignment_unmodelled_required_is_not_a_missed_claim():
    rec = _gold_rec(
        [_gold_claim("WITHIN_REFUND_WINDOW", "ORD-1")],
        foundational=[{
            "id": "order_record_resolves", "representable_as_claimkind": False,
            "required": True, "load_bearing": True, "status": "VIOLATED", "rationale": "x",
        }],
    )
    out = X.align_case(rec, [_c(ClaimKind.WITHIN_REFUND_WINDOW, "ORD-1")])
    assert out["per_gold"][0]["outcome"] == "CORRECT"  # the representable claim is fine
    assert out["unmodelled_required"] == [
        {"id": "order_record_resolves", "load_bearing": True, "status": "VIOLATED"}
    ]


def test_clause_subject_normalization_makes_policy_claims_correct_not_wrong_subject():
    rec = _gold_rec([_gold_claim("POLICY_CLAUSE_CURRENT", "clause:refund_window")])
    out = X.align_case(rec, [_c(ClaimKind.POLICY_CLAUSE_CURRENT, "refund_window")])
    assert out["per_gold"][0]["outcome"] == "CORRECT"


# --------------------------------------------------------------------------
# real run — headline numbers + arithmetic
# --------------------------------------------------------------------------
def test_actual_extractor_recovers_every_representable_gold_claim():
    agg = _report()["aggregate"]
    csr = agg["claim_set_recovery"]
    assert csr["gold_claims_in_scope"] == 210
    assert csr["correct"] == 210
    assert csr["claim_recall"] == 1.0
    assert csr["claim_precision"] == 1.0
    assert csr["missed_required_claims"] == 0
    assert csr["wrong_kind_claims"] == 0
    assert csr["wrong_subject_claims"] == 0
    assert csr["merged_cases"] == 0
    assert csr["split_cases"] == 0
    assert agg["taxonomy_counts"]["SPURIOUS_CLAIM"] == 0


def test_every_case_has_a_load_bearing_unmodelled_requirement():
    agg = _report()["aggregate"]
    um = agg["unmodelled_required"]
    assert um["cases_with_a_load_bearing_unmodelled_requirement"] == 30
    assert um["load_bearing_unmodelled_instances"] == 30
    assert um["unmodelled_required_rate_over_cases"] == 1.0


def test_silent_pass_structural_gap_is_the_four_missing_record_cases_and_none_realized():
    sp = _report()["aggregate"]["silent_pass"]
    assert sp["structural_gap_case_ids"] == ["gs-129", "gs-130", "gs-133", "gs-134"]
    assert sp["realized_opportunity_count"] == 0


def test_ambiguous_day7_claims_are_preserved_not_scored():
    for c in _report()["cases"]:
        if c["case_id"] in {"gs-141", "gs-142", "gs-143", "gs-144"}:
            row = next(r for r in c["assertion_outcome"] if r["claim_kind"] == "WITHIN_REFUND_WINDOW")
            assert row["expected_assertion"] == "AMBIGUOUS"
            assert row["scorable"] is False
            assert row["outcome_agrees"] is None
            assert row["preserved_state"] == "AMBIGUOUS"


def test_order_attributes_match_outcome_is_not_determinable_and_never_scored():
    scored_kinds = set()
    for c in _report()["cases"]:
        for r in c["assertion_outcome"]:
            if r["scorable"]:
                scored_kinds.add(r["claim_kind"])
            if r["claim_kind"] == "ORDER_ATTRIBUTES_MATCH":
                assert r["scorable"] is False
                assert r["expected_assertion"] in {"NOT_DETERMINABLE_FROM_CORPUS", "UNVERIFIABLE"}
    assert "ORDER_ATTRIBUTES_MATCH" not in scored_kinds


def test_assertion_value_layer_is_not_exercised_offline():
    avr = _report()["aggregate"]["assertion_value_recovery"]
    assert avr["cases_exercised_offline"] == 0
    assert avr["cases_total"] == 30


def test_assertion_outcome_disagreements_are_all_clause_semantics_match():
    ao = _report()["aggregate"]["assertion_outcome"]
    assert {d["claim_kind"] for d in ao["disagreements"]} == {"CLAUSE_SEMANTICS_MATCH"}


def test_metric_arithmetic_is_self_consistent():
    agg = _report()["aggregate"]
    csr = agg["claim_set_recovery"]
    tx = agg["taxonomy_counts"]
    # recall numerator == CORRECT; every gold claim has exactly one outcome
    per_gold_total = sum(len(c["per_gold"]) for c in _report()["cases"])
    assert per_gold_total == csr["gold_claims_in_scope"]
    assert tx["CORRECT"] + tx["MISSED_CLAIM"] + tx["WRONG_KIND"] + tx["WRONG_SUBJECT"] + tx["SPLIT_CLAIM"] == per_gold_total
    # precision denominator
    assert csr["aligned_extracted_claims"] == csr["comparable_extracted_claims"] - csr["spurious_claims"]
    # decomposition accuracy is CORRECT / units
    assert csr["decomposition_accuracy"] == round(csr["correct_decomposition_units"] / csr["decomposition_units"], 6)
    # outcome agreement
    ao = agg["assertion_outcome"]
    assert ao["outcome_agreement_rate"] == round(ao["outcome_agreed"] / ao["scorable_claims"], 6)


def test_p1_cross_check_covers_all_thirty_cases_and_matches_ledger_shape():
    rows = _report()["aggregate"]["p1_cross_check"]["cases"]
    assert len(rows) == 30
    for row in rows:
        assert row["gold_required_claims"] == 7
        assert row["gold_extracted_matched_claims"] == 7
        assert row["gold_missed_required_claims"] == 0


def test_no_production_code_imported_path_was_reimplemented():
    """The benchmark must call the real build_claims, not a copy."""
    src = (BENCH / "extraction_completeness_bench.py").read_text(encoding="utf-8")
    assert "from controlplane.extract import build_claims" in src
    assert "def build_claims" not in src  # no local reimplementation
