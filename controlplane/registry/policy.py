"""S6 — the policy_store.db resolver.

🔴 The whole demo, in one query: WHERE effective_to IS NULL returns v4.2 no
matter what version the agent's stale retrieval claimed. The resolver never
looks at claim.asserted_value or anything the agent said — it doesn't even
receive it. That's not discipline, it's the query: there is no WHERE clause
here that could reach into the claim's asserted_value even if someone tried.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from controlplane.registry.clock import now
from controlplane.schema import Claim, Confidence, Evidence, Reliability, SessionContext

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "data" / "policy_store.db"


class PolicyResolver:
    def resolve(self, claim: Claim, session: SessionContext) -> Evidence:
        """claim.subject is the policy_id, e.g. "refund_window"."""
        policy_id = claim.subject
        query = (
            f"SELECT version, text FROM clauses WHERE policy_id = {policy_id!r} "
            "AND effective_to IS NULL"
        )

        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT version, text FROM clauses WHERE policy_id = ? AND effective_to IS NULL",
                (policy_id,),
            ).fetchone()

            if row is None:
                return Evidence(
                    claim_id=claim.id,
                    value=None,
                    source="policy_store.db",
                    query=query,
                    fetched_at=now(),
                    reliability_class=Reliability.UNVERIFIED,
                    confidence=Confidence.NONE,
                    note=f"no current clause for policy_id={policy_id!r}",
                )

            return Evidence(
                claim_id=claim.id,
                value=row["version"],
                source="policy_store.db",
                query=query,
                fetched_at=now(),
                reliability_class=Reliability.CORROBORATED,
                confidence=Confidence.HIGH,
                version=row["version"],
                note=row["text"],
            )
        finally:
            conn.close()


# Note: the refund_authority clause's ceiling is narrative text today
# ("...up to and including INR 25,000...", data/seed/clauses.json), not a
# structured column, so it is deliberately not parsed out of prose here.
# The predicate engine reads the ceiling from the manifest instead
# (controlplane/manifest.py) — R2 specifies manifest.authority[role].ceiling,
# and that's S12's actual job: per-role policy config, not text-mined DB values.

__all__ = ["PolicyResolver"]
