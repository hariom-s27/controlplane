"""S6 — resolution. A Claim goes in, an Evidence (a fact from a system of
record) comes out.

Which resolver answers a claim is chosen by the manifest's binding
(``resolver: orders``), looked up in ``RESOLVER_BY_NAME`` below — a
name -> callable registry, not a per-use-case table. Every resolver is
adapted to one signature ``(claim, session, manifest, action) -> Evidence``
so the binding-driven path can call any of them uniformly.
"""

from __future__ import annotations

import os
from typing import Callable

from controlplane import pii
from controlplane.registry.clock import now
from controlplane.registry.entitlements import EntitlementsResolver
from controlplane.registry.orders import OrdersResolver
from controlplane.registry.policy import PolicyResolver
from controlplane.schema import Claim, Confidence, Evidence, ProposedAction, Reliability, SessionContext

_orders = OrdersResolver()
_policy = PolicyResolver()
_entitlements = EntitlementsResolver()


def _resolve_pii(claim: Claim, action: ProposedAction | None) -> Evidence:
    """EXCERPT_CONTAINS_THIRD_PARTY_PII — a S14 content check on the outbound
    excerpt at decision time, not a system-of-record read. The one kind that
    needs `action` at all."""
    excerpt = action.excerpt if action else None
    hits = pii.detect(excerpt) if excerpt else []
    mode = os.environ.get("CP_PII", "regex")
    return Evidence(
        claim_id=claim.id,
        value=bool(hits),
        source=f"pii:{mode}",
        query=f"detect(excerpt) via CP_PII={mode}",
        fetched_at=now(),
        reliability_class=Reliability.INFERRED,  # a recogniser's output, not a system-of-record fact
        confidence=Confidence.MODERATE,  # roadmap's own words: "moderate at best"
        note=f"{len(hits)} entities: {sorted({h['entity_type'] for h in hits})}" if hits else "no PII detected",
    )


def _resolve_authority(claim: Claim, session: SessionContext, manifest: dict | None) -> Evidence:
    """AMOUNT_WITHIN_AUTHORITY — manifest-backed config (the ceiling this
    manifest's action may approve), not a system of record."""
    if manifest is None or "authority_ceiling_paise" not in manifest:
        raise ValueError("AMOUNT_WITHIN_AUTHORITY needs manifest.authority_ceiling_paise")
    return Evidence(
        claim_id=claim.id,
        value=manifest["authority_ceiling_paise"],
        source=f"manifest:{manifest['_name']}",
        query="authority_ceiling_paise",
        fetched_at=now(),
        reliability_class=Reliability.CORROBORATED,
        confidence=Confidence.CERTAIN,
    )


def _resolve_intent(claim: Claim) -> Evidence:
    """CUSTOMER_INTENT — C5, genuinely unverifiable by construction."""
    return Evidence(
        claim_id=claim.id,
        value=None,
        source="none",
        query="n/a — unverifiable by construction",
        fetched_at=now(),
        reliability_class=Reliability.UNVERIFIED,
        confidence=Confidence.NONE,
        note="C5: genuinely unverifiable at decision time",
    )


# name -> (claim, session, manifest, action) -> Evidence. The manifest's
# binding names one of these; nothing here knows which use case is running.
RESOLVER_BY_NAME: dict[str, Callable[..., Evidence]] = {
    "orders": lambda c, s, m, a: _orders.resolve(c, s),
    "policy": lambda c, s, m, a: _policy.resolve(c, s),
    "entitlements": lambda c, s, m, a: _entitlements.resolve(c, s),
    "authority": lambda c, s, m, a: _resolve_authority(c, s, m),
    "pii": lambda c, s, m, a: _resolve_pii(c, a),
    "intent": lambda c, s, m, a: _resolve_intent(c),
}


def resolve_bindings(
    claims: list[Claim], specs: list[dict], session: SessionContext, manifest: dict,
    action: ProposedAction | None = None,
) -> list[Evidence]:
    """Resolve each claim through the resolver its binding names. `specs` is
    controlplane.bindings.claim_specs(manifest) — passed in rather than
    imported to keep this module free of a manifest/bindings import."""
    resolver_for_kind = {spec["claim_kind"]: spec["resolver"] for spec in specs}
    out = []
    for c in claims:
        name = resolver_for_kind.get(c.kind)
        if name is None:
            raise KeyError(f"no claim_binding for {c.kind!r} in manifest {manifest.get('_name')!r}")
        out.append(RESOLVER_BY_NAME[name](c, session, manifest, action))
    return out


__all__ = ["RESOLVER_BY_NAME", "resolve_bindings"]
