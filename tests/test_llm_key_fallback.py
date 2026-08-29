"""Multi-account key fallback (agents/llm.py). No network — `call` is a
synthetic function standing in for an OpenAI/Firecrawl request.
"""

from __future__ import annotations

import pytest

import agents.llm as llm_module
from agents.llm import call_with_key_fallback, numbered_keys


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
