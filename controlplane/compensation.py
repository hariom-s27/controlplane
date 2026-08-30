"""D49 — compensability. Risk tier and compensability are DIFFERENT AXES: a
high-risk fully-compensable action (a refund, reversible by a chargeback) is
a completely different design problem from a low-risk non-compensable one
(an email already sent). See docs/compensability.md.

Compensability is declared per manifest (the ``compensation:`` block),
because it is a property of the specific action a use case takes. The engine
reads it; it does not decide it. "Block" is mandatory for a NOT-compensable
action regardless of how the verdict was reached.
"""

from __future__ import annotations

from controlplane.schema import Compensability, CompensationPlan


def compensation_for(manifest: dict) -> CompensationPlan:
    c = (manifest or {}).get("compensation")
    if not isinstance(c, dict) or "compensability" not in c:
        raise KeyError(
            f"manifest {(manifest or {}).get('_name')!r} has no valid 'compensation' block "
            "(needs at least compensability: fully|partially|not)"
        )
    return CompensationPlan(action=c.get("action"), compensability=Compensability(c["compensability"]))


__all__ = ["compensation_for"]
