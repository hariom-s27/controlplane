#!/usr/bin/env python3
"""P3-E - foundational-requirement coverage: falsification + measurement of the P3-D architecture.

    python bench/foundational_requirement_coverage.py            # prints the JSON summary, exits non-zero on drift-guard failure
    python bench/foundational_requirement_coverage.py --write    # also (re)writes reports/foundational-requirement-coverage-v1.{md,json}
    python bench/foundational_requirement_coverage.py --check    # fail if the committed report/json would change

WHAT THIS IS
------------
P3-D recommended a separate "foundational-precondition layer" (Option B) and asked whether
foundational requirements of the `order_record_resolves` shape can be measured as a distinct
population without producing a misleading or manipulable coverage metric.

This benchmark FALSIFIES that question. It loads a FROZEN, independently authored reference
(bench/foundational_requirement_reference_v1.jsonl, sha256 pinned), classifies each candidate
requirement against a reproducible boundary test, computes the per-case requirement/evidence
states the frozen 30-case P3-B issue_refund corpus can exercise, cross-checks against P1
verification coverage, and then RUNS THE METRIC-GAMING TESTS (task section 21). If a single
coverage percentage is not a valid measurement, it says so and emits a per-requirement
observability report instead of manufacturing a number.

The reference is READ-ONLY here. It is never regenerated, never adjusted to any result.
bench/extraction_gold_v1.jsonl and the P3-C artifacts are never read or modified.

WHAT IT IS NOT
--------------
Not a population estimate. Not a pass/fail of ControlPlane. No confidence interval. No combined
safety score. It does not change P1 verification coverage, decide(), or any receipt.

DETERMINISM
-----------
Reads the frozen reference, bench/human_label_sample.csv, bench/gold_set.jsonl, data/orders.db
and data/policy_store.db (the P1 cross-check) on the frozen demo clock 2026-08-14. No network,
no model call. Same input -> byte-identical output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# benchmark-only, mirrors bench/extraction_completeness_bench.py
os.environ.setdefault("CP_RECEIPT_SECRET", "foundational-requirement-coverage-bench-not-for-production")
os.environ.setdefault("CP_MODEL", "Qwen/Qwen3-8B")

BENCH = ROOT / "bench"
REPORTS = ROOT / "reports"
REF_JSONL = BENCH / "foundational_requirement_reference_v1.jsonl"
REF_SCHEMA = BENCH / "foundational_requirement_reference_v1.schema.json"
REF_META = BENCH / "foundational_requirement_reference_v1.meta.json"
HUMAN_CSV = BENCH / "human_label_sample.csv"
GOLD_SET = BENCH / "gold_set.jsonl"
ORDERS_DB = ROOT / "data" / "orders.db"

PINNED_REFERENCE_SHA256 = "9a8f18b04726d6dd96f5634b2e9addc560b79f53a2312a1dae0dd433a49cadfa"
PINNED_HUMAN_CSV_SHA256 = "c58a3ed172458e9cd25b2a0267f51a037ce2f7d653b7acb13aa7c15049e84550"
# The P3-B gold corpus is NOT read by this benchmark; its hash is asserted only to prove
# the frozen P3-B/P3-C state is untouched by P3-E.
PINNED_P3B_GOLD_SHA256 = "79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d"

FROZEN_TODAY = "2026-08-14"
REPRO_CMD = "python bench/foundational_requirement_coverage.py --write"

MD_PATH = REPORTS / "foundational-requirement-coverage-v1.md"
JSON_PATH = REPORTS / "foundational-requirement-coverage-v1.json"


# ==========================================================================
# 1. load + freeze guard
# ==========================================================================
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference() -> list[dict]:
    sha = _sha256(REF_JSONL)
    if sha != PINNED_REFERENCE_SHA256:
        raise SystemExit(
            f"STOP: frozen reference sha256 {sha} != pinned {PINNED_REFERENCE_SHA256}. "
            "The reference population must be frozen BEFORE measurement (task section 20)."
        )
    meta = json.loads(REF_META.read_text(encoding="utf-8"))
    if meta["sha256"]["foundational_requirement_reference_v1.jsonl"] != sha:
        raise SystemExit("STOP: reference meta sha256 disagrees with the reference file.")
    recs = [json.loads(l) for l in REF_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    _validate_schema(recs)
    return recs


def _validate_schema(recs: list[dict]) -> None:
    schema = json.loads(REF_SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema  # noqa: PLC0415
    except ModuleNotFoundError:
        _validate_schema_minimal(recs, schema)
        return
    for r in recs:
        jsonschema.validate(r, schema)


def _validate_schema_minimal(recs: list[dict], schema: dict) -> None:
    """Fallback if jsonschema is not installed: check required keys + enums we rely on."""
    req = schema["required"]
    req_class = set(schema["properties"]["requirement_class"]["enum"])
    det = set(schema["properties"]["determinability"]["enum"])
    r_state = set(schema["properties"]["per_case"]["items"]["properties"]["requirement_state"]["enum"])
    e_state = set(schema["properties"]["per_case"]["items"]["properties"]["evidence_state"]["enum"])
    for r in recs:
        missing = [k for k in req if k not in r]
        if missing:
            raise SystemExit(f"STOP: reference record {r.get('requirement_id')} missing keys {missing}")
        assert r["requirement_class"] in req_class, r["requirement_id"]
        assert r["determinability"] in det, r["requirement_id"]
        for pc in r.get("per_case", []):
            assert pc["requirement_state"] in r_state, (r["requirement_id"], pc["case_id"])
            assert pc["evidence_state"] in e_state, (r["requirement_id"], pc["case_id"])


def load_corpus() -> list[dict]:
    sha = _sha256(HUMAN_CSV)
    if sha != PINNED_HUMAN_CSV_SHA256:
        raise SystemExit(f"STOP: human_label_sample.csv sha256 {sha} != pinned {PINNED_HUMAN_CSV_SHA256}.")
    rows = list(csv.DictReader(HUMAN_CSV.read_text(encoding="utf-8-sig").splitlines()))
    return rows


def load_gold_set() -> dict[str, dict]:
    return {
        json.loads(l)["id"]: json.loads(l)
        for l in GOLD_SET.read_text(encoding="utf-8").splitlines() if l.strip()
    }


# ==========================================================================
# 2. independent recompute of the per-case states  (self-consistency guard)
# ==========================================================================
def recompute_states(corpus: list[dict], gset: dict[str, dict]) -> dict[str, dict[str, str]]:
    """Re-derive the per-case requirement_state for the two corpus-exercisable FOUNDATIONAL
    requirements straight from the raw facts, so a drifted frozen reference is caught. This
    is NOT a second source of truth - it is a guard that the frozen per_case still matches
    what record_lookup_status + orders.db say."""
    conn = sqlite3.connect(ORDERS_DB)
    try:
        out: dict[str, dict[str, str]] = {"order_record_resolves": {}, "order_record_fields_complete": {}}
        for row in corpus:
            cid, oid, look = row["case_id"], row["call_order_id"], row["record_lookup_status"]
            dbrow = conn.execute(
                "SELECT customer_id,delivered_at,amount_paise,currency FROM orders WHERE order_id=?", (oid,)
            ).fetchone()
            resolves = dbrow is not None
            assert (look == "FOUND") == resolves, f"{cid}: CSV says {look} but orders.db {'has' if resolves else 'lacks'} {oid}"
            out["order_record_resolves"][cid] = "SATISFIED" if resolves else "VIOLATED"
            if not resolves:
                out["order_record_fields_complete"][cid] = "NOT_APPLICABLE"
            else:
                complete = all(v not in (None, "") for v in dbrow)
                out["order_record_fields_complete"][cid] = "SATISFIED" if complete else "VIOLATED"
        return out
    finally:
        conn.close()


# ==========================================================================
# 3. P1 verification-coverage cross-check  (repo-standard pipeline, deterministic)
# ==========================================================================
def p1_by_case(gset: dict[str, dict], case_ids: list[str]) -> dict[str, dict]:
    from bench import baselines as B  # noqa: PLC0415
    from bench import extraction_completeness_bench as X  # noqa: PLC0415
    from controlplane.bindings import claim_specs  # noqa: PLC0415
    from controlplane.manifest import load_manifest  # noqa: PLC0415
    from controlplane.registry.clock import set_clock  # noqa: PLC0415

    set_clock(date.fromisoformat(FROZEN_TODAY))
    manifest = load_manifest("servicing")
    specs = claim_specs(manifest)
    out: dict[str, dict] = {}
    for cid in case_ids:
        decision = X.run_p1(gset[cid], manifest, specs)
        L = decision.verification_ledger
        cov = L.coverage
        unavailable_kinds = sorted(
            r.kind.value for r in L.claims if r.verification_status.value == "unavailable"
        )
        out[cid] = {
            "verdict": decision.verdict.value,
            "intervention": decision.intervention.value,
            "coverage_verified": cov.verified,
            "coverage_eligible": cov.eligible,
            "coverage_value": cov.value,
            "coverage_na": cov.n_a,
            "unavailable_claim_kinds": unavailable_kinds,
        }
    return out


# ==========================================================================
# 4. the candidate metric  +  the reasons it is or is not valid
# ==========================================================================
def _assessable_foundational(recs: list[dict]) -> list[dict]:
    """The requirements a foundational-coverage % would be computed over: FOUNDATIONAL_REQUIREMENT,
    load-bearing, and actually assessable on the frozen corpus (has a per_case table)."""
    return [
        r for r in recs
        if r["requirement_class"] == "FOUNDATIONAL_REQUIREMENT"
        and r["load_bearing"]
        and r["determinability"] != "NOT_ASSESSABLE"
        and r.get("per_case")
    ]


def candidate_metric(recs: list[dict], *, states_override: dict | None = None,
                     requirement_ids: list[str] | None = None) -> dict:
    """The task-section-21 candidate: satisfied / required load-bearing foundational preconditions,
    aggregated over case x requirement observations. NOT_APPLICABLE observations are excluded from
    the denominator (they are not a failure); NOT_ESTABLISHED is counted as not-satisfied but kept
    distinct in the breakdown. Reported here only to be tested, never as a headline."""
    pool = _assessable_foundational(recs)
    if requirement_ids is not None:
        pool = [r for r in pool if r["requirement_id"] in requirement_ids]
    # dedupe by requirement_id: a foundational requirement is counted ONCE, never once per
    # downstream claim and never twice if duplicated in the list (task section 13, 21C).
    seen: set[str] = set()
    obs: list[tuple[str, str, str]] = []  # (requirement_id, case_id, state)
    for r in pool:
        rid = r["requirement_id"]
        if rid in seen:
            continue
        seen.add(rid)
        for pc in r["per_case"]:
            st = pc["requirement_state"]
            if states_override and rid in states_override and pc["case_id"] in states_override[rid]:
                st = states_override[rid][pc["case_id"]]
            obs.append((rid, pc["case_id"], st))
    dist = Counter(st for _, _, st in obs)
    denom = sum(1 for _, _, st in obs if st != "NOT_APPLICABLE")
    satisfied = dist.get("SATISFIED", 0)
    return {
        "requirements_counted": sorted(seen),
        "n_requirements": len(seen),
        "observations": len(obs),
        "state_distribution": dict(sorted(dist.items())),
        "denominator_excludes_not_applicable": denom,
        "satisfied": satisfied,
        "coverage": round(satisfied / denom, 6) if denom else None,
        "coverage_na": denom == 0,
    }


def degeneracy_proof(recs: list[dict], corpus: list[dict]) -> dict:
    """Show the order_record_resolves per-case state IS a 1:1 recode of one corpus construction
    parameter (record_lookup_status), so any ratio over it = 1 - P(record_unresolved slice)."""
    orr = next(r for r in recs if r["requirement_id"] == "issue_refund::order_record_resolves")
    by_case = {pc["case_id"]: pc["requirement_state"] for pc in orr["per_case"]}
    look = {row["case_id"]: row["record_lookup_status"] for row in corpus}
    recode_matches = all(
        (by_case[cid] == "SATISFIED") == (look[cid] == "FOUND") for cid in by_case
    )
    n_no_match = sum(1 for v in look.values() if v == "NO_MATCH")
    n = len(look)
    return {
        "requirement": "issue_refund::order_record_resolves",
        "per_case_state_is_bit_identical_to_record_lookup_status": recode_matches,
        "n_cases": n,
        "n_record_unresolved": n_no_match,
        "candidate_coverage_equals_1_minus_slice_fraction": round(1 - n_no_match / n, 6),
        "slice_fraction_is_a_corpus_construction_parameter": True,
        "construction_parameter_source": "bench/extraction_gold_v1.meta.json counts.by_difficulty_class.record_unresolved_escalate = 4",
        "precedent": "docs/retired-figures.md item 2 (order_id cross-validation): 'the detector recomputed that same boolean from the same fields ... an identity, not a measurement. The 75% baseline was 1 - P(wrong resolution) read straight off the generator's coin flips.'",
        "verdict": "DEGENERATE - the metric cannot fail for any reason not baked into how the 30 cases were sampled; it measures corpus composition, not ControlPlane.",
    }


def gaming_tests(recs: list[dict]) -> list[dict]:
    """task section 21: A add / B remove / C duplicate / D status-flip / E evidence-flip / F drop-downstream."""
    base = candidate_metric(recs)
    tests: list[dict] = []

    # A. add one genuinely-required foundational requirement that is SATISFIED on every case
    #    (order_record_fields_complete already qualifies; it is in the pool). Demonstrate by
    #    RESTRICTING to just order_record_resolves and then adding it back.
    just_orr = candidate_metric(recs, requirement_ids=["issue_refund::order_record_resolves"])
    with_fields = candidate_metric(recs, requirement_ids=[
        "issue_refund::order_record_resolves", "issue_refund::order_record_fields_complete"])
    tests.append({
        "test": "A_add_required_requirement",
        "action": "add issue_refund::order_record_fields_complete (SATISFIED on all 26 FOUND, NOT_APPLICABLE on 4) to a pool that was just {order_record_resolves}",
        "before": just_orr["coverage"], "after": with_fields["coverage"],
        "metric_changed": just_orr["coverage"] != with_fields["coverage"],
        "should_case_safety_have_changed": False,
        "finding": "the aggregate % moves purely because the denominator grew with an always-satisfied check - denominator-sensitive.",
    })

    # B. remove the one requirement that ever fails
    removed = candidate_metric(recs, requirement_ids=[
        r["requirement_id"] for r in _assessable_foundational(recs)
        if r["requirement_id"] != "issue_refund::order_record_resolves"])
    tests.append({
        "test": "B_remove_the_failing_requirement",
        "action": "drop issue_refund::order_record_resolves from the frozen pool",
        "before": base["coverage"], "after": removed["coverage"],
        "metric_changed": base["coverage"] != removed["coverage"],
        "should_case_safety_have_changed": False,
        "finding": "removing the only requirement that is ever VIOLATED makes the metric read "
                   + ("100%/N/A" if (removed["coverage"] in (1.0, None)) else str(removed["coverage"]))
                   + " - pure denominator manipulation, and nothing stops a manifest author doing it.",
    })

    # C. duplicate a requirement
    dup = list(recs) + [next(r for r in recs if r["requirement_id"] == "issue_refund::order_record_resolves")]
    dup_metric = candidate_metric(dup)
    tests.append({
        "test": "C_duplicate_a_requirement",
        "action": "append a second copy of issue_refund::order_record_resolves",
        "before": base["coverage"], "after": dup_metric["coverage"],
        "metric_changed": base["coverage"] != dup_metric["coverage"],
        "n_requirements_before": base["n_requirements"], "n_requirements_after": dup_metric["n_requirements"],
        "should_case_safety_have_changed": False,
        "finding": "the metric dedupes by requirement_id so the ratio is unchanged - counting-once works - "
                   "but a naive implementation that counted per row would halve the score.",
    })

    # D. status corruption: flip the 4 VIOLATED -> SATISFIED
    flip_status = {"issue_refund::order_record_resolves": {c: "SATISFIED" for c in ("gs-129", "gs-130", "gs-133", "gs-134")}}
    d_metric = candidate_metric(recs, states_override=flip_status)
    tests.append({
        "test": "D_status_corruption",
        "action": "flip order_record_resolves gs-129/130/133/134 from VIOLATED to SATISFIED",
        "before": base["coverage"], "after": d_metric["coverage"],
        "metric_changed": base["coverage"] != d_metric["coverage"],
        "should_case_safety_have_changed": False,
        "finding": "status corruption inflates the metric directly to "
                   + str(d_metric["coverage"])
                   + "; and because VIOLATED-vs-NOT_ESTABLISHED is itself a judgement call (P3-B says VIOLATED, "
                     "bench/label.py implies NOT_ESTABLISHED), this is not even an adversarial edit - it is a defensible re-reading.",
    })

    # E. evidence-state flip presented as status: NOT_ESTABLISHED -> SATISFIED for currency_integrity's 4
    #    (currency_integrity is ORDINARY_CLAIM so it is not in the foundational pool; show that including it
    #     - as P3-A/P3-B do - would import its 4 NOT_ESTABLISHED and then a flip inflates)
    incl_currency = candidate_metric(
        [dict(r, requirement_class="FOUNDATIONAL_REQUIREMENT") if r["requirement_id"] == "issue_refund::currency_integrity" else r for r in recs]
    )
    incl_currency_flipped = candidate_metric(
        [dict(r, requirement_class="FOUNDATIONAL_REQUIREMENT") if r["requirement_id"] == "issue_refund::currency_integrity" else r for r in recs],
        states_override={"issue_refund::currency_integrity": {c: "SATISFIED" for c in ("gs-129", "gs-130", "gs-133", "gs-134")}},
    )
    tests.append({
        "test": "E_unavailable_evidence_relabelled_satisfied",
        "action": "reclassify currency_integrity as foundational (as P3-A/P3-B do), then flip its 4 NOT_ESTABLISHED to SATISFIED",
        "before": incl_currency["coverage"], "after": incl_currency_flipped["coverage"],
        "metric_changed": incl_currency["coverage"] != incl_currency_flipped["coverage"],
        "should_case_safety_have_changed": False,
        "finding": "relabelling 'evidence unavailable' as 'requirement satisfied' inflates the metric; the two-axis "
                   "model is supposed to prevent this but nothing enforces the axis separation.",
    })

    # F. drop a downstream-claim dependency without removing the requirement
    dropped_dep = [
        dict(r, downstream_claims_gated=r["downstream_claims_gated"][:-1])
        if r["requirement_id"] == "issue_refund::order_record_resolves" else r
        for r in recs
    ]
    f_metric = candidate_metric(dropped_dep)
    tests.append({
        "test": "F_drop_downstream_dependency",
        "action": "remove one ClaimKind from order_record_resolves.downstream_claims_gated (4 -> 3)",
        "before": base["coverage"], "after": f_metric["coverage"],
        "metric_changed": base["coverage"] != f_metric["coverage"],
        "should_case_safety_have_changed": False,
        "finding": "no change - the requirement is counted once regardless of how many claims it gates. "
                   "Correct behaviour, and the reason task section 22 forbids weighting by downstream-claim count.",
    })
    return tests


# ==========================================================================
# 5. cross-tool comparability
# ==========================================================================
def cross_tool(recs: list[dict]) -> dict:
    by_family: dict[str, dict] = {}
    for r in recs:
        fam = r["tool_family"]
        b = by_family.setdefault(fam, {"foundational": [], "assessable": [], "not_assessable": [], "other_class": []})
        if r["requirement_class"] == "FOUNDATIONAL_REQUIREMENT":
            b["foundational"].append(r["requirement_id"])
            (b["assessable"] if r["determinability"] != "NOT_ASSESSABLE" else b["not_assessable"]).append(r["requirement_id"])
        else:
            b["other_class"].append(f'{r["requirement_id"]} ({r["requirement_class"]})')
    return {
        "by_family": by_family,
        "send_document_negative_control": (
            "bench/extraction_reference.py UNREPRESENTABLE_REQUIRED has NO entry for send_document; "
            "P3-D section 16 confirms its two required kinds are both bound and representable. A "
            "foundational-coverage % for send_document is 0/0 = N/A."
        ),
        "finding": (
            "issue_refund has 1 assessable load-bearing foundational requirement; the tau2 family has 0 "
            "assessable (1 NOT_ASSESSABLE + 1 already-counted-by-P3-A binding gap); send_document has none. "
            "A percentage of '100% (1/1)' for issue_refund and 'N/A (0/0)' for tau2 and send_document are not "
            "comparable quantities - they do not answer the same question and cannot be ranked."
        ),
    }


# ==========================================================================
# 6. P1 x foundational interpretation matrix + silent-pass
# ==========================================================================
def p1_matrix(recs: list[dict], p1: dict[str, dict]) -> dict:
    orr = {pc["case_id"]: pc for pc in next(r for r in recs if r["requirement_id"] == "issue_refund::order_record_resolves")["per_case"]}
    cells: dict[str, list[str]] = {"P1=100 & FR=SAT": [], "P1<100 & FR=SAT": [], "P1=100 & FR!=SAT": [], "P1<100 & FR!=SAT": []}
    per_case = []
    for cid, prow in sorted(p1.items()):
        fr = orr[cid]["requirement_state"]
        p1_full = (prow["coverage_value"] is not None and prow["coverage_value"] >= 0.999)
        key = ("P1=100" if p1_full else "P1<100") + (" & FR=SAT" if fr == "SATISFIED" else " & FR!=SAT")
        cells[key].append(cid)
        per_case.append({
            "case_id": cid,
            "p1_coverage": prow["coverage_value"],
            "p1_verified_eligible": f'{prow["coverage_verified"]}/{prow["coverage_eligible"]}',
            "p1_intervention": prow["intervention"],
            "foundational_order_record_resolves": fr,
            "foundational_evidence_state": orr[cid]["evidence_state"],
            "p1_unavailable_claim_kinds": prow["unavailable_claim_kinds"],
        })
    return {
        "cells": {k: {"n": len(v), "case_ids": v} for k, v in cells.items()},
        "interpretation": {
            "P1=100 & FR=SAT": "the modelled load-bearing claim set was fully verified AND the record precondition held. NOT demonstrated: unmodelled claims (P3-A), assertion-value accuracy, record correctness, C3 semantics.",
            "P1<100 & FR=SAT": "some modelled claims were not verified for a reason unrelated to the record precondition (here: C3 CLAUSE_SEMANTICS_MATCH is UNVERIFIED with grounding off, or a genuine contradiction on a window/authority claim). The foundational layer adds nothing on these cases.",
            "P1=100 & FR!=SAT": "did not occur in this corpus and CANNOT for issue_refund: a missing record forces >=4 of 7 load-bearing claims to UNAVAILABLE, so P1 cannot reach 100%. This is why the P3-C silent-pass count is 0 realized.",
            "P1<100 & FR!=SAT": "the 4 missing-record cases. P1 is ~29% AND the record precondition failed. The foundational line explains WHY 4 of the 5 unverified claims are unverified - a per-case causal annotation, not a coverage number.",
        },
        "per_case": per_case,
    }


def silent_pass(recs: list[dict], p1: dict[str, dict]) -> dict:
    orr = {pc["case_id"]: pc for pc in next(r for r in recs if r["requirement_id"] == "issue_refund::order_record_resolves")["per_case"]}
    structural, realized = [], []
    for cid, prow in p1.items():
        fr_failed = orr[cid]["requirement_state"] != "SATISFIED"
        if fr_failed:
            structural.append(cid)
            if (prow["coverage_value"] or 0) >= 0.80 and prow["intervention"] in ("ALLOW", "MODIFY"):
                realized.append(cid)
    return {
        "structural_gap_case_ids": sorted(structural),
        "structural_gap_count": len(structural),
        "realized_opportunity_case_ids": sorted(realized),
        "realized_opportunity_count": len(realized),
        "matches_p3c": sorted(structural) == ["gs-129", "gs-130", "gs-133", "gs-134"] and not realized,
        "does_the_foundational_layer_expose_the_gap_more_clearly_than_p1_alone": (
            "MARGINALLY. P1's per-case ledger already shows 4 claims as UNAVAILABLE with reason "
            "'authoritative_lookup_empty'. The foundational layer names the single shared cause "
            "('order_record_resolves: VIOLATED') instead of leaving it as an inference from 4 rows plus "
            "a receipt verdict (SOURCE_UNRELIABLE) and root_cause (evidence_below_reliability_floor) that "
            "both point at 'bad data' rather than 'absent record'. That is a per-case audit-trail "
            "improvement, not a coverage metric, and it does not change the 0 realized count."
        ),
    }


# ==========================================================================
# 7. assemble
# ==========================================================================
def build_report() -> dict:
    recs = load_reference()
    corpus = load_corpus()
    gset = load_gold_set()
    case_ids = [row["case_id"] for row in corpus]

    # freeze guard on P3-B/P3-C (asserted untouched, not read as input)
    p3b_sha = _sha256(BENCH / "extraction_gold_v1.jsonl")
    if p3b_sha != PINNED_P3B_GOLD_SHA256:
        raise SystemExit(f"STOP: P3-B gold sha256 changed ({p3b_sha}) - P3-E must not touch it.")

    # self-consistency: frozen per_case must still match the raw facts
    recomputed = recompute_states(corpus, gset)
    drift = []
    for rid_short, rc in recomputed.items():
        rec = next(r for r in recs if r["requirement_name"] == rid_short)
        frozen = {pc["case_id"]: pc["requirement_state"] for pc in rec["per_case"]}
        for cid, st in rc.items():
            if frozen.get(cid) != st:
                drift.append(f"{rid_short}/{cid}: frozen={frozen.get(cid)} recomputed={st}")
    if drift:
        raise SystemExit("STOP: frozen reference per_case drifted from the raw facts:\n  " + "\n  ".join(drift))

    p1 = p1_by_case(gset, case_ids)

    boundary = [
        {
            "requirement_id": r["requirement_id"],
            "requirement_class": r["requirement_class"],
            "boundary_test": r["boundary_test"],
            "load_bearing": r["load_bearing"],
            "determinability": r["determinability"],
            "downstream_claims_gated_count": len(r["downstream_claims_gated"]),
            "one_line": r["rationale"].split(".")[0] + ".",
        }
        for r in recs
    ]

    frozen_cand = candidate_metric(recs)
    frozen_cand_single = candidate_metric(recs, requirement_ids=["issue_refund::order_record_resolves"])
    # P3-D section 12 alternative form: "of the required foundational preconditions, how many have a KNOWN status?"
    n_foundational = sum(1 for r in recs if r["requirement_class"] == "FOUNDATIONAL_REQUIREMENT")
    n_foundational_with_status = sum(
        1 for r in recs if r["requirement_class"] == "FOUNDATIONAL_REQUIREMENT" and r.get("per_case")
    )
    per_requirement_observability = []
    for r in recs:
        pc = r.get("per_case", [])
        dist = Counter(x["requirement_state"] for x in pc)
        ev = Counter(x["evidence_state"] for x in pc)
        per_requirement_observability.append({
            "requirement_id": r["requirement_id"],
            "requirement_class": r["requirement_class"],
            "required": r["required"],
            "load_bearing": r["load_bearing"],
            "determinability": r["determinability"],
            "n_cases_observed": len(pc),
            "requirement_state_distribution": dict(sorted(dist.items())),
            "evidence_state_distribution": dict(sorted(ev.items())),
            "has_any_variation": len(set(x["requirement_state"] for x in pc)) > 1,
            "alt_reading_present_on_any_case": any("alt_reading" in x for x in pc),
            "counted_in_candidate_metric": r["requirement_id"] in frozen_cand["requirements_counted"],
        })

    metric_validity = {
        "candidate_definition": "satisfied load-bearing foundational preconditions / required load-bearing foundational preconditions (NOT_APPLICABLE excluded from the denominator)",
        "frozen_value": None,
        "frozen_value_note": (
            "N/A - zero requirements are non-degenerately assessable. Every FOUNDATIONAL_REQUIREMENT is either "
            "DETERMINABLE_BUT_DEGENERATE or NOT_ASSESSABLE, so there is no honest aggregate to report."
        ),
        "value_if_computed_anyway": {
            "single_requirement_order_record_resolves": frozen_cand_single["coverage"],
            "two_assessable_foundational_requirements": frozen_cand["coverage"],
            "note": "these two differ (86.7% vs 92.9%) only because the second requirement is always-satisfied - that gap IS the denominator-sensitivity problem, not a measurement.",
        },
        "p3d_section12_alternative_form": {
            "definition": "required foundational preconditions with a KNOWN status / required foundational preconditions",
            "value": round(n_foundational_with_status / n_foundational, 6) if n_foundational else None,
            "verdict": "also invalid - it measures how many requirements the reference author managed to assess (fixed by the authoring), not anything about ControlPlane. Same failure mode as the retired coverage_ratio (docs/retired-figures.md item 5).",
        },
        "frozen_breakdown": frozen_cand,
        "verdict": "INVALID",
        "reasons": [
            "R1 DEGENERATE: the only assessable load-bearing foundational requirement with any variation (order_record_resolves) has a per-case state that is a 1:1 recode of one corpus construction parameter (record_lookup_status). The aggregate value equals 1 - (record-unresolved slice fraction) by construction and cannot fail for a reason not baked into corpus sampling. This is the pattern docs/retired-figures.md item 2 retired.",
            "R2 UNEXERCISABLE HEADLINE EXAMPLE: currency_integrity - the second requirement P3-D leans on - is DORMANT on 30/30 cases (every tool call and every orders.db row is INR) and is ORDINARY_CLAIM-shaped by the boundary test, not foundational.",
            "R3 NON-COMPARABLE ACROSS TOOLS: issue_refund has 1 assessable requirement; tau2 has 0 assessable; send_document has 0. '100% (1/1)' and 'N/A (0/0)' are not the same kind of quantity.",
            "R4 DENOMINATOR NOT INDEPENDENTLY ENUMERABLE: P3-A never listed order_record_resolves; P3-B found it for issue_refund only, by construction. The candidate set is an open lower bound, so the denominator is not a fixed population.",
            "R5 MANIPULABLE: gaming tests B (remove the failing requirement -> 100%/N/A) and D (VIOLATED -> SATISFIED -> 100%) both move the metric with no change to case safety, and D is a defensible re-reading rather than an adversarial edit.",
            "R6 CATEGORY INCOHERENT: the 6 candidates split across FOUNDATIONAL_REQUIREMENT (3, one of them NOT_ASSESSABLE), ORDINARY_CLAIM (1), ACTION_VALIDITY_CHECK (1), UNCLEAR (1). A single ratio would average over structurally different things.",
        ],
        "what_is_valid_instead": "A deterministic per-requirement observability report (per_requirement_observability above) plus a per-case causal annotation on P1 unavailability (p1_x_foundational_matrix.per_case). Neither is a percentage.",
    }

    return {
        "task": "P3E_FOUNDATIONAL_REQUIREMENT_COVERAGE",
        "what_this_is": (
            "Falsification of the P3-D separate-foundational-layer recommendation and of a candidate "
            "foundational-requirement coverage percentage, over a frozen independently authored reference "
            "and the frozen 30-case P3-B issue_refund corpus. Deterministic; no model, no network."
        ),
        "frozen_reference_sha256": PINNED_REFERENCE_SHA256,
        "frozen_p3b_gold_sha256_untouched": p3b_sha,
        "frozen_clock": FROZEN_TODAY,
        "n_requirements": len(recs),
        "definition_of_foundational_requirement": json.loads(REF_META.read_text(encoding="utf-8"))["definition_of_foundational_requirement"],
        "boundary_test_results": boundary,
        "per_requirement_observability": per_requirement_observability,
        "degeneracy_proof": degeneracy_proof(recs, corpus),
        "candidate_metric_validity": metric_validity,
        "metric_gaming_tests": gaming_tests(recs),
        "cross_tool_comparability": cross_tool(recs),
        "p1_x_foundational_matrix": p1_matrix(recs, p1),
        "silent_pass": silent_pass(recs, p1),
        "second_annotator_cross_check": {
            "note": "P3-A UNREPRESENTABLE_REQUIRED and P3-B foundational_requirements[] were read only AFTER classification.",
            "P3A_lists_order_record_resolves": False,
            "P3B_order_record_resolves_status_rule": "SATISFIED if record_lookup_status==FOUND else VIOLATED (extraction_gold_build.py:672-692) - agrees case-for-case with the frozen reference",
            "P3B_currency_integrity": "DORMANT for all 30 - agrees the check is unexercised; P3-E additionally reclassifies it ORDINARY_CLAIM",
            "P3E_agreement_with_P3B_on_order_record_resolves_per_case": True,
        },
        "carried_forward_unchanged": [
            "approve_discount / AMOUNT_NOT_EXCEEDING_ORDER = NEEDS_HUMAN_DECISION",
            "tau2 / ORDER_BELONGS_TO_CUSTOMER = REQUIRED_BUT_UNREPRESENTABLE",
            "refund day-7 inclusion = AMBIGUOUS",
            "gs-145..150 post-window disposition = BLOCK|ESCALATE unresolved",
        ],
        "disposition": "COMPLETE - ARCHITECTURE VALID (descriptive-only, as P3-D Option B) BUT SINGLE COVERAGE PERCENTAGE INVALID",
        "reproduction_command": REPRO_CMD,
    }


# ==========================================================================
# 8. render
# ==========================================================================
def _pct(v):
    return "N/A" if v is None else f"{v * 100:.1f}%"


def _yn(b):
    return "yes" if b else "no"


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"


def render_markdown(report: dict) -> str:
    L: list[str] = []
    w = L.append
    mv = report["candidate_metric_validity"]
    sp = report["silent_pass"]
    dp = report["degeneracy_proof"]
    via = mv["value_if_computed_anyway"]

    w("# P3-E - foundational-requirement coverage: falsification of the P3-D architecture")
    w("")
    w("Harness: `bench/foundational_requirement_coverage.py` "
      "(regenerate with `python bench/foundational_requirement_coverage.py --write`). "
      "Section numbers 1-30 match the task's required-report checklist.")
    w("")
    w("Every line below is tagged: **[DRE]** direct repository evidence · **[BR]** benchmark result · "
      "**[AI]** architectural inference · **[REC]** recommendation.")
    w("")
    w("## 0. Headline")
    w("")
    w("- **[BR] A single foundational-requirement coverage percentage is INVALID for this evidence base.** "
      "No honest aggregate can be reported: every candidate foundational requirement is either "
      "`DETERMINABLE_BUT_DEGENERATE` or `NOT_ASSESSABLE`. Computed anyway it would read "
      f"{_pct(via['single_requirement_order_record_resolves'])} (one requirement) or "
      f"{_pct(via['two_assessable_foundational_requirements'])} (two) - and *that gap is the problem, not a result*.")
    w("- **[BR] R1 (decisive): the metric is degenerate.** `order_record_resolves` - the only assessable "
      "load-bearing foundational requirement with any variation - has a per-case state **bit-identical to the "
      f"corpus column `record_lookup_status`** ({_yn(dp['per_case_state_is_bit_identical_to_record_lookup_status'])}). "
      f"Any ratio over it equals `1 - {dp['n_record_unresolved']}/{dp['n_cases']}` = "
      f"{dp['candidate_coverage_equals_1_minus_slice_fraction']} by construction. `docs/retired-figures.md` item "
      "2 retired exactly this identity-not-measurement pattern.")
    w("- **[BR] R2: `currency_integrity`** - P3-D's second example - is DORMANT on 30/30 cases and is "
      "ORDINARY_CLAIM-shaped by the boundary test, not foundational.")
    w("- **[REC] The claim/precondition boundary itself survives falsification.** `order_record_resolves` fails "
      "every test for being a claim. A separate, **descriptive-only** foundational-precondition layer (P3-D "
      "Option B) is supported - as a per-case named line and causal annotation, **not** as a coverage %.")
    w(f"- **[BR] Silent-pass unchanged: {sp['structural_gap_count']} structural, {sp['realized_opportunity_count']} realized** "
      f"({', '.join('`'+c+'`' for c in sp['structural_gap_case_ids'])}). Matches P3-C.")
    w("")
    w(f"**Disposition: {report['disposition']}**")
    w("")

    # 1
    w("## 1. Scope")
    w("")
    w(report["what_this_is"])
    w("")
    w(f"- Frozen independent reference: `bench/foundational_requirement_reference_v1.jsonl` "
      f"(sha256 `{report['frozen_reference_sha256']}`), {report['n_requirements']} candidate requirements.")
    w("- Per-case corpus: the 30 frozen P3-B `issue_refund` cases (`bench/human_label_sample.csv`).")
    w(f"- P3-B gold sha256 `{report['frozen_p3b_gold_sha256_untouched']}` - asserted untouched, never read as input.")
    w(f"- Frozen clock `{report['frozen_clock']}`. No model, no network. Byte-identical output on repeat runs.")
    w("- Zero production files changed. `bench/extraction_gold_v1.jsonl` and the P3-C reports are not modified.")
    w("")

    # 2
    w("## 2. Research question")
    w("")
    w("> Can foundational requirements be independently defined and measured as a distinct population without "
      "creating a misleading or manipulable coverage metric? And does measuring this population add information "
      "beyond P1 verification coverage?")
    w("")
    w("**[BR] Answers:** the population can be *defined* and *listed*; it cannot be turned into a valid single "
      "percentage on this evidence base; and it adds information only as a *per-case causal annotation*, not as "
      "an aggregate number.")
    w("")

    # 3
    w("## 3. P3-D context")
    w("")
    w("P3-D (`docs/foundational-requirements-architecture-review.md`) recommended **Option B** - a separate "
      "foundational-precondition layer, descriptive first - over **Option A** (a new `ClaimKind`). It did not "
      "implement the layer and **hedged on a metric**: its section 12 left the ratio form open, and section 23 "
      "states 'no metric is invented'. P3-E tests both the separate-layer claim (section 28 here) and the "
      "concrete candidate ratio the task asks about (task section 21).")
    w("")
    w("**[DRE] P3-D internal inconsistency noted, non-material:** section 5 says `ClaimKind` has 15 members; "
      "section 8 and `controlplane/schema.py:153-178` say 12. The count is 12. This does not affect P3-D's "
      "argument or any number here.")
    w("")

    # 4
    w("## 4. Falsification methodology")
    w("")
    w("1. Author an independent reference (section 5) and **freeze it by sha256 before any measurement** "
      "(task section 20).")
    w("2. Classify every candidate against a reproducible boundary test (sections 7-8).")
    w("3. Compute the per-case requirement/evidence states the frozen corpus can exercise (sections 11-12); a "
      "self-consistency guard re-derives them from the raw facts and aborts on drift.")
    w("4. Compute the candidate ratio, then attack it: add / remove / duplicate / status-flip / evidence-flip / "
      "drop-dependency (section 23).")
    w("5. Cross-check against P1 verification coverage (sections 21, 25) and the P3-C silent-pass result "
      "(section 22).")
    w("6. Report the metric as INVALID if it fails, and emit a per-requirement observability table instead "
      "(sections 10-11, 15).")
    w("")

    # 5
    w("## 5. Independent reference methodology")
    w("")
    w("Authored **only** from: `docs/threat-model.md` threat ids; the refund/authority policy prose; the "
      "`ProposedAction` tool-argument schema; `docs/gold-set-annotation.md`; `bench/label.py` (an independent "
      "re-derivation of the refund rules that imports nothing from `controlplane.decide`/`predicates`/`ladder`/"
      "`ground`); `bench/human_label_sample.csv`; `bench/gold_set.jsonl` tool-call args; and `data/orders.db` "
      "as a fixture cross-check. Authored **without** `build_claims`/`classify_claims` output, the P1 ledger, "
      "any receipt, `decide()` output, cached `_ClaimedFields`, existing verification coverage, or "
      "`bench/extraction_gold_v1.jsonl` `foundational_requirements[]`. P3-A `UNREPRESENTABLE_REQUIRED` and P3-B "
      "`foundational_requirements[]` were read only *after* classification, as a second-annotator cross-check "
      "(Appendix A).")
    w("")

    # 6
    w("## 6. Definition of a foundational requirement")
    w("")
    w(report["definition_of_foundational_requirement"])
    w("")

    # 7
    w("## 7. Claim vs precondition boundary test")
    w("")
    w("| requirement | class | assert? | value-cmp? | resolver? | agent-attrib? | gates N claims | prerequisite? |")
    w("|---|---|:--:|:--:|:--:|:--:|--:|:--:|")
    for b in report["boundary_test_results"]:
        t = b["boundary_test"]
        w(f"| `{b['requirement_id'].split('::')[1]}` ({b['requirement_id'].split('::')[0]}) | {b['requirement_class']} | "
          f"{_yn(t['agent_can_assert_value'])} | {_yn(t['evaluated_by_value_comparison'])} | "
          f"{_yn(t['uses_normal_evidence_resolver'])} | {_yn(t['attributable_to_agent_assertion'])} | "
          f"{b['downstream_claims_gated_count']} | {_yn(t['prerequisite_for_interpreting_action'])} |")
    w("")
    w("**[BR] Only `order_record_resolves` and `order_record_fields_complete` pass every foundational test.** "
      "`currency_integrity` is asserted-and-value-compared (an ordinary claim missing a `ClaimKind`). "
      "`refund_amount_well_formed` needs no evidence and gates nothing (action validity). "
      "`independent_user_authentication` passes the test but has no evidence channel. "
      "`order_ownership_established` is a representable claim P3-A already counts as an unbound kind. "
      "**Four structurally different situations in a six-member candidate set.**")
    w("")

    # 8
    w("## 8. Action-validity boundary")
    w("")
    w("**[DRE]** `bench/label.py`'s own precedence chain interleaves three categories before it reaches ordinary "
      "claims: missing record (foundational, -> `UNVERIFIABLE`) -> blank load-bearing field (foundational, -> "
      "`SOURCE_UNRELIABLE`) -> currency mismatch (value comparison / ordinary-claim-shaped, -> `SOURCE_UNRELIABLE`) "
      "-> non-positive amount (action validity, -> `SOURCE_UNRELIABLE`). **[AI]** They are **not** one homogeneous "
      "'precondition layer' - the repo's own independent labeller distinguishes them by *verdict* and *order*, "
      "not by a separate status vocabulary. `refund_amount_well_formed` belongs in the existing "
      "Pydantic/enforcement path (threat T31), not a precondition layer. The action-validity boundary is real "
      "and does **not** sit inside the foundational set.")
    w("")

    # 9
    w("## 9. Requirement dependency analysis")
    w("")
    w("**[BR]** `order_record_resolves` gates exactly **4 of 7** `issue_refund` claims - "
      "`ORDER_BELONGS_TO_CUSTOMER`, `AMOUNT_NOT_EXCEEDING_ORDER`, `WITHIN_REFUND_WINDOW`, `ORDER_ATTRIBUTES_MATCH` "
      "(the claims on the `orders` resolver with `subject: action.order_id`). It does **not** gate "
      "`AMOUNT_WITHIN_AUTHORITY` (`authority` resolver), `POLICY_CLAUSE_CURRENT` or `CLAUSE_SEMANTICS_MATCH` "
      "(`policy` resolver). Confirmed empirically: in `gs-129` exactly those 4 claims resolve `UNAVAILABLE`.")
    w("")
    w("```")
    w("order_record_resolves")
    w("        |--> ORDER_BELONGS_TO_CUSTOMER")
    w("        |--> AMOUNT_NOT_EXCEEDING_ORDER      (one root failure, four UNAVAILABLE claims)")
    w("        |--> WITHIN_REFUND_WINDOW")
    w("        +--> ORDER_ATTRIBUTES_MATCH")
    w("```")
    w("")
    w("**[BR]** The requirement is counted **once**, never once per gated claim. Gaming test F confirms "
      "dropping a downstream dependency does not change the count. This is why task section 22 forbids "
      "weighting a coverage number by downstream-claim count - it would double-count one root failure.")
    w("")

    # 10
    w("## 10. Requirement universe")
    w("")
    w("| requirement | class | required | load-bearing | determinability | cases observed | state variation |")
    w("|---|---|:--:|:--:|---|--:|:--:|")
    for o in report["per_requirement_observability"]:
        w(f"| `{o['requirement_id'].split('::')[1]}` | {o['requirement_class']} | {_yn(o['required'])} | "
          f"{_yn(o['load_bearing'])} | {o['determinability']} | {o['n_cases_observed']} | {_yn(o['has_any_variation'])} |")
    w("")
    w("**[BR][limitation L-ENUMERATION]** This is a **lower bound, not a closed population**. P3-A never "
      "enumerated `order_record_resolves` for any tool; P3-B found it for `issue_refund` only, by construction. "
      "Absence from this list is not proof of absence - so the denominator of any coverage ratio is undefined "
      "(task stop condition: 'the denominator is ill-defined').")
    w("")

    # 11
    w("## 11. Status-state analysis")
    w("")
    w("| requirement | requirement_state distribution (over the 30 cases) |")
    w("|---|---|")
    for o in report["per_requirement_observability"]:
        if o["n_cases_observed"]:
            w(f"| `{o['requirement_id'].split('::')[1]}` | {o['requirement_state_distribution']} |")
    w("")
    w("**[BR]** Four states are authored (`SATISFIED` / `VIOLATED` / `NOT_ESTABLISHED` / `NOT_APPLICABLE`). "
      "On the frozen corpus:")
    w("")
    w("- **only `order_record_resolves` shows a load-bearing SATISFIED/VIOLATED split** (26 / 4).")
    w("- **the SATISFIED-vs-NOT_APPLICABLE and VIOLATED-vs-NOT_ESTABLISHED calls are judgement-laden.** "
      "P3-B marks the missing-record case `VIOLATED`; `bench/label.py` labels it `UNVERIFIABLE` and "
      "`docs/gold-set-annotation.md` frames `NO_MATCH` as 'we cannot check this' (i.e. `NOT_ESTABLISHED`). "
      "The frozen reference records `VIOLATED` with the alternative in `alt_reading`. Gaming test D shows the "
      "metric moves on this call - so this is not the objective status axis a coverage denominator needs.")
    w("- **is the P3-D four-state model sufficient?** For a *reference* it is adequate (it can express every "
      "situation the corpus and threat model raise). It is **not sufficient as a runtime enum** - see section 12.")
    w("")

    # 12
    w("## 12. Evidence-state analysis")
    w("")
    w("| requirement | evidence_state distribution (over the 30 cases) |")
    w("|---|---|")
    for o in report["per_requirement_observability"]:
        if o["n_cases_observed"]:
            w(f"| `{o['requirement_id'].split('::')[1]}` | {o['evidence_state_distribution']} |")
    w("")
    w("**[BR]** Requirement-state and evidence-state are genuinely different dimensions (task section 14: "
      "*missing evidence != violated requirement*). But two repository facts limit how far the distinction "
      "can be pushed:")
    w("")
    w("- **[DRE] the current runtime cannot represent either axis.** A missing row, a NULL load-bearing field, "
      "and an unreadable source all collapse to `Evidence(confidence=Confidence.NONE)` -> claim `UNAVAILABLE` "
      "-> verdict `SOURCE_UNRELIABLE`, `root_cause` `evidence_below_reliability_floor` "
      "(`controlplane/registry/orders.py:60-82`; `controlplane/decide.py:155-158, 311-329`; verified on "
      "`gs-129`). So `VIOLATED` vs `NOT_ESTABLISHED` is **not observable** in a receipt today.")
    w("- **[AI] for `order_record_resolves` the two axes partly collapse by definition** - the requirement "
      "*is* the statement 'authoritative evidence could be obtained'. Splitting status from evidence is "
      "artificial for exactly the requirement that most needs a separate layer.")
    w("")

    # 13
    w("## 13. Denominator analysis")
    w("")
    w(f"**Candidate definition:** {mv['candidate_definition']}")
    w("")
    w("**[BR] The denominator is not a fixed population:**")
    w("")
    w("- **not independently enumerable** (section 10): the candidate set is an open lower bound.")
    w("- **not stable under reasonable authoring choices**: including `order_record_fields_complete` (a genuine "
      f"foundational requirement, always SATISFIED here) moves the ratio from "
      f"{_pct(via['single_requirement_order_record_resolves'])} to "
      f"{_pct(via['two_assessable_foundational_requirements'])} (gaming test A).")
    w("- **manipulable downward**: removing `order_record_resolves` - the one requirement that ever fails - "
      "makes the ratio read 100% / N/A (gaming test B).")
    w("- **degenerate at its core**:")
    w("")
    w("```")
    for k, v in dp.items():
        w(f"{k}: {v}")
    w("```")
    w("")
    w("**[BR] The P3-D section-12 alternative form** (`required preconditions with a KNOWN status / required "
      f"preconditions` = {_pct(mv['p3d_section12_alternative_form']['value'])}) is **also invalid**: "
      f"{mv['p3d_section12_alternative_form']['verdict']}")
    w("")

    # 14
    w("## 14. Numerator analysis")
    w("")
    w("**[BR]** The numerator (`SATISFIED` observations) inherits every denominator problem plus its own: the "
      "`SATISFIED` count is a recode of `record_lookup_status == FOUND` for the one requirement that varies, "
      "and is a constant 26 (or 30) for the requirements that do not. Gaming tests D and E show the numerator "
      "moves under a status re-reading that is *defensible*, not adversarial. There is no numerator that "
      "depends on ControlPlane's runtime behaviour - unlike P1's `verified` count, which can fall if a "
      "resolver breaks.")
    w("")

    # 15
    w("## 15. Aggregate results")
    w("")
    w(f"**[BR] Verdict: {mv['verdict']}. No aggregate foundational-requirement coverage percentage is reported.** "
      f"{mv['frozen_value_note']}")
    w("")
    w("Reasons (full form):")
    w("")
    for reason in mv["reasons"]:
        w(f"- {reason}")
    w("")
    w(f"**[REC] What is valid instead:** {mv['what_is_valid_instead']} The per-requirement observability table "
      "(sections 10-12) and the per-case P1 x foundational table (section 16) are the aggregate artifacts. "
      "Task section 27 explicitly anticipates this outcome.")
    w("")

    # 16
    w("## 16. Per-case results (P1 x foundational)")
    w("")
    w("| case | P1 cov | P1 v/e | P1 interv | order_record_resolves | evidence_state | P1 UNAVAILABLE claim kinds |")
    w("|---|--:|--:|---|---|---|---|")
    for row in report["p1_x_foundational_matrix"]["per_case"]:
        uk = ", ".join(k.replace("_", " ") for k in row["p1_unavailable_claim_kinds"]) or "-"
        w(f"| `{row['case_id']}` | {_pct(row['p1_coverage'])} | {row['p1_verified_eligible']} | "
          f"{row['p1_intervention']} | {row['foundational_order_record_resolves']} | "
          f"{row['foundational_evidence_state']} | {uk} |")
    w("")
    w("**[DRE]** P1 coverage never reaches 100% on this corpus - `CLAUSE_SEMANTICS_MATCH` (tier C3) is "
      "`UNVERIFIED` in all 30 cases because grounding (`CP_GROUNDING`) is off. The empty `P1=100` rows in "
      "section 25 are that, not a foundational-requirement fact.")
    w("")

    # 17
    w("## 17. issue_refund analysis")
    w("")
    w("**[BR]** All 30 cases are `issue_refund`. 26 resolve a record (`order_record_resolves` SATISFIED), 4 do "
      "not (`gs-129/130/133/134`). `currency_integrity`, `order_record_fields_complete` and "
      "`refund_amount_well_formed` show **zero informative variation** on this corpus (respectively: no "
      "currency mismatch possible; no NULL fields in `data/orders.db`; every amount a positive integer). So "
      "the entire measurable foundational signal on the frozen corpus is **one bit per case, and that bit is "
      "`record_lookup_status`.**")
    w("")

    # 18
    w("## 18. Missing-record analysis (gs-129/130/133/134)")
    w("")
    w("**[DRE]** `record_lookup_status = NO_MATCH`; `data/orders.db` confirms no row. **[BR]** `decide()` -> "
      "4 claims `UNAVAILABLE` (`authoritative_lookup_empty`) -> `source_unreliable` AND `unverifiable` -> "
      "verdict `SOURCE_UNRELIABLE` -> `ESCALATE`. P1 coverage 2/7 (~28.6%). **[BR]** `bench/label.py` "
      "independently calls this `UNVERIFIABLE` / `ESCALATE` (recorded as `gold_verdict` in `gold_set.jsonl`).")
    w("")
    w("**[AI]** So there is genuine disagreement on whether the precondition is `VIOLATED` (a determinate "
      "breach: the query ran and returned zero rows) or `NOT_ESTABLISHED` (we could not check). The task warns "
      "against automatically reading a missing record as `VIOLATED`. The frozen reference uses `VIOLATED` "
      "(the query *did* run; a determinate negative), with `NOT_ESTABLISHED` attached as `alt_reading`. Either "
      "way the downstream `evidence_state` is `UNAVAILABLE` and the intervention is `ESCALATE` - the "
      "disagreement changes the metric (gaming test D) but not the gate outcome.")
    w("")

    # 19
    w("## 19. tau2 analysis")
    w("")
    w("**[DRE]** `independent_user_authentication` passes the foundational boundary test but has **no evidence "
      "channel** in the tau2 integration -> `NOT_ASSESSABLE`. `order_ownership_established` (tau2 "
      "`ORDER_BELONGS_TO_CUSTOMER`) is a **representable claim** that is merely **unbound**; P3-A "
      "`reports/manifest-claim-coverage.md` already counts it (tau2 manifests at 50%). **[REC]** Carry both "
      "forward unchanged: `tau2 / ORDER_BELONGS_TO_CUSTOMER = REQUIRED_BUT_UNREPRESENTABLE` (task sections 16, 34).")
    w("")
    w("**[AI]** *Conceptually representable* != *runtime assessable* (task section 16). tau2's requirements "
      "are perfectly expressible in the reference; the tau2 *integration* has no channel to assess them. A "
      "tau2 foundational-coverage % is `N/A (0/0)` - and folding `order_ownership_established` in would "
      "double-count a gap P3-A already measures.")
    w("")

    # 20
    w("## 20. Currency-integrity analysis")
    w("")
    w("**[BR]** Boundary test: `currency` is a structural `ProposedAction` field (assertable, `schema.py:230`), "
      "and `bench/label.py:183-189` checks it by **value comparison** to `data/orders.db.currency` - "
      "structurally identical to `ORDER_ATTRIBUTES_MATCH` (colour/category) and `ORDER_BELONGS_TO_CUSTOMER` "
      "(customer_id), both `ClaimKind`s. It gates no other claim; it is not a prerequisite for interpreting "
      "the action. **[REC] Classification: ORDINARY_CLAIM missing a `ClaimKind`, not a foundational "
      "requirement.**")
    w("")
    w("**[BR]** On the frozen corpus it is DORMANT 30/30 (every tool call and every `data/orders.db` row is "
      "INR). `gold_set.jsonl` `gs-136..140` (currency `USD`, records resolve) *would* exercise it - "
      "`bench/label.py` labels those `SOURCE_UNRELIABLE` - but they are outside the frozen P3-B corpus. "
      "**[DRE]** P3-D section 21 already flags this reclassification as an open modelling decision; P3-E does "
      "not resolve it, only classifies the shape.")
    w("")

    # 21
    w("## 21. P1 comparison")
    w("")
    w("**[BR]** For every case: P1 verification coverage, the `order_record_resolves` state, and the current "
      "intervention are in the section 16 table. Rolled up by the 2x2 of {P1 full / P1 partial} x "
      "{foundational SATISFIED / not}:")
    w("")
    for k, cell in report["p1_x_foundational_matrix"]["cells"].items():
        ids = ('(' + ', '.join('`'+c+'`' for c in cell['case_ids']) + ')') if cell['case_ids'] else ''
        w(f"- **{k}**: n={cell['n']} {ids}")
    w("")
    w("**[REC]** P1 is **not** the source of truth for foundational requirements; it is only a comparison. "
      "The one thing the foundational view adds on the 4 missing-record cases: it names the *single shared "
      "cause* of 4 of the 5 unverified claims.")
    w("")

    # 22
    w("## 22. Silent-pass relationship")
    w("")
    w(f"- structural gap: **{sp['structural_gap_count']}** ({', '.join('`'+c+'`' for c in sp['structural_gap_case_ids'])})")
    w(f"- realized opportunity: **{sp['realized_opportunity_count']}**")
    w(f"- matches P3-C: **{_yn(sp['matches_p3c'])}**")
    w("")
    w(f"**[BR]** {sp['does_the_foundational_layer_expose_the_gap_more_clearly_than_p1_alone']}")
    w("")
    w("**[REC]** Not a realized safety failure. For `issue_refund` a missing record forces >=4 of 7 "
      "load-bearing claims to `UNAVAILABLE`, so P1 cannot reach the >=80% silent-pass threshold on this tool - "
      "the structural gap is bounded, the realized risk is low, exactly as P3-C and P3-D already state.")
    w("")

    # 23
    w("## 23. Metric-gaming tests")
    w("")
    w("| test | action | before | after | metric moved | case safety changed? | finding |")
    w("|---|---|--:|--:|:--:|:--:|---|")
    for t in report["metric_gaming_tests"]:
        w(f"| {t['test']} | {t['action']} | {_pct(t['before'])} | {_pct(t['after'])} | "
          f"{_yn(t['metric_changed'])} | {_yn(t['should_case_safety_have_changed'])} | {t['finding']} |")
    w("")
    w("**[BR]** Tests A, B, D, E move the metric with no change to case safety. B (remove the failing "
      "requirement) and D (a defensible `VIOLATED`->`NOT_ESTABLISHED`->`SATISFIED` re-reading) are the "
      "serious ones: the first is denominator manipulation nothing prevents, the second is not even an "
      "adversarial edit. C and F confirm counting-once is implemented correctly.")
    w("")

    # 24
    w("## 24. Cross-tool comparability")
    w("")
    ct = report["cross_tool_comparability"]
    for fam, b in ct["by_family"].items():
        w(f"- **{fam}**: foundational={b['foundational'] or '-'}; assessable={b['assessable'] or '-'}; "
          f"not_assessable={b['not_assessable'] or '-'}; other={b['other_class'] or '-'}")
    w("")
    w(f"**[DRE]** {ct['send_document_negative_control']}")
    w("")
    w(f"**[BR]** {ct['finding']} No severity, business-value, or downstream-claim weighting is applied "
      "(task section 22).")
    w("")

    # 25
    w("## 25. P1 x foundational interpretation matrix")
    w("")
    for k, v in report["p1_x_foundational_matrix"]["interpretation"].items():
        w(f"- **{k}** - {v}")
    w("")
    w("**[REC]** Neither number is 'overall safety', a correctness guarantee, a risk guarantee, or a "
      "probability of correctness. No combined score is computed (task section 26).")
    w("")

    # 26
    w("## 26. Limitations")
    w("")
    for lim in json.loads(REF_META.read_text(encoding="utf-8"))["limitations"]:
        w(f"- {lim}")
    w("- L-P1-CROSSCHECK: the P1 numbers come from `bench.baselines` `action_from_case` (deterministic "
      "`claimed_*` reconstruction, 'extraction noise = 0'), not the LLM extractor - the same basis P3-C uses.")
    w("- L-NO-RUNTIME-CHANGE: this benchmark does not and must not change `decide()`, the ledger, or any "
      "receipt; the runtime's inability to represent the two-axis model is reported, not fixed.")
    w("- L-SINGLE-AUTHOR: one classification pass with a boundary test, cross-checked against P3-A/P3-B after "
      "the fact (Appendix A). Not a multi-annotator study of the classifications themselves.")
    w("")

    # 27
    w("## 27. Falsification findings")
    w("")
    w("| # | finding | outcome |")
    w("|---|---|:--:|")
    w("| F1 | the candidate coverage % is a 1:1 recode of one corpus construction parameter (`record_lookup_status`) | **supported** |")
    w("| F2 | P3-D's second example (`currency_integrity`) is unexercisable on the corpus and ordinary-claim-shaped | **supported** |")
    w("| F3 | the candidate category is incoherent - 4 structural situations across 6 members | **supported** |")
    w("| F4 | the denominator is not independently enumerable to completeness | **supported** |")
    w("| F5 | the metric is manipulable via denominator (test B) and via a defensible status re-reading (test D) | **supported** |")
    w("| F6 | the metric is not comparable across tools | **supported** |")
    w("| F7 | `order_record_resolves` is genuinely NOT a claim (P3-D's core boundary claim) | **confirmed - survives falsification** |")
    w("| F8 | a separate descriptive precondition *layer* is justified; a single coverage *percentage* is not | **supported** |")
    w("")

    # 28
    w("## 28. Recommendation")
    w("")
    w("**[REC]**")
    w("")
    w("1. **Keep the claim/precondition distinction P3-D drew.** `order_record_resolves` is not a claim; naming "
      "it as a distinct per-case precondition line is a real auditability gain over inferring it from 4 "
      "`UNAVAILABLE` claims plus a verdict (`SOURCE_UNRELIABLE`) and `root_cause` "
      "(`evidence_below_reliability_floor`) that both point at 'bad data' rather than 'absent record'.")
    w("2. **Do not build a foundational-requirement coverage percentage.** It is degenerate, denominator- "
      "and status-manipulable, non-comparable across tools, and its population is an open lower bound. This is "
      "the trap `docs/retired-figures.md` documents five times ('a benchmark that cannot fail is worth less "
      "than no benchmark').")
    w("3. **If anything ships, ship a per-case causal annotation** on the existing P1 ledger / receipt: 'these "
      "N claims are `UNAVAILABLE` because precondition `order_record_resolves` was not satisfied', plus a "
      "corrected `root_cause` (e.g. `order_record_unresolved`). Descriptive, unweighted, per-case, cannot be "
      "gamed by adding or removing list entries. This is a design recommendation, not a change made here.")
    w("4. **Reclassify `currency_integrity`** out of the foundational set - it is an ordinary claim awaiting a "
      "`ClaimKind` (a modelling decision, carried forward, not resolved here).")
    w("5. **Keep tau2 identity as `REQUIRED_BUT_UNREPRESENTABLE`**, measured by P3-A's kind-coverage, not "
      "double-counted here.")
    w("")

    # 29
    w("## 29. Whether production implementation is justified")
    w("")
    w("**[REC] Partially.** A read-only, descriptive per-case precondition annotation (recommendation 3) is "
      "justified as an observability improvement and matches the P1 discipline (descriptive first, no verdict "
      "feedback). A `FoundationalRequirement` production type *with its own coverage denominator* is **not** "
      "justified by this evidence: the denominator cannot be made honest. No production code is changed by "
      "P3-E; the recommendation is for a future, separately-reviewed task.")
    w("")

    # 30
    w("## 30. Exact reproduction command")
    w("")
    w("```")
    w(REPRO_CMD)
    w("```")
    w("")
    w("`--check` verifies the committed report/JSON are byte-identical to a fresh run. The benchmark "
      "re-hashes the frozen reference and the P3-B gold on every run and aborts on drift.")
    w("")

    # Appendix
    w("## Appendix A. Second-annotator cross-check (P3-A / P3-B, read after classification)")
    w("")
    sc = report["second_annotator_cross_check"]
    for k, v in sc.items():
        w(f"- `{k}`: {v}")
    w("")
    w("## Appendix B. Carried-forward decisions (unchanged by P3-E)")
    w("")
    for c in report["carried_forward_unchanged"]:
        w(f"- {c}")
    w("")
    return "\n".join(L) + "\n"


# ==========================================================================
# 9. main
# ==========================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write reports/foundational-requirement-coverage-v1.{md,json}")
    ap.add_argument("--check", action="store_true", help="fail if the committed report/json would change")
    args = ap.parse_args()

    report = build_report()
    want_md = render_markdown(report)
    want_js = render_json(report)

    if args.check:
        drift = []
        if not MD_PATH.exists() or MD_PATH.read_text(encoding="utf-8") != want_md:
            drift.append(MD_PATH.name)
        if not JSON_PATH.exists() or JSON_PATH.read_text(encoding="utf-8") != want_js:
            drift.append(JSON_PATH.name)
        if drift:
            print("DRIFT: " + ", ".join(drift), file=sys.stderr)
            raise SystemExit(1)
        print("no drift")
        return

    mv = report["candidate_metric_validity"]
    print(json.dumps({
        "disposition": report["disposition"],
        "candidate_metric_verdict": mv["verdict"],
        "frozen_candidate_value": mv["frozen_value"],
        "value_if_computed_anyway": mv["value_if_computed_anyway"],
        "degeneracy_recode_confirmed": report["degeneracy_proof"]["per_case_state_is_bit_identical_to_record_lookup_status"],
        "silent_pass": {
            "structural": report["silent_pass"]["structural_gap_count"],
            "realized": report["silent_pass"]["realized_opportunity_count"],
        },
        "gaming_tests_that_moved_the_metric": [t["test"] for t in report["metric_gaming_tests"] if t["metric_changed"]],
    }, indent=2))
    if args.write:
        REPORTS.mkdir(exist_ok=True)
        MD_PATH.write_text(want_md, encoding="utf-8", newline="\n")
        JSON_PATH.write_text(want_js, encoding="utf-8", newline="\n")
        print(f"\nwrote {MD_PATH.relative_to(ROOT)} and {JSON_PATH.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
