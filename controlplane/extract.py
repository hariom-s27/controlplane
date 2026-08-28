"""S4 — claim extraction: the agent's free-form tool call, justification, and
retrieved chunks turn into a typed ProposedAction (the claims) and a list of
Claim objects (the checkable assertions). D2's whole point, restated: these
are the HYPOTHESIS. The registry (S6) provides the test. See
ProposedAction.facts_for_predicate() in controlplane/schema.py — nothing
built here is trusted by construction, only by what gets independently
resolved later.

Uses instructor with Mode.JSON, not Mode.TOOLS. Its default (Mode.TOOLS)
returns silent empty extractions on most Featherless models — this is
written down because CLAUDE.md says it has already cost an afternoon once.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import instructor
from openai import OpenAI
from pydantic import BaseModel

from agents.llm import cache_key
from controlplane.schema import Claim, ClaimKind, ProposedAction

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "data" / "fixtures" / "extract"
FIXTURES.mkdir(parents=True, exist_ok=True)

EXTRACT_PROMPT = (
    "You are extracting structured claims from a customer servicing agent's "
    "justification for a proposed action. Fill each field ONLY from what the "
    "justification or retrieved policy text actually states. If a fact is "
    "not stated, leave that field null - do not guess, infer, or fill in a "
    "plausible-looking value. A missing claim is a normal, correct outcome: "
    "in practice the delivery date is absent from the customer's own message "
    "roughly 30% of the time, and a missing claim that becomes UNVERIFIABLE "
    "downstream is the system working as intended, not a failure to extract."
)


class _ClaimedFields(BaseModel):
    """The ONLY thing Instructor is allowed to populate. R1, applied to
    extraction: order_id/amount_paise/currency are structural and come from
    the tool call directly in extract_action() below — they never pass
    through this model, so the LLM has no path to overwrite them.

    Fields are required-but-nullable (`date | None` with NO `= None`
    default), not optional-with-default. That difference matters more than
    it looks: Qwen3-8B under Mode.JSON sometimes wraps its answer as
    {"_ClaimedFields": {...fields...}} instead of the flat shape asked for.
    With a `= None` default, Pydantic treats the (then-absent) top-level
    keys as "not provided, use the default" and silently validates into an
    all-None object — no exception, so Instructor never learns to retry.
    Required-but-nullable makes that same input a real validation error,
    which Instructor's retry loop feeds back to the model and which does
    then self-correct in practice (verified: retry 2/2 fixed it)."""

    claimed_delivered_at: date | None
    claimed_policy_version: str | None
    claimed_clause_text: str | None
    claimed_reasoning: str | None


# Which claims are relevant to which tool. S5's ladder.py classifies each
# into a tier; this only decides which claims exist for a given action.
_CLAIM_KINDS_BY_TOOL: dict[str, list[ClaimKind]] = {
    "issue_refund": [
        ClaimKind.ORDER_BELONGS_TO_CUSTOMER,
        ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER,
        ClaimKind.WITHIN_REFUND_WINDOW,
        ClaimKind.AMOUNT_WITHIN_AUTHORITY,
        ClaimKind.POLICY_CLAUSE_CURRENT,
        ClaimKind.CLAUSE_SEMANTICS_MATCH,
        ClaimKind.ORDER_ATTRIBUTES_MATCH,  # R3 extended: item_colour/item_category, now structural
    ],
    # S13, use case 2: correctness -> entitlement. Order matters for the
    # receipt's reasons list: classification first (the general question),
    # then the customer-specific one the cross-tenant demo hinges on.
    "send_document": [
        ClaimKind.DOC_CLASSIFICATION_PERMITTED,
        ClaimKind.RECIPIENT_ENTITLED_TO_DOC,
        ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII,
    ],
}

# Mechanical mapping from each ClaimKind to the ProposedAction field its
# asserted_value comes from. Not handed down by any spec — a judgment call
# made here for lack of a more detailed one. Adjust freely; nothing else
# depends on this beyond what shows up on a receipt line.
_ASSERTED_VALUE_FIELD: dict[ClaimKind, str] = {
    ClaimKind.ORDER_BELONGS_TO_CUSTOMER: "order_id",
    ClaimKind.AMOUNT_NOT_EXCEEDING_ORDER: "amount_paise",
    ClaimKind.WITHIN_REFUND_WINDOW: "claimed_delivered_at",
    ClaimKind.AMOUNT_WITHIN_AUTHORITY: "amount_paise",
    ClaimKind.POLICY_CLAUSE_CURRENT: "claimed_policy_version",
    ClaimKind.CLAUSE_SEMANTICS_MATCH: "claimed_clause_text",
    ClaimKind.RECIPIENT_ENTITLED_TO_DOC: "recipient_id",
    ClaimKind.DOC_CLASSIFICATION_PERMITTED: "recipient_id",
    # EXCERPT_CONTAINS_THIRD_PARTY_PII has nothing "asserted" — it's a
    # derived check on the excerpt's actual content at decision time, not a
    # claim the agent made. Left out of this table on purpose; asserted_value
    # stays None for it, same pattern as grounding's C3 check.
    # ORDER_ATTRIBUTES_MATCH needs two fields (colour + category), handled
    # as a special case in build_claims() below rather than forced into
    # this one-field-per-kind table.
}


def _fresh_client() -> OpenAI:
    """Deliberately NOT agents.llm.client()'s memoized singleton. Instructor
    patches whatever client instance it wraps; chat()'s raw, uncached-shape
    calls must keep using an unpatched one, so extraction gets its own."""
    return OpenAI(
        api_key=os.environ["FEATHERLESS_API_KEY"],
        base_url=os.environ.get("CP_BASE_URL", "https://api.featherless.ai/v1"),
    )


def extract_action(
    tool: str,
    tool_call_args: dict[str, Any],
    justification: str,
    retrieved_chunks: list[str],
    force_live: bool = False,
) -> ProposedAction:
    """tool_call_args populates the structural fields directly, unconditionally.
    Instructor only ever fills _ClaimedFields, from justification + retrieved
    text. R6: cached like every other LLM call, in its own fixture subdir."""
    payload = {
        "model": os.environ["CP_MODEL"],
        "tool": tool,
        "tool_call": tool_call_args,
        "justification": justification,
        "retrieved": retrieved_chunks,
    }
    f = FIXTURES / f"{cache_key(payload)}.json"

    if not force_live and f.exists():
        claimed = _ClaimedFields.model_validate_json(f.read_text())
    else:
        if os.environ.get("CP_MODE", "fixture") != "live":
            raise RuntimeError(
                f"No fixture {f.name} and CP_MODE != live. Run with CP_MODE=live once to record it."
            )

        extractor = instructor.from_openai(_fresh_client(), mode=instructor.Mode.JSON)
        try:
            claimed = extractor.chat.completions.create(
                model=os.environ["CP_MODEL"],
                response_model=_ClaimedFields,
                messages=[
                    {"role": "system", "content": EXTRACT_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "tool_call": tool_call_args,
                                "justification": justification,
                                "retrieved": retrieved_chunks,
                            }
                        ),
                    },
                ],
                max_retries=2,
            )
        except Exception:
            # S4's "what breaks": a model that can't hold the schema after
            # max_retries. All-None claimed_* routes to UNVERIFIABLE
            # downstream, the safe direction — never guess instead.
            claimed = _ClaimedFields(
                claimed_delivered_at=None,
                claimed_policy_version=None,
                claimed_clause_text=None,
                claimed_reasoning=None,
            )

        f.write_text(claimed.model_dump_json(indent=2))

    return ProposedAction(
        tool=tool,
        order_id=tool_call_args.get("order_id"),
        amount_paise=tool_call_args.get("amount_paise"),
        currency=tool_call_args.get("currency", "INR"),
        recipient_id=tool_call_args.get("recipient_id"),
        doc_id=tool_call_args.get("doc_id"),
        item_colour=tool_call_args.get("item_colour"),
        item_category=tool_call_args.get("item_category"),
        excerpt=tool_call_args.get("excerpt"),
        **claimed.model_dump(),
    )


def build_claims(action: ProposedAction) -> list[Claim]:
    """One Claim per ClaimKind relevant to this action's tool. tier and
    load_bearing stay unset here — controlplane/ladder.py (S5) fills them.

    Raises for an unmodeled tool rather than returning []: a tool with no
    claims sails through decide() with nothing to check, which silently
    resolves to VERIFIED/ALLOW — a real bypass of the gate, not a safe
    default. Every governed tool needs a row here, deliberately, the same
    way ladder.py and compensation.py fail loudly on a missing row."""
    if action.tool not in _CLAIM_KINDS_BY_TOOL:
        raise KeyError(
            f"controlplane/extract.py has no claim kinds for tool={action.tool!r} — "
            "every governed tool needs a row in _CLAIM_KINDS_BY_TOOL"
        )
    kinds = _CLAIM_KINDS_BY_TOOL[action.tool]
    claims = []
    for kind in kinds:
        subject = _subject_for(kind, action)
        if kind is ClaimKind.ORDER_ATTRIBUTES_MATCH:
            value = {"colour": action.item_colour, "category": action.item_category}
        else:
            field = _ASSERTED_VALUE_FIELD.get(kind)
            value = getattr(action, field, None) if field else None
            if value is not None and not isinstance(value, (str, int, float, bool)):
                value = str(value)  # e.g. a date -> ISO string; keeps asserted_value JSON-safe
        claims.append(Claim(id=f"{subject}:{kind.value}", kind=kind, subject=subject, asserted_value=value))
    return claims


# Which "entity" (schema.py's Claim.subject: "the entity this is about")
# each kind is actually about. Order-related kinds resolve against
# order_id; policy-related kinds resolve against a policy_id, which is NOT
# the same identifier — a claim about the current refund_window clause is
# about "refund_window", never about the order that happens to be in
# question. Getting this wrong sends PolicyResolver querying
# WHERE policy_id = 'ORD-88461', which finds nothing and reports
# UNVERIFIED/NONE — a real bug caught by running the milestone live.
_POLICY_ID_FOR_KIND: dict[ClaimKind, str] = {
    ClaimKind.POLICY_CLAUSE_CURRENT: "refund_window",
    ClaimKind.CLAUSE_SEMANTICS_MATCH: "refund_window",
}


def _subject_for(kind: ClaimKind, action: ProposedAction) -> str:
    if kind in _POLICY_ID_FOR_KIND:
        return _POLICY_ID_FOR_KIND[kind]
    return action.order_id or action.doc_id or "unknown"


__all__ = ["extract_action", "build_claims", "EXTRACT_PROMPT"]
