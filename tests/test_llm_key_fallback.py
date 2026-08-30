"""Multi-account key fallback (agents/llm.py). No network — `call` is a
synthetic function standing in for an OpenAI/Firecrawl request.
"""

from __future__ import annotations

import json

import pytest

import agents.llm as llm_module
from agents.llm import _validated_completion, call_with_key_fallback, numbered_keys


@pytest.fixture(autouse=True)
def _reset_preferred_key_index():
    """_preferred_key_index is module-level global state — without this,
    tests sharing an env var name (even across different values) leak
    which key "won" from one test into the next."""
    llm_module._preferred_key_index.clear()
    yield
    llm_module._preferred_key_index.clear()


class _FakeAuthError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"status {status_code}")


def test_numbered_keys_reads_suffixed_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "k1")
    monkeypatch.setenv("TEST_KEY_2", "k2")
    monkeypatch.setenv("TEST_KEY_3", "k3")
    monkeypatch.delenv("TEST_KEY_4", raising=False)
    assert numbered_keys("TEST_KEY") == ["k1", "k2", "k3"]


def test_numbered_keys_stops_at_first_gap(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "k1")
    monkeypatch.delenv("TEST_KEY_2", raising=False)
    monkeypatch.setenv("TEST_KEY_3", "k3")  # unreachable — numbering stops at the gap
    assert numbered_keys("TEST_KEY") == ["k1"]


def test_falls_back_to_second_key_on_401(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "dead")
    monkeypatch.setenv("TEST_KEY_2", "works")
    calls = []

    def call(key):
        calls.append(key)
        if key == "dead":
            raise _FakeAuthError(401)
        return f"ok:{key}"

    result = call_with_key_fallback("TEST_KEY", call)
    assert result == "ok:works"
    assert calls == ["dead", "works"]


def test_remembers_the_working_key_for_next_call(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "dead")
    monkeypatch.setenv("TEST_KEY_2", "works")
    calls = []

    def call(key):
        calls.append(key)
        if key == "dead":
            raise _FakeAuthError(402)
        return "ok"

    call_with_key_fallback("TEST_KEY", call)
    calls.clear()
    call_with_key_fallback("TEST_KEY", call)
    assert calls == ["works"], "second call should start from the key that worked last time, not retry the dead one"


def test_non_retryable_error_propagates_immediately_without_trying_other_keys(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "k1")
    monkeypatch.setenv("TEST_KEY_2", "k2")
    calls = []

    def call(key):
        calls.append(key)
        raise ValueError("not an auth/quota problem")

    with pytest.raises(ValueError):
        call_with_key_fallback("TEST_KEY", call)
    assert calls == ["k1"], "a non-retryable error must not burn through the other keys"


def test_provider_busy_400_retries_another_configured_account(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "busy")
    monkeypatch.setenv("TEST_KEY_2", "works")

    def call(key):
        if key == "busy":
            raise _FakeAuthErrorWithMessage(400, "This model is busy, please try again later.")
        return "ok"

    assert call_with_key_fallback("TEST_KEY", call) == "ok"


class _FakeAuthErrorWithMessage(_FakeAuthError):
    def __init__(self, status_code, message):
        self.status_code = status_code
        Exception.__init__(self, message)


def test_raises_last_error_when_every_key_fails(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "k1")
    monkeypatch.setenv("TEST_KEY_2", "k2")

    def call(key):
        raise _FakeAuthError(429)

    with pytest.raises(_FakeAuthError):
        call_with_key_fallback("TEST_KEY", call)


def test_missing_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("TEST_KEY_UNSET", raising=False)
    with pytest.raises(RuntimeError, match="TEST_KEY_UNSET"):
        call_with_key_fallback("TEST_KEY_UNSET", lambda key: "unreachable")


def test_zero_length_completion_raises_instead_of_becoming_a_result():
    response = {"choices": [{"message": {"content": "", "tool_calls": []}}]}

    with pytest.raises(RuntimeError, match="empty completion"):
        _validated_completion(response)


@pytest.mark.parametrize("message", [
    {"content": "", "tool_calls": []},
    {"content": "   \n\t", "tool_calls": []},
    {"content": "", "tool_calls": [{}]},
    {"content": "", "tool_calls": [{"function": {"name": "", "arguments": "{}"}}]},
    {"content": "", "tool_calls": [{"function": {"name": "issue_refund", "arguments": "not-json"}}]},
    {"content": "", "tool_calls": [{"function": {"name": "issue_refund", "arguments": "[]"}}]},
])
def test_cached_chat_rejects_empty_or_unusable_completion(monkeypatch, tmp_path, message):
    monkeypatch.setattr(llm_module, "FIXTURES", tmp_path)
    monkeypatch.setenv("CP_MODEL", "test-model")
    messages = [{"role": "user", "content": "test"}]
    payload = {"model": "test-model", "messages": messages, "temperature": 0.0,
               "max_tokens": llm_module.MAX_TOKENS}
    fixture = tmp_path / f"{llm_module.cache_key(payload)}.json"
    fixture.write_text(json.dumps({"choices": [{"message": message}]}))
    with pytest.raises(RuntimeError, match="empty completion|unusable completion"):
        llm_module.chat(messages)


def test_cached_chat_rejects_empty_choices(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_module, "FIXTURES", tmp_path)
    monkeypatch.setenv("CP_MODEL", "test-model")
    messages = [{"role": "user", "content": "test"}]
    payload = {"model": "test-model", "messages": messages, "temperature": 0.0,
               "max_tokens": llm_module.MAX_TOKENS}
    (tmp_path / f"{llm_module.cache_key(payload)}.json").write_text(json.dumps({"choices": []}))
    with pytest.raises(RuntimeError, match="no choices"):
        llm_module.chat(messages)


def test_cache_does_not_replay_fixture_keyed_without_max_tokens(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_module, "FIXTURES", tmp_path)
    monkeypatch.setenv("CP_MODEL", "test-model")
    monkeypatch.setenv("CP_MODE", "fixture")
    messages = [{"role": "user", "content": "test"}]
    legacy_payload = {"model": "test-model", "messages": messages, "temperature": 0.0}
    legacy = tmp_path / f"{llm_module.cache_key(legacy_payload)}.json"
    legacy.write_text(json.dumps({"choices": [{"message": {"content": "legacy"}}]}))
    with pytest.raises(RuntimeError, match="No fixture"):
        llm_module.chat(messages)


def test_live_chat_rejects_zero_length_completion_and_does_not_cache(monkeypatch, tmp_path):
    class FakeResponse:
        def model_dump(self):
            return {"choices": [{"message": {"content": "", "tool_calls": []}}]}

    class FakeCompletions:
        def create(self, **payload):
            assert payload["max_tokens"] == llm_module.MAX_TOKENS
            return FakeResponse()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(llm_module, "OpenAI", FakeClient)
    monkeypatch.setattr(llm_module, "FIXTURES", tmp_path)
    monkeypatch.setenv("CP_MODEL", "test-model")
    monkeypatch.setenv("CP_MODE", "live")
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")
    with pytest.raises(RuntimeError, match="empty completion"):
        llm_module.chat([{"role": "user", "content": "test"}], force_live=True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("tool_calls", [
    [{}],
    [{"function": {"name": "", "arguments": "{}"}}],
    [{"function": {"name": "issue_refund", "arguments": "not-json"}}],
    [{"function": {"name": "issue_refund", "arguments": "[]"}}],
])
def test_malformed_tool_calls_are_not_usable_completions(tool_calls):
    response = {"choices": [{"message": {"content": "", "tool_calls": tool_calls}}]}
    with pytest.raises(RuntimeError, match="unusable completion"):
        _validated_completion(response)
