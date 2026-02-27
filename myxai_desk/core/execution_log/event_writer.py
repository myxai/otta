"""Write tool-call step events to SQLite for execution radar analytics.

Each call to ``record_step`` inserts one row into the ``exec_steps`` table.
The table is auto-created on first use.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from myxai_desk.core.execution_log.error_codes import classify_action, classify_error
from myxai_desk.core.storage.sqlite import ensure_table, execute

log = logging.getLogger("myxai")

_TABLE_READY = False


def _ensure_exec_steps_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    ensure_table(
        "exec_steps",
        """
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        args_json TEXT DEFAULT '{}',
        status TEXT DEFAULT 'ok',
        error_code TEXT DEFAULT '',
        action TEXT DEFAULT 'EXEC',
        result_preview TEXT DEFAULT '',
        duration_ms INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        local_date TEXT DEFAULT ''
        """,
    )
    # Backfill: if table exists but lacks local_date column, add it
    try:
        execute("SELECT local_date FROM exec_steps LIMIT 1", readonly=True)
    except Exception:
        try:
            from myxai_desk.core.storage.sqlite import connect
            with connect() as conn:
                conn.execute("ALTER TABLE exec_steps ADD COLUMN local_date TEXT DEFAULT ''")
        except Exception:
            pass
    _TABLE_READY = True


def record_step(
    *,
    session_id: str,
    tool_name: str,
    args_json: dict | str = "",
    status: str = "ok",
    error_code: str = "",
    action: str = "EXEC",
    result_preview: str = "",
    duration_ms: int = 0,
) -> str | None:
    """Insert a single step event and return the generated step id."""
    try:
        _ensure_exec_steps_table()
        step_id = uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        local_date = datetime.now().strftime("%Y-%m-%d")
        args_str = json.dumps(args_json, ensure_ascii=False, default=str) if isinstance(args_json, dict) else str(args_json)
        execute(
            """INSERT INTO exec_steps
               (id, session_id, tool_name, args_json, status, error_code,
                action, result_preview, duration_ms, created_at, local_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                step_id,
                session_id,
                tool_name,
                args_str[:2000],
                status,
                error_code,
                action,
                result_preview[:500],
                duration_ms,
                now,
                local_date,
            ),
        )
        return step_id
    except Exception:
        log.warning("[exec_log] record_step failed", exc_info=True)
        return None


def record_step_from_event(
    *,
    session_id: str,
    tool_name: str,
    args: dict | str,
    result: str,
    turn_event: dict,
    started_at: float | None = None,
) -> str | None:
    """Convenience wrapper that derives status/error_code from a _turn_event dict."""
    action = turn_event.get("action", "UNKNOWN")
    ok = turn_event.get("ok", False)

    if ok:
        status = "ok"
        error_code = ""
    elif action in ("DENY", "CAP_BLOCK", "GUARD_BLOCK", "SANDBOX_DENY"):
        status = "blocked"
        error_code = classify_action(action, turn_event.get("code", ""))
    elif action == "CONFIRM":
        status = "pending_confirm"
        error_code = ""
    else:
        status = "soft_fail"
        error_code = classify_error(message=str(result)[:300]) if result else "E_UNKNOWN"

    duration_ms = int((time.time() - started_at) * 1000) if started_at else 0

    return record_step(
        session_id=session_id,
        tool_name=tool_name,
        args_json=args,
        status=status,
        error_code=error_code,
        action=action,
        result_preview=str(result)[:500] if result else "",
        duration_ms=duration_ms,
    )
