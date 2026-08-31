"""P06 C2 — governed-scope constants, deliberately dependency-free (stdlib
only: no `tau2`, no `controlplane`).

Split out of bench/tau2_adapter.py so both that module (which needs `tau2`
at import time) and the controlplane-side test suite (which needs
`controlplane` but must NOT need `tau2` -- see
tests/test_tau2_c2_controlplane_side.py's module docstring for why) can
import the SAME single source of truth for which tools are governed and
which manifest file governs each one, without either side pulling in a
dependency it doesn't have installed.
"""

from __future__ import annotations

TAU2_CONTROLPLANE_DOMAIN = "retail_controlplane"
TAU2_OFFICIAL_DOMAIN_NAME = "retail"
RESOLVER_NAME = "tau2_retail"

# Section 6: exactly these six retail WRITE tools are governed.
# modify_user_address is deliberately excluded -- a documented
# representational scope boundary, not an oversight (see the P06 C2 report).
GOVERNED_TOOLS: frozenset[str] = frozenset(
    {
        "cancel_pending_order",
        "exchange_delivered_order_items",
        "modify_pending_order_address",
        "modify_pending_order_items",
        "modify_pending_order_payment",
        "return_delivered_order_items",
    }
)

# tool name -> manifest file stem (manifests/<stem>.yaml).
MANIFEST_FOR_TOOL: dict[str, str] = {name: f"tau2_{name}" for name in GOVERNED_TOOLS}

__all__ = [
    "TAU2_CONTROLPLANE_DOMAIN",
    "TAU2_OFFICIAL_DOMAIN_NAME",
    "RESOLVER_NAME",
    "GOVERNED_TOOLS",
    "MANIFEST_FOR_TOOL",
]
