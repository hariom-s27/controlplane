"""P06 C2 — the tau2-bench <-> ControlPlane integration adapter.

Integration glue ONLY. No tau2 business logic is reimplemented anywhere in
this file, and nothing under external/tau2-bench/ is modified.

The public route, traced against the actual tau2 v1.0.1 source
(fc0055dc4e0a316c3f83133267fbd6faaa770992):

    tau2.registry.registry.register_domain(fn, name)   -- public method, the
        same one tau2 itself calls for every one of its own domains
        (see tau2/registry.py's own module-level registration block).
    -> TextRunConfig(domain=<our registry key>, ...)
    -> tau2.runner.build.build_environment(domain, ...)
         = registry.get_env_constructor(domain)(**kwargs)   -- calls OUR
           get_environment_controlplane(), unmodified tau2 code path
    -> tau2.environment.environment.Environment(domain_name="retail", ...)
         -- the UNMODIFIED Environment class, constructed with domain_name
            stamped as the literal string "retail" (this is what the
            evaluator keys off, NOT the registry name -- see below)
    -> orchestrator.run() drives the live simulation; every tool call goes
       through Environment.use_tool() -> ControlPlaneRetailTools.use_tool()
       (this file) -> for the six governed WRITE tools, ControlPlane's
       dispatch_tool() runs BEFORE the underlying tau2 mutation; every other
       call falls straight through to RetailTools' own, unmodified use_tool.

Why the evaluator is unaffected (this is the load-bearing design fact of the
whole adapter -- see docs comment further down and
tests/test_tau2_adapter.py::test_evaluator_reconstructs_vanilla_environment):
tau2.runner.simulation.run_simulation() computes
`domain = orchestrator.environment.get_domain_name()` -- i.e. the STRING we
stamped on the live Environment instance, "retail" -- and passes THAT to
evaluate_simulation(), which reconstructs its predicted/gold reference
environments via `registry.get_env_constructor(domain)`. Because we register
our wrapper under a DIFFERENT registry key (TAU2_CONTROLPLANE_DOMAIN,
"retail_controlplane") and stamp domain_name="retail" on the instances we
build, the evaluator's registry lookup resolves to tau2's own, completely
unmodified "retail" factory -- so replay/scoring is byte-for-byte the same
mechanism C1 uses. ControlPlane never runs during evaluation, only during
the live agent-driven run.

P02 capability status: ORDER_STATUS_SUPPORTS_ACTION -- the only claim kind
this adapter binds -- is wired through the generic status_supports_action
decision mapping, and tau2_retail is permitted by the generic manifest
resolver-name schema. Runtime resolver registration remains additive and
external to controlplane/. No use-case-specific decision branch exists.
"""

from __future__ import annotations

import contextvars
import os
import sys
import uuid
from pathlib import Path
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
CONTROLPLANE_ROOT = BENCH_DIR.parent
TAU2_SRC = CONTROLPLANE_ROOT.parent.parent / "external" / "tau2-bench" / "src"

if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))
if str(CONTROLPLANE_ROOT) not in sys.path:
    sys.path.insert(0, str(CONTROLPLANE_ROOT))
if TAU2_SRC.is_dir() and str(TAU2_SRC) not in sys.path:
    sys.path.insert(0, str(TAU2_SRC))

from controlplane.intercept import Blocked, dispatch_tool, register_tool  # noqa: E402
from controlplane.registry import RESOLVER_BY_NAME  # noqa: E402
from controlplane.registry.clock import now as cp_now  # noqa: E402
from controlplane.schema import ClaimKind, Confidence, Evidence, Reliability, SessionContext  # noqa: E402

from tau2.data_model.tasks import Task  # noqa: E402
from tau2.domains.retail.data_model import RetailDB  # noqa: E402
from tau2.domains.retail.environment import get_tasks as _retail_get_tasks  # noqa: E402
from tau2.domains.retail.tools import RetailTools  # noqa: E402
from tau2.domains.retail.utils import RETAIL_DB_PATH, RETAIL_POLICY_PATH  # noqa: E402
from tau2.environment.environment import Environment  # noqa: E402
from tau2.registry import registry as tau2_registry  # noqa: E402

from tau2_governed_scope import (  # noqa: E402
    GOVERNED_TOOLS,
    MANIFEST_FOR_TOOL,
    RESOLVER_NAME,
    TAU2_CONTROLPLANE_DOMAIN,
    TAU2_OFFICIAL_DOMAIN_NAME,
)

# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
#
# TAU2_CONTROLPLANE_DOMAIN: the KEY this adapter's environment factory is
# registered under in tau2's registry. Deliberately NOT "retail" --
# registry.register_domain() raises ValueError on a name collision, so this
# adapter is structurally incapable of replacing tau2's own "retail" entry
# even if it tried to.
#
# TAU2_OFFICIAL_DOMAIN_NAME: the STRING stamped on every Environment
# instance this adapter builds. This is what
# tau2.runner.simulation.run_simulation() reads via
# orchestrator.environment.get_domain_name() and feeds to the evaluator's
# own registry.get_env_constructor(domain) lookup -- see module docstring.
#
# GOVERNED_TOOLS / MANIFEST_FOR_TOOL / RESOLVER_NAME: defined in
# bench/tau2_governed_scope.py (stdlib-only, no tau2/controlplane import) so
# the controlplane-side test suite can share this exact same source of
# truth without needing tau2 installed. One manifest per tool because
# controlplane/intercept.py::_run_gate asserts action.tool ==
# manifest["tool"] against a SINGLE CP_MANIFEST-named file -- the current
# architecture has no multi-tool manifest shape.


# --------------------------------------------------------------------------
# Resolver -- lives here, NOT in controlplane/, per the task's explicit
# routing. (claim, session, manifest, action) -> Evidence, the exact
# signature controlplane/registry/__init__.py::resolve_bindings() calls
# uniformly for every resolver name in RESOLVER_BY_NAME.
# --------------------------------------------------------------------------

# Set by ControlPlaneRetailTools.use_tool() for the duration of one governed
# dispatch_tool() call, so this resolver can read the CURRENT, live,
# in-process tau2 RetailDB -- never agent prose, never a previous tool
# result, never the evaluator's hidden ground truth. A contextvar (not a
# plain module global) so it is correct under whatever concurrency model
# runs this adapter, even though C2's frozen configuration is concurrency=1.
_CURRENT_TAU2_TOOLS: "contextvars.ContextVar[RetailTools | None]" = contextvars.ContextVar(
    "_CURRENT_TAU2_TOOLS", default=None
)


def tau2_retail_resolver(claim, session, manifest, action) -> Evidence:  # noqa: ARG001
    """ORDER_STATUS_SUPPORTS_ACTION only -- see MANIFEST_FOR_TOOL's manifests.

    ORDER_BELONGS_TO_CUSTOMER is deliberately NOT bound by any tau2_*
    manifest and this resolver does not implement it. tau2's own retail
    task files self-document the reason (data/tau2/domains/retail/tasks.json,
    e.g. task 5's "issues" field): "Agent is allowed to do user level
    actions ... without authenticating the user." There is no structural,
    DB-level "authenticated current customer" channel in this domain
    independent of (a) previous tool output -- explicitly disallowed as
    evidence by this task's own rules, or (b) the evaluator's hidden
    evaluation_criteria ground truth -- which would make governance secretly
    consult the answer key, invalidating the C1/C2 comparison. Binding it
    anyway with a fabricated identity source was rejected; see the report.
    """
    tools = _CURRENT_TAU2_TOOLS.get()
    if tools is None:
        raise RuntimeError(
            "tau2_retail_resolver invoked with no live RetailTools bound to "
            "_CURRENT_TAU2_TOOLS. This is an adapter wiring bug (resolver "
            "called outside ControlPlaneRetailTools.use_tool), not a data "
            "problem -- it must never happen in a real run."
        )

    order_id = claim.subject
    order = tools.db.orders.get(order_id)
    fetched_at = cp_now()

    if order is None:
        return Evidence(
            claim_id=claim.id,
            value=None,
            source="tau2:RetailDB.orders (live, in-process)",
            query=f"db.orders.get({order_id!r})",
            fetched_at=fetched_at,
            reliability_class=Reliability.UNVERIFIED,
            confidence=Confidence.NONE,
            note=f"no order found for order_id={order_id!r} in tau2's live retail DB",
        )

    if claim.kind is not ClaimKind.ORDER_STATUS_SUPPORTS_ACTION:
        raise KeyError(
            f"tau2_retail_resolver has no field mapping for {claim.kind!r}; "
            "only ORDER_STATUS_SUPPORTS_ACTION is bound by any tau2_* manifest"
        )

    return Evidence(
        claim_id=claim.id,
        value=order.status,
        source="tau2:RetailDB.orders (live, in-process)",
        query=f"db.orders.get({order_id!r}).status",
        fetched_at=fetched_at,
        freshness_ms=0,
        reliability_class=Reliability.CORROBORATED,
        confidence=Confidence.HIGH,
        note="direct in-process read of the same object the orchestrator is about to mutate",
    )


def register_tau2_resolver() -> None:
    """Idempotent. Adds ONE new key to controlplane.registry.RESOLVER_BY_NAME
    -- a plain, public, module-level dict whose own docstring calls itself
    "a name -> callable registry, not a per-use-case table". This is not a
    tau2 mutation (nothing under external/tau2-bench/ is touched) and it is
    not a monkey-patch of anything ControlPlane already defines: no existing
    key's behaviour changes, only a new one is added, from outside
    controlplane/, to the registry section 5 explicitly names as reusable.

    Schema permission alone remains intentionally insufficient: manifest
    loading also requires this runtime callable registration, so an allowed
    but unregistered resolver name still fails closed.
    """
    RESOLVER_BY_NAME.setdefault(RESOLVER_NAME, tau2_retail_resolver)


# --------------------------------------------------------------------------
# The wrapper. Composition-free: a genuine subclass of tau2's own
# RetailTools, overriding exactly one method.
# --------------------------------------------------------------------------


class ControlPlaneRetailTools(RetailTools):
    """`RetailTools`, with ControlPlane's gate inserted in front of the six
    governed WRITE tools' dispatch.

    Every tool method (`cancel_pending_order`, `get_order_details`, ...) is
    inherited from `RetailTools` completely unchanged -- this class defines
    none of them. `ToolKitBase`'s metaclass (`environment/toolkit.py`)
    discovers tools by scanning each class's OWN `@is_tool`-decorated
    methods and merging with the parent's via `super()._func_tools`; since
    this subclass adds no `@is_tool` methods of its own, `self.tools`,
    `tool_type()`, `get_tools()`, discoverability, and every tool's
    docstring/signature are byte-identical to vanilla `RetailTools` for
    every one of tau2's own read/write/think/generic tools.

    The ONLY override is `use_tool`, tau2's own single dispatch point
    (`ToolKitBase.use_tool`, called by `Environment.use_tool` /
    `Environment.make_tool_call` for every tool call in the simulation).
    For a non-governed call it is a one-line passthrough to
    `super().use_tool(...)` -- tau2's real, unmodified dispatch. For a
    governed WRITE call, ControlPlane's `dispatch_tool()` runs first; on
    ALLOW/MODIFY it calls back into `super().use_tool()` internally via the
    registered implementation (see `__init__`), so the real tau2 mutation
    still executes with tau2's own business logic, unmodified, exactly once.
    """

    def __init__(self, db: RetailDB) -> None:
        super().__init__(db)
        for name in GOVERNED_TOOLS:
            # The bound method IS RetailTools' own implementation (this
            # class defines none of the six itself) -- dispatch_tool()'s
            # eventual impl(**args) call runs tau2's real business logic.
            register_tool(name, getattr(self, name))

    def use_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if tool_name not in GOVERNED_TOOLS:
            return super().use_tool(tool_name, **kwargs)

        db_token = _CURRENT_TAU2_TOOLS.set(self)
        prior_manifest = os.environ.get("CP_MANIFEST")
        try:
            os.environ["CP_MANIFEST"] = MANIFEST_FOR_TOOL[tool_name]
            session = SessionContext(
                trace_id=str(uuid.uuid4()),
                customer_id=None,  # see tau2_retail_resolver's docstring
                agent_role="tau2_retail_agent",
                use_case="tau2_retail_c2",
                manifest_id=MANIFEST_FOR_TOOL[tool_name],
                gate_enabled=True,
            )
            # BLOCK raises controlplane.intercept.Blocked, which propagates
            # out of this method exactly like any other tau2 tool's
            # ValueError -- Environment.get_response() (unmodified tau2
            # code) already catches "any Exception" uniformly and turns it
            # into an error ToolMessage. No special-casing needed here.
            # ALLOW/MODIFY reach the real tau2 mutation via the registered
            # impl inside dispatch_tool(). ESCALATE returns a
            # {"status": "pending", ...} dict, tau2's to_json_str()
            # serialises it like any other tool return value.
            return dispatch_tool(
                tool_name,
                dict(kwargs),
                session,
                justification="",
                retrieved_chunks=[],
            )
        finally:
            _CURRENT_TAU2_TOOLS.reset(db_token)
            if prior_manifest is None:
                os.environ.pop("CP_MANIFEST", None)
            else:
                os.environ["CP_MANIFEST"] = prior_manifest


def get_environment_controlplane(db: RetailDB | None = None, solo_mode: bool = False) -> Environment:
    """Registered under TAU2_CONTROLPLANE_DOMAIN. Line-for-line identical to
    tau2.domains.retail.environment.get_environment() except
    RetailTools(db) -> ControlPlaneRetailTools(db); same DB path, same
    policy path, same domain_name literal, same Environment class.
    """
    if solo_mode:
        raise ValueError("Retail domain does not support solo mode")
    if db is None:
        db = RetailDB.load(RETAIL_DB_PATH)
    tools = ControlPlaneRetailTools(db)
    with open(RETAIL_POLICY_PATH, "r") as fp:
        policy = fp.read()
    return Environment(domain_name=TAU2_OFFICIAL_DOMAIN_NAME, policy=policy, tools=tools)


def register_controlplane_domain() -> None:
    """Idempotent. The ONLY tau2-registry mutation this adapter performs,
    and it is entirely additive: a NEW key (TAU2_CONTROLPLANE_DOMAIN), via
    tau2's own public `registry.register_domain()` method -- the same call
    tau2 itself makes for airline/telecom/banking_knowledge/mock in
    tau2/registry.py. `register_domain` raises ValueError on a name
    collision, so this call is structurally incapable of touching tau2's
    existing "retail" entry.
    """
    register_tau2_resolver()
    if TAU2_CONTROLPLANE_DOMAIN not in tau2_registry.get_domains():
        tau2_registry.register_domain(get_environment_controlplane, TAU2_CONTROLPLANE_DOMAIN)


# --------------------------------------------------------------------------
# Task loading -- deliberately bypasses the tau2 registry's task-set
# machinery entirely (registry.register_tasks / get_tasks_loader) and calls
# tau2's own retail task loader directly. Simpler than registering a second
# alias, and it makes the section 14A task-set identity gate a single,
# explicit, independently-checkable assertion rather than something buried
# in registry lookup semantics.
# --------------------------------------------------------------------------


def load_c2_tasks(task_ids: list[str], task_split_name: str = "test") -> list[Task]:
    """Load the frozen C2 task list from tau2's own retail task file/split,
    via tau2's own get_tasks() (data/tau2/domains/retail/tasks.json +
    split_tasks.json, read-only, unmodified), and assert exact set equality
    against `task_ids`. Raises AssertionError -- not a silent filter -- on
    any mismatch, per section 14A: no missing IDs, no extra IDs, no
    post-hoc filtering.
    """
    all_in_split = _retail_get_tasks(task_split_name=task_split_name)
    by_id = {t.id: t for t in all_in_split}

    requested = list(task_ids)
    missing = [tid for tid in requested if tid not in by_id]
    if missing:
        raise AssertionError(
            f"task-set identity gate FAILED: {len(missing)} frozen task id(s) not found "
            f"in tau2 retail split {task_split_name!r}: {missing}"
        )

    ordered = [by_id[tid] for tid in requested]
    loaded_ids = {t.id for t in ordered}
    frozen_ids = set(requested)
    if loaded_ids != frozen_ids or len(ordered) != len(requested):
        raise AssertionError(
            "task-set identity gate FAILED: exact set-equality check failed "
            f"(loaded={sorted(loaded_ids)!r} frozen={sorted(frozen_ids)!r})"
        )
    return ordered


__all__ = [
    "TAU2_CONTROLPLANE_DOMAIN",
    "TAU2_OFFICIAL_DOMAIN_NAME",
    "RESOLVER_NAME",
    "GOVERNED_TOOLS",
    "MANIFEST_FOR_TOOL",
    "tau2_retail_resolver",
    "register_tau2_resolver",
    "ControlPlaneRetailTools",
    "get_environment_controlplane",
    "register_controlplane_domain",
    "load_c2_tasks",
]
