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
    payload = {"evidence": evidence, "action": action.facts_for_predicate(), "manifest": manifest}
    response = _decision_for(graph_name).evaluate(payload, {"trace": True})
    return {"result": response["result"], "trace": response.get("trace", {})}


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
