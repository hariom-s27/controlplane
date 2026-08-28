"""
ControlPlane — the five type contracts.

Everything in the pipeline is a function between two of these types.
Write this file first; it is what lets three people work in parallel.

THE ONE RULE THAT CARRIES THE WHOLE PITCH
-----------------------------------------
The extractor produces CLAIMS. The registry produces FACTS.
They never come from the same place.

`ProposedAction.claimed_*` fields are what the AGENT asserted. They may be
wrong. They may be None. That is normal and expected.

They are NOT inputs to the predicate engine. The predicate engine reads
`Evidence` objects whose `source` is a real system of record.

`ProposedAction.facts_for_predicate()` enforces this in code: it returns only
the fields that came structurally from the tool call itself. If you ever find
yourself passing a `claimed_*` value into a predicate, you have accidentally
rebuilt the architecture we are arguing against (ARCH-A), and the demo now
proves the opposite of what we want.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class Tier(str, Enum):
    """Checkability Ladder — how CAN this claim be verified? (D3)"""

    C1 = "C1"  # computable: recompute it deterministically
    C2 = "C2"  # look-up-able: query an authoritative system of record
    C3 = "C3"  # document-grounded: entailment against a versioned document
    C4 = "C4"  # consensus-checkable: multiple weak sources agree
    C5 = "C5"  # genuinely unverifiable at decision time


class Confidence(str, Enum):
    CERTAIN = "certain"  # C1 — arithmetic
    HIGH = "high"  # C2 — system of record
    MODERATE = "moderate"  # C3 — NLI entailment, SOTA is 77.4% not 100%
    NONE = "none"  # C4/C5 — no evidence available


class Reliability(str, Enum):
    """How trustworthy is the SOURCE itself? (D36)

    Grounded in measurement, not vibes: USPS OIG found `delivered_at` scans
    problematic at 2.45%, while 32.6% of packages were marked "Out for
    Delivery" while still sitting at the origin office. Terminal corroborated
    fields and in-flight inferred fields are not the same data class.
    """

    CORROBORATED = "corroborated"  # reconciled across ≥2 independent networks
    INFERRED = "inferred"  # a programmed assumption between checkpoints
    UNVERIFIED = "unverified"  # single-source, uncorroborated


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"
    SOURCE_UNRELIABLE = "SOURCE_UNRELIABLE"


class Intervention(str, Enum):
    """Ordered from most permissive to most restrictive.

    The ordering is load-bearing: metamorphic invariant M1 asserts that
    strictly less favourable evidence never produces a MORE permissive
    intervention, and that assertion is a comparison over this order.
    """

    ALLOW = "ALLOW"
    MODIFY = "MODIFY"
    OBSERVE_ONLY = "OBSERVE_ONLY"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"

    @property
    def rank(self) -> int:
        order = [
            Intervention.ALLOW,
            Intervention.MODIFY,
            Intervention.OBSERVE_ONLY,
            Intervention.ESCALATE,
            Intervention.BLOCK,
        ]
        return order.index(self)

    def more_permissive_than(self, other: "Intervention") -> bool:
        return self.rank < other.rank


class Compensability(str, Enum):
    """D49 — can this action be undone if we get it wrong?

    Risk tier and compensability are DIFFERENT AXES. A high-risk fully
    compensable action (a refund, reversible by a chargeback) is a completely
    different design problem from a low-risk non-compensable one (an email
    that has already been sent). "Block" is mandatory for NOT_COMPENSABLE.
    """

    FULLY = "fully"
    PARTIALLY = "partially"
    NOT = "not"


class ClaimKind(str, Enum):
    """Every claim type the system knows how to check.

    ladder.py MUST have a row for every member here. A missing row fails
    loudly rather than silently defaulting to C5 — see tests/test_ladder.py.
    """

    # --- use case 1: customer servicing (correctness) ---
    WITHIN_REFUND_WINDOW = "within_refund_window"
    AMOUNT_WITHIN_AUTHORITY = "amount_within_authority"
    ORDER_BELONGS_TO_CUSTOMER = "order_belongs_to_customer"
    AMOUNT_NOT_EXCEEDING_ORDER = "amount_not_exceeding_order"
    POLICY_CLAUSE_CURRENT = "policy_clause_current"
    CLAUSE_SEMANTICS_MATCH = "clause_semantics_match"
    ORDER_ATTRIBUTES_MATCH = "order_attributes_match"  # D52 cross-validation

    # --- use case 2: internal knowledge assistant (entitlement) ---
    RECIPIENT_ENTITLED_TO_DOC = "recipient_entitled_to_doc"
    EXCERPT_CONTAINS_THIRD_PARTY_PII = "excerpt_contains_third_party_pii"
    DOC_CLASSIFICATION_PERMITTED = "doc_classification_permitted"

    # --- unverifiable by construction ---
    CUSTOMER_INTENT = "customer_intent"


# --------------------------------------------------------------------------
# 1. ToolCall — what comes out of the agent
# --------------------------------------------------------------------------


class SessionContext(BaseModel):
    """Who is acting, on whose behalf, under which manifest."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    customer_id: str | None = None
    subject_id: str | None = None  # employee id, for use case 2
    agent_role: str = "servicing_agent"
    use_case: str = "customer_support_assistant"
    manifest_id: str = "servicing_v1"
    gate_enabled: bool = True


class ToolCall(BaseModel):
    """The raw thing the agent emitted, before ControlPlane touches it."""

    name: str
    args: dict[str, Any]
    agent_justification: str = ""
    retrieved_chunks: list[str] = Field(default_factory=list)
    session: SessionContext


# --------------------------------------------------------------------------
# 2. ProposedAction — the typed action, split into facts vs claims
# --------------------------------------------------------------------------


class ProposedAction(BaseModel):
    """
    STRUCTURAL fields come from the tool call itself — zero ambiguity.
    CLAIMED  fields come from the agent's prose — possibly wrong, possibly None.

    Only the structural fields may reach the predicate engine.
    """

    tool: str

    # --- structural (from tool args) ---
    order_id: str | None = None
    amount_paise: int | None = None
    currency: str = "INR"
    recipient_id: str | None = None
    doc_id: str | None = None
    item_colour: str | None = None  # D52 cross-validation (R3 extended) — declared
    item_category: str | None = None  # tool args, same mechanism as order_id, never prose
    excerpt: str | None = None  # send_document's payload text — structural: it IS what would be sent

    # --- claimed (from agent prose / retrieved context) ---
    claimed_delivered_at: date | None = None
    claimed_policy_version: str | None = None
    claimed_clause_text: str | None = None
    claimed_reasoning: str | None = None

    def facts_for_predicate(self) -> dict[str, Any]:
        """The ONLY things from this object the predicate engine may see.

        If you need to add a field here, ask first whether it came from the
        tool call (fine) or from the model's prose (never).
        """
        return {
            "tool": self.tool,
            "order_id": self.order_id,
            "amount_paise": self.amount_paise,
            "currency": self.currency,
            "recipient_id": self.recipient_id,
            "doc_id": self.doc_id,
            "item_colour": self.item_colour,
            "item_category": self.item_category,
        }


# --------------------------------------------------------------------------
# 3. Claim — one checkable assertion
# --------------------------------------------------------------------------


class Claim(BaseModel):
    id: str
    kind: ClaimKind
    subject: str  # the entity this is about, e.g. "ORD-88461"
    asserted_value: Any | None = None  # what the agent said, if anything
    tier: Tier | None = None  # filled in by ladder.py
    resolver: str | None = None  # filled in by ladder.py
    load_bearing: bool = False  # will the user ACT on this? (1–3 per action)


# --------------------------------------------------------------------------
# 4. Evidence — one resolved fact, fully attributed
# --------------------------------------------------------------------------


class Evidence(BaseModel):
    """A value plus everything needed to defend it on a receipt.

    `query` is not optional decoration. "SELECT delivered_at FROM orders
    WHERE id='ORD-88461' -> 2026-07-19 [live, 4ms]" is the line that makes
    the demo feel real, and it is what separates evidence from a claim.
    """

    claim_id: str
    value: Any
    source: str  # "orders.db" | "policy_store.db" | "clock" | ...
    query: str  # the literal query issued
    fetched_at: datetime
    freshness_ms: int = 0
    reliability_class: Reliability = Reliability.UNVERIFIED
    confidence: Confidence = Confidence.NONE
    version: str | None = None  # e.g. policy clause version
    note: str | None = None


# --------------------------------------------------------------------------
# 5. Decision — what the gate concluded, and why
# --------------------------------------------------------------------------


class Reason(BaseModel):
    """One line of the receipt's body. Every reason names a real rule."""

    rule: str
    expected: Any
    observed: Any
    passed: bool
    policy_version: str | None = None


class CompensationPlan(BaseModel):
    action: str | None
    compensability: Compensability


class Decision(BaseModel):
    trace_id: str
    manifest_id: str
    verdict: Verdict
    intervention: Intervention
    reasons: list[Reason] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    predicate_trace: dict[str, Any] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    root_cause: str | None = None
    compensation: CompensationPlan | None = None
    idempotency_key: str | None = None
    modified_args: dict[str, Any] | None = None

    # --- coverage telemetry (S11 logger 1) ---
    @property
    def coverage(self) -> dict[str, Any]:
        total = len(self.claims)
        by_tier: dict[str, int] = {}
        for c in self.claims:
            key = c.tier.value if c.tier else "unclassified"
            by_tier[key] = by_tier.get(key, 0) + 1
        checkable = sum(by_tier.get(t, 0) for t in ("C1", "C2", "C3"))
        return {
            "claims_total": total,
            "by_tier": by_tier,
            "deterministically_checkable": by_tier.get("C1", 0) + by_tier.get("C2", 0),
            "coverage_ratio": (checkable / total) if total else 0.0,
        }


def utcnow() -> datetime:
    """Single source of 'now'. Never call datetime.now() inline anywhere else —
    tests need to freeze time, and a one-day drift here produces a 26/27-day
    discrepancy someone will spot on the demo video."""
    return datetime.now(timezone.utc)


__all__ = [
    "Tier",
    "Confidence",
    "Reliability",
    "Verdict",
    "Intervention",
    "Compensability",
    "ClaimKind",
    "SessionContext",
    "ToolCall",
    "ProposedAction",
    "Claim",
    "Evidence",
    "Reason",
    "CompensationPlan",
    "Decision",
    "utcnow",
]
