"""Typed operational failures that may safely cross resolver boundaries."""

from __future__ import annotations


class SourceUnavailable(RuntimeError):
    """An authoritative source could not be read at decision time."""

    def __init__(self, *, source: str, operation: str) -> None:
        self.source = source
        self.operation = operation
        super().__init__(f"{source} unavailable during {operation}")


class AmbiguousPolicyState(RuntimeError):
    """A policy lookup returned more than one row marked current."""

    def __init__(self, *, policy_id: str, row_count: int, query: str) -> None:
        self.policy_id = policy_id
        self.row_count = row_count
        self.query = query
        super().__init__(f"policy {policy_id!r} has {row_count} rows marked current")


__all__ = ["SourceUnavailable", "AmbiguousPolicyState"]
