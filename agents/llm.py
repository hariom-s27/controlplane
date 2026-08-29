"""One function, one client, fixture cache built in. R6/R7.

Every call is cached to data/fixtures/<sha256-of-request>.json. CP_MODE
(default: fixture) never touches the network — that's what lets `make demo`
run on a judge's laptop with no API key. CP_MODE=live records a fixture on
first call and replays it on every call after that.

Multi-account key fallback: FEATHERLESS_API_KEY, FEATHERLESS_API_KEY_2,
FEATHERLESS_API_KEY_3, ... are tried in order (starting from whichever one
last worked), so one account running out of credit doesn't stop the
pipeline as long as another configured account still has some. See
call_with_key_fallback() below — controlplane/extract.py and
scripts/scrape_policies.py use the same mechanism for their own keys.
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
    """The plain, no-fallback client — always the FIRST configured key.
    Kept for callers that just need *a* client (e.g. one-off scripts);
    chat() and extract_action() use call_with_key_fallback() instead."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["FEATHERLESS_API_KEY"],
            base_url=os.environ.get("CP_BASE_URL", "https://api.featherless.ai/v1"),
        )
    return _client


def numbered_keys(env_var: str) -> list[str]:
    """{env_var}, {env_var}_2, {env_var}_3, ... — as many as are set. Each
    is expected to belong to a separate account with its own credit pool."""
    keys = []
    first = os.environ.get(env_var, "")
    if first:
        keys.append(first)
    i = 2
    while True:
        nxt = os.environ.get(f"{env_var}_{i}", "")
        if not nxt:
            break
        keys.append(nxt)
        i += 1
    return keys


_preferred_key_index: dict[str, int] = {}


def _default_is_retryable(exc: Exception) -> bool:
    """OpenAI-SDK-shaped: 401 (bad key), 402 (out of credit), 403
    (forbidden), 429 (rate/quota limited) mean "this key is done, try the
    next one." Anything else (a network outage, a 500, a real bug)
    propagates immediately — switching keys wouldn't fix it, and silently
    burning through every configured account on an unrelated error would
    hide what actually broke."""
    return getattr(exc, "status_code", None) in (401, 402, 403, 429)


def call_with_key_fallback(env_var: str, call, is_retryable=_default_is_retryable):
    """Tries each numbered_keys(env_var) in turn, starting from whichever
    one last succeeded, so a dead key isn't retried on every single call
    once a working one is known. `call(key)` performs the actual request
    and should raise on failure — its return value is passed straight
    through on success.
    """
    keys = numbered_keys(env_var)
    if not keys:
        raise RuntimeError(f"No {env_var} configured — see .env.example")

    start = _preferred_key_index.get(env_var, 0) % len(keys)
    order = list(range(start, len(keys))) + list(range(0, start))
    last_error: Exception | None = None
    for idx in order:
        try:
            result = call(keys[idx])
        except Exception as e:  # noqa: BLE001
            if is_retryable(e):
                last_error = e
                continue
            raise
        else:
            _preferred_key_index[env_var] = idx
            return result
    raise last_error  # every configured key failed


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

    def _call(key: str):
        t0 = time.perf_counter()
        c = OpenAI(api_key=key, base_url=os.environ.get("CP_BASE_URL", "https://api.featherless.ai/v1"))
        resp = c.chat.completions.create(**payload)
        out = resp.model_dump()
        out["_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    out = call_with_key_fallback("FEATHERLESS_API_KEY", _call)
    f.write_text(json.dumps(out, indent=2, default=str))
    return out
