"""S6 — dispatches a Claim to the resolver that actually knows how to
answer it, by ClaimKind. This is the only place that mapping lives."""

from __future__ import annotations

import os

from controlplane import pii
from controlplane.registry.clock import now
from controlplane.registry.entitlements import EntitlementsResolver
from controlplane.registry.orders import OrdersResolver
from controlplane.registry.policy import PolicyResolver
from controlplane.schema import Claim, ClaimKind, Confidence, Evidence, ProposedAction, Reliability, SessionContext

_orders = OrdersResolver()
_policy = PolicyResolver()
_entitlements = EntitlementsResolver()

_RESOLVER_FOR_KIND = {
    ClaimKind.ORDER_BELONGS_TO_CUSTOMER: _orders,
    ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: _orders,
    ClaimKind.WITHIN_REFUND_WINDOW: _orders,
    ClaimKind.ORDER_ATTRIBUTES_MATCH: _orders,
    ClaimKind.POLICY_CLAUSE_CURRENT: _policy,
    ClaimKind.CLAUSE_SEMANTICS_MATCH: _policy,
    ClaimKind.RECIPIENT_ENTITLED_TO_DOC: _entitlements,
    ClaimKind.DOC_CLASSIFICATION_PERMITTED: _entitlements,
}


def resolve_claim(
    claim: Claim, session: SessionContext, manifest: dict | None = None, action: ProposedAction | None = None
) -> Evidence:
    """AMOUNT_WITHIN_AUTHORITY and CUSTOMER_INTENT have no DB resolver:
    the first is manifest-backed config (R2: manifest.authority[role].ceiling),
    not a system of record; the second is C5, genuinely unverifiable by
    construction (schema.py's ClaimKind docstring). EXCERPT_CONTAINS_THIRD_PARTY_PII
    has no DB resolver either — it's a S14 content check on action.excerpt at
    decision time (controlplane/pii.py), which is why this is the one kind
    that needs `action` at all."""
    if claim.kind is ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII:
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

    if claim.kind is ClaimKind.AMOUNT_WITHIN_AUTHORITY:
        if manifest is None:
            raise ValueError("AMOUNT_WITHIN_AUTHORITY needs a manifest to resolve the ceiling")
        ceiling = manifest["authority"][session.agent_role]["ceiling_paise"]
        return Evidence(
            claim_id=claim.id,
            value=ceiling,
            source=f"manifest:{manifest.get('_name', 'servicing')}",
            query=f"authority.{session.agent_role}.ceiling_paise",
            fetched_at=now(),
            reliability_class=Reliability.CORROBORATED,
            confidence=Confidence.CERTAIN,
        )

    if claim.kind is ClaimKind.CUSTOMER_INTENT:
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

    resolver = _RESOLVER_FOR_KIND.get(claim.kind)
    if resolver is None:
        raise KeyError(f"controlplane/registry has no resolver for {claim.kind!r}")
    return resolver.resolve(claim, session)


def resolve_all(
    claims: list[Claim], session: SessionContext, manifest: dict | None = None, action: ProposedAction | None = None
) -> list[Evidence]:
    return [resolve_claim(c, session, manifest, action) for c in claims]


__all__ = ["resolve_claim", "resolve_all"]
