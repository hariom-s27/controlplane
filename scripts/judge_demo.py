"""Judge-facing ControlPlane demo — PRODUCT-01.

Eight deterministic, offline scenarios built entirely on the existing
runtime (controlplane/intercept.py::dispatch_tool, controlplane/decide.py,
controlplane/idempotency.py, controlplane/receipt.py). Nothing here
reimplements governance logic; every verdict, intervention, execution
outcome and receipt in this file is produced by calling that existing
code, not by inventing new decision logic.

The only piece of the real pipeline this script does not exercise is the
LLM-backed claim extractor (controlplane/extract.py::extract_action),
because that requires a live model call. Every scenario below stubs it
with a fixed ProposedAction built from the tool call's structural arguments
and, where the scenario explicitly supplies agent claims, keeps those values
in the ProposedAction's claimed_* fields — the exact technique tests/test_intercept.py's own
`test_gate_on_unmodeled_tool_fails_loudly_never_calls_impl` and
tests/test_knowledge_assistant.py's `_dispatch_send` already use for the
same reason. Everything downstream of that point — claim classification,
registry resolution against the real data/entitlements.db, the Zen JDM
predicate graph, decide(), idempotency and receipt signing — runs for
real. Each scenario below is labeled RUNTIME or FIXTURE (see
_ScenarioResult.evidence_source) so this is never ambiguous on screen.

Run:  python -m scripts.judge_demo            (all eight scenarios)
      python -m scripts.judge_demo --scenario 7
      python -m scripts.judge_demo --reset     (clear demo-local state)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
# The four RUNTIME scenarios (1, 3, 4, 6) all dispatch send_document, which
# only makes sense under the knowledge_assistant manifest — .env's own
# default is CP_MANIFEST=servicing (for the shipped `make demo`), so this
# must be a real assignment, not setdefault. Scenario 2 loads the servicing
# manifest explicitly by name and does not depend on this variable.
os.environ["CP_MANIFEST"] = "knowledge_assistant"

import agents.knowledge_assistant as ka  # noqa: E402
import agents.servicing_agent as servicing  # noqa: E402
from controlplane.decide import decide  # noqa: E402
from controlplane.idempotency import reset_execution_ledger  # noqa: E402
from controlplane.intercept import (  # noqa: E402
    REGISTRY,
    Blocked,
    Pending,
    dispatch_tool,
    register_tool,
)
from controlplane.manifest import load_manifest  # noqa: E402
from controlplane import receipt as cp_receipt  # noqa: E402
from controlplane.receipt import build_receipt  # noqa: E402
from controlplane.receipt import verify as verify_receipt  # noqa: E402
from controlplane.render import to_rupees  # noqa: E402
from controlplane.registry.clock import now as cp_now  # noqa: E402
from controlplane.schema import (  # noqa: E402
    Claim,
    ClaimKind,
    Confidence,
    Evidence,
    ProposedAction,
    Reliability,
    SessionContext,
    Tier,
)

ENTITLEMENTS_DB = ROOT / "data" / "entitlements.db"

_OK, _WARN, _FAIL = "[OK]", "[WARN]", "[FAIL]"

# ---------------------------------------------------------------------------
# Wiring — reuse the real implementations, only adding a call counter so the
# EXECUTION section can show a real, observed call count.
# ---------------------------------------------------------------------------

_call_log: list[dict] = []


def _counting_send_document(**kwargs) -> dict:
    _call_log.append(kwargs)
    return ka._send_document_impl(**kwargs)


_registered_issue_refund = REGISTRY["issue_refund"]


def _counting_issue_refund(**kwargs) -> dict:
    _call_log.append(kwargs)
    return _registered_issue_refund(**kwargs)


register_tool("send_document", _counting_send_document)
register_tool("issue_refund", _counting_issue_refund)


def _extract_stub(**kwargs):
    """Stands in for the LLM-backed extract_action(): the only thing it
    does is turn the tool call's own structural arguments into a
    ProposedAction, with no inference and no model call — matching how
    the real extractor already treats issue_refund/send_document's
    structural fields (schema.py's own tool/order_id/recipient_id/... are
    all structural, never claimed)."""
    return ProposedAction(tool=kwargs["tool"], **kwargs["tool_call_args"])


# ---------------------------------------------------------------------------
# Result type + rendering
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    number: int
    key: str
    title: str
    evidence_source: str  # "RUNTIME" | "FIXTURE" | "N/A"
    available: bool = True
    unavailable_reason: str = ""
    ai_intent: str = ""
    evidence_lines: list[str] = field(default_factory=list)
    policy_lines: list[str] = field(default_factory=list)
    verdict: str | None = None
    intervention: str | None = None
    execution_status: str = ""
    call_count: str = "0"
    execution_result: str = ""
    receipt: dict | None = None
    receipt_verified: bool | None = None
    reasons: list[str] = field(default_factory=list)
    claims_detail: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _receipt_evidence_lines(receipt: dict) -> list[str]:
    lines = []
    for e in receipt.get("evidence", []):
        lines.append(
            f"  {e['claim_id']}: {e['value']!r}  <- {e['source']}  "
            f"(reliability={e['reliability_class']}, confidence={e['confidence']})"
        )
    return lines


def _receipt_policy_lines(receipt: dict) -> list[str]:
    trace = receipt.get("predicate_trace", {})
    lines = []
    for k, v in trace.items():
        if k in ("clause_match", "grounding_score") and v is None:
            continue
        mark = _OK if v is True else (_FAIL if v is False else _WARN)
        lines.append(f"  {mark} {k}: {v}")
    return lines


def _receipt_reason_lines(receipt: dict) -> list[str]:
    reasons = receipt.get("reasons", [])
    if not reasons:
        return ["  (none — every checked rule passed)"]
    return [
        f"  FAILED {r['rule']}: expected {r['expected']!r}, observed {r['observed']!r}"
        for r in reasons
    ]


def _finish_from_receipt(result: ScenarioResult, receipt: dict) -> None:
    result.receipt = receipt
    result.verdict = receipt["verdict"]
    result.intervention = receipt["intervention"]
    result.evidence_lines = _receipt_evidence_lines(receipt) or ["  (no evidence resolved)"]
    result.policy_lines = _receipt_policy_lines(receipt) or ["  (no policy predicate evaluated)"]
    result.reasons = _receipt_reason_lines(receipt)
    result.claims_detail = [
        f"  {c['kind']} (tier={c['tier']}, load_bearing={c['load_bearing']}) asserted={c['asserted']!r}"
        for c in receipt.get("claims", [])
    ]
    result.receipt_verified = verify_receipt(receipt)


# ---------------------------------------------------------------------------
# Shared dispatch helper — runs the REAL dispatch_tool() pipeline with only
# extract_action stubbed (see module docstring). Captures the receipt that
# controlplane/telemetry.py::record() genuinely builds and signs.
# ---------------------------------------------------------------------------


def _run_dispatch(
    trace_id: str,
    subject_id: str | None,
    args: dict,
    *,
    isolate: bool = True,
    tool: str = "send_document",
    manifest_name: str = "knowledge_assistant",
    manifest_id: str = "knowledge_assistant-v1",
    customer_id: str | None = None,
    agent_role: str = "knowledge_assistant",
    use_case: str = "knowledge_assistant",
    claimed_fields: dict[str, Any] | None = None,
    justification: str = "",
    retrieved_chunks: list[str] | None = None,
):
    if isolate:
        reset_execution_ledger()
        _call_log.clear()

    session = SessionContext(
        trace_id=trace_id,
        customer_id=customer_id,
        subject_id=subject_id,
        agent_role=agent_role,
        use_case=use_case,
        manifest_id=manifest_id,
        gate_enabled=True,
    )

    from controlplane import telemetry as _telemetry_mod

    captured: list[dict] = []
    real_record = _telemetry_mod.record

    def _capturing_record(decision, action_dict, latency_ms):
        line = real_record(decision, action_dict, latency_ms)
        captured.append(line)
        return line

    calls_before = len(_call_log)
    status = "EXECUTED"
    exec_result = None
    claimed_fields = claimed_fields or {}

    def _scenario_extract_stub(**kwargs):
        action_fields = _extract_stub(**kwargs).model_dump()
        action_fields.update(claimed_fields)
        return ProposedAction(**action_fields)

    with patch.dict(os.environ, {"CP_MANIFEST": manifest_name}), \
         patch("controlplane.intercept.extract_action", _scenario_extract_stub), \
         patch("controlplane.intercept.record", _capturing_record):
        try:
            exec_result = dispatch_tool(
                tool,
                args,
                session,
                justification=justification,
                retrieved_chunks=retrieved_chunks or [],
            )
        except Blocked:
            status = "BLOCKED"
        except Pending:
            status = "PENDING"

    executed_this_call = len(_call_log) > calls_before
    receipt = captured[-1]["receipt"] if captured else None
    return status, exec_result, executed_this_call, receipt


# ---------------------------------------------------------------------------
# Scenario 1 — NORMAL ALLOW
# ---------------------------------------------------------------------------


def scenario_1_allow() -> ScenarioResult:
    args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-1042",
        "excerpt": "Refunds are accepted within seven days of delivery, per policy v4.2.",
    }
    result = ScenarioResult(
        number=1, key="allow", title="NORMAL ALLOW", evidence_source="RUNTIME"
    )
    result.ai_intent = f"send_document(recipient_id={args['recipient_id']!r}, doc_id={args['doc_id']!r})"
    result.notes.append(
        "EMP-4410 asks for an internal FAQ document that belongs to no specific "
        "customer, and requests it be sent to themself."
    )

    status, exec_result, executed, receipt = _run_dispatch("demo-s1-allow", "EMP-4410", args)
    _finish_from_receipt(result, receipt)
    result.execution_status = status
    result.call_count = "1" if executed else "0"
    result.execution_result = repr(exec_result) if exec_result is not None else "(not executed)"
    return result


# ---------------------------------------------------------------------------
# Scenario 2 — SOURCE UNRELIABLE
# ---------------------------------------------------------------------------


def scenario_2_source_unreliable() -> ScenarioResult:
    result = ScenarioResult(
        number=2,
        key="source_unreliable",
        title="SOURCE UNRELIABLE",
        evidence_source="FIXTURE",
    )
    result.ai_intent = "issue_refund(order_id='ORD-1', amount_paise=100000, currency='INR')"
    result.notes.append(
        "Deterministic demo fixture: the delivery-date evidence is constructed with "
        "reliability_class=INFERRED (below servicing.yaml's 'corroborated' floor) to "
        "exercise controlplane/decide.py's reliability-floor escalation rule "
        "(controlplane/registry/freshness.py) without depending on which row of the "
        "real orders.db happens to be inferred today. The verdict, intervention and "
        "receipt below are produced by the real decide() and receipt signer — only "
        "the input evidence is fixture data."
    )

    manifest = load_manifest("servicing")
    trace_id = "demo-s2-source-unreliable"
    action = ProposedAction(tool="issue_refund", order_id="ORD-1", amount_paise=100000, currency="INR")
    claim = Claim(
        id="c1", kind=ClaimKind.WITHIN_REFUND_WINDOW, subject="ORD-1", tier=Tier.C2, load_bearing=True
    )
    evidence = [
        Evidence(
            claim_id="c1",
            value="2026-08-11",
            source="orders.db (demo fixture)",
            query="SELECT delivered_at FROM orders WHERE order_id='ORD-1'",
            fetched_at=cp_now(),
            reliability_class=Reliability.INFERRED,
            confidence=Confidence.HIGH,
            note="fixture: reliability deliberately set below the manifest's floor",
        )
    ]
    decision = decide(
        trace_id, manifest["manifest_id"], action, [claim], evidence, {"within_window": True}, manifest
    )
    receipt = build_receipt(decision, action.facts_for_predicate(), {})
    cp_receipt.persist({"receipt": receipt, "telemetry": {"source": "judge_demo fixture scenario"}})

    _finish_from_receipt(result, receipt)
    result.execution_status = "PENDING" if result.intervention != "ALLOW" else "EXECUTED"
    result.call_count = "0"
    result.execution_result = "(not executed — awaiting human review)"
    return result


# ---------------------------------------------------------------------------
# Scenario 3 — RELIABLE CONTRADICTION
# ---------------------------------------------------------------------------


def scenario_3_contradiction() -> ScenarioResult:
    args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-2277",
        "excerpt": "Customer Priya Raghavan ... order ORD-77301 ...",
    }
    result = ScenarioResult(
        number=3, key="contradiction", title="RELIABLE CONTRADICTION", evidence_source="RUNTIME"
    )
    result.ai_intent = f"send_document(recipient_id={args['recipient_id']!r}, doc_id={args['doc_id']!r})"
    result.notes.append(
        "Retrieval surfaced a real, correctly-classified internal document — but it "
        "concerns a different customer (CUST-7788) than EMP-4410 is entitled to "
        "(CUST-2291 only). The entitlement predicate reliably contradicts the request."
    )

    status, exec_result, executed, receipt = _run_dispatch("demo-s3-contradiction", "EMP-4410", args)
    _finish_from_receipt(result, receipt)
    result.execution_status = status
    result.call_count = "1" if executed else "0"
    result.execution_result = "(not executed)" if exec_result is None else repr(exec_result)
    return result


# ---------------------------------------------------------------------------
# Scenario 4 — INVALID MODIFY / SAFETY REFUSAL
# ---------------------------------------------------------------------------


def scenario_4_invalid_modify() -> ScenarioResult:
    args = {"recipient_id": "EMP-4410", "doc_id": "DOC-9999", "excerpt": "n/a"}
    result = ScenarioResult(
        number=4, key="invalid_modify", title="INVALID MODIFY / SAFETY REFUSAL", evidence_source="RUNTIME"
    )
    result.ai_intent = f"send_document(recipient_id={args['recipient_id']!r}, doc_id={args['doc_id']!r})"
    result.notes.append(
        "DOC-9999 does not exist in entitlements.db. Both load-bearing claims resolve "
        "to no evidence, so the verdict is UNVERIFIABLE. knowledge_assistant.yaml maps "
        "UNVERIFIABLE to 'allow_with_caveat' (Intervention.MODIFY) — but the real "
        "decide() never computes modified_args for this path, so it stays None. "
        "controlplane/intercept.py::dispatch_tool() treats a non-dict modified_args as "
        "an unresolved MODIFY and raises Pending — it never falls back to executing "
        "the original arguments. This is the input being invalid, not the product."
    )

    status, exec_result, executed, receipt = _run_dispatch("demo-s4-invalid-modify", "EMP-4410", args)
    _finish_from_receipt(result, receipt)
    result.execution_status = "REFUSED — execution prevented" if status == "PENDING" else status
    result.call_count = "1" if executed else "0"
    result.execution_result = "(not executed — original arguments were never substituted)"
    return result


# ---------------------------------------------------------------------------
# Scenario 5 — UNSAFE MODIFY / SAFETY REFUSAL
# ---------------------------------------------------------------------------


def scenario_5_unsafe_modify() -> ScenarioResult:
    args = {"recipient_id": "EMP-0000", "doc_id": "DOC-1042", "excerpt": "n/a"}
    result = ScenarioResult(
        number=5, key="unsafe_modify", title="UNSAFE MODIFY / SAFETY REFUSAL", evidence_source="RUNTIME"
    )
    result.ai_intent = f"send_document(recipient_id={args['recipient_id']!r}, doc_id={args['doc_id']!r})"
    result.notes.append(
        "EMP-0000 does not exist in entitlements.db's subjects table (DOC-1042 does exist — "
        "it is the same real document scenario 1 sends). With no recognized recipient, both "
        "entitlement claims resolve to evidence with confidence=NONE, so the verdict is "
        "UNVERIFIABLE. knowledge_assistant.yaml maps UNVERIFIABLE to 'allow_with_caveat' "
        "(Intervention.MODIFY) — but the real decide() never computes modified_args for this "
        "path, so it stays None. controlplane/intercept.py::dispatch_tool() treats a non-dict "
        "modified_args as an unresolved MODIFY and raises Pending — it never falls back to "
        "executing the original arguments. This is the same unsafe-MODIFY safety refusal "
        "scenario 4 exercises (an unresolved recipient here, instead of an unresolved "
        "document) — no second governance rule, just the existing path with different input."
    )

    status, exec_result, executed, receipt = _run_dispatch("demo-s5-unsafe-modify", "EMP-4410", args)
    _finish_from_receipt(result, receipt)
    result.execution_status = "REFUSED — execution prevented" if status == "PENDING" else status
    result.call_count = "1" if executed else "0"
    result.execution_result = "(not executed — original arguments were never substituted)"
    return result


# ---------------------------------------------------------------------------
# Scenario 6 — DUPLICATE / REPLAY
# ---------------------------------------------------------------------------


def scenario_6_duplicate_replay() -> ScenarioResult:
    args = {
        "recipient_id": "EMP-4410",
        "doc_id": "DOC-1042",
        "excerpt": "Refunds are accepted within seven days of delivery, per policy v4.2.",
    }
    result = ScenarioResult(
        number=6, key="duplicate_replay", title="DUPLICATE / REPLAY", evidence_source="RUNTIME"
    )
    result.ai_intent = f"send_document(recipient_id={args['recipient_id']!r}, doc_id={args['doc_id']!r})  — sent twice, identical trace"

    reset_execution_ledger()
    _call_log.clear()
    status1, exec1, executed1, receipt1 = _run_dispatch(
        "demo-s6-duplicate", "EMP-4410", args, isolate=False
    )
    status2, exec2, executed2, receipt2 = _run_dispatch(
        "demo-s6-duplicate", "EMP-4410", args, isolate=False
    )

    _finish_from_receipt(result, receipt2)
    result.call_count = str(len(_call_log))
    result.execution_status = f"first={status1} (executed={executed1})  second={status2} (executed={executed2})"
    result.execution_result = f"first result={exec1!r}\n  second result={exec2!r}"
    result.notes.append(
        f"idempotency_key is identical on both requests: {receipt1['idempotency_key']} == "
        f"{receipt2['idempotency_key']}. The second request replayed the first's stored result "
        "(controlplane/idempotency.py::ExecutionLedger) without calling the implementation again."
    )
    return result


SERVICING_HERO_ARGS = {
    "order_id": "ORD-88461",
    "amount_paise": 4299900,
    "currency": "INR",
    "item_colour": "blue",
    "item_category": "shoes",
}
SERVICING_ALLOW_ARGS = {
    "order_id": "ORD-90233",
    "amount_paise": 849900,
    "currency": "INR",
    "item_colour": "grey",
    "item_category": "shirt",
}
SERVICING_HERO_TITLE = f"{to_rupees(SERVICING_HERO_ARGS['amount_paise'])} STALE-POLICY REFUND"
SERVICING_ALLOW_TITLE = f"{to_rupees(SERVICING_ALLOW_ARGS['amount_paise'])} IN-POLICY REFUND"


def _run_servicing_refund(
    trace_id: str,
    args: dict,
    *,
    claimed_fields: dict[str, Any] | None = None,
    justification: str = "",
    retrieved_chunks: list[str] | None = None,
):
    return _run_dispatch(
        trace_id,
        None,
        args,
        tool="issue_refund",
        manifest_name="servicing",
        manifest_id="servicing-v1",
        customer_id="CUST-2291",
        agent_role="servicing_agent",
        use_case="servicing",
        claimed_fields=claimed_fields,
        justification=justification,
        retrieved_chunks=retrieved_chunks,
    )


# ---------------------------------------------------------------------------
# Scenario 7 — ₹42,999 STALE-POLICY REFUND (primary Customer Support hero)
# ---------------------------------------------------------------------------


def scenario_7_stale_policy_refund() -> ScenarioResult:
    args = dict(SERVICING_HERO_ARGS)
    retrieved_policy = servicing._retrieve_policy(servicing.CUSTOMER_MESSAGE)
    stale_policy = next(
        chunk for chunk in retrieved_policy if chunk["chunk_id"] == "refund_window_v38"
    )
    claimed_fields = {
        "claimed_policy_version": stale_policy["version"],
        "claimed_clause_text": stale_policy["text"],
        "claimed_reasoning": (
            f"The retrieved {stale_policy['version']} policy permits a full refund "
            "within 30 days of delivery."
        ),
    }
    result = ScenarioResult(
        number=7,
        key="stale_policy_refund",
        title=SERVICING_HERO_TITLE,
        evidence_source="RUNTIME",
    )
    item = f"{args['item_colour']} running {args['item_category']}"
    result.ai_intent = (
        f"Refund {to_rupees(args['amount_paise'])} for {item} on {args['order_id']} "
        f"using retrieved policy {stale_policy['version']}"
    )
    result.notes.append(
        f"The agent's stale retrieval supplied refund policy {stale_policy['version']}; "
        "ControlPlane resolves the order, current policy, and authority ceiling from "
        "authoritative company sources before execution."
    )

    status, exec_result, executed, receipt = _run_servicing_refund(
        "demo-s7-stale-policy-refund",
        args,
        claimed_fields=claimed_fields,
        justification=claimed_fields["claimed_reasoning"],
        retrieved_chunks=[chunk["text"] for chunk in retrieved_policy],
    )
    _finish_from_receipt(result, receipt)
    result.execution_status = status
    result.call_count = "1" if executed else "0"
    result.execution_result = "(not executed)" if exec_result is None else repr(exec_result)
    return result


# ---------------------------------------------------------------------------
# Scenario 8 — Customer Support ALLOW control
# ---------------------------------------------------------------------------


def scenario_8_servicing_allow() -> ScenarioResult:
    args = dict(SERVICING_ALLOW_ARGS)
    result = ScenarioResult(
        number=8,
        key="servicing_allow",
        title=SERVICING_ALLOW_TITLE,
        evidence_source="RUNTIME",
    )
    result.ai_intent = (
        f"Refund {to_rupees(args['amount_paise'])} for order {args['order_id']} "
        "under the current policy"
    )

    status, exec_result, executed, receipt = _run_servicing_refund(
        "demo-s8-servicing-allow",
        args,
    )
    _finish_from_receipt(result, receipt)
    result.execution_status = status
    result.call_count = "1" if executed else "0"
    result.execution_result = repr(exec_result) if exec_result is not None else "(not executed)"
    return result


@dataclass(frozen=True)
class ScenarioDefinition:
    index: int
    key: str
    title: str
    supported_profiles: tuple[str, ...]
    hero: bool
    run: Callable[[], ScenarioResult]

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "key": self.key,
            "title": self.title,
            "supported_profiles": list(self.supported_profiles),
            "hero": self.hero,
        }


SCENARIO_DEFINITIONS = [
    ScenarioDefinition(1, "allow", "NORMAL ALLOW", ("knowledge_assistant-v1",), False, scenario_1_allow),
    ScenarioDefinition(2, "source_unreliable", "SOURCE UNRELIABLE", ("servicing-v1",), False, scenario_2_source_unreliable),
    ScenarioDefinition(3, "contradiction", "RELIABLE CONTRADICTION", ("knowledge_assistant-v1",), False, scenario_3_contradiction),
    ScenarioDefinition(4, "invalid_modify", "INVALID MODIFY / SAFETY REFUSAL", ("knowledge_assistant-v1",), False, scenario_4_invalid_modify),
    ScenarioDefinition(5, "unsafe_modify", "UNSAFE MODIFY / SAFETY REFUSAL", ("knowledge_assistant-v1",), False, scenario_5_unsafe_modify),
    ScenarioDefinition(6, "duplicate_replay", "DUPLICATE / REPLAY", ("knowledge_assistant-v1",), False, scenario_6_duplicate_replay),
    ScenarioDefinition(7, "stale_policy_refund", SERVICING_HERO_TITLE, ("servicing-v1",), True, scenario_7_stale_policy_refund),
    ScenarioDefinition(8, "servicing_allow", SERVICING_ALLOW_TITLE, ("servicing-v1",), False, scenario_8_servicing_allow),
]
SCENARIOS = [definition.run for definition in SCENARIO_DEFINITIONS]


def scenario_catalog() -> list[dict[str, Any]]:
    """Presentation metadata from the same definitions that dispatch RUN."""
    return [definition.catalog_entry() for definition in SCENARIO_DEFINITIONS]


# ---------------------------------------------------------------------------
# Rendering — the primary screen (section 8 of the spec this implements)
# ---------------------------------------------------------------------------


def render(result: ScenarioResult) -> None:
    width = 70
    print("=" * width)
    print("CONTROLPLANE")
    print("AI ACTION GOVERNANCE")
    print("=" * width)
    print(
        f"SCENARIO {result.number}/{len(SCENARIOS)} — {result.title}   "
        f"[evidence source: {result.evidence_source}]"
    )
    print()

    if not result.available:
        print("NOT AVAILABLE")
        print(f"  {result.unavailable_reason}")
        print()
        for n in result.notes:
            print(f"  note: {n}")
        print("-" * width)
        return

    print("AI INTENT")
    print(f"  {result.ai_intent}")
    print()
    print("EVIDENCE")
    for line in result.evidence_lines:
        print(line)
    print()
    print("POLICY")
    for line in result.policy_lines:
        print(line)
    print()
    print("DECISION")
    print(f"  Verdict: {result.verdict}")
    print()
    print("INTERVENTION")
    print(f"  {result.intervention}")
    print()
    print("EXECUTION")
    print(f"  Status: {result.execution_status}")
    print(f"  Call count: {result.call_count}")
    print(f"  Result: {result.execution_result}")
    print()
    print("AUDIT RECEIPT")
    print(f"  Trace ID: {result.receipt['trace_id']}")
    print(f"  Idempotency: {result.receipt['idempotency_key']}")
    sig_state = "VALID" if result.receipt_verified else "INVALID"
    print(f"  Signature: {sig_state}")
    print()

    if result.notes:
        for n in result.notes:
            print(f"  note: {n}")
        print()

    print("-" * width)
    print("WHY DID CONTROLPLANE DECIDE THIS? (expand)")
    print("  claims:")
    for line in result.claims_detail:
        print(" " + line)
    print("  reasons (failed checks only):")
    for line in result.reasons:
        print(" " + line)
    print("  root cause: " + str(result.receipt.get("root_cause")))
    print("-" * width)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _check_preconditions() -> None:
    if not ENTITLEMENTS_DB.exists():
        print(
            "ControlPlane databases are not built yet.\n"
            "Run setup first:\n"
            "  Windows:      .\\make.ps1 setup\n"
            "  macOS/Linux:  make setup\n"
        )
        sys.exit(1)


def reset_demo() -> None:
    reset_execution_ledger()
    _call_log.clear()
    for p in (cp_receipt.OPERATIONAL_TRAIL, cp_receipt.PRIVILEGED_TRAIL):
        if p.exists():
            p.unlink()
    print("Demo state reset: idempotency ledger cleared, decisions.jsonl removed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Judge-facing ControlPlane demo (PRODUCT-01)")
    parser.add_argument(
        "--scenario",
        type=int,
        choices=range(1, len(SCENARIOS) + 1),
        default=None,
        help="run one scenario only",
    )
    parser.add_argument("--reset", action="store_true", help="reset demo-local state and exit")
    args = parser.parse_args(argv)

    if args.reset:
        reset_demo()
        return 0

    _check_preconditions()

    to_run = [SCENARIOS[args.scenario - 1]] if args.scenario else SCENARIOS
    for fn in to_run:
        # fn() itself performs the real dispatch, and the real (registered)
        # tool implementation may print its own execution line (e.g.
        # "DOCUMENT SENT ...") as a side effect — genuine runtime output,
        # not part of this script's rendering. Anchor it under a header
        # first so it doesn't appear to float above the scenario it belongs to.
        print(f">>> running scenario {fn.__name__} ...")
        render(fn())

    print("All scenarios rendered. Run again with --reset to clear demo-local state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
