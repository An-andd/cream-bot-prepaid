"""Tiny SQLite session store.

Render restarts workers freely, so conversation state cannot live in memory.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time

from . import config

_lock = threading.Lock()

IDLE = "idle"
AWAITING_BILLER = "awaiting_biller"
COLLECTING = "collecting"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock, _conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                   wa_id     TEXT PRIMARY KEY,
                   state     TEXT NOT NULL,
                   biller    TEXT DEFAULT '',
                   biller_id TEXT DEFAULT '',
                   orders    TEXT DEFAULT '[]',
                   updated   REAL
               )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS seen_messages (
                   msg_id TEXT PRIMARY KEY, ts REAL)"""
        )


def get_session(wa_id: str) -> dict:
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT state, biller, biller_id, orders FROM sessions WHERE wa_id=?",
            (wa_id,),
        ).fetchone()
    if not row:
        return {"state": IDLE, "biller": "", "biller_id": "", "orders": []}
    return {
        "state": row[0],
        "biller": row[1],
        "biller_id": row[2],
        "orders": json.loads(row[3] or "[]"),
    }


def save_session(wa_id: str, session: dict) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            """INSERT INTO sessions (wa_id, state, biller, biller_id, orders, updated)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(wa_id) DO UPDATE SET
                   state=excluded.state, biller=excluded.biller,
                   biller_id=excluded.biller_id, orders=excluded.orders,
                   updated=excluded.updated""",
            (
                wa_id,
                session.get("state", IDLE),
                session.get("biller", ""),
                session.get("biller_id", ""),
                json.dumps(session.get("orders", [])),
                time.time(),
            ),
        )


def reset_session(wa_id: str) -> None:
    save_session(wa_id, {"state": IDLE, "biller": "", "biller_id": "", "orders": []})


def already_seen(msg_id: str) -> bool:
    """WhatsApp retries webhooks; never process one message twice."""
    if not msg_id:
        return False
    with _lock, _conn() as conn:
        try:
            conn.execute("INSERT INTO seen_messages (msg_id, ts) VALUES (?,?)",
                         (msg_id, time.time()))
        except sqlite3.IntegrityError:
            return True
        conn.execute("DELETE FROM seen_messages WHERE ts < ?", (time.time() - 86400,))
    return False
