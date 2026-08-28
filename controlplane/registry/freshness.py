"""S6 — the SOURCE_UNRELIABLE escalation rule.

Reliability is a property of the FIELD, not the system it lives in (D36).
orders.db's own field_reliability table (built in data/build_db.py from
data/seed/orders.json) is the actual source of truth for orders' fields:
delivered_at/amount_paise/customer_id/item_description/order_id are
corroborated (reconciled against the carrier scan and the payment rail);
order_status is inferred — a programmed assumption between checkpoints,
grounded in the USPS OIG finding that 163 of 500 packages (32.6%) stayed
marked "Out for Delivery" while still sitting at the origin office.

policy_store.db and entitlements.db don't have their own field_reliability
tables (nothing in this demo models an unreliable field in either), so
resolvers for those default to corroborated — the DB itself is the
authoritative record, not a downstream inference from one.
"""

from __future__ import annotations

import sqlite3

from controlplane.schema import Claim, Evidence, Reliability, Verdict

_DEFAULT_RELIABILITY: dict[str, Reliability] = {
    "policy_store": Reliability.CORROBORATED,
    "entitlements": Reliability.CORROBORATED,
    # Fallback for an orders.db field with no explicit row in the DB's own
    # field_reliability table (e.g. item_colour/item_category, which aren't
    # separately seeded — they're the same corroborated data as
    # item_description, just decomposed). order_status stays inferred
    # because the DB table itself has an explicit row for it, which the
    # conn-based lookup above always checks first.
    "orders": Reliability.CORROBORATED,
}


def reliability_for_field(table: str, field: str, conn: sqlite3.Connection | None = None) -> Reliability:
    """table is the DB's own table name (e.g. "orders"), not the .db filename."""
    if conn is not None:
        row = conn.execute(
            "SELECT reliability FROM field_reliability WHERE table_name = ? AND field_name = ?",
            (table, field),
        ).fetchone()
        if row is not None:
            return Reliability(row[0])
    return _DEFAULT_RELIABILITY.get(table, Reliability.UNVERIFIED)


def escalation_for(evidence: Evidence, claim: Claim) -> Verdict | None:
    """An inferred field backing a load-bearing claim can't safely ALLOW or
    CONTRADICT on its own — it escalates instead of either. This is the
    system's answer to "your systems of record are wrong too": named in the
    Round 2 brief as "a mix of well-governed and loosely governed internal
    data sources," so this is a required feature, not a hedge.

    Returns None when no escalation is needed.
    """
    if claim.load_bearing and evidence.reliability_class == Reliability.INFERRED:
        return Verdict.SOURCE_UNRELIABLE
    return None


__all__ = ["reliability_for_field", "escalation_for"]
