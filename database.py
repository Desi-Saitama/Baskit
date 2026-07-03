"""
database.py — SQLite persistence layer for the Invoice Tracker.
All tables are created here; no ORM, plain sqlite3 for zero-dependency portability.
"""

import sqlite3
import hashlib
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "tracker.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # ── Auth ──────────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auth (
            id       INTEGER PRIMARY KEY,
            username TEXT    NOT NULL UNIQUE,
            pw_hash  TEXT    NOT NULL
        )
    """)

    # ── Orders ────────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            order_date    TEXT    NOT NULL,          -- ISO date  YYYY-MM-DD
            app_name      TEXT    NOT NULL,          -- zepto / blinkit / …
            app_category  TEXT    NOT NULL,          -- groceries / food / both
            order_id      TEXT,
            total_amount  REAL    NOT NULL DEFAULT 0,
            delivery_fee  REAL    NOT NULL DEFAULT 0,
            discount      REAL    NOT NULL DEFAULT 0,
            notes         TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Items ────────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            brand       TEXT,
            category    TEXT,
            quantity    TEXT,
            unit_price  REAL    NOT NULL DEFAULT 0,
            total_price REAL    NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check(password: str, pw_hash: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), pw_hash.encode())


def create_user(username: str, password: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO auth (username, pw_hash) VALUES (?, ?)",
        (username, _hash(password))
    )
    conn.commit()
    conn.close()


def verify_user(username: str, password: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT pw_hash FROM auth WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    if row is None:
        return False
    return _check(password, row["pw_hash"])


def user_exists() -> bool:
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM auth").fetchone()[0]
    conn.close()
    return count > 0


# ── Duplicate detection ───────────────────────────────────────────────────────

def _normalise_name(name: str) -> str:
    """Lowercase, strip whitespace for fuzzy item-name comparison."""
    return name.lower().strip()


def is_duplicate_order(
    order_id: str,
    app_name: str,
    incoming_items: list[dict],
) -> bool:
    """
    Return True only when ALL three conditions hold:
      1. A non-empty order_id is given.
      2. An existing order in the DB has the same order_id AND the same app.
      3. The existing order's item names fully overlap with the incoming item
         names (i.e. the normalised name sets are identical or the incoming
         set is a subset of what's already stored).

    If the incoming items contain at least one name that is NOT in the stored
    order → not a duplicate → return False (allow insertion).
    """
    if not order_id:
        return False

    conn = get_conn()

    # Find all existing orders with the same order_id + app_name
    existing_orders = conn.execute(
        """
        SELECT id FROM orders
        WHERE order_id = ? AND app_name = ?
        """,
        (order_id, app_name),
    ).fetchall()

    if not existing_orders:
        conn.close()
        return False

    # Build normalised set of incoming item names
    incoming_names: set[str] = {
        _normalise_name(it.get("name", ""))
        for it in incoming_items
        if it.get("name", "").strip()
    }

    for row in existing_orders:
        stored_items = conn.execute(
            "SELECT name FROM items WHERE order_id = ?", (row["id"],)
        ).fetchall()
        stored_names: set[str] = {
            _normalise_name(r["name"]) for r in stored_items if r["name"]
        }

        # If *every* incoming item is already in this stored order → duplicate
        if incoming_names and incoming_names.issubset(stored_names):
            conn.close()
            return True

    conn.close()
    return False


# ── Order / Item CRUD ─────────────────────────────────────────────────────────

def insert_order(
    order_date: str,
    app_name: str,
    app_category: str,
    order_id: str,
    total_amount: float,
    delivery_fee: float,
    discount: float,
    notes: str,
    items: list[dict],
    skip_duplicate_check: bool = False,
) -> tuple[int, bool]:
    """
    Insert an order and its items.

    Returns
    -------
    (db_id, was_duplicate)
        db_id          — the new row's primary key, or -1 if rejected.
        was_duplicate  — True when the order was rejected as a full duplicate.
    """
    if not skip_duplicate_check and is_duplicate_order(order_id, app_name, items):
        return -1, True

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders
            (order_date, app_name, app_category, order_id, total_amount,
             delivery_fee, discount, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_date, app_name, app_category, order_id,
          total_amount, delivery_fee, discount, notes))
    oid = cur.lastrowid

    for it in items:
        cur.execute("""
            INSERT INTO items
                (order_id, name, brand, category, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            oid,
            it.get("name", ""),
            it.get("brand", ""),
            it.get("category", ""),
            it.get("quantity", ""),
            float(it.get("unit_price", 0) or 0),
            float(it.get("total_price", 0) or 0),
        ))

    conn.commit()
    conn.close()
    return oid, False


def get_bulk_imported_stems() -> set[str]:
    """
    Return the set of file stems already saved via bulk import.

    Bulk-imported orders have notes like:  '[bulk import] invoice_xyz_1.pdf'
    We extract the filename and strip the extension to get the stem, which is
    what ProcessedFileTracker uses as its key.
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT notes FROM orders WHERE notes LIKE '[bulk import] %'"
    ).fetchall()
    conn.close()

    stems: set[str] = set()
    for row in rows:
        note: str = row["notes"] or ""
        # note format: "[bulk import] filename.pdf"
        fname = note.removeprefix("[bulk import] ").strip()
        if fname:
            stems.add(Path(fname).stem)
    return stems


def get_orders_df():

    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT o.id, o.order_date, o.app_name, o.app_category,
               o.order_id, o.total_amount, o.delivery_fee, o.discount, o.notes,
               o.created_at
        FROM orders o
        ORDER BY o.order_date DESC
    """, conn)
    conn.close()
    return df


def get_items_df():
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT i.*, o.order_date, o.app_name, o.app_category
        FROM items i
        JOIN orders o ON i.order_id = o.id
        ORDER BY o.order_date DESC
    """, conn)
    conn.close()
    return df


def get_order_items(order_db_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM items WHERE order_id = ?", (order_db_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_order(order_db_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_db_id,))
    conn.commit()
    conn.close()


def update_order_and_items(order_db_id: int, fields: dict, items: list[dict]):
    conn = get_conn()
    conn.execute("""
        UPDATE orders SET
            order_date   = :order_date,
            app_name     = :app_name,
            app_category = :app_category,
            order_id     = :order_id,
            total_amount = :total_amount,
            delivery_fee = :delivery_fee,
            discount     = :discount,
            notes        = :notes
        WHERE id = :id
    """, {**fields, "id": order_db_id})

    conn.execute("DELETE FROM items WHERE order_id = ?", (order_db_id,))
    for it in items:
        conn.execute("""
            INSERT INTO items
                (order_id, name, brand, category, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_db_id,
            it.get("name", ""),
            it.get("brand", ""),
            it.get("category", ""),
            it.get("quantity", ""),
            float(it.get("unit_price", 0) or 0),
            float(it.get("total_price", 0) or 0),
        ))
    conn.commit()
    conn.close()
