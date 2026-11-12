"""P3-A — the kind-level manifest claim-coverage metric.

    manifest_claim_coverage(tool) = bound required load-bearing kinds
                                    / independently required load-bearing kinds

This suite proves the metric is deterministic, that an under-bound manifest
produces a non-empty unbound list, that an empty reference universe is
`not_assessed` (never 1.0), and that the tau2 `ORDER_BELONGS_TO_CUSTOMER`
omission surfaces. It also re-runs the P1 verification-coverage bench to show
P3-A did not disturb it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Same pattern as tests/test_receipt.py / test_product_views.py: the P1
# verification-coverage bench (re-run below) signs a receipt, which needs a
# secret. setdefault so a real environment value still wins.
os.environ.setdefault("CP_RECEIPT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("CP_MODEL", "Qwen/Qwen3-8B")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import extraction_reference as ref  # noqa: E402
import manifest_claim_coverage as mcc  # noqa: E402


@pytest.fixture(scope="module")
def report() -> dict:
    return mcc.build_report()


# --------------------------------------------------------------------------
# determinism + shape
# --------------------------------------------------------------------------


def _strip_volatile(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "generated_at_utc"}


def test_benchmark_is_deterministic():
    a, b = mcc.build_report(), mcc.build_report()
    assert _strip_volatile(a) == _strip_volatile(b)


def test_every_manifest_is_covered(report):
    manifests = sorted(p.stem for p in (ROOT / "manifests").glob("*.yaml"))
    assert sorted(r["manifest"] for r in report["manifests"]) == manifests


def test_reports_instance_level_metrics_as_not_measured(report):
    nm = report["not_measured"]
    assert set(nm) >= {
        "instance_level_extraction_recall",
        "instance_level_precision",
        "decomposition_accuracy",
        "silent_pass_rate",
    }
    assert all("NOT_MEASURED" in v for v in nm.values())


# --------------------------------------------------------------------------
# the metric itself
# --------------------------------------------------------------------------


def _row(report: dict, manifest: str) -> dict:
    return next(r for r in report["manifests"] if r["manifest"] == manifest)


def test_servicing_binds_every_required_kind(report):
    r = _row(report, "servicing")
    assert r["status"] == "assessed"
    assert r["coverage"] == 1.0
    assert r["unbound_load_bearing_kinds"] == []


def test_tau2_order_belongs_to_customer_is_an_unbound_required_kind(report):
    r = _row(report, "tau2_cancel_pending_order")
    assert r["status"] == "assessed"
    assert r["coverage"] == 0.5
    assert "ORDER_BELONGS_TO_CUSTOMER" in r["unbound_load_bearing_kinds"]
    detail = {d["kind"]: d["binding_note"] for d in r["unbound_load_bearing_detail"]}
    assert detail["ORDER_BELONGS_TO_CUSTOMER"], "the unbound kind must carry its binding_note"
    # and it is a grouped finding naming every tau2 manifest
    tau2_finding = next(
        f for f in report["findings"]
        if f["type"] == "unbound_required" and f["kind"] == "ORDER_BELONGS_TO_CUSTOMER"
    )
    assert len(tau2_finding["manifests"]) == 6


def test_under_bound_manifest_produces_nonempty_unbound():
    r = mcc._assess_tool(
        "issue_refund", "synthetic_underbound", "x-v1",
        bound=["ORDER_BELONGS_TO_CUSTOMER"],  # 1 of the 7 required kinds
    )
    assert r["status"] == "assessed"
    assert 0.0 < r["coverage"] < 1.0
    assert len(r["unbound_load_bearing_kinds"]) == len(r["required_load_bearing_kinds"]) - 1
    assert "AMOUNT_NOT_EXCEEDING_ORDER" in r["unbound_load_bearing_kinds"]


def test_empty_reference_universe_is_not_assessed_never_one(monkeypatch):
    monkeypatch.setitem(ref.REQUIRED, "_probe_tool_empty", ())
    r = mcc._assess_tool("_probe_tool_empty", "synthetic", "x-v1", bound=[])
    assert r["status"] == "not_assessed"
    assert r["coverage"] is None  # never 1.0


def test_fully_bound_synthetic_is_100pct():
    required = [rk.kind for rk in ref.REQUIRED["approve_service_credit"]]
    r = mcc._assess_tool("approve_service_credit", "synthetic", "x-v1", bound=required)
    assert r["coverage"] == 1.0
    assert r["unbound_load_bearing_kinds"] == []


def test_pii_bound_but_not_required_is_classified_non_load_bearing(report):
    r = _row(report, "knowledge_assistant")
    assert "EXCERPT_CONTAINS_THIRD_PARTY_PII" in r["bound_not_in_reference_non_load_bearing"]
    assert r["bound_not_in_reference_load_bearing"] == []
    assert r["coverage"] == 1.0  # the non-LB extra does not change the ratio


def test_malformed_reference_is_a_structural_error(monkeypatch):
    bad = ref.RequiredKind(kind="NOT_A_REAL_CLAIMKIND", rationale="x", basis=("action-semantics",))
    monkeypatch.setitem(ref.REQUIRED, "issue_refund", (bad,))
    with pytest.raises(mcc.ReferenceError):
        mcc._validate_reference()


# --------------------------------------------------------------------------
# --write touches only its own report
# --------------------------------------------------------------------------


def test_write_regenerates_only_the_one_report(tmp_path, monkeypatch, report):
    other = ROOT / "reports" / "summary.json"
    before = other.read_bytes() if other.exists() else None
    monkeypatch.setattr(mcc, "REPORTS", tmp_path)
    text = mcc.write_markdown(report)
    assert (tmp_path / "manifest-claim-coverage.md").read_text(encoding="utf-8") == text
    assert list(tmp_path.iterdir()) == [tmp_path / "manifest-claim-coverage.md"]
    if before is not None:
        assert other.read_bytes() == before  # summary.json untouched


# --------------------------------------------------------------------------
# P1 is undisturbed
# --------------------------------------------------------------------------


def test_p1_verification_coverage_bench_still_all_pass():
    import verification_coverage_bench as vcb

    assert vcb.build_report()["all_pass"] is True
