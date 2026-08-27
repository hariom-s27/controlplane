#!/usr/bin/env python3
"""
STEP 0 — the provider probe. Run this before you write anything else.

    python scripts/probe.py

WHY THIS EXISTS
---------------
Featherless is OpenAI-compatible, but their docs are explicit that NATIVE
function calling works on only two model families:

    moonshotai/Kimi-K2-Instruct
    the Qwen 3 family

Everything else needs response_format={"type": "json_object"} plus careful
prompting. If you discover on day 4 that your chosen model silently ignores
`tools=[...]`, you lose the day and probably the second use case.

Three assertions, ten minutes:

    1  plain completion returns text
    2  tools=[...] returns a tool_calls block         <- the agent needs this
    3  response_format json_object returns valid JSON <- the extractor needs this

Assertion 2 gates S2 (the agent). Assertion 3 gates S4 (the extractor).
If 2 fails, see the FALLBACK note printed at the end — the demo survives,
because ControlPlane intercepts at a Python function boundary, not at a
provider feature.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    print("FAIL  the `openai` package is not installed.")
    print("      pip install -r requirements.txt")
    sys.exit(1)

BASE_URL = os.getenv("CP_BASE_URL", "https://api.featherless.ai/v1")
API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
MODEL = os.getenv("CP_MODEL", "Qwen/Qwen3-8B")

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if os.name == "nt" and not os.getenv("WT_SESSION"):
    GREEN = RED = YELLOW = DIM = RESET = ""


def ok(msg: str) -> None:
    print(f"{GREEN}PASS{RESET}  {msg}")


def bad(msg: str) -> None:
    print(f"{RED}FAIL{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}WARN{RESET}  {msg}")


# The tool the servicing agent will actually emit. Keep this schema identical
# to the one in agents/servicing_agent.py — if they drift, the probe stops
# telling you anything useful.
ISSUE_REFUND_TOOL = {
    "type": "function",
    "function": {
        "name": "issue_refund",
        "description": "Issue a refund to the customer for a delivered order.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order identifier, e.g. ORD-88461",
                },
                "amount_paise": {
                    "type": "integer",
                    "description": "Refund amount in paise (INR x 100). Integers only.",
                },
                "currency": {"type": "string", "enum": ["INR"]},
            },
            "required": ["order_id", "amount_paise", "currency"],
        },
    },
}


def main() -> int:
    print()
    print("ControlPlane — provider probe")
    print(f"{DIM}  base_url : {BASE_URL}{RESET}")
    print(f"{DIM}  model    : {MODEL}{RESET}")
    print(f"{DIM}  key      : {'set (' + API_KEY[:6] + '...)' if API_KEY else 'MISSING'}{RESET}")
    print()

    if not API_KEY:
        bad("FEATHERLESS_API_KEY is not set.")
        print()
        print("      1. copy .env.example to .env")
        print("      2. paste your key into it")
        print("      3. run this again")
        return 1

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=120.0)
    results: dict[str, bool] = {}

    # ---------------------------------------------------------------- warm-up
    # The FIRST call to a Featherless model can cold-start and take tens of
    # seconds. Never quote that number as your latency. Measure the second one.
    print(f"{DIM}  warming the model (first call may take 30s+, this is normal)...{RESET}")
    try:
        t0 = time.perf_counter()
        client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=8,
        )
        print(f"{DIM}  cold start: {time.perf_counter() - t0:.1f}s{RESET}")
        print()
    except Exception as e:  # noqa: BLE001
        bad(f"could not reach the API: {type(e).__name__}: {e}")
        print()
        print("      Check, in this order:")
        print("      - is the model string exactly right? a typo returns 404, not a hint")
        print("      - is the key valid and does your plan cover this model?")
        print("      - are you behind a proxy or firewall?")
        return 1

    # -------------------------------------------------- 1. plain completion
    try:
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Say exactly: hello"}],
            max_tokens=16,
        )
        dt = (time.perf_counter() - t0) * 1000
        text = (r.choices[0].message.content or "").strip()
        if text:
            ok(f"1  plain completion            {dt:>7.0f} ms   -> {text[:40]!r}")
            results["plain"] = True
        else:
            bad("1  plain completion returned empty content")
            results["plain"] = False
    except Exception as e:  # noqa: BLE001
        bad(f"1  plain completion: {type(e).__name__}: {e}")
        results["plain"] = False

    # ------------------------------------------------- 2. native tool calling
    try:
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a customer servicing agent. Use the tools available to you.",
                },
                {
                    "role": "user",
                    "content": (
                        "Refund order ORD-88461 for the customer. "
                        "The order total is 42999 rupees. Issue the refund now."
                    ),
                },
            ],
            tools=[ISSUE_REFUND_TOOL],
            tool_choice="auto",
            max_tokens=256,
        )
        dt = (time.perf_counter() - t0) * 1000
        calls = r.choices[0].message.tool_calls
        if calls:
            fn = calls[0].function
            args = json.loads(fn.arguments)
            ok(f"2  native tool calling         {dt:>7.0f} ms   -> {fn.name}({args})")
            results["tools"] = True
        else:
            bad("2  native tool calling: no tool_calls block returned")
            print(f"{DIM}       content was: {(r.choices[0].message.content or '')[:120]!r}{RESET}")
            results["tools"] = False
    except Exception as e:  # noqa: BLE001
        bad(f"2  native tool calling: {type(e).__name__}: {e}")
        results["tools"] = False

    # ------------------------------------------------------- 3. JSON mode
    try:
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You output ONLY valid JSON, no prose and no markdown fences. "
                        'Use exactly this shape: {"order_id": string, "amount_paise": integer, '
                        '"policy_version": string or null}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Under refund policy v3.8, order ORD-88461 qualifies for a "
                        "full refund of 42999 rupees. Extract the fields."
                    ),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=256,
        )
        dt = (time.perf_counter() - t0) * 1000
        raw = (r.choices[0].message.content or "").strip()
        # Some models wrap JSON in markdown fences even in json_object mode.
        if raw.startswith("```"):
            raw = raw.strip("`").lstrip("json").strip()
        parsed = json.loads(raw)
        ok(f"3  json_object mode            {dt:>7.0f} ms   -> {parsed}")
        results["json"] = True
    except json.JSONDecodeError:
        bad("3  json_object mode returned text that is not valid JSON")
        print(f"{DIM}       raw: {raw[:200]!r}{RESET}")
        results["json"] = False
    except Exception as e:  # noqa: BLE001
        bad(f"3  json_object mode: {type(e).__name__}: {e}")
        results["json"] = False

    # ------------------------------------------------------------- verdict
    print()
    print("-" * 68)
    if results.get("tools") and results.get("json"):
        print(f"{GREEN}READY{RESET}  Pin this in .env and do not change it mid-build:")
        print()
        print(f"       CP_MODEL={MODEL}")
        print()
        print("       S2 (the agent)     -> native tool calling")
        print("       S4 (the extractor) -> Instructor with Mode.JSON")
        print()
        print(f"{YELLOW}       Set Instructor's mode EXPLICITLY. Its default is Mode.TOOLS,{RESET}")
        print(f"{YELLOW}       which returns silent empty objects on most Featherless models.{RESET}")
        return 0

    if results.get("json") and not results.get("tools"):
        warn("this model does not do native tool calling.")
        print()
        print("       Two options, in order of preference:")
        print()
        print("       A) Try another model and re-run this probe:")
        print("            CP_MODEL=Qwen/Qwen3-14B          python scripts/probe.py")
        print("            CP_MODEL=moonshotai/Kimi-K2-Instruct  python scripts/probe.py")
        print()
        print("       B) Keep this model and have the agent emit its tool call as")
        print("          JSON, which your loop parses into a ToolCall. The demo is")
        print("          UNAFFECTED: ControlPlane intercepts at dispatch_tool(), a")
        print("          Python function boundary, not a provider feature. Say so")
        print("          in the README - it is a strength, not a workaround.")
        return 2

    bad("the provider is not usable yet. Fix assertion 1 first, then re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
