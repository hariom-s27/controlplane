#!/usr/bin/env python3
"""Task P08 -- robustness and failure injection.

This harness exercises the production interception path while keeping every
mutable database, receipt trail, queue, and execution ledger isolated.  It
does not edit the frozen P03 gold set or the P04/P05 artifacts.

The record-error sweep is predeclared here, rather than selected after seeing
results.  It uses the P04 headline binary-direction estimand on the 140
non-ambiguous cases and compares against the frozen B4 TraceGrounded value
123/140.  P03 cases sharing an order are one fault-allocation unit.

Run from the repository root:

    python bench/failure_injection.py            # prints the JSON result only
    python bench/failure_injection.py --write    # also writes the committed report

``--write`` regenerates ``reports/robustness.md`` and merges
``reports/summary.json['p08_robustness']`` in place, touching no other key.  The
frozen P03/P04/P05 artifacts are never written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sqlite3
import sys
import tempfile
import traceback
from collections import Counter
from contextlib import ExitStack, closing, contextmanager
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import baselines as B  # noqa: E402  (frozen P04 helpers, read-only)
import controlplane.escalation as escalation_module  # noqa: E402
import controlplane.ground as ground_module  # noqa: E402
import controlplane.intercept as intercept  # noqa: E402
import controlplane.receipt as receipt_module  # noqa: E402
import controlplane.registry.entitlements as entitlements_registry  # noqa: E402
import controlplane.registry.orders as orders_registry  # noqa: E402
import controlplane.registry.policy as policy_registry  # noqa: E402
import controlplane.telemetry as telemetry_module  # noqa: E402
from controlplane.idempotency import reset_execution_ledger  # noqa: E402
from controlplane.manifest import load_manifest  # noqa: E402
from controlplane.registry.clock import set_clock  # noqa: E402
from controlplane.schema import (  # noqa: E402
    ClaimKind,
    Confidence,
    Intervention,
    ProposedAction,
    Reliability,
    SessionContext,
    Verdict,
)


DATA = ROOT / "data"
REPORTS = ROOT / "reports"

FROZEN_TODAY = date(2026, 8, 14)
WINDOW_DAYS = 7
FROZEN_B4_CORRECT = 123
FROZEN_B4_N = 140
FROZEN_B4_ACCURACY = FROZEN_B4_CORRECT / FROZEN_B4_N
GRID = tuple(i / 20 for i in range(21))  # fixed 0.00, 0.05, ..., 1.00
RANK_SALT = "p08-wrong-record-v1"
EXPECTED_ELIGIBLE_RECORDS = 85
BOOTSTRAP_ITERS = 5000
BOOTSTRAP_SEED = 20260814
FLAGGED = {"BLOCK", "ESCALATE", "MODIFY"}

CURRENT_CLAUSE = (
    "Customers may request a full refund within 7 days of the delivery date. "
    "Requests made after 7 days may be eligible for store credit at the "
    "discretion of a supervisor. Refunds are issued to the original payment "
    "method within 5-7 business days of approval."
)

FROZEN_INPUTS = (
    ROOT / "bench" / "gold_set.jsonl",
    ROOT / "bench" / "ground_truth_holdout.jsonl",
    ROOT / "bench" / "human_label_sample.csv",
    REPORTS / "baselines.md",
    REPORTS / "evidence-ablation.md",
    REPORTS / "summary.json",
)

_MISSING = object()


# ---------------------------------------------------------------------------
# Isolation and small helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): _sha256(path) for path in FROZEN_INPUTS}


def _assert_frozen_b4() -> None:
    summary = json.loads((REPORTS / "summary.json").read_text(encoding="utf-8"))
    observed = summary["p04_baselines"]["mcnemar_b4_vs_b5"]["accuracy_b4"]
    if not math.isclose(float(observed), FROZEN_B4_ACCURACY, rel_tol=0.0, abs_tol=1e-15):
        raise AssertionError(
            "P08 comparator drift: expected frozen P04 B4 binary accuracy "
            f"{FROZEN_B4_CORRECT}/{FROZEN_B4_N}, observed {observed!r}"
        )


def _clone_store(source: Path, target: Path) -> Path:
    """Create a transaction-consistent clone without opening the source writable."""

    target.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    # closing(), not the bare `with`: sqlite3's context manager only manages a
    # transaction, it never closes the handle. On Windows a leaked handle keeps
    # the cloned file locked and breaks TemporaryDirectory cleanup.
    with closing(sqlite3.connect(source_uri, uri=True)) as src, closing(
        sqlite3.connect(target)
    ) as dst:
        src.backup(dst)
    return target


@contextmanager
def _patched_attr(obj: Any, name: str, value: Any) -> Iterator[None]:
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextmanager
def _patched_env(name: str, value: str | None) -> Iterator[None]:
    old = os.environ.get(name, _MISSING)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if old is _MISSING:
            os.environ.pop(name, None)
        else:
            os.environ[name] = str(old)


@contextmanager
def _patched_mapping(mapping: dict, key: str, value: Any) -> Iterator[None]:
    old = mapping.get(key, _MISSING)
    mapping[key] = value
    try:
        yield
    finally:
        if old is _MISSING:
            mapping.pop(key, None)
        else:
            mapping[key] = old


def _fixed_extractor(
    action: ProposedAction,
    after_extract: Callable[[], None] | None = None,
) -> Callable[..., ProposedAction]:
    """Hold extraction noise at zero while retaining the real downstream path."""

    def extract_action(**_kwargs: Any) -> ProposedAction:
        if after_extract is not None:
            after_extract()
        return action

    return extract_action


@contextmanager
def _runtime_scope(
    root: Path,
    *,
    manifest_name: str,
    orders_db: Path | None = None,
    policy_db: Path | None = None,
    entitlements_db: Path | None = None,
    extractor: Callable[..., ProposedAction] | None = None,
    active_manifest: dict | None = None,
    grounding: str = "off",
    ground_score: Callable[..., float] | None = None,
    tools: dict[str, Callable[..., Any]] | None = None,
) -> Iterator[dict[str, Path]]:
    """Redirect every P08 mutation/write and restore process globals afterward."""

    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "root": root,
        "trail": root / "decisions.jsonl",
        "privileged_trail": root / "decisions_privileged.jsonl",
        "pending": root / "pending_actions.jsonl",
    }

    reset_execution_ledger()
    set_clock(FROZEN_TODAY)
    try:
        with ExitStack() as stack:
            stack.enter_context(_patched_env("CP_RECEIPT_SECRET", "p08-isolated-secret"))
            stack.enter_context(_patched_env("CP_GROUNDING", grounding))
            stack.enter_context(_patched_env("CP_MANIFEST", manifest_name))
            stack.enter_context(_patched_attr(receipt_module, "OPERATIONAL_TRAIL", paths["trail"]))
            stack.enter_context(
                _patched_attr(receipt_module, "PRIVILEGED_TRAIL", paths["privileged_trail"])
            )
            stack.enter_context(_patched_attr(telemetry_module, "OPERATIONAL_TRAIL", paths["trail"]))
            stack.enter_context(_patched_attr(escalation_module, "OPERATIONAL_TRAIL", paths["trail"]))
            stack.enter_context(_patched_attr(escalation_module, "PENDING_QUEUE", paths["pending"]))

            if orders_db is not None:
                stack.enter_context(_patched_attr(orders_registry, "DB", orders_db))
            if policy_db is not None:
                stack.enter_context(_patched_attr(policy_registry, "DB", policy_db))
            if entitlements_db is not None:
                stack.enter_context(_patched_attr(entitlements_registry, "DB", entitlements_db))
            if extractor is not None:
                stack.enter_context(_patched_attr(intercept, "extract_action", extractor))
            if active_manifest is not None:
                stack.enter_context(
                    _patched_attr(intercept, "_active_manifest", lambda: active_manifest)
                )
            if ground_score is not None:
                stack.enter_context(_patched_attr(ground_module, "score", ground_score))
            for name, impl in (tools or {}).items():
                stack.enter_context(_patched_mapping(intercept.REGISTRY, name, impl))

            yield paths
    finally:
        reset_execution_ledger()
        set_clock(None)


def _servicing_action() -> ProposedAction:
    return ProposedAction(
        tool="issue_refund",
        order_id="ORD-90233",
        amount_paise=849900,
        currency="INR",
        item_colour="grey",
        item_category="shirt",
        claimed_delivered_at="2026-08-11",
        claimed_policy_version="v4.2",
        claimed_clause_text=CURRENT_CLAUSE,
        claimed_reasoning="Current record and policy support the refund.",
    )


def _knowledge_action() -> ProposedAction:
    return ProposedAction(
        tool="send_document",
        doc_id="DOC-2277",
        recipient_id="EMP-4410",
        excerpt="Requested support document.",
        claimed_reasoning="Send the requested document.",
    )


def _args(action: ProposedAction) -> dict[str, Any]:
    return {
        key: value
        for key, value in action.facts_for_predicate().items()
        if key != "tool" and value is not None
    }


def _take_store_offline(path: Path) -> None:
    """Replace a cloned SQLite file with a directory after extraction."""

    if path.is_file():
        path.replace(path.with_suffix(path.suffix + ".offline"))
        path.mkdir()


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise AssertionError("scenario produced no operational receipt")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latest_envelope(path: Path) -> dict[str, Any]:
    for entry in reversed(_read_entries(path)):
        if "receipt" in entry:
            return entry
    raise AssertionError("operational trail contains no receipt envelope")


def _receipt_excerpt(
    receipt: dict[str, Any],
    *,
    evidence_query_contains: str | None = None,
) -> dict[str, Any]:
    evidence = receipt.get("evidence", [])
    if evidence_query_contains is not None:
        evidence = [e for e in evidence if evidence_query_contains in str(e.get("query", ""))]
    return {
        "receipt_id": receipt.get("receipt_id"),
        "trace_id": receipt.get("trace_id"),
        "manifest_id": receipt.get("manifest_id"),
        "idempotency_key": receipt.get("idempotency_key"),
        "action": receipt.get("action"),
        "verdict": receipt.get("verdict"),
        "intervention": receipt.get("intervention"),
        "verification_state": receipt.get("verification_state"),
        "root_cause": receipt.get("root_cause"),
        "failure_context": receipt.get("failure_context"),
        "component_status": receipt.get("component_status"),
        "reasons": receipt.get("reasons"),
        "evidence": evidence,
        "sig": receipt.get("sig"),
        "signature_valid": receipt_module.verify(receipt),
    }


def _correct_binary(gold_label: str, intervention: str) -> bool:
    flagged = intervention in FLAGGED
    return (not flagged) if gold_label == "ALLOW" else flagged


def _distribution(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


# ---------------------------------------------------------------------------
# Scenario 1 -- wrong records and the fixed crossover sweep
# ---------------------------------------------------------------------------


def _eligible_dates(cases: list[dict[str, Any]]) -> dict[str, date]:
    order_ids = sorted({str(case["tool_call"]["args"].get("order_id")) for case in cases})
    placeholders = ",".join("?" for _ in order_ids)
    uri = (DATA / "orders.db").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        rows = conn.execute(
            f"SELECT order_id, delivered_at FROM orders WHERE order_id IN ({placeholders})",
            order_ids,
        ).fetchall()
    result = {
        str(order_id): date.fromisoformat(delivered_at)
        for order_id, delivered_at in rows
        if delivered_at is not None
    }
    if len(result) != EXPECTED_ELIGIBLE_RECORDS:
        raise AssertionError(
            "P08 record-error population drift: expected "
            f"{EXPECTED_ELIGIBLE_RECORDS} existing date-bearing records, got {len(result)}"
        )
    return result


def _ranked_order_ids(dates: dict[str, date]) -> list[str]:
    return sorted(
        dates,
        key=lambda order_id: hashlib.sha256(
            f"{RANK_SALT}|{order_id}".encode("utf-8")
        ).hexdigest(),
    )


def _flip_date(original: date) -> date:
    elapsed = (FROZEN_TODAY - original).days
    if elapsed <= WINDOW_DAYS:
        return FROZEN_TODAY - timedelta(days=WINDOW_DAYS + 1)
    return FROZEN_TODAY


def _corrupt_dates(path: Path, selected: list[str], originals: dict[str, date]) -> None:
    with closing(sqlite3.connect(path)) as conn:
        for order_id in selected:
            changed = conn.execute(
                "UPDATE orders SET delivered_at = ? WHERE order_id = ?",
                (_flip_date(originals[order_id]).isoformat(), order_id),
            ).rowcount
            if changed != 1:
                raise AssertionError(f"expected one row for record corruption: {order_id}")
        conn.commit()


def _bootstrap_crossover(
    curve_internal: list[dict[str, Any]],
    clusters: list[str],
) -> dict[str, Any]:
    """Cluster-bootstrap the fixed-grid crossover; never interpolate/tune."""

    rng = random.Random(BOOTSTRAP_SEED)
    crossings: list[float] = []
    no_crossing = 0
    for _ in range(BOOTSTRAP_ITERS):
        sample = [rng.choice(clusters) for _ in clusters]
        crossing = None
        for point in curve_internal:
            by_cluster = point["cluster_correctness"]
            correct = sum(by_cluster[key][0] for key in sample)
            total = sum(by_cluster[key][1] for key in sample)
            accuracy = correct / total
            if accuracy < FROZEN_B4_ACCURACY:
                crossing = point["achieved_rate"]
                break
        if crossing is None:
            no_crossing += 1
        else:
            crossings.append(crossing)

    crossings.sort()
    if crossings:
        lo = crossings[int(0.025 * (len(crossings) - 1))]
        hi = crossings[int(0.975 * (len(crossings) - 1))]
        median = crossings[int(0.5 * (len(crossings) - 1))]
    else:
        lo = hi = median = None
    return {
        "method": "percentile bootstrap over public source-order clusters",
        "iterations": BOOTSTRAP_ITERS,
        "random_seed": BOOTSTRAP_SEED,
        "crossing_draws": len(crossings),
        "draws_with_no_crossing": no_crossing,
        "median": median,
        "interval_95": [lo, hi] if lo is not None else None,
        "note": (
            "Interval is over fixed-grid crossing points; no interpolation. "
            "Draws without a measured crossing are counted separately."
        ),
    }


def scenario_wrong_record() -> dict[str, Any]:
    all_cases = B.load_cases()
    cases = [case for case in all_cases if case["gold_label"] != "AMBIGUOUS"]
    if len(cases) != FROZEN_B4_N:
        raise AssertionError(f"expected {FROZEN_B4_N} non-ambiguous cases, got {len(cases)}")

    originals = _eligible_dates(cases)
    ranked = _ranked_order_ids(originals)
    clusters = sorted({B.cluster_id(case) for case in cases})
    curve_internal: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="p08-wrong-record-") as tmp:
        tmp_root = Path(tmp)
        holder: dict[str, ProposedAction] = {}

        def extractor(**_kwargs: Any) -> ProposedAction:
            return holder["action"]

        for index, target_rate in enumerate(GRID):
            cell_root = tmp_root / f"grid-{index:02d}"
            orders_db = _clone_store(DATA / "orders.db", cell_root / "orders.db")
            policy_db = _clone_store(DATA / "policy_store.db", cell_root / "policy_store.db")
            selected_n = math.floor(target_rate * len(ranked) + 0.5)
            selected = ranked[:selected_n]
            _corrupt_dates(orders_db, selected, originals)

            predictions: list[str] = []
            correctness: list[bool] = []
            by_cluster: dict[str, list[int]] = {}
            with _runtime_scope(
                cell_root,
                manifest_name="servicing",
                orders_db=orders_db,
                policy_db=policy_db,
                extractor=extractor,
            ):
                for case in cases:
                    holder["action"] = B.action_from_case(case)
                    decision, _latency, _receipt = intercept._run_gate(
                        case["tool_call"]["name"],
                        dict(case["tool_call"]["args"]),
                        B.session_from_case(case),
                        case.get("justification") or "",
                        list(case.get("retrieved_chunks", [])),
                    )
                    predicted = decision.intervention.value
                    correct = _correct_binary(case["gold_label"], predicted)
                    predictions.append(predicted)
                    correctness.append(correct)
                    cluster = B.cluster_id(case)
                    counts = by_cluster.setdefault(cluster, [0, 0])
                    counts[0] += int(correct)
                    counts[1] += 1

            curve_internal.append({
                "target_rate": target_rate,
                "selected_records": selected_n,
                "eligible_records": len(ranked),
                "achieved_rate": selected_n / len(ranked),
                "correct": sum(correctness),
                "n": len(correctness),
                "accuracy": sum(correctness) / len(correctness),
                "prediction_distribution": _distribution(predictions),
                "selected_order_ids_sha256": hashlib.sha256(
                    "\n".join(selected).encode("utf-8")
                ).hexdigest(),
                "cluster_correctness": {
                    key: (value[0], value[1]) for key, value in by_cluster.items()
                },
            })

        # Required directed witness: a valid order is made eight days old and
        # is blocked because ControlPlane honestly trusts the wrong record.
        witness_case = next(case for case in cases if case["id"] == "gs-001")
        witness_action = B.action_from_case(witness_case)
        witness_order = str(witness_case["tool_call"]["args"]["order_id"])
        witness_root = tmp_root / "directed-witness"
        witness_orders = _clone_store(DATA / "orders.db", witness_root / "orders.db")
        witness_policy = _clone_store(
            DATA / "policy_store.db", witness_root / "policy_store.db"
        )
        _corrupt_dates(witness_orders, [witness_order], originals)
        executions: list[dict[str, Any]] = []
        with _runtime_scope(
            witness_root,
            manifest_name="servicing",
            orders_db=witness_orders,
            policy_db=witness_policy,
            extractor=_fixed_extractor(witness_action),
            tools={
                "issue_refund": lambda **kwargs: executions.append(kwargs)
                or {"executed": True}
            },
        ) as paths:
            blocked = False
            try:
                intercept.dispatch_tool(
                    "issue_refund",
                    dict(witness_case["tool_call"]["args"]),
                    B.session_from_case(witness_case),
                    witness_case.get("justification") or "",
                    list(witness_case.get("retrieved_chunks", [])),
                )
            except intercept.Blocked:
                blocked = True
            witness_receipt = _latest_envelope(paths["trail"])["receipt"]
            witness_excerpt = _receipt_excerpt(
                witness_receipt, evidence_query_contains="delivered_at"
            )
            witness_signed = receipt_module.verify(witness_receipt)

    point_crossing = next(
        (
            point["achieved_rate"]
            for point in curve_internal
            if point["accuracy"] < FROZEN_B4_ACCURACY
        ),
        None,
    )
    bootstrap = _bootstrap_crossover(curve_internal, clusters)
    curve = [
        {key: value for key, value in point.items() if key != "cluster_correctness"}
        for point in curve_internal
    ]
    witness_pass = (
        blocked
        and not executions
        and witness_receipt["intervention"] == Intervention.BLOCK.value
        and witness_receipt["root_cause"] == "outside_window"
        and witness_signed
        and any(
            evidence.get("value") == (FROZEN_TODAY - timedelta(days=8)).isoformat()
            for evidence in witness_receipt["evidence"]
            if "delivered_at" in evidence.get("query", "")
        )
    )

    return {
        "id": 1,
        "scenario": "wrong_record",
        "expected": (
            "A directed wrong delivered_at record blocks the valid action; the limitation "
            "curve reports the first fixed-grid rate below frozen B4 123/140."
        ),
        "observed": {
            "directed_witness": {
                "case_id": witness_case["id"],
                "order_id": witness_order,
                "corrupted_delivered_at": (FROZEN_TODAY - timedelta(days=8)).isoformat(),
                "intervention": witness_receipt["intervention"],
                "root_cause": witness_receipt["root_cause"],
            },
            "record_error_crossover": point_crossing,
            "no_crossover": point_crossing is None,
            "frozen_b4_accuracy": FROZEN_B4_ACCURACY,
            "curve": curve,
            "crossover_uncertainty": bootstrap,
            "interpretation": (
                "Inherited source-of-record errors are a limitation. A changed date "
                "predicate may leave the final block unchanged when another independent "
                "contradiction remains."
            ),
        },
        "pass": witness_pass and len(curve) == len(GRID),
        "action_executed": False,
        "receipt_excerpt": witness_excerpt,
        "pre_fix": (
            "No crash: ControlPlane treated the corrupted corroborated date as authoritative "
            "and blocked. P08 records this as inherited-record error, not a win."
        ),
    }


# ---------------------------------------------------------------------------
# Scenarios 2-8
# ---------------------------------------------------------------------------


def scenario_record_unavailable() -> dict[str, Any]:
    observations: dict[str, Any] = {}
    excerpts: dict[str, Any] = {}
    executed: dict[str, bool] = {}

    with tempfile.TemporaryDirectory(prefix="p08-unavailable-servicing-") as tmp:
        root = Path(tmp)
        orders_db = _clone_store(DATA / "orders.db", root / "orders.db")
        policy_db = _clone_store(DATA / "policy_store.db", root / "policy_store.db")
        action = _servicing_action()
        executions: list[dict[str, Any]] = []
        with _runtime_scope(
            root,
            manifest_name="servicing",
            orders_db=orders_db,
            policy_db=policy_db,
            extractor=_fixed_extractor(action, lambda: _take_store_offline(orders_db)),
            tools={
                "issue_refund": lambda **kwargs: executions.append(kwargs)
                or {"executed": True}
            },
        ) as paths:
            blocked = False
            try:
                intercept.dispatch_tool(
                    "issue_refund",
                    _args(action),
                    SessionContext(
                        trace_id="p08-unavailable-servicing", customer_id="CUST-2291"
                    ),
                )
            except intercept.Blocked:
                blocked = True
            receipt = _latest_envelope(paths["trail"])["receipt"]
            excerpts["servicing"] = _receipt_excerpt(receipt)
            executed["servicing"] = bool(executions)
            context = receipt.get("failure_context") or {}
            observations["servicing"] = {
                "source": context.get("source"),
                "risk_tier": context.get("risk_tier"),
                "configured_fail_posture": context.get("fail_posture"),
                "outcome": context.get("posture_outcome"),
                "compensability": receipt["action"]["compensability"],
                "verification_state": receipt["verification_state"],
                "blocked_exception": blocked,
                "signature_valid": receipt_module.verify(receipt),
            }

    with tempfile.TemporaryDirectory(prefix="p08-unavailable-knowledge-") as tmp:
        root = Path(tmp)
        entitlements_db = _clone_store(
            DATA / "entitlements.db", root / "entitlements.db"
        )
        action = _knowledge_action()
        executions = []
        with _runtime_scope(
            root,
            manifest_name="knowledge_assistant",
            entitlements_db=entitlements_db,
            extractor=_fixed_extractor(
                action, lambda: _take_store_offline(entitlements_db)
            ),
            tools={
                "send_document": lambda **kwargs: executions.append(kwargs)
                or {"executed": True}
            },
        ) as paths:
            result = intercept.dispatch_tool(
                "send_document",
                _args(action),
                SessionContext(
                    trace_id="p08-unavailable-knowledge",
                    subject_id="EMP-4410",
                    use_case="knowledge_assistant",
                ),
            )
            receipt = _latest_envelope(paths["trail"])["receipt"]
            excerpts["knowledge_assistant"] = _receipt_excerpt(receipt)
            executed["knowledge_assistant"] = bool(executions)
            context = receipt.get("failure_context") or {}
            observations["knowledge_assistant"] = {
                "source": context.get("source"),
                "risk_tier": context.get("risk_tier"),
                "configured_fail_posture": context.get("fail_posture"),
                "outcome": context.get("posture_outcome"),
                "compensability": receipt["action"]["compensability"],
                "verification_state": receipt["verification_state"],
                "result": result,
                "signature_valid": receipt_module.verify(receipt),
            }

    servicing_ok = observations["servicing"] == {
        "source": "orders.db",
        "risk_tier": 2,
        "configured_fail_posture": "closed",
        "outcome": "blocked",
        "compensability": "fully",
        "verification_state": "unverified",
        "blocked_exception": True,
        "signature_valid": True,
    }
    knowledge = observations["knowledge_assistant"]
    knowledge_ok = (
        knowledge["source"] == "entitlements.db"
        and knowledge["risk_tier"] == 0
        and knowledge["configured_fail_posture"] == "open"
        and knowledge["outcome"] == "executed"
        and knowledge["compensability"] == "partially"
        and knowledge["verification_state"] == "unverified"
        and knowledge["result"] == {"executed": True}
        and knowledge["signature_valid"] is True
    )
    return {
        "id": 2,
        "scenario": "record_unavailable",
        "expected": {
            "servicing": "orders.db outage -> configured tier_2 closed -> no execution",
            "knowledge_assistant": (
                "entitlements.db outage -> configured tier_0 open -> execute with unverified receipt"
            ),
            "precedence": (
                "The active manifest's tier-specific fail_posture is authoritative; "
                "compensability is reported metadata and does not override it."
            ),
        },
        "observed": observations,
        "pass": servicing_ok and knowledge_ok and executed == {
            "servicing": False,
            "knowledge_assistant": True,
        },
        "action_executed": executed,
        "receipt_excerpt": excerpts,
        "pre_fix": (
            "Both SQLite availability errors escaped dispatch with no signed failure receipt; "
            "neither configured fail posture was applied."
        ),
    }


def scenario_null_field() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p08-null-field-") as tmp:
        root = Path(tmp)
        orders_db = _clone_store(DATA / "orders.db", root / "orders.db")
        policy_db = _clone_store(DATA / "policy_store.db", root / "policy_store.db")
        with closing(sqlite3.connect(orders_db)) as conn:
            conn.execute(
                "UPDATE orders SET delivered_at = NULL WHERE order_id = ?",
                ("ORD-90233",),
            )
            conn.commit()
        action = _servicing_action()
        with _runtime_scope(
            root,
            manifest_name="servicing",
            orders_db=orders_db,
            policy_db=policy_db,
            extractor=_fixed_extractor(action),
        ):
            decision, _latency, receipt = intercept._run_gate(
                "issue_refund",
                _args(action),
                SessionContext(trace_id="p08-null-delivered", customer_id="CUST-2291"),
                "",
                [],
            )
            resolved = next(
                e for e in receipt["evidence"] if "delivered_at" in e["query"]
            )
            excerpt = _receipt_excerpt(receipt, evidence_query_contains="delivered_at")
            signature_valid = receipt_module.verify(receipt)

    passed = (
        decision.verdict is Verdict.SOURCE_UNRELIABLE
        and decision.intervention is Intervention.ESCALATE
        and resolved["value"] is None
        and resolved["confidence"] == Confidence.NONE.value
        and resolved["reliability_class"] == Reliability.UNVERIFIED.value
        and receipt["verification_state"] == "unverified"
        and signature_valid
    )
    return {
        "id": 3,
        "scenario": "null_delivered_at",
        "expected": "SOURCE_UNRELIABLE then ESCALATE, not an exception or execution",
        "observed": {
            "verdict": decision.verdict.value,
            "intervention": decision.intervention.value,
            "resolved_value": resolved["value"],
            "reliability_class": resolved["reliability_class"],
            "confidence": resolved["confidence"],
        },
        "pass": passed,
        "action_executed": False,
        "receipt_excerpt": excerpt,
        "pre_fix": (
            "orders resolver returned NULL as corroborated/HIGH; Zen date coercion raised "
            "RuntimeError and no receipt was produced."
        ),
    }


def scenario_inferred_field() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p08-inferred-status-") as tmp:
        root = Path(tmp)
        orders_db = _clone_store(DATA / "orders.db", root / "orders.db")
        policy_db = _clone_store(DATA / "policy_store.db", root / "policy_store.db")
        action = _servicing_action()
        manifest = load_manifest("servicing")
        manifest["claim_bindings"] = [
            *manifest["claim_bindings"],
            {
                "claim_kind": "ORDER_STATUS_SUPPORTS_ACTION",
                "resolver": "orders",
                "subject": "action.order_id",
                "predicate_key": None,
            },
        ]
        with _runtime_scope(
            root,
            manifest_name="servicing",
            orders_db=orders_db,
            policy_db=policy_db,
            extractor=_fixed_extractor(action),
            active_manifest=manifest,
        ):
            decision, _latency, receipt = intercept._run_gate(
                "issue_refund",
                _args(action),
                SessionContext(trace_id="p08-inferred-status", customer_id="CUST-2291"),
                "",
                [],
            )
            status_claim = next(
                claim
                for claim in decision.claims
                if claim.kind is ClaimKind.ORDER_STATUS_SUPPORTS_ACTION
            )
            status_evidence = next(
                evidence
                for evidence in decision.evidence
                if evidence.claim_id == status_claim.id
            )
            excerpt = _receipt_excerpt(receipt, evidence_query_contains="order_status")
            signature_valid = receipt_module.verify(receipt)

    passed = (
        status_claim.load_bearing
        and status_evidence.value == "delivered"
        and status_evidence.reliability_class is Reliability.INFERRED
        and decision.verdict is Verdict.SOURCE_UNRELIABLE
        and decision.intervention is Intervention.ESCALATE
        and receipt["verification_state"] == "unverified"
        and signature_valid
    )
    return {
        "id": 4,
        "scenario": "inferred_order_status_high_severity",
        "expected": "inferred load-bearing order_status -> SOURCE_UNRELIABLE -> ESCALATE",
        "observed": {
            "fixture": "P08-only in-memory servicing binding; no production manifest changed",
            "claim_load_bearing": status_claim.load_bearing,
            "resolved_value": status_evidence.value,
            "reliability_class": status_evidence.reliability_class.value,
            "verdict": decision.verdict.value,
            "intervention": decision.intervention.value,
        },
        "pass": passed,
        "action_executed": False,
        "receipt_excerpt": excerpt,
        "pre_fix": (
            "Hand-built inferred Evidence could escalate, but the production resolver had "
            "no order_status claim/field path, so the required scenario was not end-to-end representable."
        ),
    }


def scenario_ambiguous_policy() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p08-ambiguous-policy-") as tmp:
        root = Path(tmp)
        orders_db = _clone_store(DATA / "orders.db", root / "orders.db")
        policy_db = _clone_store(DATA / "policy_store.db", root / "policy_store.db")
        with closing(sqlite3.connect(policy_db)) as conn:
            conn.execute(
                """
                INSERT INTO clauses (
                    clause_id, policy_id, version, title, text, window_days,
                    effective_from, effective_to, superseded_by
                )
                SELECT ?, policy_id, ?, title, text, window_days,
                       effective_from, NULL, NULL
                FROM clauses
                WHERE policy_id = ? AND effective_to IS NULL
                """,
                (
                    "refund-window-v4.2-p08-duplicate",
                    "v4.2-p08-duplicate",
                    "refund_window",
                ),
            )
            conn.commit()
        action = _servicing_action()
        executions: list[dict[str, Any]] = []
        with _runtime_scope(
            root,
            manifest_name="servicing",
            orders_db=orders_db,
            policy_db=policy_db,
            extractor=_fixed_extractor(action),
            tools={
                "issue_refund": lambda **kwargs: executions.append(kwargs)
                or {"executed": True}
            },
        ) as paths:
            blocked = False
            try:
                intercept.dispatch_tool(
                    "issue_refund",
                    _args(action),
                    SessionContext(
                        trace_id="p08-ambiguous-policy", customer_id="CUST-2291"
                    ),
                )
            except intercept.Blocked:
                blocked = True
            envelope = _latest_envelope(paths["trail"])
            receipt = envelope["receipt"]
            data_quality = envelope.get("telemetry", {}).get("data_quality")
            excerpt = _receipt_excerpt(receipt)
            signature_valid = receipt_module.verify(receipt)

    passed = (
        blocked
        and not executions
        and receipt["intervention"] == Intervention.BLOCK.value
        and receipt["failure_context"]["kind"] == "ambiguous_policy_state"
        and receipt["failure_context"]["fail_posture"] == "closed"
        and data_quality == {
            "status": "detected",
            "policy_id": "refund_window",
            "current_row_count": 2,
            "expected_current_row_count": 1,
        }
        and signature_valid
    )
    return {
        "id": 5,
        "scenario": "ambiguous_policy_state",
        "expected": "two current rows -> fail closed, no execution, logged data-quality event",
        "observed": {
            "intervention": receipt["intervention"],
            "failure_context": receipt["failure_context"],
            "data_quality_event": data_quality,
            "blocked_exception": blocked,
        },
        "pass": passed,
        "action_executed": bool(executions),
        "receipt_excerpt": excerpt,
        "pre_fix": (
            "PolicyResolver used fetchone(), silently accepted one of two current rows, "
            "and emitted no data-quality event."
        ),
    }


def scenario_grounding_timeout() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p08-ground-timeout-") as tmp:
        root = Path(tmp)
        orders_db = _clone_store(DATA / "orders.db", root / "orders.db")
        policy_db = _clone_store(DATA / "policy_store.db", root / "policy_store.db")
        action = _servicing_action()
        executions: list[dict[str, Any]] = []

        def timeout(**_kwargs: Any) -> float:
            raise TimeoutError("P08 injected HHEM timeout")

        with _runtime_scope(
            root,
            manifest_name="servicing",
            orders_db=orders_db,
            policy_db=policy_db,
            extractor=_fixed_extractor(action),
            grounding="on",
            ground_score=timeout,
            tools={
                "issue_refund": lambda **kwargs: executions.append(kwargs)
                or {"executed": True}
            },
        ) as paths:
            result = intercept.dispatch_tool(
                "issue_refund",
                _args(action),
                SessionContext(trace_id="p08-ground-timeout", customer_id="CUST-2291"),
            )
            envelope = _latest_envelope(paths["trail"])
            receipt = envelope["receipt"]
            excerpt = _receipt_excerpt(receipt)
            signature_valid = receipt_module.verify(receipt)
            coverage = envelope.get("telemetry", {}).get("coverage")

    passed = (
        result == {"executed": True}
        and len(executions) == 1
        and receipt["verdict"] == Verdict.VERIFIED.value
        and receipt["intervention"] == Intervention.ALLOW.value
        and receipt["component_status"].get("C3")
        == {"status": "unavailable", "reason": "timeout"}
        and coverage.get("c3_unavailable_n", 0) >= 1
        and signature_valid
    )
    return {
        "id": 6,
        "scenario": "grounding_timeout",
        "expected": "HHEM timeout degrades to C1/C2; C3 is explicit unavailable; valid action proceeds",
        "observed": {
            "verdict": receipt["verdict"],
            "intervention": receipt["intervention"],
            "component_status": receipt["component_status"],
            "coverage": coverage,
            "result": result,
        },
        "pass": passed,
        "action_executed": bool(executions),
        "receipt_excerpt": excerpt,
        "pre_fix": "TimeoutError escaped the grounding stage and no decision receipt was produced.",
    }


def scenario_tampered_receipt() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p08-tampered-receipt-") as tmp:
        root = Path(tmp)
        orders_db = _clone_store(DATA / "orders.db", root / "orders.db")
        policy_db = _clone_store(DATA / "policy_store.db", root / "policy_store.db")
        action = _servicing_action()
        executions: list[dict[str, Any]] = []
        with _runtime_scope(
            root,
            manifest_name="servicing",
            orders_db=orders_db,
            policy_db=policy_db,
            extractor=_fixed_extractor(action),
            tools={
                "issue_refund": lambda **kwargs: executions.append(kwargs)
                or {"executed": True}
            },
        ) as paths:
            intercept.dispatch_tool(
                "issue_refund",
                _args(action),
                SessionContext(
                    trace_id="p08-persisted-tamper", customer_id="CUST-2291"
                ),
            )
            entries = _read_entries(paths["trail"])
            if len(entries) != 1:
                raise AssertionError(f"expected one persisted receipt, got {len(entries)}")
            original = deepcopy(entries[0]["receipt"])
            verification_before = receipt_module.verify(original)
            original_excerpt = _receipt_excerpt(original)

            entries[0]["receipt"]["verdict"] = Verdict.CONTRADICTED.value
            paths["trail"].write_text(
                json.dumps(entries[0], sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered = _read_entries(paths["trail"])[0]["receipt"]
            verification_after = receipt_module.verify(tampered)
            tampered_excerpt = _receipt_excerpt(tampered)

    passed = (
        bool(executions)
        and verification_before is True
        and verification_after is False
        and tampered["verdict"] == Verdict.CONTRADICTED.value
        and tampered["sig"] == original["sig"]
    )
    return {
        "id": 7,
        "scenario": "tampered_persisted_receipt",
        "expected": "modifying a receipt already persisted to disk makes signature validation fail",
        "observed": {
            "modified_field": "verdict",
            "original_value": original["verdict"],
            "tampered_value": tampered["verdict"],
            "signature_valid_before": verification_before,
            "signature_valid_after": verification_after,
        },
        "pass": passed,
        "action_executed": bool(executions),
        "receipt_excerpt": {
            "original": original_excerpt,
            "tampered": tampered_excerpt,
        },
        "pre_fix": (
            "HMAC verification already rejected in-memory mutation, but no test exercised "
            "a receipt reloaded after persisted-trail tampering."
        ),
    }


def scenario_retry_after_timeout() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p08-timeout-retry-") as tmp:
        root = Path(tmp)
        entitlements_db = _clone_store(
            DATA / "entitlements.db", root / "entitlements.db"
        )
        executions: list[dict[str, Any]] = []
        action = _knowledge_action().model_copy(
            update={"doc_id": "DOC-1042", "excerpt": "Refund policy FAQ."}
        )
        key = "p08-caller-supplied-idempotency-key"
        with _runtime_scope(
            root,
            manifest_name="knowledge_assistant",
            entitlements_db=entitlements_db,
            extractor=_fixed_extractor(action),
            tools={
                "send_document": lambda **kwargs: executions.append(kwargs)
                or {"executed": True, "sequence": len(executions)}
            },
        ) as paths:
            session = SessionContext(
                trace_id="p08-timeout-retry",
                subject_id="EMP-4410",
                use_case="knowledge_assistant",
            )
            timed_out = False
            try:
                first = intercept.dispatch_tool(
                    "send_document", _args(action), session, idempotency_key=key
                )
                raise TimeoutError(
                    "P08 caller timeout: response lost after committed execution"
                )
            except TimeoutError as exc:
                timed_out = "lost after committed execution" in str(exc)

            second = intercept.dispatch_tool(
                "send_document", _args(action), session, idempotency_key=key
            )
            receipts = [
                entry["receipt"]
                for entry in _read_entries(paths["trail"])
                if "receipt" in entry
            ]
            replay = receipts[-1]
            signatures_valid = all(receipt_module.verify(receipt) for receipt in receipts)
            excerpt = _receipt_excerpt(replay)

    passed = (
        timed_out
        and first == {"executed": True, "sequence": 1}
        and second == first
        and len(executions) == 1
        and len(receipts) == 3
        and all(receipt["idempotency_key"] == key for receipt in receipts)
        and replay["failure_context"]["kind"] == "idempotent_replay"
        and replay["component_status"]["execution"]
        == {
            "status": "duplicate_suppressed",
            "reason": "completed_result_replayed",
        }
        and signatures_valid
    )
    return {
        "id": 8,
        "scenario": "retry_after_timeout",
        "expected": (
            "caller-visible timeout after committed execution; retry with same key replays "
            "the result and does not execute the action twice"
        ),
        "observed": {
            "timeout_boundary": "after execution committed, before caller retained response",
            "idempotency_key": key,
            "first_result": first,
            "retry_result": second,
            "execution_count": len(executions),
            "receipt_count": len(receipts),
            "replay_component_status": replay["component_status"]["execution"],
        },
        "pass": passed,
        "action_executed": len(executions) == 1,
        "receipt_excerpt": excerpt,
        "pre_fix": (
            "The deterministic key was receipt metadata only; two dispatches with the same "
            "key invoked the tool twice."
        ),
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


SCENARIOS: tuple[Callable[[], dict[str, Any]], ...] = (
    scenario_wrong_record,
    scenario_record_unavailable,
    scenario_null_field,
    scenario_inferred_field,
    scenario_ambiguous_policy,
    scenario_grounding_timeout,
    scenario_tampered_receipt,
    scenario_retry_after_timeout,
)


def _failed_scenario(index: int, name: str, exc: BaseException) -> dict[str, Any]:
    return {
        "id": index,
        "scenario": name,
        "expected": "scenario completes in its specified safe state with receipt evidence",
        "observed": {
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        },
        "pass": False,
        "action_executed": None,
        "receipt_excerpt": None,
        "pre_fix": "Unexpected harness/runtime exception; this remains a loud P08 finding.",
    }


def build_report() -> dict[str, Any]:
    """Run all eight isolated scenarios and return a JSON-serializable result."""

    _assert_frozen_b4()
    hashes_before = _frozen_hashes()
    results: list[dict[str, Any]] = []
    for index, runner in enumerate(SCENARIOS, start=1):
        try:
            results.append(runner())
        except BaseException as exc:  # every crash is an explicit P08 finding
            results.append(_failed_scenario(index, runner.__name__, exc))

    hashes_after = _frozen_hashes()
    frozen_unchanged = hashes_before == hashes_after
    scenario_one = next((result for result in results if result["id"] == 1), None)
    crossover = None
    if scenario_one and isinstance(scenario_one.get("observed"), dict):
        crossover = scenario_one["observed"].get("record_error_crossover")

    all_pass = all(result["pass"] for result in results) and frozen_unchanged
    return {
        "task": "P08_ROBUSTNESS_AND_FAILURE_INJECTION",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "gold_set": str(B.GOLD_SET.relative_to(ROOT)),
            "gold_set_sha256": _sha256(B.GOLD_SET),
            "frozen_clock": FROZEN_TODAY.isoformat(),
            "scenario_1_grid": list(GRID),
            "scenario_1_rank": f"SHA256({RANK_SALT}|order_id)",
            "scenario_1_selection": "k=floor(target_rate*N+0.5); nested prefix",
            "scenario_1_fault_unit": "unique date-bearing source-order record",
            "scenario_1_date_flip": "<=7 elapsed days -> day 8; >7 -> day 0",
            "scenario_1_scoring": "P04 binary direction on 140 non-ambiguous cases",
            "frozen_b4_tracegrounded": {
                "correct": FROZEN_B4_CORRECT,
                "n": FROZEN_B4_N,
                "accuracy": FROZEN_B4_ACCURACY,
                "summary_path": "p04_baselines.mcnemar_b4_vs_b5.accuracy_b4",
            },
            "crossover_rule": "first achieved fixed-grid rate with accuracy strictly below B4",
            "bootstrap": {
                "iterations": BOOTSTRAP_ITERS,
                "seed": BOOTSTRAP_SEED,
                "unit": "public source-order cluster",
            },
            "runtime_path": (
                "controlplane.intercept from classification through signed receipt; "
                "deterministic fixed actions hold extraction noise at zero and prevent fixture writes"
            ),
            "isolation": (
                "SQLite backup clones plus temporary receipt/queue paths; globals restored in finally"
            ),
            "scenario_2_precedence": (
                "active manifest tier fail_posture controls execution; compensability is reported metadata"
            ),
        },
        "scenario_results": results,
        "record_error_crossover": crossover,
        "frozen_input_integrity": {
            "unchanged": frozen_unchanged,
            "before": hashes_before,
            "after": hashes_after,
        },
        "all_pass": all_pass,
    }


# ---------------------------------------------------------------------------
# Committed report generation (only when --write is passed)
# ---------------------------------------------------------------------------


CROSSOVER_METHOD = (
    "Fixed 21-point grid 0.00..1.00 step 0.05, locked before any result was "
    "seen. Records are ranked deterministically by SHA256(\"p08-wrong-record-v1"
    "|order_id\"); point k selects the nested prefix of "
    "floor(rate * 85 + 0.5) date-bearing orders.db records and flips each "
    "selected non-null delivered_at across the frozen v4.2 seven-day boundary "
    "(<=7 elapsed days -> day 8, >7 -> day 0). Every point runs on its own "
    "SQLite backup clone of orders.db through the real controlplane.intercept "
    "gate; the 140 non-ambiguous P03 gold cases are scored on the P04 binary "
    "direction (flag = BLOCK/ESCALATE/MODIFY). Crossover is the first achieved "
    "grid rate whose accuracy is strictly below the frozen P04 B4 TraceGrounded "
    "value 123/140 = 0.8785714286. The grid is never retuned after the run; a "
    "cluster bootstrap over public source-order ids (5000 iters, seed "
    f"{BOOTSTRAP_SEED}) reports uncertainty over the fixed grid points only."
)


def _pf(ok: bool) -> str:
    return "pass" if ok else "**FAIL**"


def _committed(obj: Any) -> Any:
    """Strip the one non-deterministic field before a value is written to a
    committed artifact. The HMAC ``sig`` is computed over the whole receipt,
    which includes wall-clock ``latency_ms``, so it wobbles run to run; its
    verification result (``signature_valid``) is the property that matters and
    it is kept."""

    if isinstance(obj, dict):
        return {k: _committed(v) for k, v in obj.items() if k != "sig"}
    if isinstance(obj, list):
        return [_committed(v) for v in obj]
    return obj


def _one_line_excerpt(scenario: dict[str, Any]) -> str:
    """A single Markdown-table-safe cell summarising the signed receipt."""

    excerpt = scenario.get("receipt_excerpt")
    if not excerpt:
        return "_no receipt produced — see scenario section_"
    if scenario["id"] == 2:  # two receipts, one per manifest
        parts = []
        for key in ("servicing", "knowledge_assistant"):
            sub = excerpt.get(key, {})
            fc = sub.get("failure_context") or {}
            parts.append(
                f"{key}: `verdict={sub.get('verdict')}` `intervention={sub.get('intervention')}` "
                f"`fail_posture={fc.get('fail_posture')}` `posture_outcome={fc.get('posture_outcome')}` "
                f"`verification_state={sub.get('verification_state')}` sig_valid={sub.get('signature_valid')}"
            )
        return "<br>".join(parts)
    if scenario["id"] == 7:  # before/after tamper
        before = excerpt.get("original", {})
        after = excerpt.get("tampered", {})
        return (
            f"before: `verdict={before.get('verdict')}` sig_valid={before.get('signature_valid')}<br>"
            f"after: `verdict={after.get('verdict')}` sig_valid={after.get('signature_valid')}"
        )
    fc = excerpt.get("failure_context") or {}
    bits = [
        f"`verdict={excerpt.get('verdict')}`",
        f"`intervention={excerpt.get('intervention')}`",
        f"`root_cause={excerpt.get('root_cause')}`",
        f"`verification_state={excerpt.get('verification_state')}`",
    ]
    if fc:
        bits.append(f"`failure_context.kind={fc.get('kind')}`")
        bits.append(f"`fail_posture={fc.get('fail_posture')}`")
    cs = excerpt.get("component_status") or {}
    if "C3" in cs:
        bits.append(f"`component_status.C3={json.dumps(cs['C3'], sort_keys=True)}`")
    bits.append(f"sig_valid={excerpt.get('signature_valid')}")
    return " ".join(bits)


def _summary_entry(report: dict[str, Any]) -> dict[str, Any]:
    """The reports/summary.json['p08_robustness'] payload. No wall-clock field,
    so it stays as deterministic as the P04/P05 entries beside it."""

    s1 = next(r for r in report["scenario_results"] if r["id"] == 1)
    integrity = report["frozen_input_integrity"]
    return {
        "config": report["config"],
        "record_error_crossover": report["record_error_crossover"],
        "crossover_method": CROSSOVER_METHOD,
        "frozen_b4_accuracy": FROZEN_B4_ACCURACY,
        "wrong_record": {
            "directed_witness": s1["observed"]["directed_witness"],
            "curve": s1["observed"]["curve"],
            "crossover_uncertainty": s1["observed"]["crossover_uncertainty"],
        },
        "scenarios": [
            {
                "id": r["id"],
                "scenario": r["scenario"],
                "pass": r["pass"],
                "action_executed": r["action_executed"],
                "expected": r["expected"],
                "observed": r["observed"],
                "pre_fix_finding": r["pre_fix"],
                "receipt_excerpt": _committed(r["receipt_excerpt"]),
            }
            for r in report["scenario_results"]
        ],
        "frozen_inputs_checked": sorted(integrity["before"]),
        "frozen_inputs_unchanged_during_run": integrity["unchanged"],
        "all_pass": report["all_pass"],
    }


def merge_summary_json(report: dict[str, Any]) -> None:
    path = REPORTS / "summary.json"
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    before = {k: v for k, v in existing.items() if k != "p08_robustness"}
    existing["p08_robustness"] = _summary_entry(report)
    # Guard: adding our key must not perturb any sibling experiment's payload.
    for key, value in before.items():
        if existing[key] != value:
            raise AssertionError(f"summary.json merge would have altered {key!r}")
    path.write_text(
        json.dumps(existing, indent=2, default=str, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any]) -> str:
    cfg = report["config"]
    results = report["scenario_results"]
    s1 = next(r for r in results if r["id"] == 1)
    crossover = report["record_error_crossover"]
    unc = s1["observed"]["crossover_uncertainty"]

    lines: list[str] = []
    lines.append("# P08 — robustness and failure injection")
    lines.append("")
    lines.append(
        "Harness: `bench/failure_injection.py` (regenerate with `python "
        "bench/failure_injection.py --write`). Every scenario runs the real "
        "`controlplane.intercept` path from claim classification through the "
        "signed Decision Receipt. All mutable state — SQLite stores, the "
        "`decisions.jsonl` trail, the pending-action queue, the in-process "
        "execution ledger — is redirected to a temporary directory and restored "
        "in a `finally` block. Extraction noise is held at zero with a fixed "
        "`ProposedAction` so the harness isolates *verification* behaviour."
    )
    lines.append("")
    lines.append(
        f"Frozen comparator: P04 B4 TraceGrounded = {FROZEN_B4_CORRECT}/"
        f"{FROZEN_B4_N} = {FROZEN_B4_ACCURACY:.10f} "
        "(`summary.json['p04_baselines']['mcnemar_b4_vs_b5']['accuracy_b4']`, "
        "asserted equal at run start). Gold set "
        f"`{cfg['gold_set']}` SHA-256 `{cfg['gold_set_sha256']}`. Frozen clock "
        f"{cfg['frozen_clock']}."
    )
    lines.append("")
    lines.append(
        "P03 gold set, P04 baseline artifacts and P05 evidence-ablation "
        "artifacts are read-only here. The harness hashes them before and after "
        "the run: **"
        + ("unchanged" if report["frozen_input_integrity"]["unchanged"] else "CHANGED — see JSON")
        + "**."
    )
    lines.append("")

    lines.append("## Result table")
    lines.append("")
    lines.append("| # | scenario | expected | observed | pass/fail | receipt excerpt |")
    lines.append("|--:|---|---|---|:--:|---|")
    for r in results:
        expected = r["expected"]
        if isinstance(expected, dict):
            expected = "; ".join(f"**{k}**: {v}" for k, v in expected.items())
        observed = _table_observed(r)
        lines.append(
            f"| {r['id']} | {r['scenario']} | {_md_cell(expected)} | {_md_cell(observed)} "
            f"| {_pf(r['pass'])} | {_one_line_excerpt(r)} |"
        )
    lines.append("")
    lines.append(
        f"All scenarios pass: **{report['all_pass']}**. "
        "A scenario passes only when the real runtime path reaches the safe "
        "state *and* emits a signed receipt that records what happened and why."
    )
    lines.append("")

    lines.append("## Scenario 1 — wrong record (LIMITATION, not a win)")
    lines.append("")
    lines.append(
        "The verifier has no way to know a system-of-record value is wrong; it "
        "inherits the record's errors. This is the honest reading and it is "
        "reported as a limitation."
    )
    lines.append("")
    dw = s1["observed"]["directed_witness"]
    lines.append(
        f"**Directed witness.** Order `{dw['order_id']}` (gold case "
        f"`{dw['case_id']}`, genuinely inside the window) has its `delivered_at` "
        f"rewritten to `{dw['corrupted_delivered_at']}` — eight days before the "
        f"frozen clock. ControlPlane reads the corrupted date from `orders.db`, "
        f"the seven-day predicate fails, and the valid refund is "
        f"`{dw['intervention']}`ed with `root_cause={dw['root_cause']}`. No "
        "crash: the gate trusted the wrong record exactly as designed."
    )
    lines.append("")
    lines.append(
        f"**Record-error crossover: {_pct(crossover)}** "
        f"(achieved grid rate `{crossover}`)."
    )
    lines.append("")
    lines.append(f"Method — {CROSSOVER_METHOD}")
    lines.append("")
    lines.append(
        f"Cluster bootstrap ({unc['iterations']} iters, seed "
        f"{unc['random_seed']}): median crossover {_pct(unc['median'])}, "
        f"95% interval [{_pct(unc['interval_95'][0])}, {_pct(unc['interval_95'][1])}], "
        f"{unc['draws_with_no_crossing']}/{unc['iterations']} resamples with no "
        "crossing on the swept grid."
    )
    lines.append("")
    lines.append(
        "| target rate | selected records | achieved rate | accuracy | correct / n | prediction mix |"
    )
    lines.append("|--:|--:|--:|--:|--:|---|")
    for p in s1["observed"]["curve"]:
        mark = " ⟵ first below B4" if (
            crossover is not None and abs(p["achieved_rate"] - crossover) < 1e-12
        ) else ""
        lines.append(
            f"| {p['target_rate']:.2f} | {p['selected_records']} | "
            f"{p['achieved_rate']:.4f} | {p['accuracy']:.4f}{mark} | "
            f"{p['correct']} / {p['n']} | "
            f"{json.dumps(p['prediction_distribution'], sort_keys=True)} |"
        )
    lines.append("")
    if crossover is None:
        lines.append("No crossover observed in the tested range.")
        lines.append("")

    lines.append("## Per-scenario detail — pre-fix finding vs post-fix behaviour")
    lines.append("")
    lines.append(
        "Receipt excerpts below are the signed receipt with the raw `sig` hex "
        "removed — the HMAC covers wall-clock `latency_ms` and so is not "
        "reproducible byte-for-byte; `signature_valid` is the verified property "
        "and is retained."
    )
    lines.append("")
    for r in results:
        lines.append(f"### {r['id']}. {r['scenario']} — {_pf(r['pass'])}")
        lines.append("")
        expected = r["expected"]
        if isinstance(expected, dict):
            expected = "; ".join(f"**{k}**: {v}" for k, v in expected.items())
        lines.append(f"- **Expected:** {expected}")
        lines.append(f"- **Pre-fix finding:** {r['pre_fix']}")
        lines.append(f"- **Post-fix observed:** {_md_cell(_table_observed(r))}")
        lines.append(f"- **Action executed:** `{json.dumps(r['action_executed'])}`")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(_committed(r["receipt_excerpt"]), indent=2, sort_keys=True, default=str))
        lines.append("```")
        lines.append("")

    lines.append("## Isolation and determinism")
    lines.append("")
    lines.append(f"- Runtime path: {cfg['runtime_path']}")
    lines.append(f"- Isolation: {cfg['isolation']}")
    lines.append(f"- Scenario 2 precedence: {cfg['scenario_2_precedence']}")
    lines.append(
        "- Windows note: SQLite clone connections are closed explicitly "
        "(`contextlib.closing`), not left to `sqlite3`'s transaction-only "
        "context manager, so `TemporaryDirectory` cleanup does not fail on a "
        "locked file."
    )
    lines.append("")
    lines.append(
        "See `docs/limitations.md` for what SOURCE-UNRELIABLE does and does not "
        "cover, and for the inherited-record-error reading of scenario 1."
    )
    lines.append("")

    text = "\n".join(lines)
    (REPORTS / "robustness.md").write_text(text, encoding="utf-8")
    return text


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _md_cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table_observed(scenario: dict[str, Any]) -> str:
    obs = scenario["observed"]
    if not isinstance(obs, dict):
        return str(obs)
    if "exception_type" in obs:
        return f"CRASH: {obs['exception_type']}: {obs['exception']}"
    sid = scenario["id"]
    if sid == 1:
        return (
            f"witness {obs['directed_witness']['intervention']} "
            f"({obs['directed_witness']['root_cause']}); crossover "
            f"{_pct(obs['record_error_crossover'])}"
        )
    if sid == 2:
        s = obs["servicing"]
        k = obs["knowledge_assistant"]
        return (
            f"servicing: {s['configured_fail_posture']} posture, {s['outcome']}, "
            f"verification={s['verification_state']}; "
            f"knowledge_assistant: {k['configured_fail_posture']} posture, "
            f"{k['outcome']}, verification={k['verification_state']}"
        )
    return _md_cell(json.dumps(obs, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate reports/robustness.md and summary.json['p08_robustness']",
    )
    args = parser.parse_args()
    report = build_report()
    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))
    if args.write:
        write_markdown(report)
        merge_summary_json(report)
        print(
            "\nwrote reports/robustness.md and reports/summary.json['p08_robustness']",
            file=sys.stderr,
        )
    if not report["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
