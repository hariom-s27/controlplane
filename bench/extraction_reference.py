#!/usr/bin/env python3
"""P3-A — the INDEPENDENT kind-level extraction reference.

For each governed tool this module states, as static data, the set of
**load-bearing checks a correct verifier of that tool must run**, named by
``ClaimKind``. `bench/manifest_claim_coverage.py` compares this set against
what each manifest actually binds.

WHY THIS EXISTS
---------------
P1 verification coverage measures ``verified / eligible`` over the claims the
manifest *did* model (its ``claim_bindings``). It explicitly does not know
what a perfect extractor would have produced — ``docs/verification-coverage.md``
says so, and ``docs/threat-model.md`` T32 ("Extraction differs from agent
intent", status NOT TESTED) names the gap. If a manifest omits a binding for
a load-bearing fact, that fact never becomes a ``Claim``, never enters the P1
denominator, and coverage stays high — a silent pass.

This file is the missing half: an independently authored statement of what
*should* be checked, so the omission shows up as a number instead of staying
a buried YAML comment.

HARD INDEPENDENCE CONSTRAINT (mirrors bench/label.py / P03)
----------------------------------------------------------
The required-kind sets below are authored ONLY from:

  a) the tool argument schema (the parameters each tool implementation takes),
  b) policy prose (the refund-window / authority / validity rules stated in
     words, in ``manifests/*.yaml`` comments and clause text — never the
     ``claim_bindings`` list),
  c) ``docs/threat-model.md`` (the enumerated threats to executed arguments).

This module:
  * imports nothing from ``controlplane/`` — it must not be a function of the
    system it audits;
  * reads no file — no ``manifests/`` load, no YAML, no I/O at all. It is
    static data. ``tests/test_extraction_reference.py`` parses this file's
    AST and fails on any import from ``controlplane`` or any file access.

WHAT THIS IS NOT
----------------
  * Not an extraction-completeness guarantee. "The manifest binds every kind
    this file lists" is not "the manifest checks everything that matters" —
    this file is human-authored and bounded by its author's reading of the
    schema, the prose and the threat model.
  * Not an instance-level gold set. It says nothing about whether a given
    action's specific claims were decomposed correctly; that needs an
    independent per-action reference corpus, which does not exist (the P3
    per-instance benchmark stays HELD — see docs/extraction-reliability.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

REFERENCE_ID = "extraction-reference-v1"

# Controlled vocabulary for RequiredKind.basis — every token must be one of
# these or match r"^threat-model:T\d+$". Keeps the "where did this requirement
# come from" trail auditable. tests/test_extraction_reference.py enforces it.
BASIS_VOCAB = frozenset({"tool-arg-schema", "action-semantics", "policy-prose"})


@dataclass(frozen=True)
class RequiredKind:
    """One load-bearing check a correct verifier of ``tool`` must run.

    ``kind`` is a ``ClaimKind`` *name* (a string, not the enum — this module
    does not import ``controlplane``). The metric resolves and validates it.
    """

    kind: str
    rationale: str
    basis: tuple[str, ...]
    # Context when this required check is hard or impossible to bind for this
    # tool as currently integrated — so a low coverage number is not mistaken
    # for "just add one line of YAML".
    binding_note: str | None = None


@dataclass(frozen=True)
class UnrepresentableRequirement:
    """A load-bearing check that SHOULD run but has no ``ClaimKind`` to carry
    it — loss point L2 in the P3 report. Advisory only: never counted in the
    coverage ratio (there is nothing to bind), always listed so it is not
    invisible.
    """

    name: str
    rationale: str
    basis: tuple[str, ...]


def _tau2_order_action(status_rationale: str) -> tuple[RequiredKind, ...]:
    """The two load-bearing checks every tau2 retail order action shares.

    They differ only in which lifecycle state the action needs, which is the
    ``status_rationale`` string; both map to ORDER_STATUS_SUPPORTS_ACTION.
    """
    return (
        RequiredKind(
            kind="ORDER_STATUS_SUPPORTS_ACTION",
            rationale=status_rationale,
            basis=("action-semantics", "tool-arg-schema", "threat-model:T2"),
        ),
        RequiredKind(
            kind="ORDER_BELONGS_TO_CUSTOMER",
            rationale=(
                "The action operates on a live order and moves money or goods. "
                "If the order is not the requesting user's, the action is "
                "misdirected — a wrong-ID / cross-tenant failure."
            ),
            basis=("action-semantics", "tool-arg-schema", "threat-model:T2", "threat-model:T34"),
            binding_note=(
                "No tau2 retail manifest binds this. The tau2 retail domain exposes no "
                "structural, DB-level authenticated-identity channel independent of the "
                "agent conversation (tau2's own task data documents this as an open issue). "
                "Binding it would need previous-tool-output as evidence (disallowed) or the "
                "evaluator's hidden ground truth (circular). The check stays required; the "
                "domain as integrated cannot satisfy it — this is not a one-line binding fix."
            ),
        ),
    )


# --------------------------------------------------------------------------
# The reference. One entry per governed tool. GOVERNED_TOOLS below is the
# authoritative list; a manifest whose tool is not a key here is a loud
# failure in bench/manifest_claim_coverage.py.
# --------------------------------------------------------------------------

REQUIRED: dict[str, tuple[RequiredKind, ...]] = {
    # --- use case 1: customer servicing --------------------------------------
    "issue_refund": (
        RequiredKind(
            kind="ORDER_BELONGS_TO_CUSTOMER",
            rationale=(
                "A refund moves money against a specific order; if that order is "
                "not the session customer's, the refund is misdirected."
            ),
            basis=("action-semantics", "tool-arg-schema", "threat-model:T2", "threat-model:T34"),
        ),
        RequiredKind(
            kind="AMOUNT_NOT_EXCEEDING_ORDER",
            rationale=(
                "A refund cannot correctly exceed the order's own total — an "
                "over-refund returns money that was never taken."
            ),
            basis=("action-semantics", "tool-arg-schema", "threat-model:T2"),
        ),
        RequiredKind(
            kind="WITHIN_REFUND_WINDOW",
            rationale=(
                "The refund clause grants a full refund only within a fixed number "
                "of days of delivery; outside it the action needs a different "
                "disposition (store credit / supervisor)."
            ),
            basis=("policy-prose", "threat-model:T2"),
        ),
        RequiredKind(
            kind="AMOUNT_WITHIN_AUTHORITY",
            rationale=(
                "The authority clause caps what a servicing agent may approve "
                "without escalation; above the ceiling the action must escalate."
            ),
            basis=("policy-prose", "threat-model:T2"),
        ),
        RequiredKind(
            kind="POLICY_CLAUSE_CURRENT",
            rationale=(
                "The window length comes from a versioned policy document; judging "
                "the refund against a superseded version is silent supersession."
            ),
            basis=("policy-prose", "threat-model:T3", "threat-model:T13"),
        ),
        RequiredKind(
            kind="CLAUSE_SEMANTICS_MATCH",
            rationale=(
                "The rule the agent relied on must actually match what the current "
                "clause says; a paraphrase that drifts from the clause is the "
                "ordinary hallucination case."
            ),
            basis=("action-semantics", "threat-model:T1", "threat-model:T3"),
        ),
        RequiredKind(
            kind="ORDER_ATTRIBUTES_MATCH",
            rationale=(
                "The tool call carries the item the customer described (colour, "
                "category). If the resolved order is a different item, the agent "
                "matched the wrong order and every downstream check is about the "
                "wrong record."
            ),
            basis=("tool-arg-schema", "action-semantics", "threat-model:T2"),
        ),
    ),
    # --- use case 2: internal knowledge assistant ---------------------------
    "send_document": (
        RequiredKind(
            kind="RECIPIENT_ENTITLED_TO_DOC",
            rationale=(
                "Sending a customer record to a recipient not entitled to that "
                "customer's data is a cross-tenant disclosure; entitlement of the "
                "actual execution recipient is the load-bearing check."
            ),
            basis=("action-semantics", "tool-arg-schema", "threat-model:T33", "threat-model:T34"),
        ),
        RequiredKind(
            kind="DOC_CLASSIFICATION_PERMITTED",
            rationale=(
                "Independently of the customer link, the document's classification "
                "must be one the recipient is cleared to receive."
            ),
            basis=("action-semantics", "tool-arg-schema", "threat-model:T34"),
        ),
    ),
    # --- use case 3: goodwill discount / store credit ----------------------
    "approve_discount": (
        RequiredKind(
            kind="ORDER_BELONGS_TO_CUSTOMER",
            rationale="A credit issued against a specific order must be that order's owner's.",
            basis=("action-semantics", "tool-arg-schema", "threat-model:T2", "threat-model:T34"),
        ),
        RequiredKind(
            kind="WITHIN_REFUND_WINDOW",
            rationale=(
                "The goodwill credit is valid only within a fixed number of days of "
                "delivery (the use case's own prose); the ladder reuses this kind "
                "for any date-vs-window check."
            ),
            basis=("policy-prose", "threat-model:T2"),
        ),
        RequiredKind(
            kind="AMOUNT_WITHIN_AUTHORITY",
            rationale="The agent's discount authority is capped; above it, the action must escalate.",
            basis=("policy-prose", "threat-model:T2"),
        ),
        RequiredKind(
            kind="AMOUNT_NOT_EXCEEDING_ORDER",
            rationale=(
                "A goodwill credit issued against a specific order should not exceed "
                "that order's own total. The structurally identical service-credit "
                "use case states this rule explicitly ('the credit may never exceed "
                "the order's own total'); the same reasoning applies here."
            ),
            basis=("action-semantics", "tool-arg-schema", "policy-prose", "threat-model:T2"),
            binding_note=(
                "The active discount manifest does not bind this check; "
                "service_credit_approval, a structurally identical goodwill-credit "
                "action, does. Flagged for review — a deliberate goodwill exception "
                "or an oversight."
            ),
        ),
    ),
    # --- use case 4: service credit (onboarding measurement) --------------
    "approve_service_credit": (
        RequiredKind(
            kind="ORDER_BELONGS_TO_CUSTOMER",
            rationale="A credit issued against a specific order must be that order's owner's.",
            basis=("action-semantics", "tool-arg-schema", "threat-model:T2", "threat-model:T34"),
        ),
        RequiredKind(
            kind="AMOUNT_NOT_EXCEEDING_ORDER",
            rationale="The use case's own prose: 'the credit may never exceed the order's own total'.",
            basis=("policy-prose", "action-semantics", "tool-arg-schema", "threat-model:T2"),
        ),
        RequiredKind(
            kind="AMOUNT_WITHIN_AUTHORITY",
            rationale="A lower goodwill-credit authority ceiling applies; above it, escalate.",
            basis=("policy-prose", "threat-model:T2"),
        ),
    ),
    # --- P06 C2: tau2-bench retail domain (6 write tools) -----------------
    "cancel_pending_order": _tau2_order_action(
        "cancel_pending_order is valid only for an order still in 'pending' state; "
        "cancelling anything else is the primary business-rule violation."
    ),
    "modify_pending_order_address": _tau2_order_action(
        "modifying a pending order's shipping address is valid only while the order "
        "is pending; redirecting a shipped order is the business-rule violation "
        "(and, on someone else's order, a package-redirection attack)."
    ),
    "modify_pending_order_items": _tau2_order_action(
        "changing a pending order's items is valid only while the order is pending."
    ),
    "modify_pending_order_payment": _tau2_order_action(
        "changing a pending order's payment method is valid only while the order is pending."
    ),
    "exchange_delivered_order_items": _tau2_order_action(
        "an exchange is valid only for an order that has actually been delivered."
    ),
    "return_delivered_order_items": _tau2_order_action(
        "a return is valid only for an order that has actually been delivered."
    ),
}

# ClaimKinds a reader might expect on a tool but which are deliberately NOT
# required — recorded so the reference is seen to have made a choice, not an
# omission. (kind name, why not.)
DELIBERATELY_NOT_REQUIRED: dict[str, tuple[tuple[str, str], ...]] = {
    "send_document": (
        (
            "EXCERPT_CONTAINS_THIRD_PARTY_PII",
            "PII in an excerpt does not by itself make the send wrong: if the "
            "recipient is entitled to that customer's record, the PII in it is "
            "fine. What makes a send wrong is the entitlement check failing — "
            "detection is a signal, not a gate. (Matches the knowledge-assistant "
            "use case's own thesis.)",
        ),
    ),
    "approve_service_credit": (
        (
            "WITHIN_REFUND_WINDOW",
            "A service complaint (late / damaged / poor experience) is explicitly "
            "not gated by how long ago the order was delivered — unlike a refund "
            "or a discount credit. The use case's own prose says there is no "
            "delivery-window check.",
        ),
    ),
}

# Load-bearing checks with NO ClaimKind to carry them (loss point L2). Advisory
# only — never in the coverage ratio, always listed.
_CURRENCY_INTEGRITY = UnrepresentableRequirement(
    name="currency_integrity",
    rationale=(
        "The disbursed currency should equal the order's currency; a payout in the "
        "wrong currency is a value error. No ClaimKind expresses currency / field "
        "integrity today."
    ),
    basis=("tool-arg-schema", "threat-model:T2"),
)
_TAU2_IDENTITY = UnrepresentableRequirement(
    name="independent_user_authentication",
    rationale=(
        "There is no claim kind or evidence channel for 'the session user is who "
        "they claim to be' in the tau2 retail integration. ORDER_BELONGS_TO_CUSTOMER "
        "is the closest expressible check and is itself unbindable here (see its "
        "binding_note)."
    ),
    basis=("action-semantics", "threat-model:T2", "threat-model:T34"),
)

UNREPRESENTABLE_REQUIRED: dict[str, tuple[UnrepresentableRequirement, ...]] = {
    "issue_refund": (_CURRENCY_INTEGRITY,),
    "approve_discount": (_CURRENCY_INTEGRITY,),
    "approve_service_credit": (_CURRENCY_INTEGRITY,),
    **{
        tool: (_TAU2_IDENTITY,)
        for tool in (
            "cancel_pending_order",
            "modify_pending_order_address",
            "modify_pending_order_items",
            "modify_pending_order_payment",
            "exchange_delivered_order_items",
            "return_delivered_order_items",
        )
    },
}

# The authoritative set of tools this reference covers. A governed manifest
# whose tool is not here must fail loudly in the metric — a new use case
# cannot be silently un-assessed.
GOVERNED_TOOLS: frozenset[str] = frozenset(REQUIRED)


def required_kind_names(tool: str) -> frozenset[str]:
    """The ClaimKind names the reference requires for ``tool``. Raises
    KeyError (loudly) if the tool has no reference entry."""
    return frozenset(rk.kind for rk in REQUIRED[tool])


__all__ = [
    "REFERENCE_ID",
    "BASIS_VOCAB",
    "RequiredKind",
    "UnrepresentableRequirement",
    "REQUIRED",
    "DELIBERATELY_NOT_REQUIRED",
    "UNREPRESENTABLE_REQUIRED",
    "GOVERNED_TOOLS",
    "required_kind_names",
]
