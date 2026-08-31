"""Offline final C2 checks using the dedicated joint Python environment.

This does not construct an agent, user simulator, orchestrator run, evaluator
run, or benchmark task. It makes no model/provider call. The only mutations
are to freshly loaded, in-memory RetailDB fixtures and temporary receipt files.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
TAU2_ROOT = ROOT.parent.parent / "external" / "tau2-bench"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(TAU2_ROOT / "src"))

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"
os.environ["CP_MODE"] = "fixture"
os.environ["CP_GROUNDING"] = "off"
os.environ["CP_DEMO_DATE"] = "2026-08-14"
os.environ["CP_RECEIPT_SECRET"] = "p06-c2-offline-joint-environment-check"
os.environ.pop("FEATHERLESS_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

from controlplane import receipt as receipt_module  # noqa: E402
from controlplane import intercept as intercept_module  # noqa: E402
from controlplane.intercept import Blocked  # noqa: E402
from controlplane.schema import ProposedAction  # noqa: E402
from tau2.domains.retail.tools import RetailTools  # noqa: E402
from tau2.registry import registry as tau2_registry  # noqa: E402

from run_c2 import _configured_evaluation_type  # noqa: E402
from tau2_adapter import (  # noqa: E402
    ControlPlaneRetailTools,
    get_environment_controlplane,
    load_c2_tasks,
    register_controlplane_domain,
)
from tau2_governed_scope import (  # noqa: E402
    GOVERNED_TOOLS,
    TAU2_CONTROLPLANE_DOMAIN,
)


_passes = 0
_failures: list[str] = []


def check(label: str, condition: bool) -> None:
    global _passes
    if condition:
        _passes += 1
        print(f"PASS {label}")
    else:
        _failures.append(label)
        print(f"FAIL {label}")


config = json.loads((BENCH / "p06-c2-config.json").read_text(encoding="utf-8"))

check("Python satisfies tau2 constraint", sys.version_info[:2] == (3, 12))
check("tau2 version is pinned", version("tau2") == "1.0.1")
check(
    "C2 evaluation enum matches C1 lock",
    _configured_evaluation_type(config).name == "ALL_WITH_NL_ASSERTIONS",
)
check("exactly six governed writes", len(GOVERNED_TOOLS) == 6)
check("modify_user_address excluded", "modify_user_address" not in GOVERNED_TOOLS)

before_domains = set(tau2_registry.get_domains())
register_controlplane_domain()
after_domains = set(tau2_registry.get_domains())
check(
    "public domain registration is additive",
    after_domains == before_domains | {TAU2_CONTROLPLANE_DOMAIN},
)

task_ids = config["task_selection"]["task_ids"]
tasks = load_c2_tasks(task_ids, config["task_selection"]["split"])
check("task count is 40", len(tasks) == 40)
check("task IDs preserve exact order", [task.id for task in tasks] == task_ids)
check("task IDs have no duplicates", len({task.id for task in tasks}) == 40)

live = get_environment_controlplane()
check("official retail domain identity preserved", live.get_domain_name() == "retail")
check("official Environment class retained", live.__class__.__name__ == "Environment")
check("live tools use external adapter", type(live.tools) is ControlPlaneRetailTools)
check(
    "current policy bytes retained",
    live.get_policy() == (TAU2_ROOT / "data/tau2/domains/retail/policy.md").read_text(encoding="utf-8"),
)

vanilla = tau2_registry.get_env_constructor(live.get_domain_name())()
check("evaluator-domain lookup remains vanilla retail", type(vanilla.tools) is RetailTools)
check("vanilla retail registration was not replaced", type(vanilla.tools) is not ControlPlaneRetailTools)

fresh_a = get_environment_controlplane()
fresh_b = get_environment_controlplane()
check("fresh environments use distinct DB objects", fresh_a.tools.db is not fresh_b.tools.db)
probe_id = next(iter(fresh_a.tools.db.orders))
probe_before = fresh_b.tools.db.orders[probe_id].status
fresh_a.tools.db.orders[probe_id].status = "__offline_probe__"
check("in-memory state does not leak between tasks", fresh_b.tools.db.orders[probe_id].status == probe_before)

non_governed = get_environment_controlplane()
order_id = next(iter(non_governed.tools.db.orders))
detail = non_governed.tools.use_tool("get_order_details", order_id=order_id)
check("non-governed read passes through", detail.order_id == order_id)

with tempfile.TemporaryDirectory(prefix="p06-c2-receipts-") as tmp:
    prior_operational = receipt_module.OPERATIONAL_TRAIL
    prior_privileged = receipt_module.PRIVILEGED_TRAIL
    prior_extract = intercept_module.extract_action
    receipt_module.OPERATIONAL_TRAIL = Path(tmp) / "decisions.jsonl"
    receipt_module.PRIVILEGED_TRAIL = Path(tmp) / "decisions_privileged.jsonl"

    def local_extract(*, tool, tool_call_args, justification, retrieved_chunks):  # noqa: ARG001
        return ProposedAction(tool=tool, order_id=tool_call_args.get("order_id"))

    intercept_module.extract_action = local_extract
    try:
        blocked_env = get_environment_controlplane()
        delivered_id = next(
            order_id for order_id, order in blocked_env.tools.db.orders.items()
            if order.status == "delivered"
        )
        blocked_before = blocked_env.tools.db.orders[delivered_id].status
        try:
            blocked_env.tools.use_tool(
                "cancel_pending_order", order_id=delivered_id, reason="no longer needed"
            )
            blocked_raised = False
        except Blocked:
            blocked_raised = True
        check("governed invalid write raises ControlPlane Blocked", blocked_raised)
        check(
            "blocked governed write cannot mutate DB",
            blocked_env.tools.db.orders[delivered_id].status == blocked_before,
        )

        allowed_env = get_environment_controlplane()
        pending_id = next(
            order_id for order_id, order in allowed_env.tools.db.orders.items()
            if order.status == "pending"
        )
        allowed = allowed_env.tools.use_tool(
            "cancel_pending_order", order_id=pending_id, reason="no longer needed"
        )
        check("allowed governed write executes original tau2 tool", allowed.status == "cancelled")
        check(
            "allowed governed write mutates only its in-memory DB",
            allowed_env.tools.db.orders[pending_id].status == "cancelled",
        )

        lines = [
            json.loads(line)
            for line in receipt_module.OPERATIONAL_TRAIL.read_text(encoding="utf-8").splitlines()
        ]
        check("one signed receipt exists per governed gate", len(lines) == 2)
        check(
            "receipts expose tool trace and stage latency",
            all(
                row["receipt"].get("trace_id")
                and row["receipt"]["action"].get("tool")
                and row["receipt"].get("ts")
                and row["receipt"].get("latency_ms")
                for row in lines
            ),
        )
        check(
            "receipts honestly lack direct task provenance",
            all(
                "task_id" not in row["receipt"]
                and "entry_timestamp" not in row["receipt"]
                and "exit_timestamp" not in row["receipt"]
                and "end_to_end" not in row["receipt"]["latency_ms"]
                for row in lines
            ),
        )
    finally:
        intercept_module.extract_action = prior_extract
        receipt_module.OPERATIONAL_TRAIL = prior_operational
        receipt_module.PRIVILEGED_TRAIL = prior_privileged

adapter_source = (BENCH / "tau2_adapter.py").read_text(encoding="utf-8").lower()
forbidden = ["registry." + "_domains", "_dom" + "ains[", "set" + "attr("]
check("adapter contains no private tau2 replacement", not any(x in adapter_source for x in forbidden))
check("latency status is explicitly unavailable", config["latency_provenance"]["status"] == "UNAVAILABLE")
check("latency percentiles are not claimed ready", config["latency_provenance"]["p50_p95_ready"] is False)

print(f"RESULT {_passes} passed, {len(_failures)} failed")
if _failures:
    raise SystemExit(1)
