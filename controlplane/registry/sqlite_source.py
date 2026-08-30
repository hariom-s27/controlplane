"""SQLite helpers that classify availability failures without hiding bugs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from controlplane.errors import SourceUnavailable

_AVAILABILITY_CODES = {
    sqlite3.SQLITE_BUSY,
    sqlite3.SQLITE_LOCKED,
    sqlite3.SQLITE_IOERR,
    sqlite3.SQLITE_CANTOPEN,
}


def _is_availability_failure(exc: sqlite3.OperationalError) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    if code is None:
        # Python/SQLite builds that do not expose an error code still provide
        # stable messages for the two connection-level failures P08 injects.
        message = str(exc).lower()
        return "unable to open database file" in message or "database is locked" in message
    return (int(code) & 0xFF) in _AVAILABILITY_CODES


def translate_availability(
    exc: sqlite3.OperationalError, *, source: str, operation: str
) -> None:
    """Raise a typed outage only for availability-class SQLite failures.

    SQL errors such as a missing table or malformed query are programming or
    schema failures.  They are intentionally re-raised unchanged rather than
    being laundered through a fail-closed decision.
    """

    if _is_availability_failure(exc):
        raise SourceUnavailable(source=source, operation=operation) from exc
    raise exc


def connect_readwrite(path: Path, *, source: str) -> sqlite3.Connection:
    """Open an existing SQLite source without creating a missing empty DB.

    The explicit file check preserves the original path passed to
    ``sqlite3.connect``.  P05's frozen isolation probe treats that source name
    as a structural guarantee, so adding URI query text would incorrectly make
    the same live store look like a different evidence source.
    """

    if not path.is_file():
        raise SourceUnavailable(source=source, operation="connect")
    try:
        return sqlite3.connect(path)
    except sqlite3.OperationalError as exc:
        translate_availability(exc, source=source, operation="connect")
        raise AssertionError("translate_availability must raise")  # pragma: no cover


__all__ = ["connect_readwrite", "translate_availability"]
