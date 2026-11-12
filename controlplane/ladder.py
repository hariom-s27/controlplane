"""S5 — the Checkability Ladder. Classifies each ClaimKind into a tier
(C1-C5, controlplane/schema.py) and marks whether it is load-bearing.

This is the honest-coverage machinery: it is what lets the pitch say "C1/C2
are ~100% because SQL and arithmetic are exact; C3 is bounded by published
NLI SOTA (77.4%) and that is the actual bottleneck" instead of claiming 100%
and being disbelieved.

schema.py's ClaimKind docstring is explicit: this file MUST have a row for
every member, and a missing row must fail loudly rather than silently
default to C5. The completeness check below runs at import time so that's
true before any test even runs, not just when a particular kind is used.
"""

from __future__ import annotations

from controlplane.schema import ClaimKind, Tier

# C1 vs C2 is drawn the same way the roadmap's own two examples draw it:
# C1 answers the claim with a single system-of-record read (a query IS the
# check). C2 needs an extra derivation on top of one or more C1 facts before
# there's an answer — the roadmap's own C2 example, days_elapsed = clock -
# delivered_at, is exactly that: two C1 reads plus a subtraction and a
# threshold compare.
_TIER: dict[ClaimKind, Tier] = {
    # --- order / amount / policy shaped claims ---
    ClaimKind.ORDER_BELONGS_TO_CUSTOMER: Tier.C1,   # one query: order_id's customer_id == session's
    ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: Tier.C1,  # one query: claimed amount vs that order's own amount_paise
    ClaimKind.WITHIN_REFUND_WINDOW: Tier.C2,        # days_elapsed derived from two C1 facts, then compared
    ClaimKind.AMOUNT_WITHIN_AUTHORITY: Tier.C2,     # two independent C1 reads (order, authority ceiling) combined
    ClaimKind.POLICY_CLAUSE_CURRENT: Tier.C1,       # one query: WHERE effective_to IS NULL
    ClaimKind.CLAUSE_SEMANTICS_MATCH: Tier.C3,      # the roadmap's own C3 example, verbatim
    ClaimKind.ORDER_ATTRIBUTES_MATCH: Tier.C2,      # D52: resolved order's attributes vs the distractor's, compared
    ClaimKind.ORDER_STATUS_SUPPORTS_ACTION: Tier.C1,  # P08: one inferred source field, deliberately load-bearing
    # --- entitlement shaped claims ---
    ClaimKind.RECIPIENT_ENTITLED_TO_DOC: Tier.C1,       # one query: recipient_id in the doc's entitled list
    ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII: Tier.C2,  # a deterministic rule (regex/presidio) applied to text
    ClaimKind.DOC_CLASSIFICATION_PERMITTED: Tier.C1,    # one query: doc.classification in subject's entitled list
    # --- unverifiable by construction ---
    ClaimKind.CUSTOMER_INTENT: Tier.C5,             # the roadmap's own C5 example, verbatim
}

# A claim is load-bearing if, were it false, the action would be wrong.
# Kept as its own explicit table rather than derived from tier (e.g.
# "tier != C5") — load-bearing-ness and checkability are different axes,
# the same way schema.py keeps risk tier and Compensability separate. They
# happen to coincide for every kind that exists today, which is exactly why
# collapsing them would be easy to get away with until it silently wasn't.
_LOAD_BEARING: dict[ClaimKind, bool] = {
    ClaimKind.ORDER_BELONGS_TO_CUSTOMER: True,
    ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: True,
    ClaimKind.WITHIN_REFUND_WINDOW: True,
    ClaimKind.AMOUNT_WITHIN_AUTHORITY: True,
    ClaimKind.POLICY_CLAUSE_CURRENT: True,
    ClaimKind.CLAUSE_SEMANTICS_MATCH: True,
    ClaimKind.ORDER_ATTRIBUTES_MATCH: True,
    ClaimKind.ORDER_STATUS_SUPPORTS_ACTION: True,
    ClaimKind.RECIPIENT_ENTITLED_TO_DOC: True,
    # NOT load-bearing, deliberately — this is S13's entire thesis. PII
    # being present in an excerpt does not by itself make sending it wrong:
    # if the recipient IS entitled to that customer's record, their PII
    # being in it is completely fine. What makes an action wrong is the
    # entitlement check above failing, not detection alone. Marking this
    # load-bearing would let decide() treat "found PII" as a contradiction
    # in its own right — exactly the "detection is enough" claim the
    # cross-tenant demo exists to disprove.
    ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII: False,
    ClaimKind.DOC_CLASSIFICATION_PERMITTED: True,
    # Genuinely unverifiable at decision time: there is never evidence to
    # contradict it with, so it can never be the reason an action is wrong.
    ClaimKind.CUSTOMER_INTENT: False,
}


# P1 — which tiers have an implemented authoritative check path. C1/C2 are
# system-of-record reads and arithmetic; C3 is document entailment. C4
# (weak-source consensus) has no resolver in this build, and C5 is
# unverifiable by definition — so a C4/C5 claim is NOT verification-eligible
# and never enters the coverage denominator. This is derived from the tier
# rather than kept as a third table on purpose: unlike load-bearing-ness,
# eligibility is not an independent policy axis — it is exactly "is there a
# checker for this tier", which is a property of the tier itself. If a C4
# resolver is ever added, widen this set in one place.
_VERIFIABLE_TIERS: frozenset[Tier] = frozenset({Tier.C1, Tier.C2, Tier.C3})


def classify(kind: ClaimKind) -> Tier:
    try:
        return _TIER[kind]
    except KeyError:
        raise KeyError(f"ladder.py has no tier for {kind!r} — every ClaimKind needs a row") from None


def verification_eligible(kind: ClaimKind) -> bool:
    """P1 — is there an authoritative way to check this ClaimKind at all?
    True for C1/C2/C3, False for C4/C5. Raises (via classify) if the kind
    has no ladder row, same as every other ladder lookup."""
    return classify(kind) in _VERIFIABLE_TIERS


def is_load_bearing(kind: ClaimKind) -> bool:
    try:
        return _LOAD_BEARING[kind]
    except KeyError:
        raise KeyError(f"ladder.py has no load-bearing row for {kind!r} — every ClaimKind needs one") from None


def classify_claims(claims: list) -> list:
    """Fills tier and load_bearing on each Claim in place. Returns the same
    list for convenience."""
    for c in claims:
        c.tier = classify(c.kind)
        c.load_bearing = is_load_bearing(c.kind)
    return claims


_missing_tier = set(ClaimKind) - set(_TIER)
_missing_load_bearing = set(ClaimKind) - set(_LOAD_BEARING)
if _missing_tier or _missing_load_bearing:
    raise RuntimeError(
        "controlplane/ladder.py is missing rows — every ClaimKind member needs one in "
        f"both tables: missing tier={_missing_tier}, missing load_bearing={_missing_load_bearing}"
    )


__all__ = ["classify", "verification_eligible", "is_load_bearing", "classify_claims"]
