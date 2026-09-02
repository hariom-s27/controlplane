"""S6 — the entitlements.db resolver, for use case 2 (the internal knowledge
assistant). Built per spec; nothing calls it yet since agents/servicing_agent.py
is use case 1 only and the knowledge-assistant agent doesn't exist. Kept
here, tested directly, ready for when it does.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from controlplane.registry.clock import now
from controlplane.registry.sqlite_source import connect_readwrite, translate_availability
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, Reliability, SessionContext

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "data" / "entitlements.db"


class EntitlementsResolver:
    def resolve(self, claim: Claim, session: SessionContext) -> Evidence:
        """claim.subject is the doc_id."""
        doc_id = claim.subject
        conn = connect_readwrite(DB, source="entitlements.db")
        conn.row_factory = sqlite3.Row
        try:
            try:
                doc = conn.execute(
                    "SELECT classification, about_customer_id FROM documents WHERE doc_id = ?",
                    (doc_id,),
                ).fetchone()
            except sqlite3.OperationalError as exc:
                translate_availability(exc, source="entitlements.db", operation="read document")
                raise AssertionError("translate_availability must raise")  # pragma: no cover

            if doc is None:
                return Evidence(
                    claim_id=claim.id,
                    value=None,
                    source="entitlements.db",
                    query=f"SELECT * FROM documents WHERE doc_id = {doc_id!r}",
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"no document found for doc_id={doc_id!r}",
                )

            # Two independent boolean checks, deliberately not one combined
            # "entitled" flag — S13 asks two different questions:
            #   DOC_CLASSIFICATION_PERMITTED: is this classification
            #     something this recipient may EVER see, regardless of whose
            #     record it is?
            #   RECIPIENT_ENTITLED_TO_DOC: if the record is about a specific
            #     customer, is this recipient entitled to THAT customer's
            #     records? This is the one the cross-tenant demo hinges on:
            #     a support agent can be fully permitted to read "internal"
            #     documents in general and still have no right to this
            #     particular customer's ticket.
            # The execution target is the structural recipient_id carried in
            # claim.asserted_value. Querying session.subject_id here would
            # authorize one employee and then allow dispatch to send the
            # document to a different, unchecked recipient.
            recipient_id = claim.asserted_value
            query = f"SELECT entitled_classifications, entitled_customer_ids FROM subjects WHERE subject_id = {recipient_id!r}"
            try:
                subj = conn.execute(
                    "SELECT entitled_classifications, entitled_customer_ids FROM subjects WHERE subject_id = ?",
                    (recipient_id,),
                ).fetchone()
            except sqlite3.OperationalError as exc:
                translate_availability(
                    exc,
                    source="entitlements.db",
                    operation="read subject entitlements",
                )
                raise AssertionError("translate_availability must raise")  # pragma: no cover

            if subj is None:
                return Evidence(
                    claim_id=claim.id,
                    value=False,
                    source="entitlements.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"no recipient found for recipient_id={recipient_id!r}",
                )

            entitled_classifications = json.loads(subj["entitled_classifications"])
            entitled_customers = json.loads(subj["entitled_customer_ids"])

            if claim.kind == ClaimKind.DOC_CLASSIFICATION_PERMITTED:
                class_ok = doc["classification"] in entitled_classifications
                return Evidence(
                    claim_id=claim.id,
                    value=class_ok,
                    source="entitlements.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.CORROBORATED,
                    confidence=Confidence.HIGH,
                    note=f"classification={doc['classification']!r}",
                )

            # RECIPIENT_ENTITLED_TO_DOC
            customer_ok = doc["about_customer_id"] is None or doc["about_customer_id"] in entitled_customers
            return Evidence(
                claim_id=claim.id,
                value=customer_ok,
                source="entitlements.db",
                query=query,
                fetched_at=now(),
                reliability_class=Reliability.CORROBORATED,
                confidence=Confidence.HIGH,
                note=f"about_customer_id={doc['about_customer_id']!r}",
            )
        finally:
            conn.close()


__all__ = ["EntitlementsResolver"]
