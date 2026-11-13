"""Content hash of the SQLite stores, independent of file layout (P05 V11).

`data/build_db.py` aims for byte-identical .db files, but a different SQLite
version can lay out the same rows differently on disk. This script hashes what
the database *contains*, so a fresh build can be compared on content:

  for each table, in sorted name order:
      "TABLE <name>"  +  its CREATE statement from sqlite_master
      every row, encoded with typed tokens, sorted, one per line
  -> sha256 of the UTF-8 text

Row encoding: NULL -> N ; int -> I:<n> ; float -> F:<repr> ;
text -> S:<json string> ; blob -> B:<hex>. Values are joined with a tab.

Each database is opened read-only and immutable (it is never modified).
Stdlib only.

Usage: python scripts/db_content_hash.py [DB ...]
       (default: data/entitlements.db data/orders.db data/policy_store.db)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DBS = ("entitlements.db", "orders.db", "policy_store.db")


def _token(value: object) -> str:
    if value is None:
        return "N"
    if isinstance(value, bool):  # sqlite3 never returns bool; guard anyway
        return f"I:{int(value)}"
    if isinstance(value, int):
        return f"I:{value}"
    if isinstance(value, float):
        return f"F:{value!r}"
    if isinstance(value, str):
        return "S:" + json.dumps(value, ensure_ascii=False)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "B:" + bytes(value).hex()
    raise TypeError(f"unexpected SQLite value type: {type(value).__name__}")


def content_text(db: Path) -> str:
    uri = db.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    try:
        tables = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        out: list[str] = []
        for name, sql in tables:
            out.append(f"TABLE {name}")
            out.append(sql or "")
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(
                "\t".join(_token(v) for v in row)
                for row in conn.execute(f"SELECT * FROM {quoted}")
            )
            out.append(f"ROWS {len(rows)}")
            out.extend(rows)
        return "\n".join(out) + "\n"
    finally:
        conn.close()


def content_sha256(db: Path) -> str:
    return hashlib.sha256(content_text(db).encode("utf-8")).hexdigest()


def file_sha256(db: Path) -> str:
    return hashlib.sha256(db.read_bytes()).hexdigest()


def main(argv: list[str]) -> int:
    dbs = [Path(a) for a in argv] or [ROOT / "data" / n for n in DEFAULT_DBS]
    missing = [str(d) for d in dbs if not d.is_file()]
    if missing:
        print("missing:", ", ".join(missing), file=sys.stderr)
        return 2
    for db in dbs:
        print(f"{db.name}\tfile_sha256={file_sha256(db)}\tcontent_sha256={content_sha256(db)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
