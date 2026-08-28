"""D49 — the compensation registry. Risk tier and compensability are
DIFFERENT AXES: a high-risk fully-compensable action (a refund, reversible
by a chargeback) is a completely different design problem from a low-risk
non-compensable one (an email already sent). See docs/compensability.md.
"""

from __future__ import annotations

from controlplane.schema import Compensability, CompensationPlan

_TABLE: dict[str, tuple[str | None, Compensability]] = {
    "issue_refund": ("reverse_refund", Compensability.FULLY),
    "update_entitlement": ("restore_entitlement", Compensability.PARTIALLY),
    "send_customer_email": (None, Compensability.NOT),
    "send_document": ("revoke_access", Compensability.PARTIALLY),
}


def compensation_for(tool: str) -> CompensationPlan:
    try:
        action, compensability = _TABLE[tool]
    except KeyError:
        raise KeyError(
            f"controlplane/compensation.py has no row for tool={tool!r} — every governed tool needs one"
        ) from None
    return CompensationPlan(action=action, compensability=compensability)


__all__ = ["compensation_for"]
