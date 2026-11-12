"""P3-E - the foundational-requirement coverage falsification benchmark.

`bench/foundational_requirement_coverage.py` loads a FROZEN independently authored
reference (`bench/foundational_requirement_reference_v1.jsonl`, sha256 pinned),
classifies each candidate against a boundary test, and RUNS THE METRIC-GAMING
TESTS to decide whether a single foundational-requirement coverage percentage is
valid. This suite pins the reference hash, checks determinism, and exercises the
denominator / status / dependency / counterfactual machinery so each falsification
finding is demonstrably reproduced.

Does not weaken or alter any existing test. The known pre-existing failure
(tests/test_tau2_c2_controlplane_side.py, stale P06 hash) is unrelated and untouched.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from bench import foundational_requirement_coverage as F  # noqa: E402

PINNED_REFERENCE_SHA256 = "9a8f18b04726d6dd96f5634b2e9addc560b79f53a2312a1dae0dd433a49cadfa"
PINNED_P3B_GOLD_SHA256 = "79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d"

_CACHED: dict[str, object] = {}


def _report() -> dict:
    if "r" not in _CACHED:
        _CACHED["r"] = F.build_report()
    return _CACHED["r"]


# --------------------------------------------------------------------------
# frozen inputs + schema
# --------------------------------------------------------------------------
def test_frozen_reference_hash_is_unchanged():
    actual = hashlib.sha256((BENCH / "foundational_requirement_reference_v1.jsonl").read_bytes()).hexdigest()
    assert actual == PINNED_REFERENCE_SHA256
    assert F.PINNED_REFERENCE_SHA256 == PINNED_REFERENCE_SHA256


def test_p3b_gold_is_untouched_by_p3e():
    actual = hashlib.sha256((BENCH / "extraction_gold_v1.jsonl").read_bytes()).hexdigest()
    assert actual == PINNED_P3B_GOLD_SHA256
    assert F.PINNED_P3B_GOLD_SHA256 == PINNED_P3B_GOLD_SHA256


def test_reference_validates_against_its_schema():
    recs = F.load_reference()  # raises on schema failure or hash drift
    assert len(recs) == 6
    schema = json.loads((BENCH / "foundational_requirement_reference_v1.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["requirement_class"]["enum"] == [
        "FOUNDATIONAL_REQUIREMENT", "ORDINARY_CLAIM", "ACTION_VALIDITY_CHECK", "UNCLEAR",
    ]


def test_build_report_aborts_if_reference_hash_drifts(monkeypatch):
    monkeypatch.setattr(F, "PINNED_REFERENCE_SHA256", "deadbeef")
    with pytest.raises(SystemExit):
        F.load_reference()


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------
def test_report_is_deterministic_across_two_builds():
    a = F.render_json(F.build_report())
    b = F.render_json(F.build_report())
    assert a == b


def test_committed_report_has_no_drift():
    r = subprocess.run(
        [sys.executable, str(BENCH / "foundational_requirement_coverage.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, f"drift:\n{r.stdout}\n{r.stderr}"


# --------------------------------------------------------------------------
# boundary test / classification
# --------------------------------------------------------------------------
def test_only_genuine_preconditions_are_classed_foundational():
    recs = F.load_reference()
    by_id = {r["requirement_id"]: r for r in recs}
    assert by_id["issue_refund::order_record_resolves"]["requirement_class"] == "FOUNDATIONAL_REQUIREMENT"
    assert by_id["issue_refund::order_record_fields_complete"]["requirement_class"] == "FOUNDATIONAL_REQUIREMENT"
    # currency_integrity is asserted + value-compared -> ordinary claim, not foundational
    cur = by_id["issue_refund::currency_integrity"]
    assert cur["requirement_class"] == "ORDINARY_CLAIM"
    assert cur["boundary_test"]["agent_can_assert_value"] is True
    assert cur["boundary_test"]["evaluated_by_value_comparison"] is True
    # amount well-formedness needs no evidence and gates nothing -> action validity
    amt = by_id["issue_refund::refund_amount_well_formed"]
    assert amt["requirement_class"] == "ACTION_VALIDITY_CHECK"
    assert amt["boundary_test"]["uses_normal_evidence_resolver"] is False
    assert amt["downstream_claims_gated"] == []


def test_every_foundational_requirement_passes_every_boundary_criterion():
    for r in F.load_reference():
        if r["requirement_class"] != "FOUNDATIONAL_REQUIREMENT":
            continue
        b = r["boundary_test"]
        assert b["agent_can_assert_value"] is False
        assert b["evaluated_by_value_comparison"] is False
        assert b["uses_normal_evidence_resolver"] is False
        assert b["attributable_to_agent_assertion"] is False
        assert b["gates_multiple_downstream_claims"] is True
        assert b["prerequisite_for_interpreting_action"] is True


# --------------------------------------------------------------------------
# per-case states: VIOLATED vs NOT_ESTABLISHED, unavailable evidence
# --------------------------------------------------------------------------
def test_missing_record_cases_are_the_four_and_carry_an_alt_reading():
    orr = next(r for r in F.load_reference() if r["requirement_id"] == "issue_refund::order_record_resolves")
    violated = [pc for pc in orr["per_case"] if pc["requirement_state"] == "VIOLATED"]
    assert sorted(pc["case_id"] for pc in violated) == ["gs-129", "gs-130", "gs-133", "gs-134"]
    for pc in violated:
        assert pc["evidence_state"] == "UNAVAILABLE"
        # the VIOLATED-vs-NOT_ESTABLISHED judgement is disclosed, not hidden
        assert "alt_reading" in pc and "NOT_ESTABLISHED" in pc["alt_reading"]


def test_not_established_and_not_applicable_are_distinct_states():
    by_id = {r["requirement_id"]: r for r in F.load_reference()}
    cur = {pc["case_id"]: pc for pc in by_id["issue_refund::currency_integrity"]["per_case"]}
    fields = {pc["case_id"]: pc for pc in by_id["issue_refund::order_record_fields_complete"]["per_case"]}
    # currency: no record to compare against -> NOT_ESTABLISHED (we could not check)
    assert cur["gs-129"]["requirement_state"] == "NOT_ESTABLISHED"
    # field completeness: moot when the row is absent -> NOT_APPLICABLE (subsumed)
    assert fields["gs-129"]["requirement_state"] == "NOT_APPLICABLE"
    assert fields["gs-129"]["evidence_state"] == "NOT_REQUIRED"


def test_self_consistency_guard_recomputes_states_from_raw_facts():
    # build_report() raises if the frozen per_case drifts from record_lookup_status + orders.db
    _report()  # would have raised


# --------------------------------------------------------------------------
# denominator arithmetic + zero denominator
# --------------------------------------------------------------------------
def test_candidate_metric_arithmetic_is_self_consistent():
    recs = F.load_reference()
    m = F.candidate_metric(recs, requirement_ids=["issue_refund::order_record_resolves"])
    assert m["satisfied"] == 26
    assert m["denominator_excludes_not_applicable"] == 30
    assert m["coverage"] == round(26 / 30, 6)


def test_zero_denominator_returns_na_not_one():
    recs = F.load_reference()
    # a pool of only NOT_ASSESSABLE requirements -> no per_case -> denominator 0
    m = F.candidate_metric(recs, requirement_ids=["tau2_retail_order_action::independent_user_authentication"])
    assert m["coverage"] is None
    assert m["coverage_na"] is True


def test_not_applicable_is_excluded_from_the_denominator():
    recs = F.load_reference()
    m = F.candidate_metric(recs, requirement_ids=["issue_refund::order_record_fields_complete"])
    # 26 SATISFIED + 4 NOT_APPLICABLE -> denominator 26, coverage 1.0
    assert m["denominator_excludes_not_applicable"] == 26
    assert m["coverage"] == 1.0


# --------------------------------------------------------------------------
# counted once / duplicate / dependency
# --------------------------------------------------------------------------
def test_duplicate_requirement_does_not_change_the_ratio():
    recs = F.load_reference()
    base = F.candidate_metric(recs)
    dup = F.candidate_metric(recs + [dict(recs[0])])  # recs[0] is order_record_resolves
    assert dup["coverage"] == base["coverage"]
    assert dup["n_requirements"] == base["n_requirements"]  # deduped by requirement_id


def test_dropping_a_downstream_dependency_does_not_change_the_count():
    recs = F.load_reference()
    base = F.candidate_metric(recs)
    trimmed = [
        dict(r, downstream_claims_gated=r["downstream_claims_gated"][:-1])
        if r["requirement_id"] == "issue_refund::order_record_resolves" else r
        for r in recs
    ]
    assert F.candidate_metric(trimmed)["coverage"] == base["coverage"]


def test_order_record_resolves_gates_exactly_four_of_seven_claims():
    orr = next(r for r in F.load_reference() if r["requirement_id"] == "issue_refund::order_record_resolves")
    assert sorted(orr["downstream_claims_gated"]) == sorted([
        "ORDER_BELONGS_TO_CUSTOMER", "AMOUNT_NOT_EXCEEDING_ORDER",
        "WITHIN_REFUND_WINDOW", "ORDER_ATTRIBUTES_MATCH",
    ])


# --------------------------------------------------------------------------
# the decisive falsification findings
# --------------------------------------------------------------------------
def test_degeneracy_proof_the_state_is_a_recode_of_record_lookup_status():
    dp = _report()["degeneracy_proof"]
    assert dp["per_case_state_is_bit_identical_to_record_lookup_status"] is True
    assert dp["n_record_unresolved"] == 4
    assert dp["candidate_coverage_equals_1_minus_slice_fraction"] == round(1 - 4 / 30, 6)


def test_metric_verdict_is_invalid_and_no_aggregate_is_reported():
    mv = _report()["candidate_metric_validity"]
    assert mv["verdict"] == "INVALID"
    assert mv["frozen_value"] is None
    assert len(mv["reasons"]) >= 6


def test_counterfactual_denominator_sensitivity_is_demonstrated():
    tests = {t["test"]: t for t in _report()["metric_gaming_tests"]}
    # A: adding an always-satisfied requirement moves the metric
    assert tests["A_add_required_requirement"]["metric_changed"] is True
    # B: removing the only failing requirement inflates it
    assert tests["B_remove_the_failing_requirement"]["metric_changed"] is True
    assert tests["B_remove_the_failing_requirement"]["after"] in (1.0, None)
    # D: a defensible status re-reading inflates it to 1.0
    assert tests["D_status_corruption"]["after"] == 1.0
    # C, F: counting-once holds
    assert tests["C_duplicate_a_requirement"]["metric_changed"] is False
    assert tests["F_drop_downstream_dependency"]["metric_changed"] is False


def test_cross_tool_comparability_is_rejected():
    ct = _report()["cross_tool_comparability"]
    fams = ct["by_family"]
    assert fams["customer_servicing"]["assessable"]  # non-empty
    assert not fams["tau2_retail_order_action"]["assessable"]  # empty -> N/A, not comparable


# --------------------------------------------------------------------------
# P1 comparison + silent-pass
# --------------------------------------------------------------------------
def test_p1_cross_check_covers_all_thirty_cases():
    per_case = _report()["p1_x_foundational_matrix"]["per_case"]
    assert len(per_case) == 30
    gs129 = next(r for r in per_case if r["case_id"] == "gs-129")
    assert gs129["p1_verified_eligible"] == "2/7"
    assert gs129["p1_intervention"] == "ESCALATE"
    assert gs129["foundational_order_record_resolves"] == "VIOLATED"
    assert sorted(gs129["p1_unavailable_claim_kinds"]) == sorted([
        "amount_not_exceeding_order", "order_attributes_match",
        "order_belongs_to_customer", "within_refund_window",
    ])


def test_silent_pass_matches_p3c_four_structural_zero_realized():
    sp = _report()["silent_pass"]
    assert sp["structural_gap_case_ids"] == ["gs-129", "gs-130", "gs-133", "gs-134"]
    assert sp["realized_opportunity_count"] == 0
    assert sp["matches_p3c"] is True


def test_p1_full_coverage_is_unreachable_on_this_corpus():
    # the empty "P1=100" matrix rows are a grounding-off fact, not a foundational one
    cells = _report()["p1_x_foundational_matrix"]["cells"]
    assert cells["P1=100 & FR=SAT"]["n"] == 0
    assert cells["P1=100 & FR!=SAT"]["n"] == 0


# --------------------------------------------------------------------------
# no production code touched / no combined score
# --------------------------------------------------------------------------
def test_benchmark_imports_no_production_write_path_and_invents_no_score():
    src = (BENCH / "foundational_requirement_coverage.py").read_text(encoding="utf-8")
    # reuses the real P1 pipeline, does not reimplement decide()/build_claims
    assert "from controlplane.decide import decide" not in src  # only via bench.extraction_completeness_bench.run_p1
    assert "def decide(" not in src
    for banned in ("overall_safety", "combined_coverage", "safety_score", "risk_score", "confidence_score"):
        assert banned not in src


def test_disposition_is_architecture_valid_metric_invalid():
    assert "ARCHITECTURE VALID" in _report()["disposition"]
    assert "COVERAGE PERCENTAGE INVALID" in _report()["disposition"]
