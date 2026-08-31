"""Typed operational failures that may safely cross resolver boundaries."""

from __future__ import annotations


class SourceUnavailable(RuntimeError):
    """An authoritative source could not be read at decision time."""

    def __init__(self, *, source: str, operation: str) -> None:
        self.source = source
        self.operation = operation
        super().__init__(f"{source} unavailable during {operation}")


__all__ = ["SourceUnavailable"]
