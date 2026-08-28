"""S6 — the Resolver protocol every registry module implements.

Two independent reads of the same store is the liveness that matters here,
per README's own claim: the agent read from a stale index at propose-time; a
Resolver reads the same underlying store fresh, at decision time, and
returns an Evidence carrying enough (source, query, fetched_at) that the
query on a receipt could be re-run by a regulator, not just trusted.
"""

from __future__ import annotations

from typing import Protocol

from controlplane.schema import Claim, Evidence, SessionContext


class Resolver(Protocol):
    def resolve(self, claim: Claim, session: SessionContext) -> Evidence: ...


__all__ = ["Resolver"]
