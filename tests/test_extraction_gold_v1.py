"""P3-B — the independent per-action extraction gold corpus.

`bench/extraction_gold_v1.jsonl` states, per proposed `issue_refund` action,
the load-bearing checks a correct verifier must represent. If the generator
could import `controlplane` extraction/decision code or read the manifests,
the holdout, or the construction `slice`, the corpus would be a restatement
of the system it will later be compared against — the circularity
`docs/experiment-audit.md` retired for P01 and
`tests/test_label_independence.py` / `tests/test_extraction_reference.py`
guard elsewhere.

This suite checks: AST independence of both P3-B modules; the frozen corpus
against its JSON Schema; every internal-consistency rule in
`bench/extraction_gold.py::validate`; byte-determinism of the generator; and
that the base sheets are untouched.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BENCH))

import extraction_gold as eg  # noqa: E402
from controlplane.schema import ClaimKind  # noqa: E402  (test-only vocabulary cross-check)

BUILD_PY = BENCH / "extraction_gold_build.py"
GOLD_PY = BENCH / "extraction_gold.py"
JSONL = BENCH / "extraction_gold_v1.jsonl"
META = BENCH / "extraction_gold_v1.meta.json"
SCHEMA = BENCH / "extraction_gold_v1.schema.json"
CSV = BENCH / "human_label_sample.csv"

# Freeze tripwire. Update ONLY with a deliberate re-annotation + a note in
# docs/extraction-gold-annotation.md. `bench/extraction_gold_build.py --check`
# must pass whenever this changes.
PINNED_JSONL_SHA256 = "79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d"

# committed blobs of the base sheets — the corpus must not have edited them
BASE_UNTOUCHED = {
    "bench/human_label_sample.csv": "c58a3ed172458e9cd25b2a0267f51a037ce2f7d653b7acb13aa7c15049e84550",
    "bench/gold_set.jsonl": "09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e",
    "bench/ground_truth_holdout.jsonl": "204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb",
}


# --------------------------------------------------------------------------
# independence — AST, mirrors tests/test_extraction_reference.py
# --------------------------------------------------------------------------
def _imported_modules(src: str) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


_READ_METHODS = {"read_text", "read_bytes", "open", "read", "load", "safe_load", "glob", "iterdir"}


def _module_path_constants(src: str) -> dict[str, str]:
    """name -> the trailing string literal of a module-level Path assignment,
    e.g. CSV_PATH = BENCH / "human_label_sample.csv"  ->  {"CSV_PATH": "human_label_sample.csv"}."""
    out: dict[str, str] = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            while isinstance(v, ast.BinOp) and isinstance(v.op, ast.Div):
                if isinstance(v.right, ast.Constant) and isinstance(v.right.value, str):
                    out[node.targets[0].id] = v.right.value
                v = v.left
    return out


def _read_call_targets(src: str) -> set[str]:
    """String literals and Path-constant names that are the receiver/argument
    of a file-reading call (x.read_text(), open("y"), yaml.safe_load(z))."""
    consts = _module_path_constants(src)
    hits: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else None)
        if name not in _READ_METHODS:
            continue
        # receiver of a method call: x.read_text()
        if isinstance(fn, ast.Attribute):
            recv = fn.value
            if isinstance(recv, ast.Name):
                hits.add(consts.get(recv.id, recv.id))
            elif isinstance(recv, ast.Constant) and isinstance(recv.value, str):
                hits.add(recv.value)
        # positional args: open("x"), yaml.safe_load(path.read_text())
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                hits.add(a.value)
            elif isinstance(a, ast.Name):
                hits.add(consts.get(a.id, a.id))
    return hits


@pytest.mark.parametrize("mod", [BUILD_PY, GOLD_PY])
def test_p3b_modules_import_nothing_from_controlplane(mod):
    cp = sorted(m for m in _imported_modules(mod.read_text(encoding="utf-8"))
                if m == "controlplane" or m.startswith("controlplane."))
    assert not cp, f"{mod.name} imports {cp} — the corpus must not be a function of the system under test"


@pytest.mark.parametrize("mod", [BUILD_PY, GOLD_PY])
def test_p3b_modules_only_import_stdlib(mod):
    mods = _imported_modules(mod.read_text(encoding="utf-8"))
    extra = mods - {"__future__", "argparse", "csv", "hashlib", "io", "json", "re", "sys",
                    "datetime", "pathlib"}
    assert not extra, f"{mod.name} has unexpected imports: {sorted(extra)}"


@pytest.mark.parametrize("mod", [BUILD_PY, GOLD_PY])
def test_p3b_modules_read_no_forbidden_file(mod):
    """AST-level: no file-reading call in either module targets a manifest, the
    holdout, an extract fixture, gold_set.jsonl, orders.db or a policy store."""
    targets = _read_call_targets(mod.read_text(encoding="utf-8"))
    forbidden_substr = ("manifest", "ground_truth_holdout", "gold_set", "orders.db",
                        "policy_store", "fixtures/extract", "fixtures\\extract", ".yaml")
    bad = sorted(t for t in targets if any(s in t for s in forbidden_substr))
    assert not bad, f"{mod.name} reads {bad} — see docs/extraction-gold-annotation.md §3"


def test_build_reads_only_the_base_csv():
    targets = _read_call_targets(BUILD_PY.read_text(encoding="utf-8"))
    file_like = sorted(t for t in targets if "." in t and "/" not in t and t.endswith((".csv", ".json", ".jsonl")))
    # the generator's only *input* file is the base sheet; the 4 artifacts it
    # also names are outputs (write_bytes) / its own --check re-read.
    assert "human_label_sample.csv" in targets
    assert all(t.startswith("extraction_gold_v1") or t == "human_label_sample.csv" for t in file_like), file_like


def test_generator_docstring_states_the_independence_rule():
    doc = ast.get_docstring(ast.parse(BUILD_PY.read_text(encoding="utf-8"))) or ""
    assert "HARD INDEPENDENCE CONSTRAINT" in doc
    assert "claim_bindings" in doc  # names what is excluded


# --------------------------------------------------------------------------
# vocabulary — the pinned CLAIM_KINDS equals the real enum
# --------------------------------------------------------------------------
def test_claim_kind_vocabulary_matches_the_enum():
    assert eg.CLAIM_KINDS == {k.name for k in ClaimKind}, (
        "bench/extraction_gold.py CLAIM_KINDS has drifted from controlplane.schema.ClaimKind"
    )


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------
def test_every_record_matches_the_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for rec in eg.load():
        errs = sorted(validator.iter_errors(rec), key=lambda e: e.path)
        assert not errs, f"{rec['case_id']}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errs[:4])


# --------------------------------------------------------------------------
# internal consistency — every QC rule
# --------------------------------------------------------------------------
def test_corpus_passes_all_internal_consistency_checks():
    problems = eg.validate()
    assert not problems, "\n".join(problems)


def test_case_ids_match_the_source_sheet_set_and_order():
    assert [r["case_id"] for r in eg.load()] == eg.source_csv_ids()


def test_thirty_cases_two_hundred_ten_claims():
    recs = eg.load()
    assert len(recs) == 30
    assert sum(len(r["gold_claims"]) for r in recs) == 30 * 7


def test_suitability_split_is_18_12_0():
    s = eg.summary()["by_suitability"]
    assert s == {"SUITABLE": 18, "SUITABLE_WITH_NOTE": 12}
    assert "EXCLUDED" not in s


def test_ambiguous_window_is_preserved_not_resolved():
    for r in eg.load():
        if r["case_id"] in {"gs-141", "gs-142", "gs-143", "gs-144"}:
            win = next(c for c in r["gold_claims"] if c["claim_kind"] == "WITHIN_REFUND_WINDOW")
            assert win["expected_assertion"] == "AMBIGUOUS"
            assert r["independent_gate_outcome"] == "AMBIGUOUS"
            assert r["unresolved_policy"]


def test_multi_violation_case_keeps_two_distinct_violated_claims():
    r = next(r for r in eg.load() if r["case_id"] == "gs-093")
    violated = {c["claim_kind"] for c in r["gold_claims"] if c["expected_assertion"] == "VIOLATED"}
    assert violated == {"WITHIN_REFUND_WINDOW", "AMOUNT_WITHIN_AUTHORITY"}
    for c in r["gold_claims"]:
        if c["claim_kind"] in violated:
            assert "merge" in c["decomposition_note"].lower() or "distinct" in c["decomposition_note"].lower()


def test_stale_policy_case_violates_both_clause_claims_on_the_clause_subject():
    r = next(r for r in eg.load() if r["case_id"] == "gs-088")
    for kind in ("POLICY_CLAUSE_CURRENT", "CLAUSE_SEMANTICS_MATCH"):
        c = next(c for c in r["gold_claims"] if c["claim_kind"] == kind)
        assert c["expected_assertion"] == "VIOLATED"
        assert c["subject"] == "clause:refund_window"
        assert c["subject_note"]  # flags the L7 order-id fallback trap


def test_no_match_cases_escalate_and_mark_the_missing_record():
    for r in eg.load():
        if r["action"]["record_lookup_status"] == "NO_MATCH":
            assert r["independent_gate_outcome"] == "ESCALATE"
            fr = next(f for f in r["foundational_requirements"] if f["id"] == "order_record_resolves")
            assert fr["status"] == "VIOLATED"
            order_scoped = [c for c in r["gold_claims"]
                            if c["claim_kind"] in {"ORDER_BELONGS_TO_CUSTOMER", "WITHIN_REFUND_WINDOW",
                                                   "AMOUNT_NOT_EXCEEDING_ORDER", "ORDER_ATTRIBUTES_MATCH"}]
            assert all(c["expected_assertion"] == "UNVERIFIABLE" for c in order_scoped)


def test_cross_reference_is_never_cited_by_a_gold_claim():
    for r in eg.load():
        for c in r["gold_claims"]:
            blob = json.dumps(c).lower()
            for forbidden in ("human_label", "human_notes", "cross_reference", "gold_label"):
                assert forbidden not in blob, f"{c['claim_id']} cites {forbidden}"


def test_independent_gate_outcome_agrees_with_human_label_where_determinate():
    """Disclosure check — the independent annotation must not contradict the
    existing gate-intervention labels except in the one documented zone."""
    for r in eg.load():
        indep, human = r["independent_gate_outcome"], r["cross_reference"]["human_label"]
        if indep == "BLOCK|ESCALATE":
            assert human in {"BLOCK", "ESCALATE"}  # gs-145..150 — label.py says AMBIGUOUS
        else:
            assert indep == human, f"{r['case_id']}: independent {indep} vs human {human}"


# --------------------------------------------------------------------------
# freeze + determinism
# --------------------------------------------------------------------------
def test_jsonl_matches_the_pinned_sha256():
    actual = hashlib.sha256(JSONL.read_bytes()).hexdigest()
    assert actual == PINNED_JSONL_SHA256, (
        f"corpus sha256 {actual} != pinned {PINNED_JSONL_SHA256}. If this change is "
        "intentional, update PINNED_JSONL_SHA256 and docs/extraction-gold-annotation.md."
    )
    assert eg.load_meta()["sha256"]["extraction_gold_v1.jsonl"] == actual


def test_generator_is_byte_deterministic():
    r = subprocess.run([sys.executable, str(BUILD_PY), "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"extraction_gold_build.py --check reported drift:\n{r.stdout}\n{r.stderr}"


# --------------------------------------------------------------------------
# the base sheets are untouched
# --------------------------------------------------------------------------
@pytest.mark.parametrize("rel,sha", sorted(BASE_UNTOUCHED.items()))
def test_base_sheets_are_byte_identical(rel, sha):
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, (
        f"{rel} changed — P3-B must not modify the base corpus or the gold set"
    )
