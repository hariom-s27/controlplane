"""P03 — the gold set is byte-deterministic and structurally sound.

Regenerating it from the committed seeds must produce identical files (a judge
who reruns the build must get the published numbers), every case must trace to
a real orders.db row, the slice counts must match the P03 distribution, and
bench/label.py's independent verdict must match the slice each case was built
for.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
DATA = ROOT / "data"
sys.path.insert(0, str(BENCH))

# Pinned over the committed seed DBs (CP_SEED=20260814, CP_DEMO_DATE=2026-08-14),
# computed on LF-exact bytes. A change here means the gold set moved and every
# downstream number must be regenerated — that is the point of the assertion.
PINNED_SHA256 = {
    "gold_set.jsonl": "09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e",
    "ground_truth_holdout.jsonl": "204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb",
    # M4: human sheet re-emitted without the `slice` column (a construction-intent
    # leak). Same 30 cases, same SEED sampling — only the visible schema changed.
    # gold_set.jsonl / ground_truth_holdout.jsonl bytes are unaffected.
    "human_label_sample.csv": "48f069133e63ef87fb7f6027e1b259ab5ae534016f41ca1640a375d74130d3c9",
}

EXPECTED_SLICE_COUNTS = {
    "allow_in_window": 50,
    "outside_window": 20,
    "over_authority": 15,
    "distractor_present": 20,
    "stale_policy_context": 20,
    "corrupted_or_missing_record": 15,
    "ambiguous_under_policy": 10,
}
EXPECTED_LABEL_COUNTS = {"ALLOW": 50, "BLOCK": 75, "ESCALATE": 15, "AMBIGUOUS": 10}


@pytest.fixture(scope="module", autouse=True)
def _built():
    # Build the stores only if they are missing. Rebuilding unconditionally
    # races test_data.py's own rebuild for the orders.db file handle on
    # Windows (unlink-open-file -> PermissionError). CI builds them before
    # pytest; test_data.py builds them too.
    dbs = [DATA / n for n in ("orders.db", "policy_store.db")]
    if not all(p.exists() for p in dbs):
        subprocess.run([sys.executable, str(DATA / "build_db.py")], check=True,
                       capture_output=True, cwd=ROOT)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def summary(_built):
    import gold_set_build

    # first build (also refreshes any partly-stale committed copy)
    s1 = gold_set_build.build()
    shas1 = {name: _sha(BENCH / name) for name in PINNED_SHA256}
    # second build — must be byte-identical
    s2 = gold_set_build.build()
    shas2 = {name: _sha(BENCH / name) for name in PINNED_SHA256}
    assert shas1 == shas2, "regenerating the gold set changed its bytes"
    return {"summary": s1, "sha256": shas1}


def test_regeneration_matches_the_pinned_hashes(summary):
    assert summary["sha256"] == PINNED_SHA256, (
        "gold-set bytes differ from the pinned hashes. If this was intentional "
        "(seed data changed, construction logic changed) regenerate with "
        "`python bench/gold_set_build.py` and update PINNED_SHA256 — and every "
        "downstream figure."
    )


def test_slice_distribution_is_exactly_p03(summary):
    assert summary["summary"]["per_slice_case_counts"] == EXPECTED_SLICE_COUNTS


def test_independent_labeller_distribution(summary):
    assert summary["summary"]["label_py_distribution"] == EXPECTED_LABEL_COUNTS


def test_no_case_disagrees_with_its_constructed_slice(summary):
    assert summary["summary"]["disagreements"] == []


def test_every_case_derives_from_a_real_orders_db_row(summary):
    conn = sqlite3.connect(DATA / "orders.db")
    real = {r[0] for r in conn.execute("SELECT order_id FROM orders")}
    conn.close()

    holdout = [json.loads(l) for l in (BENCH / "ground_truth_holdout.jsonl")
               .read_text(encoding="utf-8").splitlines() if l.strip()]
    gold = [json.loads(l) for l in (BENCH / "gold_set.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    gold_by_id = {c["id"]: c for c in gold}

    assert len(holdout) == 150
    for truth in holdout:
        # the construction source is always a real row
        assert truth["source_order_id"] in real, truth["id"]
        call_oid = gold_by_id[truth["id"]]["tool_call"]["args"]["order_id"]
        corruption = truth.get("corruption")
        if corruption and corruption.get("kind") == "order_id_transcription":
            # the emitted id is a deliberate corruption; it must NOT resolve
            assert call_oid not in real, truth["id"]
            assert corruption["original"] in real
        else:
            assert call_oid in real, truth["id"]


def test_cases_are_clustered_not_independent(summary):
    """Several cases legitimately share one source order (the DB has only 5
    in-window rows). Downstream CIs must know that."""
    n_unique = summary["summary"]["n_unique_source_orders"]
    assert 90 <= n_unique <= 109
    # the allow slice is the clustered one
    assert summary["summary"]["per_slice_unique_source_orders"]["allow_in_window"] == 5


def test_gold_labels_are_not_from_decide(summary):
    gold = [json.loads(l) for l in (BENCH / "gold_set.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    for c in gold:
        assert "label.py" in c["label_source"]
        assert "decide" not in c["label_source"].replace("not controlplane.decide", "")
        assert c["gold_label"] in {"ALLOW", "BLOCK", "ESCALATE", "AMBIGUOUS"}
