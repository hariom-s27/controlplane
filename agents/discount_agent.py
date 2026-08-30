"""Use case 3 — goodwill discount / store-credit approval.

Added with ZERO changes to anything under controlplane/. Same gate, same
ladder, same verdict logic, same receipt — a new action, a new manifest
(manifests/discount_approval.yaml), and this agent. Contrast the servicing
demo: there the window is 7 days and the ceiling is INR 25,000; here the
manifest says 14 days and INR 5,000, and the engine does not know or care
which use case it is running.

Demo scenario: a customer asks for a goodwill credit on an old order
(ORD-88461, delivered 26 days ago). The agent proposes it; the gate blocks
it — outside the 14-day discount window AND over the agent's INR 5,000
discount authority.
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
    "I've been a loyal customer for years and the blue running shoes I got a "
    "while ago just haven't worked out. Any chance of a goodwill credit of "
    "about 8000 rupees on that order?"
)

SYSTEM_PROMPT = (
    "You are a customer servicing agent who can approve goodwill discounts "
    "and store credits. Below is the customer's recent order history. If a "
    "goodwill credit is warranted, call the approve_discount tool with the "
    "order's id, the credit amount in paise, and its currency."
)

APPROVE_DISCOUNT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "approve_discount",
            "description": "Approve a goodwill discount or store credit against a delivered order.",
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


def _approve_discount_impl(order_id: str, amount_paise: int, currency: str) -> dict:
    """Private — dispatch_tool via the registry below is the only caller."""
    print(f"DISCOUNT APPROVED {to_rupees(amount_paise)} · order {order_id}")
    return {"status": "approved", "order_id": order_id, "amount_paise": amount_paise, "currency": currency}


register_tool("approve_discount", _approve_discount_impl)


def propose(customer_message: str, customer_id: str = "CUST-2291") -> tuple[dict | None, dict, str]:
    orders = _recent_orders(customer_id)
    context = _render_context(orders)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
        {"role": "user", "content": customer_message},
    ]
    r = chat(messages, tools=APPROVE_DISCOUNT_TOOL)
    message = r["choices"][0]["message"]
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return None, message, context
    call = tool_calls[0]["function"]
    return {"name": call["name"], "args": json.loads(call["arguments"])}, message, context


def run(customer_id: str = "CUST-2291", gate_enabled: bool | None = None) -> None:
    if gate_enabled is None:
        gate_enabled = os.environ.get("CP_GATE", "on").strip().lower() != "off"

    # This agent's manifest, always — not left to whoever invokes it.
    os.environ["CP_MANIFEST"] = "discount_approval"

    session = SessionContext(
        trace_id=str(uuid.uuid4()), customer_id=customer_id,
        agent_role="discount_agent", use_case="discount_approval",
        manifest_id="discount_approval-v1", gate_enabled=gate_enabled,
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
