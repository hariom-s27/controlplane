"""Integrity record v2 (P05 V6, V7; PR-02).

Checks the live files against docs/m1-integrity-v2.sha256, which hashes text files
LF-normalised so CRLF and LF checkouts agree. Also verifies the latency evidence
pack's SHA256SUMS (raw bytes). Needs no .git: runs on an archive copy.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import integrity_record as IR  # noqa: E402

RECORD = ROOT / "docs" / "m1-integrity-v2.sha256"
PACK = ROOT / "bench" / "results" / "latency-m1-356ec58"

# The approved v2 path set (P05a Part D: 14 v1 paths + PROTECTED + tracked FROZEN extras).
EXPECTED_PATHS = {
    # v1
    "bench/gold_set.jsonl",
    "bench/ground_truth_holdout.jsonl",
    "bench/human_label_sample.csv",
    "bench/human_label_sample_pass1.csv",
    "docs/onboarding-measurement.md",
    "reports/baselines.md",
    "reports/evidence-ablation.md",
    "reports/robustness.md",
    "reports/latency.md",
    "reports/summary.json",
    "controlplane/manifest.py",
    "controlplane/bindings.py",
    "controlplane/intercept.py",
    "tests/test_manifest_hardening.py",
    # PROTECTED, not in v1
    "controlplane/decide.py",
    "schemas/manifest.schema.json",
    "manifests/discount_approval.yaml",
    "manifests/knowledge_assistant.yaml",
    "manifests/service_credit_approval.yaml",
    "manifests/servicing.yaml",
    "manifests/tau2_cancel_pending_order.yaml",
    "manifests/tau2_exchange_delivered_order_items.yaml",
    "manifests/tau2_modify_pending_order_address.yaml",
    "manifests/tau2_modify_pending_order_items.yaml",
    "manifests/tau2_modify_pending_order_payment.yaml",
    "manifests/tau2_return_delivered_order_items.yaml",
    # FROZEN, not in v1
    "bench/label.py",
    "bench/extraction_gold_v1.jsonl",
    "reports/README.md",
    "reports/evidence-ablation-absence.png",
    "reports/evidence-ablation-staleness.png",
    "reports/extraction-completeness-v1.json",
    "reports/extraction-completeness-v1.md",
    "reports/foundational-requirement-coverage-v1.json",
    "reports/foundational-requirement-coverage-v1.md",
    "reports/manifest-claim-coverage.md",
    "reports/tau2-bench.md",
    "reports/verification-coverage.md",
}


def _rows() -> list[dict]:
    return IR.read_v2(RECORD)


def test_a_record_parses():
    text = RECORD.read_bytes().decode("utf-8").replace("\r\n", "\n")
    header = [line for line in text.split("\n") if line.startswith("#")]
    assert any(line.startswith("# base commit: ") for line in header)
    method = next(line for line in header if line.startswith("# method: "))
    for suffix in IR.TEXT_SUFFIXES:
        assert f" {suffix} " in method or method.endswith(f" {suffix}")
    rows = _rows()
    assert len(rows) == 38
    for row in rows:
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256_lf"]), row
        assert row["status"] in IR.STATUSES, row
        assert row["authority"], row


def test_b_path_set_is_the_approved_set():
    paths = [row["path"] for row in _rows()]
    assert len(paths) == len(set(paths))
    assert set(paths) == EXPECTED_PATHS
    assert set(IR.planned_paths()) == EXPECTED_PATHS


def test_c_every_live_file_matches_the_record():
    assert IR.check(RECORD) == []


def _authority_parts(authority: str, known: set[str]) -> list[str]:
    """Split an authority field into labels. Labels may contain '; ' themselves
    (e.g. 'P03 local commit, decision D10; P3-A (a5549b7)'), so match known labels
    longest-first instead of splitting on the separator."""
    parts, rest = [], authority
    while rest:
        label = next((k for k in sorted(known, key=len, reverse=True) if rest.startswith(k)), None)
        if label is None:
            m = re.match(r"baseline [0-9a-f]{7}|v1: [A-Za-z0-9_]+|v1(?=$|; )", rest)
            assert m, f"unknown authority label at: {rest!r}"
            label = m.group(0)
        parts.append(label)
        rest = rest[len(label):]
        if rest:
            assert rest.startswith("; "), f"bad separator at: {rest!r}"
            rest = rest[2:]
    return parts


def test_d_every_row_names_an_authority():
    known = set(IR.AUTHORITY.values()) | {IR.PUBLIC_LABEL}
    for row in _rows():
        parts = _authority_parts(row["authority"], known)
        if row["status"] == "UNCHANGED_SINCE_V1":
            assert parts == ["v1"], row
            continue
        assert "v1" not in parts, row
        if row["status"] == "CHANGED_AUTHORIZED":
            assert any(p in known for p in parts), row
        if row["status"] == "NEW_IN_V2":
            assert re.fullmatch(r"baseline [0-9a-f]{7}", parts[0]), row


def test_e_unchanged_rows_agree_with_v1():
    v1 = {r["path"]: r for r in IR.read_v1()}
    for row in _rows():
        if row["status"] != "UNCHANGED_SINCE_V1":
            continue
        data = IR.normalised(ROOT / row["path"])
        forms = {hashlib.sha256(data).hexdigest(),
                 hashlib.sha256(data.replace(b"\n", b"\r\n")).hexdigest()}
        assert v1[row["path"]]["current"] in forms, row["path"]


def test_f_every_v1_path_is_in_v2():
    v1 = IR.read_v1()
    assert len(v1) == 14
    v2_paths = {row["path"] for row in _rows()}
    assert {r["path"] for r in v1} <= v2_paths
    statuses = {row["path"]: row["status"] for row in _rows()}
    assert all(statuses[r["path"]] != "NEW_IN_V2" for r in v1)


def test_g_latency_pack_sha256sums_verify():
    listed = {}
    for line in (PACK / "SHA256SUMS").read_bytes().decode("utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        listed[name.lstrip("*")] = digest
    actual = {p.relative_to(PACK).as_posix() for p in PACK.rglob("*")
              if p.is_file() and p.name != "SHA256SUMS"}
    assert set(listed) == actual, sorted(set(listed) ^ actual)
    for name, digest in listed.items():
        assert hashlib.sha256((PACK / name).read_bytes()).hexdigest() == digest, name
