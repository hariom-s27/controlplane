#!/usr/bin/env python3
"""P3-B — loader + internal-consistency validator for the extraction gold corpus.

    python bench/extraction_gold.py                # validate + print a summary
    python bench/extraction_gold.py --json          # the summary as JSON

The corpus itself is ``bench/extraction_gold_v1.jsonl`` (built by
``bench/extraction_gold_build.py``). This module is the read side: it loads
the corpus, and ``validate()`` runs the quality-control checks
(``docs/extraction-gold-annotation.md`` §quality-control) that
``tests/test_extraction_gold_v1.py`` asserts and that a future
extraction-vs-gold benchmark can call before it starts.

Independence: this module imports nothing from ``controlplane`` — not even
``schema``. The ClaimKind vocabulary is pinned here as ``CLAIM_KINDS`` and
``tests/test_extraction_gold_v1.py`` cross-checks it against
``controlplane.schema.ClaimKind`` so a drift is caught without making the
corpus a function of the system it will later be compared against.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
JSONL = BENCH / "extraction_gold_v1.jsonl"
META = BENCH / "extraction_gold_v1.meta.json"
FLAT = BENCH / "extraction_gold_v1.flat.csv"
SOURCE_CSV = BENCH / "human_label_sample.csv"

# The ClaimKind names the corpus is allowed to use. Pinned here (not imported)
# for independence; tests/test_extraction_gold_v1.py asserts this equals
# {k.name for k in controlplane.schema.ClaimKind}.
CLAIM_KINDS = frozenset({
    "WITHIN_REFUND_WINDOW", "AMOUNT_WITHIN_AUTHORITY", "ORDER_BELONGS_TO_CUSTOMER",
    "AMOUNT_NOT_EXCEEDING_ORDER", "POLICY_CLAUSE_CURRENT", "CLAUSE_SEMANTICS_MATCH",
    "ORDER_ATTRIBUTES_MATCH", "ORDER_STATUS_SUPPORTS_ACTION",
    "RECIPIENT_ENTITLED_TO_DOC", "EXCERPT_CONTAINS_THIRD_PARTY_PII",
    "DOC_CLASSIFICATION_PERMITTED", "CUSTOMER_INTENT",
})

ASSERTION_VALUES = frozenset({
    "HOLDS", "VIOLATED", "AMBIGUOUS", "UNVERIFIABLE", "NOT_DETERMINABLE_FROM_CORPUS",
})
SUITABILITY_VALUES = frozenset({"SUITABLE", "SUITABLE_WITH_NOTE", "EXCLUDED"})
GATE_VALUES = frozenset({"ALLOW", "BLOCK", "ESCALATE", "AMBIGUOUS", "BLOCK|ESCALATE"})

# tokens allowed as a source_basis prefix / value
_BASIS_OK_PREFIX = ("csv:", "tool-args:", "threat-model:T", "extraction-reference-v1:")
_BASIS_OK_EXACT = frozenset({"docs/gold-set-annotation.md"})

# fields a gold claim must never cite (would break independence)
_FORBIDDEN_IN_BASIS = ("gold_label", "gold_verdict", "gold_intervention", "label_rationale",
                       "slice", "claim_bindings", "holdout", "human_label", "human_notes",
                       "verification_ledger", "_ClaimedFields", "decide(")


class CorpusError(AssertionError):
    """An internal-consistency failure in the frozen corpus."""


def load() -> list[dict]:
    return [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_meta() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


def source_csv_ids() -> list[str]:
    text = SOURCE_CSV.read_text(encoding="utf-8-sig")
    return [r["case_id"] for r in csv.DictReader(text.splitlines()) if (r.get("case_id") or "").strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(records: list[dict] | None = None, meta: dict | None = None) -> list[str]:
    """Return [] if the corpus is internally consistent, else a list of problems.

    Checks (docs/extraction-gold-annotation.md §quality-control):
      QC1  every case_id exists in the source sheet, set + order identical
      QC2  the source sheet is byte-identical to the sha256 pinned in the meta
      QC3  every claim_kind is a real ClaimKind name
      QC4  every expected_assertion / suitability / gate value is in range
      QC5  no duplicate claim_id within a case
      QC6  every claim has required=true, a non-empty rationale and source_basis
      QC7  every source_basis token is from the controlled vocabulary and
           names none of the forbidden (circularity) fields
      QC8  AMBIGUOUS cases carry the ambiguity on a claim and in unresolved_policy
      QC9  claim_set_complete is true and the 7 issue_refund kinds are all present
      QC10 the flat CSV is row-consistent with the JSONL
      QC11 EXCLUDED cases (if any) carry a suitability_note explaining the exclusion
      QC12 a load_bearing VIOLATED/UNVERIFIABLE claim's case gate is not ALLOW
    """
    records = records if records is not None else load()
    meta = meta if meta is not None else load_meta()
    problems: list[str] = []

    def bad(msg: str) -> None:
        problems.append(msg)

    # QC1 -----------------------------------------------------------------
    corpus_ids = [r["case_id"] for r in records]
    sheet_ids = source_csv_ids()
    if corpus_ids != sheet_ids:
        bad(f"QC1 case_id list/order differs from {SOURCE_CSV.name}: "
            f"corpus={corpus_ids[:3]}… sheet={sheet_ids[:3]}…")

    # QC2 -----------------------------------------------------------------
    pinned = meta.get("source_corpus", {}).get("sha256")
    actual = sha256(SOURCE_CSV)
    if pinned != actual:
        bad(f"QC2 {SOURCE_CSV.name} sha256 {actual} != pinned {pinned} — the base sheet moved; "
            "regenerate the corpus and re-freeze deliberately")

    # QC3–QC9, QC12 -----------------------------------------------------
    ISSUE_REFUND_KINDS = {
        "ORDER_BELONGS_TO_CUSTOMER", "AMOUNT_NOT_EXCEEDING_ORDER", "WITHIN_REFUND_WINDOW",
        "AMOUNT_WITHIN_AUTHORITY", "POLICY_CLAUSE_CURRENT", "CLAUSE_SEMANTICS_MATCH",
        "ORDER_ATTRIBUTES_MATCH",
    }
    for r in records:
        cid = r["case_id"]
        if r.get("suitability") not in SUITABILITY_VALUES:
            bad(f"QC4 {cid}: suitability {r.get('suitability')!r}")
        if r.get("independent_gate_outcome") not in GATE_VALUES:
            bad(f"QC4 {cid}: gate {r.get('independent_gate_outcome')!r}")
        if r.get("suitability") == "EXCLUDED" and not r.get("suitability_note"):
            bad(f"QC11 {cid}: EXCLUDED with no suitability_note")

        claims = r.get("gold_claims", [])
        ids = [c["claim_id"] for c in claims]
        if len(ids) != len(set(ids)):
            bad(f"QC5 {cid}: duplicate claim_id")
        if not r.get("claim_set_complete"):
            bad(f"QC9 {cid}: claim_set_complete is not true")
        kinds = {c["claim_kind"] for c in claims}
        if r.get("tool") == "issue_refund" and kinds != ISSUE_REFUND_KINDS:
            bad(f"QC9 {cid}: issue_refund kinds {sorted(kinds)} != the 7 required")

        gate = r.get("independent_gate_outcome")
        for c in claims:
            k = c["claim_kind"]
            if k not in CLAIM_KINDS:
                bad(f"QC3 {cid}/{k}: not a ClaimKind name")
            if c.get("expected_assertion") not in ASSERTION_VALUES:
                bad(f"QC4 {cid}/{k}: expected_assertion {c.get('expected_assertion')!r}")
            if c.get("required") is not True:
                bad(f"QC6 {cid}/{k}: required is not true")
            if not (c.get("rationale") or "").strip():
                bad(f"QC6 {cid}/{k}: empty rationale")
            sb = c.get("source_basis") or []
            if not sb:
                bad(f"QC6 {cid}/{k}: empty source_basis")
            for tok in sb:
                if not (tok in _BASIS_OK_EXACT or tok.startswith(_BASIS_OK_PREFIX)):
                    bad(f"QC7 {cid}/{k}: source_basis token {tok!r} not in the controlled vocabulary")
            blob = json.dumps({"rationale": c.get("rationale"), "source_basis": sb,
                               "assertion_basis": c.get("assertion_basis")})
            for f in _FORBIDDEN_IN_BASIS:
                if f in blob:
                    bad(f"QC7 {cid}/{k}: claim basis mentions forbidden field {f!r} (circularity)")
            if (c.get("load_bearing") and c.get("expected_assertion") in ("VIOLATED", "UNVERIFIABLE")
                    and gate == "ALLOW"):
                bad(f"QC12 {cid}/{k}: load-bearing {c['expected_assertion']} but case gate is ALLOW")

        # QC8
        has_ambig_claim = any(c.get("expected_assertion") == "AMBIGUOUS" for c in claims)
        if gate == "AMBIGUOUS" and not has_ambig_claim:
            bad(f"QC8 {cid}: gate AMBIGUOUS but no claim carries expected_assertion=AMBIGUOUS")
        if has_ambig_claim and not r.get("unresolved_policy"):
            bad(f"QC8 {cid}: a claim is AMBIGUOUS but unresolved_policy is empty")

    # QC10 ---------------------------------------------------------------
    if FLAT.exists():
        flat = list(csv.DictReader(FLAT.read_text(encoding="utf-8").splitlines()))
        flat_ids = [row["claim_id"] for row in flat]
        jsonl_ids = [c["claim_id"] for r in records for c in r["gold_claims"]]
        if flat_ids != jsonl_ids:
            bad("QC10 flat CSV claim_id order/content differs from the JSONL "
                "(regenerate with bench/extraction_gold_build.py)")

    return problems


def summary(records: list[dict] | None = None) -> dict:
    records = records if records is not None else load()
    by_suit: dict[str, int] = {}
    by_class: dict[str, int] = {}
    by_gate: dict[str, int] = {}
    by_assertion: dict[str, int] = {}
    lb_violated = 0
    for r in records:
        by_suit[r["suitability"]] = by_suit.get(r["suitability"], 0) + 1
        by_class[r["difficulty_class"]] = by_class.get(r["difficulty_class"], 0) + 1
        by_gate[r["independent_gate_outcome"]] = by_gate.get(r["independent_gate_outcome"], 0) + 1
        for c in r["gold_claims"]:
            by_assertion[c["expected_assertion"]] = by_assertion.get(c["expected_assertion"], 0) + 1
            if c["load_bearing"] and c["expected_assertion"] in ("VIOLATED", "UNVERIFIABLE"):
                lb_violated += 1
    return {
        "n_cases": len(records),
        "n_gold_claims": sum(len(r["gold_claims"]) for r in records),
        "by_suitability": dict(sorted(by_suit.items())),
        "by_difficulty_class": dict(sorted(by_class.items())),
        "by_independent_gate_outcome": dict(sorted(by_gate.items())),
        "by_expected_assertion": dict(sorted(by_assertion.items())),
        "load_bearing_violated_or_unverifiable_claims": lb_violated,
        "jsonl_sha256": sha256(JSONL),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    records = load()
    problems = validate(records)
    s = summary(records)
    if args.json:
        print(json.dumps({"valid": not problems, "problems": problems, "summary": s}, indent=2))
    else:
        print(f"bench/extraction_gold_v1.jsonl — {s['n_cases']} cases, {s['n_gold_claims']} gold claims")
        print(f"  sha256 {s['jsonl_sha256']}")
        print(f"  suitability   {s['by_suitability']}")
        print(f"  gate outcome  {s['by_independent_gate_outcome']}")
        print(f"  assertions    {s['by_expected_assertion']}")
        print(f"  load-bearing VIOLATED/UNVERIFIABLE claims: {s['load_bearing_violated_or_unverifiable_claims']}")
        if problems:
            print("\nINVALID:")
            for p in problems:
                print(f"  - {p}")
        else:
            print("\nvalid — all internal-consistency checks pass")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
