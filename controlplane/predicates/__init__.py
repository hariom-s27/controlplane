"""S7 — the predicate engine. Rules are data (a Zen Engine JDM graph named
by the manifest, ``predicate_graph: graphs/<name>.json``), not code, per the
Round 2 brief's "configurable policy layer."

A clause-version check ("claimed_version == current_version") deliberately
does NOT live in a graph: comparing a claimed value against evidence
requires the claimed value to cross into the engine, which is exactly what
the architecture ("no claimed_* field crosses this boundary, ever")
forbids. That comparison is a different operation — checking a claim's own
assertion against its own resolved evidence, which is decide()'s job (S9).
See clause_matches_claim() below, intentionally NOT part of evaluate()'s
guarded path.

Everything the graph sees arrives through ``action.facts_for_predicate()``
and the manifest's evidence bindings (controlplane/bindings.py) — never a
prose-derived ``claimed_*`` field.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import zen

from controlplane.schema import Claim, Evidence, ProposedAction

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFESTS_DIR = ROOT / "manifests"

_engine = zen.ZenEngine()
_decisions: dict[str, object] = {}  # graph path (relative to manifests/) -> zen.ZenDecision


def _decision_for(graph_rel: str):
    if graph_rel not in _decisions:
        path = MANIFESTS_DIR / graph_rel
        _decisions[graph_rel] = _engine.create_decision(path.read_text(encoding="utf-8"))
    return _decisions[graph_rel]


def evaluate(evidence: dict, action: ProposedAction, manifest: dict) -> dict:
    """The only boundary the predicate engine is allowed to see through.
    `action.facts_for_predicate()` — never action.model_dump() — is what
    makes it structurally impossible for a claimed_* field to reach here.

    One graph per use case: the manifest names its own graph
    (``predicate_graph: graphs/<name>.json``, relative to manifests/) —
    never the tool name. "Same engine, different behaviour" means the
    manifest is what decides, the same way it decides window_days or the
    authority ceiling."""
    safe_evidence = copy.deepcopy(evidence)
    unavailable_predicates: dict[str, str] = {}
    # Zen's date() function throws on null.  A null authoritative field is an
    # availability/reliability result, not a predicate-engine crash.  Use a
    # transient parseable sentinel only to let independent expressions run,
    # then erase both date-dependent outputs before they can influence decide.
    # Manifest-driven, not name-gated: only a manifest whose own
    # claim_bindings actually declare a delivered_at predicate_key can be
    # missing it — a use case with no such binding (e.g. knowledge_assistant)
    # must never have this key spuriously injected. Checked by "is this key
    # bound at all", so absence (the claim never resolved, so build_predicate_payload
    # omitted the key) and an explicit null both take this path.
    _expects_delivered_at = any(
        b.get("predicate_key") == "delivered_at" for b in manifest.get("claim_bindings", [])
    )
    if _expects_delivered_at and safe_evidence.get("delivered_at") is None:
        safe_evidence["delivered_at"] = safe_evidence.get("clock", {}).get("today")
        unavailable_predicates = {
            "days_elapsed": "delivered_at is NULL",
            "within_window": "delivered_at is NULL",
        }

    order = safe_evidence.get("order")
    if isinstance(order, dict):
        if order.get("customer_id") is None:
            order["customer_id"] = safe_evidence.get("session", {}).get("customer_id")
            unavailable_predicates["entity_match"] = "order.customer_id is unavailable"
        if order.get("amount_paise") is None:
            order["amount_paise"] = action.amount_paise or 0
            unavailable_predicates["amount_sane"] = "order.amount_paise is unavailable"
        if order.get("item_colour") is None:
            order["item_colour"] = action.item_colour
            unavailable_predicates["attributes_match"] = "order attributes are unavailable"
        if order.get("item_category") is None:
            order["item_category"] = action.item_category
            unavailable_predicates["attributes_match"] = "order attributes are unavailable"

    if "authority_ceiling_paise" in safe_evidence and safe_evidence.get("authority_ceiling_paise") is None:
        safe_evidence["authority_ceiling_paise"] = action.amount_paise or 0
        unavailable_predicates["within_authority"] = "authority ceiling is unavailable"

    payload = {
        "evidence": safe_evidence,
        "action": action.facts_for_predicate(),
        # only the policy scalars the graph reads — not the P02 structural
        # keys (claim_bindings / predicate_payload / compensation), which the
        # Zen engine has no reason to see and would have to serialise.
        "manifest": {k: v for k, v in manifest.items()
                     if k not in ("claim_bindings", "predicate_payload", "compensation")
                     and not k.startswith("_")},
    }
    response = _decision_for(manifest["predicate_graph"]).evaluate(payload, {"trace": True})
    result = dict(response["result"])
    for key in unavailable_predicates:
        result[key] = None
    trace = response.get("trace", {})
    if unavailable_predicates:
        trace = {
            "engine": trace,
            "unavailable_predicates": unavailable_predicates,
        }
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
