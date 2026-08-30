"""Atomic in-process execution ledger for governed tool calls.

The ledger gives dispatch retries at-most-once execution within a running
ControlPlane process.  P08 exercises the common caller-timeout case: the first
execution completed, its response was lost, and a retry reuses the same key.
Durability across process restarts remains an explicit limitation.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable


class DuplicateExecutionSuppressed(RuntimeError):
    """A prior attempt may have executed but did not complete cleanly."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"execution suppressed for indeterminate idempotency key {key!r}")


@dataclass(frozen=True)
class ExecutionOutcome:
    result: Any
    replayed: bool


@dataclass
class _Entry:
    state: str
    result: Any = None


class ExecutionLedger:
    def __init__(self) -> None:
        self._lock = RLock()
        self._entries: dict[str, _Entry] = {}

    def execute_once(self, key: str, call: Callable[[], Any]) -> ExecutionOutcome:
        if not key:
            raise ValueError("idempotency key must be non-empty")

        with self._lock:
            prior = self._entries.get(key)
            if prior is not None:
                if prior.state == "completed":
                    return ExecutionOutcome(result=prior.result, replayed=True)
                raise DuplicateExecutionSuppressed(key)
            self._entries[key] = _Entry(state="in_flight")

        try:
            result = call()
        except BaseException:
            # Conservatively retain an indeterminate marker.  Retrying an
            # operation that may already have produced a side effect is less
            # safe than requiring explicit reconciliation.
            with self._lock:
                self._entries[key].state = "indeterminate"
            raise

        with self._lock:
            self._entries[key] = _Entry(state="completed", result=result)
        return ExecutionOutcome(result=result, replayed=False)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


_LEDGER = ExecutionLedger()


def execute_once(key: str, call: Callable[[], Any]) -> ExecutionOutcome:
    return _LEDGER.execute_once(key, call)


def reset_execution_ledger() -> None:
    """P08/test isolation hook; production callers never need to reset it."""

    _LEDGER.reset()


__all__ = [
    "DuplicateExecutionSuppressed",
    "ExecutionLedger",
    "ExecutionOutcome",
    "execute_once",
    "reset_execution_ledger",
]
