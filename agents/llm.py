"""One function, one client, fixture cache built in. R6/R7.

Every call is cached to data/fixtures/<sha256-of-request>.json. CP_MODE
(default: fixture) never touches the network — that's what lets `make demo`
run on a judge's laptop with no API key. CP_MODE=live records a fixture on
first call and replays it on every call after that.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

FIXTURES = ROOT / "data" / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["FEATHERLESS_API_KEY"],
            base_url=os.environ.get("CP_BASE_URL", "https://api.featherless.ai/v1"),
        )
    return _client


def cache_key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]


def chat(messages, tools=None, json_mode=False, temperature=0.0, force_live=False):
    """R6: every call is cached. CP_MODE=fixture (default) never touches the network.

    force_live skips reading an existing fixture, for callers whose whole point
    is to prove the network path works right now (scripts/probe.py) rather than
    replay a recording of when it once did. The fresh response still overwrites
    the fixture, so later fixture-mode callers get the new recording.
    """
    payload = {
        "model": os.environ["CP_MODEL"],
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    f = FIXTURES / f"{cache_key(payload)}.json"
    if not force_live and f.exists():
        return json.loads(f.read_text())

    if os.environ.get("CP_MODE", "fixture") != "live":
        raise RuntimeError(
            f"No fixture {f.name} and CP_MODE != live. Run with CP_MODE=live once to record it."
        )

    t0 = time.perf_counter()
    resp = client().chat.completions.create(**payload)
    out = resp.model_dump()
    out["_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    f.write_text(json.dumps(out, indent=2, default=str))
    return out
