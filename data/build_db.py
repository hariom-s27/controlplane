#!/usr/bin/env python3
"""
Build the three SQLite stores from the committed JSON seeds.

    python data/build_db.py

Run it twice and the .db files are BYTE-IDENTICAL. That property is what makes
the whole demo reproducible, and tests/test_data.py asserts it.

Why SQLite and not Postgres
---------------------------
The liveness that matters here is PROCEDURAL, not infrastructural: two
independent reads of the same store, one from the agent's stale retrieval
context and one a fresh query at decision time. SQLite gives you that. Docker
and Postgres buy nothing for what is being demonstrated and cost setup time
for anyone cloning the repo. Say this in the README before a reviewer says it
for you.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seed"
DATA_DIR = ROOT / "data"

# Fixed seed => deterministic filler rows. Same number as SEB-1 so the whole
# project has one seed to quote.
CP_SEED = int(os.getenv("CP_SEED", "20260814"))

# The demo clock is FROZEN. If you use the real system date, "26 days elapsed"
# becomes 27, then 28, and the recorded video goes stale within a week.
DEMO_TODAY = date.fromisoformat(os.getenv("CP_DEMO_DATE", "2026-08-14"))


def _load(name: str) -> dict:
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))


def _fresh(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=DELETE")  # no -wal file, keeps builds identical
    return conn


# --------------------------------------------------------------------------
# orders.db
# --------------------------------------------------------------------------


def build_orders() -> int:
    spec = _load("orders.json")
    conn = _fresh(DATA_DIR / "orders.db")
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE orders (
            order_id         TEXT PRIMARY KEY,
            customer_id      TEXT NOT NULL,
            item_description TEXT NOT NULL,
            item_colour      TEXT,
            item_category    TEXT,
            amount_paise     INTEGER NOT NULL,
            currency         TEXT NOT NULL DEFAULT 'INR',
            placed_at        TEXT NOT NULL,
            delivered_at     TEXT,
            order_status     TEXT NOT NULL
        )
        """
    )
    # Per-FIELD reliability, not per-system. This table is where
    # SOURCE-UNRELIABLE comes from.
    cur.execute(
        """
        CREATE TABLE field_reliability (
            table_name  TEXT NOT NULL,
            field_name  TEXT NOT NULL,
            reliability TEXT NOT NULL,
            PRIMARY KEY (table_name, field_name)
        )
        """
    )

    rows: list[tuple] = []
    demo_ids: set[str] = set()
    for o in spec["demo_orders"]:
        demo_ids.add(o["order_id"])
        rows.append(
            (
                o["order_id"],
                o["customer_id"],
                o["item_description"],
                o["item_colour"],
                o["item_category"],
                o["amount_paise"],
                o["currency"],
                o["placed_at"],
                o["delivered_at"],
                o["order_status"],
            )
        )

    # --- deterministic filler ---
    f = spec["filler"]
    rng = random.Random(CP_SEED)
    oid = 10000
    for c in range(1, f["n_customers"] + 1):
        customer_id = f"CUST-{1000 + c * 37}"
        if customer_id == "CUST-2291":  # never collide with the demo customer
            continue
        n_orders = rng.randint(*f["orders_per_customer"])
        for _ in range(n_orders):
            oid += rng.randint(1, 9)  # non-contiguous ids, like a real system
            order_id = f"ORD-{oid}"
            if order_id in demo_ids:
                continue
            colour = rng.choice(f["colours"])
            category = rng.choice(f["categories"])
            days_ago = rng.randint(*f["days_ago_range"])
            delivered = DEMO_TODAY - timedelta(days=days_ago)
            placed = delivered - timedelta(days=rng.randint(2, 6))
            rows.append(
                (
                    order_id,
                    customer_id,
                    f"{colour} {category}",
                    colour,
                    category,
                    rng.randint(*f["amount_paise_range"]),
                    "INR",
                    placed.isoformat(),
                    delivered.isoformat(),
                    "delivered",
                )
            )

    rows.sort(key=lambda r: r[0])  # sorted => byte-identical file
    cur.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)", rows
    )
    cur.executemany(
        "INSERT INTO field_reliability VALUES (?,?,?)",
        sorted(
            ("orders", k, v)
            for k, v in spec["_field_reliability"].items()
            if not k.startswith("_")
        ),
    )
    conn.commit()
    conn.close()
    return len(rows)


# --------------------------------------------------------------------------
# policy_store.db
# --------------------------------------------------------------------------


def build_policy() -> int:
    spec = _load("clauses.json")
    conn = _fresh(DATA_DIR / "policy_store.db")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE clauses (
            clause_id      TEXT PRIMARY KEY,
            policy_id      TEXT NOT NULL,
            version        TEXT NOT NULL,
            title          TEXT NOT NULL,
            text           TEXT NOT NULL,
            window_days    INTEGER,
            effective_from TEXT NOT NULL,
            effective_to   TEXT,          -- NULL == currently in force
            superseded_by  TEXT
        )
        """
    )
    rows = sorted(
        (
            c["clause_id"],
            c["policy_id"],
            c["version"],
            c["title"],
            c["text"],
            c.get("window_days"),
            c["effective_from"],
            c.get("effective_to"),
            c.get("superseded_by"),
        )
        for c in spec["clauses"]
    )
    cur.executemany("INSERT INTO clauses VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return len(rows)


# --------------------------------------------------------------------------
# entitlements.db
# --------------------------------------------------------------------------


def build_entitlements() -> tuple[int, int]:
    spec = _load("entitlements.json")
    conn = _fresh(DATA_DIR / "entitlements.db")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE subjects (
            subject_id                TEXT PRIMARY KEY,
            display_name              TEXT NOT NULL,
            department                TEXT NOT NULL,
            entitled_classifications  TEXT NOT NULL,  -- json list
            entitled_customer_ids     TEXT NOT NULL   -- json list
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE documents (
            doc_id            TEXT PRIMARY KEY,
            title             TEXT NOT NULL,
            classification    TEXT NOT NULL,
            about_customer_id TEXT,
            body              TEXT NOT NULL
        )
        """
    )
    subs = sorted(
        (
            s["subject_id"],
            s["display_name"],
            s["department"],
            json.dumps(s["entitled_classifications"], sort_keys=True),
            json.dumps(s["entitled_customer_ids"], sort_keys=True),
        )
        for s in spec["subjects"]
    )
    docs = sorted(
        (
            d["doc_id"],
            d["title"],
            d["classification"],
            d.get("about_customer_id"),
            d["body"],
        )
        for d in spec["documents"]
    )
    cur.executemany("INSERT INTO subjects VALUES (?,?,?,?,?)", subs)
    cur.executemany("INSERT INTO documents VALUES (?,?,?,?,?)", docs)
    conn.commit()
    conn.close()
    return len(subs), len(docs)


# --------------------------------------------------------------------------
# the stale retrieval index — the bug that makes the agent fail honestly
# --------------------------------------------------------------------------


def build_stale_index() -> int:
    """A retrieval index over clause text that does NOT filter on effective_to.

    That single omission is the whole failure mode, and it is a real one:
    VersionRAG measured naive RAG at 58% on version-sensitive questions and
    0-10% on silent supersession. We are not inventing a strawman; we are
    reproducing a published one.
    """
    spec = _load("clauses.json")
    out = DATA_DIR / "stale_index"
    out.mkdir(exist_ok=True)
    chunks = [
        {
            "chunk_id": c["clause_id"],
            "policy_id": c["policy_id"],
            "version": c["version"],  # present, but the retriever ignores it
            "text": f"{c['title']}. {c['text']}",
        }
        for c in spec["clauses"]
    ]
    chunks.sort(key=lambda c: c["chunk_id"])
    (out / "chunks.json").write_text(
        json.dumps(chunks, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return len(chunks)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> None:
    n_orders = build_orders()
    n_clauses = build_policy()
    n_subj, n_docs = build_entitlements()
    n_chunks = build_stale_index()

    print("ControlPlane — data build")
    print(f"  seed        : {CP_SEED}")
    print(f"  demo clock  : {DEMO_TODAY.isoformat()}  (FROZEN)")
    print()
    print(f"  orders.db       {n_orders:>4} orders     sha256:{_sha(DATA_DIR / 'orders.db')}")
    print(f"  policy_store.db {n_clauses:>4} clauses    sha256:{_sha(DATA_DIR / 'policy_store.db')}")
    print(f"  entitlements.db {n_subj:>4} subjects, {n_docs} documents")
    print(f"  stale_index     {n_chunks:>4} chunks     (contains BOTH v3.8 and v4.2)")
    print()
    print("  Run this twice: the sha256 values must not change.")


if __name__ == "__main__":
    main()
