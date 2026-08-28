"""
Step 6 checkpoint — three assertions that prove the data layer is correct.

    pytest tests/test_data.py -v

If any of these fail, STOP. Every step after this inherits the problem and
costs more to fix later.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


@pytest.fixture(scope="module", autouse=True)
def built():
    """Build the DBs once before the tests in this file."""
    subprocess.run(
        [sys.executable, str(DATA / "build_db.py")],
        check=True,
        capture_output=True,
        cwd=ROOT,
    )


@contextmanager
def _conn(name: str):
    c = sqlite3.connect(DATA / name)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 1. The policy store returns v4.2 and ONLY v4.2 as current.
#    This is the whole demo. Test it directly.
# ---------------------------------------------------------------------------
def test_current_clause_is_v42_only():
    with _conn("policy_store.db") as c:
        rows = c.execute(
            "SELECT version, window_days FROM clauses "
            "WHERE policy_id='refund_window' AND effective_to IS NULL"
        ).fetchall()

    assert len(rows) == 1, f"expected exactly one current clause, got {len(rows)}"
    assert rows[0]["version"] == "v4.2"
    assert rows[0]["window_days"] == 7


def test_v38_exists_but_is_superseded():
    """The old clause must still be IN the store — that is what makes the
    stale-retrieval failure realistic rather than staged."""
    with _conn("policy_store.db") as c:
        row = c.execute(
            "SELECT effective_to, superseded_by, window_days FROM clauses "
            "WHERE policy_id='refund_window' AND version='v3.8'"
        ).fetchone()

    assert row is not None
    assert row["effective_to"] is not None, "v3.8 must be closed off"
    assert row["superseded_by"] == "v4.2"
    assert row["window_days"] == 30  # the number that makes the agent wrong


# ---------------------------------------------------------------------------
# 2. The stale index still surfaces v3.8. That omission IS the bug.
# ---------------------------------------------------------------------------
def test_stale_index_surfaces_the_superseded_clause():
    chunks = json.loads((DATA / "stale_index" / "chunks.json").read_text())
    versions = {c["version"] for c in chunks if c["policy_id"] == "refund_window"}
    assert versions == {"v3.8", "v4.2"}, (
        "the index must contain BOTH versions unfiltered — if it only has "
        "v4.2, the agent cannot fail and there is no negative control"
    )


def test_stale_index_ranks_v38_in_top_3_for_a_realistic_query():
    """Existing somewhere in the index isn't the same claim as being
    reachable. This checks the actual retrieval function the agent calls
    (agents/servicing_agent.py, built in S2) surfaces the superseded clause
    for a query that never mentions a version number."""
    from agents.servicing_agent import _retrieve_policy

    ranked = _retrieve_policy("refund window after delivery", k=3)
    versions = [c["version"] for c in ranked]
    assert "v3.8" in versions, (
        "a realistic query about the refund window must actually surface "
        "the superseded clause in the top 3, not just have it exist "
        "somewhere in the underlying index"
    )


# ---------------------------------------------------------------------------
# 3. Byte-determinism. Build twice, compare hashes.
# ---------------------------------------------------------------------------
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_build_is_byte_deterministic():
    before = {n: _sha(DATA / n) for n in ("orders.db", "policy_store.db", "entitlements.db")}
    subprocess.run(
        [sys.executable, str(DATA / "build_db.py")],
        check=True,
        capture_output=True,
        cwd=ROOT,
    )
    after = {n: _sha(DATA / n) for n in ("orders.db", "policy_store.db", "entitlements.db")}
    assert before == after, (
        "rebuilding changed the database bytes. A judge who reruns your code "
        "must get your published numbers. Check for unsorted inserts, an "
        "unseeded RNG, or a timestamp leaking into the build."
    )


# ---------------------------------------------------------------------------
# The demo scenario itself — the numbers on the deck must be true of the data.
# ---------------------------------------------------------------------------
def test_demo_order_is_26_days_past_delivery_at_the_frozen_clock():
    with _conn("orders.db") as c:
        row = c.execute(
            "SELECT customer_id, delivered_at, amount_paise, item_colour "
            "FROM orders WHERE order_id='ORD-88461'"
        ).fetchone()

    assert row is not None, "ORD-88461 is the whole demo; it must exist"
    assert row["customer_id"] == "CUST-2291"
    assert row["amount_paise"] == 4299900  # ₹42,999 — integer paise, never float
    assert row["item_colour"] == "blue"

    elapsed = (date(2026, 8, 14) - date.fromisoformat(row["delivered_at"])).days
    assert elapsed == 26, f"the deck says 26 days; the data says {elapsed}"
    assert elapsed > 7, "must be OUTSIDE the v4.2 window or there is nothing to block"


def test_allow_case_is_inside_the_window():
    """The demo must not be block-only."""
    with _conn("orders.db") as c:
        row = c.execute(
            "SELECT delivered_at, amount_paise FROM orders WHERE order_id='ORD-90233'"
        ).fetchone()

    elapsed = (date(2026, 8, 14) - date.fromisoformat(row["delivered_at"])).days
    assert elapsed <= 7, "the ALLOW case must be inside the 7-day window"
    assert row["amount_paise"] <= 2500000, "and under the ₹25,000 authority ceiling"


def test_distractor_order_exists_for_d52():
    """Same customer, same colour, near-adjacent id. If the agent resolves
    'the blue one' to this instead, order_id cross-validation is what catches
    it — D52, and SEB-1 experiment 3 made live."""
    with _conn("orders.db") as c:
        rows = c.execute(
            "SELECT order_id FROM orders "
            "WHERE customer_id='CUST-2291' AND item_colour='blue'"
        ).fetchall()
    ids = {r["order_id"] for r in rows}
    assert {"ORD-88461", "ORD-88472"} <= ids


def test_cross_tenant_document_setup():
    """EMP-4410 must NOT be entitled to CUST-7788's records, and DOC-2277 must
    be about CUST-7788. Without both, the privacy demo has nothing to show."""
    with _conn("entitlements.db") as c:
        emp = c.execute(
            "SELECT entitled_customer_ids FROM subjects WHERE subject_id='EMP-4410'"
        ).fetchone()
        doc = c.execute(
            "SELECT about_customer_id FROM documents WHERE doc_id='DOC-2277'"
        ).fetchone()

    entitled = json.loads(emp["entitled_customer_ids"])
    assert doc["about_customer_id"] == "CUST-7788"
    assert "CUST-7788" not in entitled, (
        "the cross-tenant leak demo needs EMP-4410 to lack entitlement to "
        "CUST-7788 — otherwise the entitlement check has nothing to block"
    )
