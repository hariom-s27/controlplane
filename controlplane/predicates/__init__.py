"""S7 — the predicate engine. Rules are data (a Zen Engine JDM graph,
controlplane/predicates/graphs/servicing.json), not code, per the Round 2
brief's "configurable policy layer."

R1 (window) · R2 (authority) · R3 (entity match, extended) · R4 (amount
sane) live in the graph. R5 ("claimed_version == current_version")
deliberately does NOT: comparing a claimed value against evidence requires
the claimed value to cross into the engine, which is exactly what R1 of the
architecture ("no claimed_* field crosses this boundary, ever") forbids.
That comparison is a different operation — checking a claim's own assertion
against its own resolved evidence, which is decide()'s job (S9), not a
business rule to evaluate over trusted facts. See clause_matches_claim()
below, which is intentionally NOT part of evaluate()'s guarded path.

R3 is split into two output fields: `entity_match` (customer_id identity)
and `attributes_match` (D52: does the item the agent said the customer
described — item_colour/item_category, DECLARED tool-call arguments on
issue_refund, not agent prose — match the resolved order's actual
attributes). Both are structural: they reach here the same way order_id
does, through facts_for_predicate(), never through claimed_clause_text or
any other prose-derived field.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import zen

from controlplane.schema import Claim, Evidence, ProposedAction

ROOT = Path(__file__).resolve().parent.parent.parent
GRAPHS_DIR = ROOT / "controlplane" / "predicates" / "graphs"

_engine = zen.ZenEngine()
_decisions: dict[str, object] = {}  # graph name -> zen.ZenDecision, loaded lazily once each


def _decision_for(graph_name: str):
    if graph_name not in _decisions:
        path = GRAPHS_DIR / f"{graph_name}.json"
        _decisions[graph_name] = _engine.create_decision(path.read_text(encoding="utf-8"))
    return _decisions[graph_name]


def evaluate(evidence: dict, action: ProposedAction, manifest: dict) -> dict:
    """The only boundary the predicate engine is allowed to see through.
    `action.facts_for_predicate()` — never action.model_dump() — is what
    makes it structurally impossible for a claimed_* field to reach here.

    One graph per use case (S13): which graph is picked by manifest["_name"]
    (set by controlplane/manifest.py's loader), never by the tool name
    directly — "same engine, different behaviour" means the manifest is
    what decides, the same way it decides window_days or the authority
    ceiling."""
    graph_name = manifest.get("_name", "servicing")
    safe_evidence = copy.deepcopy(evidence)
    unavailable_predicates: dict[str, str] = {}

    # Zen's date() throws on null. Parseable sentinels let unrelated
    # predicates run; affected outputs are erased before decide() sees them.
    if graph_name == "servicing" and safe_evidence.get("delivered_at") is None:
        safe_evidence["delivered_at"] = safe_evidence.get("clock", {}).get("today", "1970-01-01")
        unavailable_predicates.update(
            {
                "days_elapsed": "delivered_at is unavailable",
                "within_window": "delivered_at is unavailable",
            }
        )

    order = safe_evidence.setdefault("order", {}) if graph_name == "servicing" else None
    if isinstance(order, dict):
        if order.get("customer_id") is None:
            order["customer_id"] = safe_evidence.get("session", {}).get("customer_id") or "__unavailable__"
            unavailable_predicates["entity_match"] = "order.customer_id is unavailable"
        if order.get("amount_paise") is None:
            order["amount_paise"] = action.amount_paise or 0
            unavailable_predicates["amount_sane"] = "order.amount_paise is unavailable"
        if order.get("item_colour") is None:
            order["item_colour"] = action.item_colour or "__unavailable__"
            unavailable_predicates["attributes_match"] = "order attributes are unavailable"
        if order.get("item_category") is None:
            order["item_category"] = action.item_category or "__unavailable__"
            unavailable_predicates["attributes_match"] = "order attributes are unavailable"

    if graph_name == "servicing" and safe_evidence.get("authority_ceiling_paise") is None:
        safe_evidence["authority_ceiling_paise"] = action.amount_paise or 0
        unavailable_predicates["within_authority"] = "authority ceiling is unavailable"

    payload = {"evidence": safe_evidence, "action": action.facts_for_predicate(), "manifest": manifest}
    response = _decision_for(graph_name).evaluate(payload, {"trace": True})
    result = dict(response["result"])
    for field in unavailable_predicates:
        result[field] = None
    trace = response.get("trace", {})
    if unavailable_predicates:
        trace = {"engine": trace, "unavailable_predicates": unavailable_predicates}
    return {"result": result, "trace": trace}


def clause_matches_claim(claim: Claim, evidence: Evidence) -> bool:
    """The R5-equivalent check, deliberately outside evaluate()'s guarded
    payload: does what the agent claimed match what's actually current?
    Both claim.asserted_value and evidence.value are already-extracted /
    already-resolved values by the time this runs — this compares two
    known facts, it doesn't smuggle prose into a business-rule engine.

    No assertion (asserted_value is None, S4's normal "missing is a correct
    outcome" case) is NOT a mismatch — there's nothing to contradict. It's
    UNVERIFIABLE territory, not CONTRADICTED, and decide() is what
    distinguishes those, not this function."""
    if claim.asserted_value is None:
        return True
    return claim.asserted_value == evidence.value


__all__ = ["evaluate", "clause_matches_claim"]
