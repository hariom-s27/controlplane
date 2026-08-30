"""S6 — the entitlements.db resolver: answers entitlement-shaped claims
(is this recipient allowed this document? is this classification within
their remit?). Which manifests route claims here is up to those manifests'
``claim_bindings`` — this file names no use case.
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
            #     something this subject may EVER see, regardless of whose
            #     record it is?
            #   RECIPIENT_ENTITLED_TO_DOC: if the record is about a specific
            #     customer, is this subject entitled to THAT customer's
            #     records? This is the one the cross-tenant demo hinges on:
            #     a support agent can be fully permitted to read "internal"
            #     documents in general and still have no right to this
            #     particular customer's ticket.
            subject_id = session.subject_id
            query = f"SELECT entitled_classifications, entitled_customer_ids FROM subjects WHERE subject_id = {subject_id!r}"
            try:
                subj = conn.execute(
                    "SELECT entitled_classifications, entitled_customer_ids FROM subjects WHERE subject_id = ?",
                    (subject_id,),
                ).fetchone()
            except sqlite3.OperationalError as exc:
                translate_availability(exc, source="entitlements.db", operation="read subject entitlements")
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
                    note=f"no subject found for subject_id={subject_id!r}",
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
