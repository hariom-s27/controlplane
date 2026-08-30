"""Use case 4 (onboarding measurement) — service credit approval.

Added with ZERO changes to anything under controlplane/. Same gate, same
ladder, same verdict logic, same receipt — a new action, a new manifest
(manifests/service_credit_approval.yaml), and this agent. Unlike servicing
and discount_approval, this manifest has no delivery-window check at all: a
service complaint (late delivery, damaged packaging) is not gated by how
long ago the order arrived, only by ownership and the agent's authority
ceiling (here INR 3,000, vs discount_approval's INR 5,000).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from agents.llm import chat  # noqa: E402
from controlplane.intercept import Blocked, Pending, dispatch_tool, register_tool  # noqa: E402
from controlplane.render import to_rupees  # noqa: E402
from controlplane.schema import SessionContext  # noqa: E402

DB = ROOT / "data" / "orders.db"

CUSTOMER_MESSAGE = (
    "My order arrived four days late and the box was crushed — nothing broken, "
    "but it was a bad experience. Could I get a small service credit, maybe "
    "500 rupees, for the trouble?"
)

SYSTEM_PROMPT = (
    "You are a customer servicing agent who can approve small goodwill service "
    "credits for a bad delivery experience (not a return). Below is the "
    "customer's recent order history. If a service credit is warranted, call "
    "the approve_service_credit tool with the order's id, the credit amount "
    "in paise, and its currency."
)

APPROVE_SERVICE_CREDIT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "approve_service_credit",
            "description": "Approve a goodwill service credit against an order for a delivery/service complaint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order identifier, e.g. ORD-88461"},
                    "amount_paise": {"type": "integer", "description": "Credit amount in paise (INR x 100). Integers only."},
                    "currency": {"type": "string", "enum": ["INR"]},
                },
                "required": ["order_id", "amount_paise", "currency"],
            },
        },
    }
]


def _recent_orders(customer_id: str) -> list[dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT order_id, item_description, amount_paise, currency, delivered_at "
            "FROM orders WHERE customer_id = ? ORDER BY delivered_at DESC",
            (customer_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _render_context(orders: list[dict]) -> str:
    lines = "\n".join(
        f"- {o['order_id']}: {o['item_description']}, delivered {o['delivered_at']}, "
        f"amount_paise={o['amount_paise']}, currency={o['currency']}"
        for o in orders
    ) or "(no orders on file)"
    return f"Customer's recent orders:\n{lines}"


def _approve_service_credit_impl(order_id: str, amount_paise: int, currency: str) -> dict:
    """Private — dispatch_tool via the registry below is the only caller."""
    print(f"SERVICE CREDIT APPROVED {to_rupees(amount_paise)} · order {order_id}")
    return {"status": "approved", "order_id": order_id, "amount_paise": amount_paise, "currency": currency}


register_tool("approve_service_credit", _approve_service_credit_impl)


def propose(customer_message: str, customer_id: str = "CUST-1407") -> tuple[dict | None, dict, str]:
    orders = _recent_orders(customer_id)
    context = _render_context(orders)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
        {"role": "user", "content": customer_message},
    ]
    r = chat(messages, tools=APPROVE_SERVICE_CREDIT_TOOL)
    message = r["choices"][0]["message"]
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return None, message, context
    call = tool_calls[0]["function"]
    return {"name": call["name"], "args": json.loads(call["arguments"])}, message, context


def run(customer_id: str = "CUST-1407", gate_enabled: bool | None = None) -> None:
    if gate_enabled is None:
        gate_enabled = os.environ.get("CP_GATE", "on").strip().lower() != "off"

    # This agent's manifest, always — not left to whoever invokes it.
    os.environ["CP_MANIFEST"] = "service_credit_approval"

    session = SessionContext(
        trace_id=str(uuid.uuid4()), customer_id=customer_id,
        agent_role="service_credit_agent", use_case="service_credit_approval",
        manifest_id="service_credit_approval-v1", gate_enabled=gate_enabled,
    )

    call, message, context = propose(CUSTOMER_MESSAGE, customer_id)

    print(f"gate: {'ON' if gate_enabled else 'OFF'}  ·  trace: {session.trace_id}")
    print(f"\n{context}\n")
    print(f"customer> {CUSTOMER_MESSAGE}\n")
    if message.get("content"):
        print(f"agent (reasoning)> {message['content']}\n")
    if call is None:
        print("agent did not propose a tool call.")
        return
    print(f"agent proposes> {call['name']}({call['args']})\n")

    try:
        result = dispatch_tool(call["name"], call["args"], session, justification=message.get("content") or "")
        print(f"dispatch> {result}")
    except Blocked as e:
        print(f"dispatch> {e}")
    except Pending as e:
        print(f"dispatch> {e}")


if __name__ == "__main__":
    run()
