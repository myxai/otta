"""SQLite helpers for structured storage needs.

Provides a lightweight wrapper around sqlite3 for modules that need
relational queries (e.g. audit search, profile analytics, budget tracking).
The database file lives at ``~/.nanobot/storage/myxai.db``.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING

from myxai_desk.core.storage.paths import NANOBOT_HOME, ensure_dir

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

_DB_PATH = NANOBOT_HOME / "storage" / "myxai.db"
_lock = Lock()


def db_path() -> Path:
    ensure_dir(_DB_PATH.parent)
    return _DB_PATH


@contextmanager
def connect(readonly: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a sqlite3 connection.

    Uses WAL mode for concurrent readers and serialises writes via a lock.
    """
    ensure_dir(_DB_PATH.parent)
    uri = f"file:{_DB_PATH}"
    if readonly:
        uri += "?mode=ro"

    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if not readonly:
        _lock.acquire()
    try:
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        if not readonly:
            conn.rollback()
        raise
    finally:
        if not readonly:
            _lock.release()
        conn.close()


def execute(sql: str, params: tuple = (), *, readonly: bool = False) -> list[dict]:
    """Execute a SQL statement and return rows as dicts."""
    with connect(readonly=readonly) as conn:
        cursor = conn.execute(sql, params)
        if cursor.description:
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]
        return []


def execute_many(sql: str, params_list: list[tuple]) -> int:
    """Execute a SQL statement with multiple parameter sets."""
    with connect() as conn:
        cursor = conn.executemany(sql, params_list)
        return cursor.rowcount


def ensure_table(name: str, schema: str) -> None:
    """Create a table if it doesn't exist."""
    with connect() as conn:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({schema})")


# ── Pre-defined schemas ───────────────────────────────────────────


def init_default_tables() -> None:
    """Create the standard tables used by myxai_desk modules."""
    ensure_table(
        "audit_entries",
        """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        app_id TEXT DEFAULT '',
        source TEXT DEFAULT 'official',
        mode TEXT DEFAULT '',
        capability TEXT NOT NULL,
        args_digest TEXT DEFAULT '',
        result_digest TEXT DEFAULT '',
        action TEXT DEFAULT 'ALLOW',
        risk INTEGER DEFAULT 0,
        reason_code TEXT DEFAULT '',
        undo_action_id TEXT DEFAULT '',
        entry_hash TEXT DEFAULT ''
    """,
    )

    ensure_table(
        "budget_usage",
        """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id TEXT NOT NULL,
        date TEXT NOT NULL,
        tokens_used INTEGER DEFAULT 0,
        search_calls INTEGER DEFAULT 0,
        UNIQUE(app_id, date)
    """,
    )

    ensure_table(
        "profile_events",
        """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        ts REAL NOT NULL,
        data_json TEXT DEFAULT '{}'
    """,
    )

    ensure_table(
        "task_runs",
        """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        scheduled_for TEXT NOT NULL,
        scheduled_local_date TEXT NOT NULL,
        trigger TEXT DEFAULT 'tick',
        started_at TEXT,
        finished_at TEXT,
        status TEXT DEFAULT 'pending',
        error TEXT DEFAULT '',
        artifacts TEXT DEFAULT '{}',
        UNIQUE(idempotency_key)
    """,
    )
