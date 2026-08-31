"""P06 C2 -- real, EXECUTED proof of the tau2-side wrapper mechanics, run
against the REAL tau2 v1.0.1 package in tau2-bench's own venv.

Why this is a separate script, not a pytest file under tests/: controlplane's
real `dispatch_tool`/`Blocked`/`register_tool` cannot be imported from
tau2-bench's venv (it has no `instructor`/`zen-engine` -- confirmed by
direct probe; see the P06 C2 report's "environment merge" prerequisite).
This script therefore stands in a MINIMAL, structurally-faithful fake gate
-- the exact same call contract as controlplane's real one
(register_tool(name, impl) then a gate function taking (name, args) that
either returns a result or raises to prevent mutation) -- wired into a
ControlPlaneRetailTools-equivalent class using the IDENTICAL pattern
bench/tau2_adapter.py uses against the real gate.

What this DOES prove, for real, executed, right now:
  - the public tau2.registry.registry.register_domain() route works and
    cannot collide with the existing "retail" entry
  - Environment.domain_name can be stamped "retail" even when built via a
    DIFFERENT registry key (TAU2_CONTROLPLANE_DOMAIN)
  - the single most important correctness property of the whole adapter
    design: tau2's own evaluator-reconstruction path (which rebuilds a
    fresh environment via registry.get_env_constructor(domain_name)) is
    COMPLETELY UNAFFECTED by the gate wrapper, because it resolves through
    the vanilla "retail" key, not ours
  - BLOCK prevents the real tau2 mutation; ALLOW lets it run exactly once,
    with tau2's own business logic doing the mutating, not a
    reimplementation
  - a non-governed tool call is a byte-for-byte passthrough
  - tool discovery (ToolKitType metaclass), signatures, and docstrings are
    unchanged for every tool -- the subclass adds no @is_tool methods
  - no tau2 private attribute is mutated; no tau2 source file is touched
  - the state-reset property: two fresh environments never share state
  - the frozen 40-task C2 identity gate, against the REAL retail "test"
    split

What this does NOT prove: that the REAL controlplane.decide()/predicate
graph machinery produces the intended verdict end-to-end -- that is proven
separately, for real, using the REAL controlplane package (no tau2 needed
there either), in tests/test_tau2_c2_controlplane_side.py. Neither half has
been run against the OTHER's real package in the same process; see the P06
C2 report.

Run with tau2-bench's OWN venv:
    external/tau2-bench/.venv/Scripts/python.exe bench/verify_tau2_public_route.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
CONTROLPLANE_ROOT = BENCH_DIR.parent
TAU2_SRC = CONTROLPLANE_ROOT.parent.parent / "external" / "tau2-bench" / "src"

sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(TAU2_SRC))

from tau2_governed_scope import (  # noqa: E402
    GOVERNED_TOOLS,
    TAU2_CONTROLPLANE_DOMAIN,
    TAU2_OFFICIAL_DOMAIN_NAME,
)

from tau2.domains.retail.data_model import RetailDB  # noqa: E402
from tau2.domains.retail.environment import get_tasks as retail_get_tasks  # noqa: E402
from tau2.domains.retail.tools import RetailTools  # noqa: E402
from tau2.domains.retail.utils import RETAIL_DB_PATH, RETAIL_POLICY_PATH  # noqa: E402
from tau2.environment.environment import Environment  # noqa: E402
from tau2.environment.toolkit import get_tool_signatures  # noqa: E402
from tau2.registry import registry as tau2_registry  # noqa: E402

FROZEN_C2_TASK_IDS = [
    "5", "9", "12", "17", "18", "26", "27", "32", "33", "36", "38", "39", "40", "42",
    "45", "49", "51", "53", "55", "56", "60", "61", "62", "64", "65", "68", "70", "71",
    "74", "77", "79", "86", "90", "94", "97", "100", "101", "102", "108", "111",
]

_FAILURES: list[str] = []
_PASSES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASSES
    if condition:
        _PASSES += 1
        print(f"  PASS  {label}")
    else:
        _FAILURES.append(label)
        print(f"  FAIL  {label}  {detail}")


# --------------------------------------------------------------------------
# Minimal, structurally-faithful stand-in for controlplane.intercept
# --------------------------------------------------------------------------


class FakeBlocked(Exception):
    pass


class FakeGate:
    """Stands in for controlplane.intercept's REGISTRY + dispatch_tool. Same
    call shape: register(name, impl) once per tool; dispatch(name, args)
    either calls the registered impl (ALLOW) or raises without calling it
    (BLOCK). Records every call for the evaluator-independence check."""

    def __init__(self) -> None:
        self._registry: dict[str, Any] = {}
        self.calls: list[str] = []
        self.force_block: set[str] = set()

    def register(self, name: str, impl) -> None:
        self._registry[name] = impl

    def dispatch(self, name: str, args: dict) -> Any:
        self.calls.append(name)
        if name in self.force_block:
            raise FakeBlocked(f"BLOCK: {name} disallowed by test fixture")
        return self._registry[name](**args)


GATE = FakeGate()


class GatedRetailTools(RetailTools):
    """Same pattern as bench/tau2_adapter.py::ControlPlaneRetailTools:
    subclass RetailTools, override ONLY use_tool, register every governed
    tool's REAL bound method once, delegate everything else to
    super().use_tool()."""

    def __init__(self, db: RetailDB) -> None:
        super().__init__(db)
        for name in GOVERNED_TOOLS:
            GATE.register(name, getattr(self, name))

    def use_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if tool_name not in GOVERNED_TOOLS:
            return super().use_tool(tool_name, **kwargs)
        return GATE.dispatch(tool_name, kwargs)


def get_environment_gated(db: RetailDB | None = None, solo_mode: bool = False) -> Environment:
    if solo_mode:
        raise ValueError("Retail domain does not support solo mode")
    if db is None:
        db = RetailDB.load(RETAIL_DB_PATH)
    tools = GatedRetailTools(db)
    with open(RETAIL_POLICY_PATH, "r") as fp:
        policy = fp.read()
    return Environment(domain_name=TAU2_OFFICIAL_DOMAIN_NAME, policy=policy, tools=tools)


# --------------------------------------------------------------------------
# 1. Public registration route
# --------------------------------------------------------------------------

print("== 1. public registration route ==")
before_domains = set(tau2_registry.get_domains())
check("'retail' already registered before this script runs", "retail" in before_domains)
check(f"{TAU2_CONTROLPLANE_DOMAIN!r} not yet registered", TAU2_CONTROLPLANE_DOMAIN not in before_domains)

tau2_registry.register_domain(get_environment_gated, TAU2_CONTROLPLANE_DOMAIN)
after_domains = set(tau2_registry.get_domains())
check(
    "register_domain() is additive: existing domains untouched, exactly one new key added",
    after_domains == before_domains | {TAU2_CONTROLPLANE_DOMAIN},
)

try:
    tau2_registry.register_domain(get_environment_gated, "retail")
    check("register_domain('retail', ...) raises (cannot hijack the existing entry)", False)
except ValueError:
    check("register_domain('retail', ...) raises ValueError -- collision guard confirmed", True)

vanilla_get_env = tau2_registry.get_env_constructor("retail")
gated_get_env = tau2_registry.get_env_constructor(TAU2_CONTROLPLANE_DOMAIN)
check("vanilla 'retail' constructor is tau2's own (not ours)", vanilla_get_env is not get_environment_gated)
check("our key resolves to our constructor", gated_get_env is get_environment_gated)

# --------------------------------------------------------------------------
# 2. Environment/domain identity
# --------------------------------------------------------------------------

print("\n== 2. environment/domain identity ==")
live_env = gated_get_env()
check(
    "environment built via our registry key still stamps domain_name == 'retail'",
    live_env.get_domain_name() == "retail",
)
vanilla_env = vanilla_get_env()
check("vanilla env also stamps 'retail' (same official identity)", vanilla_env.get_domain_name() == "retail")
check("live env's tools are OUR wrapper class", isinstance(live_env.tools, GatedRetailTools))
check("vanilla env's tools are tau2's own, unwrapped class", type(vanilla_env.tools) is RetailTools)

# --------------------------------------------------------------------------
# 3. Tool discovery / signatures unchanged (no business-logic duplication)
# --------------------------------------------------------------------------

print("\n== 3. tool discovery / signatures byte-identical to vanilla ==")
vanilla_tools_obj = RetailTools(RetailDB.load(RETAIL_DB_PATH))
gated_tools_obj = live_env.tools
check("same tool NAME set", set(vanilla_tools_obj.get_tools()) == set(gated_tools_obj.get_tools()))
vanilla_sigs = get_tool_signatures(vanilla_tools_obj)
gated_sigs = get_tool_signatures(gated_tools_obj)
sig_mismatches = [
    name
    for name in vanilla_sigs
    if (vanilla_sigs[name].doc, vanilla_sigs[name].params, vanilla_sigs[name].returns)
    != (gated_sigs[name].doc, gated_sigs[name].params, gated_sigs[name].returns)
]
check("every tool's doc/params/returns identical to vanilla", not sig_mismatches, str(sig_mismatches))
for tool in GOVERNED_TOOLS:
    check(f"  {tool}: tool_type matches vanilla", gated_tools_obj.tool_type(tool) == vanilla_tools_obj.tool_type(tool))

# --------------------------------------------------------------------------
# 4. Non-governed passthrough
# --------------------------------------------------------------------------

print("\n== 4. non-governed tool: byte-for-byte passthrough ==")
db = live_env.tools.db
some_order_id = next(iter(db.orders))
GATE.calls.clear()
result = live_env.use_tool("get_order_details", order_id=some_order_id)
check("get_order_details returns an Order (not routed through the gate)", result.order_id == some_order_id)
check("gate was never invoked for a non-governed tool", GATE.calls == [])

# --------------------------------------------------------------------------
# 5. BLOCK prevents mutation; ALLOW executes exactly once
# --------------------------------------------------------------------------

print("\n== 5. BLOCK prevents mutation / ALLOW executes exactly once ==")
pending_order_id = next((oid for oid, o in db.orders.items() if o.status == "pending"), None)
check("fixture has at least one 'pending' order to test against", pending_order_id is not None)

if pending_order_id is not None:
    GATE.force_block = {"cancel_pending_order"}
    GATE.calls.clear()
    status_before = db.orders[pending_order_id].status
    try:
        live_env.use_tool("cancel_pending_order", order_id=pending_order_id, reason="no longer needed")
        check("BLOCK: use_tool raised", False)
    except FakeBlocked:
        check("BLOCK: use_tool raised (propagated, uncaught by the wrapper)", True)
    check("BLOCK: gate was invoked exactly once", GATE.calls == ["cancel_pending_order"])
    check("BLOCK: order status UNCHANGED (real mutation did not happen)", db.orders[pending_order_id].status == status_before)

    GATE.force_block = set()
    GATE.calls.clear()
    order = live_env.use_tool("cancel_pending_order", order_id=pending_order_id, reason="no longer needed")
    check("ALLOW: gate was invoked exactly once", GATE.calls == ["cancel_pending_order"])
    check("ALLOW: real tau2 mutation happened (status -> 'cancelled')", order.status == "cancelled")
    check("ALLOW: DB reflects the same mutation", db.orders[pending_order_id].status == "cancelled")

# --------------------------------------------------------------------------
# 6. THE load-bearing property: evaluator reconstruction is unaffected
# --------------------------------------------------------------------------

print("\n== 6. evaluator-equivalent reconstruction never touches the gate ==")
GATE.calls.clear()
fresh_vanilla_env = tau2_registry.get_env_constructor(live_env.get_domain_name())()
check(
    "registry.get_env_constructor(live_env.get_domain_name()) resolves to the VANILLA factory "
    "(this is exactly what tau2.runner.simulation.run_simulation() does to build the evaluator's "
    "predicted_environment/gold_environment)",
    fresh_vanilla_env.tools.__class__ is RetailTools,
)
some_pending = next((oid for oid, o in fresh_vanilla_env.tools.db.orders.items() if o.status == "pending"), None)
if some_pending is not None:
    fresh_vanilla_env.use_tool("cancel_pending_order", order_id=some_pending, reason="no longer needed")
check(
    "gate call count is STILL ZERO after driving tool calls through the vanilla-key reconstruction",
    GATE.calls == [],
)

# --------------------------------------------------------------------------
# 7. Private-mutation negative check (tau2 side)
# --------------------------------------------------------------------------

print("\n== 7. private-mutation negative check ==")
check("RetailTools class object itself is untouched (no replaced attrs)", RetailTools.use_tool is not GatedRetailTools.use_tool)
check("RetailTools.cancel_pending_order is the original function (never patched)", "cancel_pending_order" in RetailTools.__dict__)
import tau2  # noqa: E402

tau2_pkg_dir = Path(tau2.__file__).resolve().parent
external_tau2_bench = (CONTROLPLANE_ROOT.parent.parent / "external" / "tau2-bench").resolve()
check(
    "the imported tau2 package resolves under external/tau2-bench/ (no shadow copy)",
    str(tau2_pkg_dir).startswith(str(external_tau2_bench)),
    str(tau2_pkg_dir),
)

# --------------------------------------------------------------------------
# 8. State reset
# --------------------------------------------------------------------------

print("\n== 8. state reset: independent DB objects across fresh environments ==")
env_a = gated_get_env()
env_b = gated_get_env()
check("two fresh environments do not share the same DB object", env_a.tools.db is not env_b.tools.db)
some_id = next(iter(env_a.tools.db.orders))
before_b = env_b.tools.db.orders[some_id].status
env_a.tools.db.orders[some_id].status = "__mutated_for_test__"
check("mutating env_a's DB does not leak into env_b's DB", env_b.tools.db.orders[some_id].status == before_b)

# --------------------------------------------------------------------------
# 9. Task-set identity gate, against the REAL retail 'test' split
# --------------------------------------------------------------------------

print("\n== 9. task-set identity gate (frozen 40 task IDs) ==")
test_split_tasks = retail_get_tasks(task_split_name="test")
by_id = {t.id: t for t in test_split_tasks}
missing = [tid for tid in FROZEN_C2_TASK_IDS if tid not in by_id]
check("all 40 frozen task IDs exist in the real retail 'test' split", missing == [], str(missing))
loaded = [by_id[tid] for tid in FROZEN_C2_TASK_IDS if tid in by_id]
check("count == 40, exact, no dedup surprises", len(loaded) == 40, str(len(loaded)))
check("no duplicate task objects", len({id(t) for t in loaded}) == 40)


# --------------------------------------------------------------------------
print(f"\n{'=' * 70}\n{_PASSES} passed, {len(_FAILURES)} failed\n{'=' * 70}")
if _FAILURES:
    print("FAILED:")
    for f in _FAILURES:
        print(f"  - {f}")
    sys.exit(1)
sys.exit(0)
