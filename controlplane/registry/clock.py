"""The ONLY source of 'now' in the system.

Never call datetime.now() anywhere else. Two reasons:

1. The demo clock is frozen at CP_DEMO_DATE. With the real system date,
   "26 days elapsed" becomes 27 tomorrow and the recorded video goes stale.
2. Tests must be able to freeze time. A one-day drift between the clock, the
   stored dates and a policy's effective_from produces a 26/27-day
   discrepancy that someone will spot on the video.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timezone

from controlplane.schema import Claim, Confidence, Evidence, Reliability, SessionContext

_OVERRIDE: date | None = None


def set_clock(d: date | None) -> None:
    """Freeze the clock for a test. Pass None to restore env behaviour."""
    global _OVERRIDE
    _OVERRIDE = d


def today() -> date:
    if _OVERRIDE is not None:
        return _OVERRIDE
    frozen = os.getenv("CP_DEMO_DATE")
    if frozen:
        return date.fromisoformat(frozen)
    return datetime.now(timezone.utc).date()


def now() -> datetime:
    return datetime.combine(today(), time(10, 0), tzinfo=timezone.utc)


def resolve(claim_id: str) -> Evidence:
    """The clock as a C1 evidence source. Certain, zero-latency, no query."""
    return Evidence(
        claim_id=claim_id,
        value=today().isoformat(),
        source="clock",
        query="now()",
        fetched_at=now(),
        freshness_ms=0,
        reliability_class=Reliability.CORROBORATED,
        confidence=Confidence.CERTAIN,
        note="frozen demo clock" if os.getenv("CP_DEMO_DATE") else "system clock",
    )


class ClockResolver:
    """The Resolver-protocol wrapper around resolve() above, for the S6 spec's
    literal "four resolvers: orders.py, policy.py, clock.py, entitlements.py."
    No ClaimKind is actually "about" the clock — there's no claim whose
    subject is a date, the way ORD-88461 is a claim's subject — so nothing
    in controlplane/registry/__init__.py's dispatch table routes to this
    class today. controlplane/intercept.py still calls today() directly for
    that reason. Kept for interface completeness and because a future
    ClaimKind (e.g. "claimed_today") could route here without any other
    change."""

    def resolve(self, claim: Claim, session: SessionContext) -> Evidence:
        return resolve(claim.id)
