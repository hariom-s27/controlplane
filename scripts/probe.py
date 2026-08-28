#!/usr/bin/env python3
"""
STEP 0 — the provider probe. Run this before you write anything else.

    python scripts/probe.py

Three assertions against agents/llm.py — the same chat() the real agent and
extractor call — so a pass here is a pass for the actual pipeline, not just
for a hand-rolled OpenAI client:

    1  plain completion returns text
    2  tools=[...] returns a native tool_calls block
    3  json_mode returns valid JSON

The probe always goes live (force_live=True): a cached fixture from a
previous run would prove nothing about whether the provider works today.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["CP_MODE"] = "live"  # the probe always goes live

from agents.llm import chat  # noqa: E402

REFUND_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Issue a refund for an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount_paise": {"type": "integer"},
                    "currency": {"type": "string"},
                },
                "required": ["order_id", "amount_paise", "currency"],
            },
        },
    }
]


def show(n, ok, note):
    print(f"[{'PASS' if ok else 'FAIL'}] {n}  {note}")
    return ok


def main() -> int:
    if not os.environ.get("FEATHERLESS_API_KEY"):
        print("FAIL  FEATHERLESS_API_KEY is not set. Paste your key into .env and retry.")
        return 1

    ok = True
    m = os.environ["CP_MODEL"]

    r = chat([{"role": "user", "content": "Reply with the single word: ready"}], force_live=True)
    ok &= show(
        "1 plain completion",
        bool(r["choices"][0]["message"].get("content")),
        f"{m} · {r.get('_latency_ms')}ms",
    )

    r = chat(
        [{"role": "user", "content": "Refund order ORD-88461 for 4299900 paise INR. Use the tool."}],
        tools=REFUND_TOOL,
        force_live=True,
    )
    tc = r["choices"][0]["message"].get("tool_calls")
    ok &= show("2 native tool call", bool(tc), f"{tc[0]['function']['name'] if tc else 'no tool_calls block'}")

    r = chat(
        [{"role": "user", "content": 'Return JSON only: {"order_id":"ORD-1","amount_paise":100}'}],
        json_mode=True,
        force_live=True,
    )
    try:
        json.loads(r["choices"][0]["message"]["content"])
        good = True
    except Exception:
        good = False
    ok &= show("3 json mode", good, "parsed")

    print("\nALL PASS — pin this model." if ok else "\nSOMETHING FAILED — see fallback below.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
