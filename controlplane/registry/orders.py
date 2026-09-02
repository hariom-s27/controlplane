"""S6 — the orders.db resolver.

claim.subject is the order_id for every ClaimKind this resolver handles.
Each Evidence's value is the raw resolved FACT (a customer_id, a date, an
amount) — never a verdict. The predicate engine (S7) does the comparing;
the registry's only job is to say what the system of record actually says,
right now, independent of whatever the agent's stale retrieval claimed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from controlplane.registry import freshness
from controlplane.registry.clock import now
from controlplane.registry.sqlite_source import connect_readwrite, translate_availability
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Reliability, SessionContext

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "data" / "orders.db"

# Which raw orders.db column answers each ClaimKind.
_FIELD_FOR_KIND: dict[ClaimKind, str] = {
    ClaimKind.ORDER_BELONGS_TO_CUSTOMER: "customer_id",
    ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: "amount_paise",
    ClaimKind.WITHIN_REFUND_WINDOW: "delivered_at",
    ClaimKind.ORDER_STATUS_SUPPORTS_ACTION: "order_status",
}

# ORDER_ATTRIBUTES_MATCH (R3 extended, D52) needs two columns at once —
# handled separately from the single-field table above.
_ATTRIBUTE_FIELDS = ("item_colour", "item_category")
_RANK = {Reliability.UNVERIFIED: 0, Reliability.INFERRED: 1, Reliability.CORROBORATED: 2}


class OrdersResolver:
    def resolve(self, claim: Claim, session: SessionContext) -> Evidence:
        order_id = claim.subject
        if claim.kind is ClaimKind.ORDER_ATTRIBUTES_MATCH:
            return self._resolve_attributes(claim, order_id)

        try:
            field = _FIELD_FOR_KIND[claim.kind]
        except KeyError:
            raise KeyError(f"OrdersResolver has no field mapping for {claim.kind!r}") from None
        query = f"SELECT {field} FROM orders WHERE order_id = {order_id!r}"

        conn = connect_readwrite(DB, source="orders.db")
        conn.row_factory = sqlite3.Row
        try:
            try:
                row = conn.execute(
                    f"SELECT {field} FROM orders WHERE order_id = ?", (order_id,)
                ).fetchone()
            except sqlite3.OperationalError as exc:
                translate_availability(exc, source="orders.db", operation=f"read {field}")
                raise AssertionError("translate_availability must raise")  # pragma: no cover

            if row is None:
                return Evidence(
                    claim_id=claim.id,
                    value=None,
                    source="orders.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"no order found for order_id={order_id!r}",
                )

            if row[field] is None:
                return Evidence(
                    claim_id=claim.id,
                    value=None,
                    source="orders.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"source field {field!r} is NULL for order_id={order_id!r}",
                )

            return Evidence(
                claim_id=claim.id,
                value=row[field],
                source="orders.db",
                query=query,
                fetched_at=now(),
                reliability_class=freshness.reliability_for_field("orders", field, conn),
                confidence=Confidence.HIGH,
            )
        finally:
            conn.close()

    def _resolve_attributes(self, claim: Claim, order_id: str) -> Evidence:
        cols = ", ".join(_ATTRIBUTE_FIELDS)
        query = f"SELECT {cols} FROM orders WHERE order_id = {order_id!r}"

        conn = connect_readwrite(DB, source="orders.db")
        conn.row_factory = sqlite3.Row
        try:
            try:
                row = conn.execute(f"SELECT {cols} FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            except sqlite3.OperationalError as exc:
                translate_availability(exc, source="orders.db", operation="read order attributes")
                raise AssertionError("translate_availability must raise")  # pragma: no cover

            if row is None:
                return Evidence(
                    claim_id=claim.id,
                    value=None,
                    source="orders.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"no order found for order_id={order_id!r}",
                )

            values = {"colour": row["item_colour"], "category": row["item_category"]}
            if any(value is None for value in values.values()):
                return Evidence(
                    claim_id=claim.id,
                    value=values,
                    source="orders.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"one or more order attributes are NULL for order_id={order_id!r}",
                )

            reliabilities = [freshness.reliability_for_field("orders", f, conn) for f in _ATTRIBUTE_FIELDS]
            return Evidence(
                claim_id=claim.id,
                value=values,
                source="orders.db",
                query=query,
                fetched_at=now(),
                reliability_class=min(reliabilities, key=lambda r: _RANK[r]),
                confidence=Confidence.HIGH,
            )
        finally:
            conn.close()


__all__ = ["OrdersResolver"]
