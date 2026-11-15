"""P07a: demo2 / demo3 run offline from pinned legacy recordings.

b4ef009 added max_tokens to the chat() cache key; the demo2 and demo3
recordings predate it. agents/llm.py::_legacy_replay() replays such a
recording only when it is pinned by sha256 in data/fixtures/legacy_replay.json
and code shows it answers this request (apart from max_tokens), was not cut
off, fits under the cap and came from the requested model. These tests cover
that policy (accept and reject), exact-key precedence, both demos end to end,
and the exit-2 safety net in the agents' main().

Everything runs in-process: tests/conftest.py redirects the decision trail,
and its session guard fails the run if a test writes the repo-root trail.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

import agents.llm as llm  # noqa: E402

PINS = {
    # requested key (today's payload) -> (legacy file, completion tokens recorded)
    "demo2": ("1be373c0ba35ffb89501", "1f178c3adfd04c2dbbd3.json", 360),
    "demo3": ("4b57e71075df8b5b7077", "e67b69f08a2a8d7658ee.json", 371),
}
REASON = ("recorded before max_tokens joined the cache key (commit b4ef009); "
          "replayed only when pinned by sha256 and proven complete by code")


def _built() -> None:
    for name in ("orders.db", "entitlements.db"):
        if not (DATA / name).exists():
            subprocess.run([sys.executable, str(DATA / "build_db.py")], check=True,
                           capture_output=True, cwd=ROOT)


@pytest.fixture
def fixture_mode(monkeypatch):
    """Fixture mode exactly as a fresh clone has it, keys irrelevant."""
    monkeypatch.delenv("CP_MODE", raising=False)
    monkeypatch.setenv("CP_MODEL", "Qwen/Qwen3-8B")
    monkeypatch.setenv("CP_GATE", "on")
    # run() assigns os.environ["CP_MANIFEST"] itself; setenv first so teardown restores it
    monkeypatch.setenv("CP_MANIFEST", "servicing")
    if not os.environ.get("CP_RECEIPT_SECRET"):
        monkeypatch.setenv("CP_RECEIPT_SECRET", "test-only-receipt-key-not-for-production")
    _built()


def _demo(name: str):
    if name == "demo2":
        import agents.knowledge_assistant as mod
        return mod, lambda: mod.propose(mod.EMPLOYEE_QUESTION)
    import agents.discount_agent as mod
    return mod, lambda: mod.propose(mod.CUSTOMER_MESSAGE, "CUST-2291")


# --------------------------------------------------------------------------
# the pin file itself
# --------------------------------------------------------------------------

def test_pin_file_lists_exactly_the_two_demo_recordings_with_their_sha256():
    entries = json.loads((DATA / "fixtures" / "legacy_replay.json").read_text(encoding="utf-8"))["entries"]
    assert len(entries) == 2
    by_key = {e["requested_key"]: e for e in entries}
    for requested, legacy_file, _tokens in PINS.values():
        e = by_key[requested]
        assert set(e) == {"requested_key", "legacy_file", "legacy_sha256", "reason"}
        assert e["legacy_file"] == legacy_file
        assert e["reason"] == REASON
        raw = (DATA / "fixtures" / legacy_file).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == e["legacy_sha256"]
        # the exact (today's) key really is absent: the replay is the only offline path
        assert not (DATA / "fixtures" / f"{requested}.json").exists()


# --------------------------------------------------------------------------
# policy: accept (both real entries) and reject (synthetic, one condition broken each)
# --------------------------------------------------------------------------

def _synthetic(tmp_path, monkeypatch, *, listed=True, sha_ok=True, finish="tool_calls",
               tokens=10, model="test-model", mode=None):
    monkeypatch.setattr(llm, "FIXTURES", tmp_path)
    monkeypatch.setattr(llm, "LEGACY_REPLAY", tmp_path / "legacy_replay.json")
    monkeypatch.setenv("CP_MODEL", "test-model")
    if mode is None:
        monkeypatch.delenv("CP_MODE", raising=False)
    else:
        monkeypatch.setenv("CP_MODE", mode)
    messages = [{"role": "user", "content": "synthetic pinned-replay case"}]
    payload = {"model": "test-model", "messages": messages, "temperature": 0.0, "max_tokens": llm.MAX_TOKENS}
    requested = llm.cache_key(payload)
    legacy_file = f"{llm.cache_key({k: v for k, v in payload.items() if k != 'max_tokens'})}.json"
    body = {"model": model, "usage": {"completion_tokens": tokens},
            "choices": [{"finish_reason": finish, "message": {"content": "legacy answer"}}]}
    raw = json.dumps(body).encode("utf-8")
    (tmp_path / legacy_file).write_bytes(raw)
    entry = {"requested_key": requested if listed else "0" * 20, "legacy_file": legacy_file,
             "legacy_sha256": hashlib.sha256(raw).hexdigest() if sha_ok else "0" * 64, "reason": REASON}
    (tmp_path / "legacy_replay.json").write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    return messages


class _LiveCalled(Exception):
    pass


POLICY_CASES = [
    # (id, kind, kwargs, expected)
    ("accept-demo2-real", "real", {"demo": "demo2"}, "accept"),
    ("accept-demo3-real", "real", {"demo": "demo3"}, "accept"),
    ("accept-synthetic-control", "synthetic", {}, "accept"),
    ("reject-key-not-listed", "synthetic", {"listed": False}, "reject"),
    ("reject-sha256-mismatch", "synthetic", {"sha_ok": False}, "reject"),
    ("reject-finish-length", "synthetic", {"finish": "length"}, "reject"),
    ("reject-tokens-equal-cap", "synthetic", {"tokens": "cap"}, "reject"),
    ("reject-tokens-above-cap", "synthetic", {"tokens": "cap+1"}, "reject"),
    ("reject-model-differs", "synthetic", {"model": "other-model"}, "reject"),
    ("reject-live-mode", "synthetic", {"mode": "live"}, "live"),
    ("reject-force-live", "synthetic", {"force_live": True}, "reject"),
]


@pytest.mark.parametrize("case_id,kind,kw,expected", POLICY_CASES, ids=[c[0] for c in POLICY_CASES])
def test_legacy_replay_policy(case_id, kind, kw, expected, tmp_path, monkeypatch, capsys, fixture_mode):
    if kind == "real":
        requested, legacy_file, tokens = PINS[kw["demo"]]
        mod, propose = _demo(kw["demo"])
        call, message, _context = propose()[:3]
        assert call is not None
        if kw["demo"] == "demo2":
            assert call["name"] == "send_document"
            assert call["args"]["recipient_id"] == "EMP-4410" and call["args"]["doc_id"] == "DOC-2277"
        else:
            assert call["name"] == "approve_discount"
            assert call["args"]["order_id"] == "ORD-88461" and call["args"]["amount_paise"] == 800000
        err = capsys.readouterr().err
        assert (f"replayed {legacy_file} (recorded before b4ef009); sha256 ok; "
                f"finish=tool_calls, {tokens} tokens < cap {llm.MAX_TOKENS}") in err
        return

    force_live = kw.pop("force_live", False)
    if kw.get("tokens") == "cap":
        kw["tokens"] = llm.MAX_TOKENS
    elif kw.get("tokens") == "cap+1":
        kw["tokens"] = llm.MAX_TOKENS + 1
    messages = _synthetic(tmp_path, monkeypatch, **kw)

    if expected == "live":
        # live mode never consults the legacy list: it goes to the provider
        class FakeClient:
            def __init__(self, **_):
                raise _LiveCalled()
        monkeypatch.setattr(llm, "OpenAI", FakeClient)
        monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")
        with pytest.raises(_LiveCalled):
            llm.chat(messages)
        assert "replayed" not in capsys.readouterr().err
        return
    if expected == "accept":
        r = llm.chat(messages, force_live=force_live)
        assert r["choices"][0]["message"]["content"] == "legacy answer"
        assert "(recorded before b4ef009); sha256 ok; finish=tool_calls, 10 tokens < cap" in capsys.readouterr().err
        return
    with pytest.raises(RuntimeError, match=r"^No fixture .* and CP_MODE != live"):
        llm.chat(messages, force_live=force_live)
    assert "replayed" not in capsys.readouterr().err


def test_exact_key_is_preferred_over_a_valid_legacy_recording(tmp_path, monkeypatch, capsys):
    messages = _synthetic(tmp_path, monkeypatch)
    payload = {"model": "test-model", "messages": messages, "temperature": 0.0, "max_tokens": llm.MAX_TOKENS}
    exact = {"choices": [{"finish_reason": "stop", "message": {"content": "exact answer"}}]}
    (tmp_path / f"{llm.cache_key(payload)}.json").write_text(json.dumps(exact))
    r = llm.chat(messages)
    assert r["choices"][0]["message"]["content"] == "exact answer"
    assert "replayed" not in capsys.readouterr().err


# --------------------------------------------------------------------------
# end to end, in-process, with the expected decisions
# --------------------------------------------------------------------------

def test_demo2_end_to_end_offline_blocks_the_cross_tenant_document(fixture_mode, capsys):
    import agents.knowledge_assistant as ka
    assert ka.main() == 0
    out = capsys.readouterr().out
    assert "agent proposes> send_document(" in out
    assert "dispatch> BLOCK: CONTRADICTED — ['recipient_entitled']" in out
    assert "DOCUMENT SENT" not in out


def test_demo3_end_to_end_offline_blocks_the_discount(fixture_mode, capsys):
    import agents.discount_agent as da
    assert da.main() == 0
    out = capsys.readouterr().out
    assert "agent proposes> approve_discount(" in out
    assert "dispatch> BLOCK: CONTRADICTED — ['within_window', 'within_authority']" in out
    assert "DISCOUNT APPROVED" not in out


# --------------------------------------------------------------------------
# safety net: only "No fixture" becomes exit 2
# --------------------------------------------------------------------------

@pytest.mark.parametrize("demo,module,hint", [
    ("demo2", "agents.knowledge_assistant", ".\\make.ps1 judge-demo (offline; covers use case 2)"),
    ("demo3", "agents.discount_agent", "python -m pytest tests/test_third_use_case.py (offline)"),
])
def test_missing_recording_exits_2_with_a_clear_message(demo, module, hint, fixture_mode, monkeypatch, capsys):
    mod = __import__(module, fromlist=["main"])
    monkeypatch.setenv("CP_MODEL", "no-such-model")  # neither key nor pinned legacy key matches
    assert mod.main() == 2
    err = capsys.readouterr().err
    assert err.startswith(f"{demo}: no usable recorded LLM response for this request (No fixture ")
    assert "Set CP_MODE=live and a provider key in .env (paid API)" in err
    assert hint in err


@pytest.mark.parametrize("module", ["agents.knowledge_assistant", "agents.discount_agent"])
@pytest.mark.parametrize("exc", [RuntimeError("LLM returned an empty completion: no choices"), ValueError("boom")])
def test_other_errors_still_propagate(module, exc, monkeypatch):
    mod = __import__(module, fromlist=["main"])

    def failing_run(*_a, **_k):
        raise exc
    monkeypatch.setattr(mod, "run", failing_run)
    with pytest.raises(type(exc)):
        mod.main()
