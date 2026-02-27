"""Data access layer for Intent Engine tables (ie_runs, ie_cases)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from myxai_desk.core.storage.sqlite import connect, ensure_table, execute

log = logging.getLogger("myxai")

_TABLES_READY = False


# ── Table initialisation ──────────────────────────────────────────

def init_ie_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return

    ensure_table(
        "ie_runs",
        """
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        user_text TEXT DEFAULT '',
        context_json TEXT DEFAULT '{}',
        route_label TEXT DEFAULT '',
        route_conf REAL DEFAULT 0.0,
        decision_mode TEXT DEFAULT 'rule',
        tool_group TEXT DEFAULT '[]',
        tools_before INTEGER DEFAULT 0,
        tools_after INTEGER DEFAULT 0,
        outcome TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        local_date TEXT DEFAULT ''
        """,
    )

    ensure_table(
        "ie_cases",
        """
        id TEXT PRIMARY KEY,
        task_text TEXT NOT NULL,
        context_fp TEXT DEFAULT '',
        route_label TEXT DEFAULT '',
        plan_json TEXT DEFAULT '[]',
        pitfalls TEXT DEFAULT '',
        fail_reason TEXT DEFAULT '',
        outcome TEXT DEFAULT 'success',
        embedding_id TEXT DEFAULT '',
        sim_hash TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        usage_count INTEGER DEFAULT 0
        """,
    )
    _TABLES_READY = True


# ── ie_runs operations ────────────────────────────────────────────

def insert_run(
    *,
    session_id: str,
    user_text: str,
    context: dict | None = None,
    route_label: str = "",
    route_conf: float = 0.0,
    decision_mode: str = "rule",
    tool_group: list[str] | None = None,
    tools_before: int = 0,
    tools_after: int = 0,
) -> str | None:
    """Insert one ie_runs row, return the generated id."""
    try:
        init_ie_tables()
        run_id = uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        local_date = datetime.now().strftime("%Y-%m-%d")
        execute(
            """INSERT INTO ie_runs
               (id, session_id, user_text, context_json, route_label,
                route_conf, decision_mode, tool_group,
                tools_before, tools_after, outcome, created_at, local_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
            (
                run_id,
                session_id,
                (user_text or "")[:2000],
                json.dumps(context or {}, ensure_ascii=False, default=str),
                route_label,
                route_conf,
                decision_mode,
                json.dumps(tool_group or [], ensure_ascii=False),
                tools_before,
                tools_after,
                now,
                local_date,
            ),
        )
        return run_id
    except Exception:
        log.warning("[ie_dao] insert_run failed", exc_info=True)
        return None


def update_outcome(run_id: str, outcome: str) -> None:
    """Set the outcome (success / fail / unknown) for a run."""
    try:
        init_ie_tables()
        execute("UPDATE ie_runs SET outcome = ? WHERE id = ?", (outcome, run_id))
    except Exception:
        log.warning("[ie_dao] update_outcome failed", exc_info=True)


def get_runs(
    *,
    local_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    init_ie_tables()
    if local_date:
        return execute(
            "SELECT * FROM ie_runs WHERE local_date = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (local_date, limit, offset),
            readonly=True,
        )
    return execute(
        "SELECT * FROM ie_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
        readonly=True,
    )


def get_runs_stats(days: int = 7) -> dict:
    """Aggregate stats for the last N days."""
    init_ie_tables()
    rows = execute(
        """SELECT
             local_date,
             COUNT(*) AS total,
             SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) AS success,
             SUM(CASE WHEN outcome='fail' THEN 1 ELSE 0 END) AS fail,
             AVG(route_conf) AS avg_conf,
             AVG(tools_before) AS avg_before,
             AVG(tools_after) AS avg_after,
             SUM(CASE WHEN decision_mode='case_reuse' THEN 1 ELSE 0 END) AS reuse_count
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY local_date
           ORDER BY local_date""",
        (f"-{days} days",),
        readonly=True,
    )
    return {"days": days, "daily": rows}


# ── ie_cases operations ───────────────────────────────────────────

def insert_case(
    *,
    task_text: str,
    context_fp: str = "",
    route_label: str = "",
    plan_json: list[dict] | None = None,
    pitfalls: str = "",
    fail_reason: str = "",
    outcome: str = "success",
    embedding_id: str = "",
    sim_hash: str = "",
) -> str | None:
    try:
        init_ie_tables()
        case_id = uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        execute(
            """INSERT INTO ie_cases
               (id, task_text, context_fp, route_label, plan_json,
                pitfalls, fail_reason, outcome, embedding_id, sim_hash,
                created_at, usage_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                case_id,
                (task_text or "")[:2000],
                context_fp,
                route_label,
                json.dumps(plan_json or [], ensure_ascii=False, default=str),
                pitfalls[:2000],
                fail_reason[:2000],
                outcome,
                embedding_id,
                sim_hash,
                now,
            ),
        )
        return case_id
    except Exception:
        log.warning("[ie_dao] insert_case failed", exc_info=True)
        return None


def get_cases(
    *,
    outcome: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    init_ie_tables()
    if outcome:
        return execute(
            "SELECT * FROM ie_cases WHERE outcome = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (outcome, limit, offset),
            readonly=True,
        )
    return execute(
        "SELECT * FROM ie_cases ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
        readonly=True,
    )


def increment_case_usage(case_id: str) -> None:
    try:
        execute("UPDATE ie_cases SET usage_count = usage_count + 1 WHERE id = ?", (case_id,))
    except Exception:
        pass
