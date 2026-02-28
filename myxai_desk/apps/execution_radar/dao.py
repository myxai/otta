"""Data-access layer for execution radar tables.

Tables: ``er_tasks``, ``er_steps``, ``er_daily_metrics``, ``golden_candidates``.
All live in the shared ``myxai.db`` SQLite database.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from myxai_desk.core.storage.sqlite import ensure_table, execute, execute_many

log = logging.getLogger("myxai")

_TABLES_READY = False


def _migrate_legacy_tables() -> None:
    """Rename old hc_* tables to er_* if they exist (one-time migration)."""
    renames = [
        ("hc_tasks", "er_tasks"),
        ("hc_steps", "er_steps"),
        ("hc_daily_metrics", "er_daily_metrics"),
    ]
    for old, new in renames:
        try:
            rows = execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (old,),
                readonly=True,
            )
            if rows:
                new_exists = execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (new,),
                    readonly=True,
                )
                if not new_exists:
                    from myxai_desk.core.storage.sqlite import connect
                    with connect() as conn:
                        conn.execute(f"ALTER TABLE {old} RENAME TO {new}")
                    log.info("[execution_radar] migrated table %s → %s", old, new)
        except Exception:
            log.debug("[execution_radar] table migration %s → %s skipped", old, new, exc_info=True)


def init_radar_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return

    _migrate_legacy_tables()

    ensure_table(
        "er_tasks",
        """
        task_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        user_text TEXT DEFAULT '',
        total_steps INTEGER DEFAULT 0,
        success INTEGER DEFAULT 0,
        hit_rate REAL DEFAULT 0,
        attempts INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        final_error_code TEXT DEFAULT ''
        """,
    )

    ensure_table(
        "er_steps",
        """
        step_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        step_index INTEGER DEFAULT 0,
        tool_name TEXT NOT NULL,
        args_json TEXT DEFAULT '{}',
        status TEXT DEFAULT 'ok',
        error_code TEXT DEFAULT '',
        duration_ms INTEGER DEFAULT 0,
        result_json TEXT DEFAULT '{}',
        token_used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
        """,
    )

    ensure_table(
        "er_daily_metrics",
        """
        date TEXT PRIMARY KEY,
        total_tasks INTEGER DEFAULT 0,
        instrumented_tasks INTEGER DEFAULT 0,
        success_tasks INTEGER DEFAULT 0,
        single_tasks INTEGER DEFAULT 0,
        single_hits INTEGER DEFAULT 0,
        single_hit_rate REAL DEFAULT 0,
        single_avg_attempts REAL DEFAULT 0,
        multi_tasks INTEGER DEFAULT 0,
        multi_hits INTEGER DEFAULT 0,
        multi_hit_rate REAL DEFAULT 0,
        multi_avg_attempts REAL DEFAULT 0,
        multi_avg_effective REAL DEFAULT 0,
        avg_attempts REAL DEFAULT 0,
        avg_tokens INTEGER DEFAULT 0,
        top_error_codes TEXT DEFAULT '[]',
        top_tools TEXT DEFAULT '[]',
        report_text TEXT DEFAULT ''
        """,
    )

    ensure_table(
        "golden_candidates",
        """
        candidate_id TEXT PRIMARY KEY,
        case_key TEXT NOT NULL,
        source_run_id TEXT NOT NULL,
        candidate_plan_json TEXT DEFAULT '[]',
        quality_score REAL DEFAULT 0,
        removed_steps INTEGER DEFAULT 0,
        original_steps INTEGER DEFAULT 0,
        user_text TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        status TEXT DEFAULT 'new'
        """,
    )

    _gc_backfill = [
        ("original_steps", "INTEGER DEFAULT 0"),
        ("user_text", "TEXT DEFAULT ''"),
    ]
    for col, typedef in _gc_backfill:
        try:
            execute(f"SELECT {col} FROM golden_candidates LIMIT 1", readonly=True)
        except Exception:
            try:
                from myxai_desk.core.storage.sqlite import connect
                with connect() as conn:
                    conn.execute(f"ALTER TABLE golden_candidates ADD COLUMN {col} {typedef}")
            except Exception:
                pass

    _backfill_columns = [
        ("instrumented_tasks", "INTEGER DEFAULT 0"),
        ("single_hit_rate", "REAL DEFAULT 0"),
        ("single_avg_attempts", "REAL DEFAULT 0"),
        ("multi_hit_rate", "REAL DEFAULT 0"),
        ("multi_avg_attempts", "REAL DEFAULT 0"),
        ("multi_avg_effective", "REAL DEFAULT 0"),
        ("avg_attempts", "REAL DEFAULT 0"),
        ("avg_tokens", "INTEGER DEFAULT 0"),
        ("avg_removed_steps", "REAL DEFAULT 0"),
        ("candidates_generated", "INTEGER DEFAULT 0"),
    ]
    for col, typedef in _backfill_columns:
        try:
            execute(f"SELECT {col} FROM er_daily_metrics LIMIT 1", readonly=True)
        except Exception:
            try:
                from myxai_desk.core.storage.sqlite import connect
                with connect() as conn:
                    conn.execute(f"ALTER TABLE er_daily_metrics ADD COLUMN {col} {typedef}")
            except Exception:
                pass

    _TABLES_READY = True


# ── er_tasks CRUD ──────────────────────────────────────────────────


def delete_date_data(date_str: str) -> None:
    """Remove all tasks, steps, and candidates for a given date before re-import."""
    init_radar_tables()
    task_ids = execute(
        "SELECT task_id FROM er_tasks WHERE created_at LIKE ?",
        (f"{date_str}%",),
        readonly=True,
    )
    if task_ids:
        ids = [r["task_id"] for r in task_ids]
        placeholders = ",".join("?" * len(ids))
        execute(f"DELETE FROM er_steps WHERE task_id IN ({placeholders})", ids)
    execute("DELETE FROM er_tasks WHERE created_at LIKE ?", (f"{date_str}%",))
    execute("DELETE FROM golden_candidates WHERE created_at LIKE ?", (f"{date_str}%",))


def upsert_task(task: dict) -> None:
    init_radar_tables()
    execute(
        """INSERT OR REPLACE INTO er_tasks
           (task_id, session_id, created_at, user_text, total_steps,
            success, hit_rate, attempts, total_tokens, final_error_code)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task["task_id"],
            task["session_id"],
            task["created_at"],
            task.get("user_text", "")[:2000],
            task.get("total_steps", 0),
            int(task.get("success", False)),
            task.get("hit_rate", 0.0),
            task.get("attempts", 0),
            task.get("total_tokens", 0),
            task.get("final_error_code", ""),
        ),
    )


def upsert_tasks(tasks: list[dict]) -> None:
    init_radar_tables()
    execute_many(
        """INSERT OR REPLACE INTO er_tasks
           (task_id, session_id, created_at, user_text, total_steps,
            success, hit_rate, attempts, total_tokens, final_error_code)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                t["task_id"],
                t["session_id"],
                t["created_at"],
                t.get("user_text", "")[:2000],
                t.get("total_steps", 0),
                int(t.get("success", False)),
                t.get("hit_rate", 0.0),
                t.get("attempts", 0),
                t.get("total_tokens", 0),
                t.get("final_error_code", ""),
            )
            for t in tasks
        ],
    )


def upsert_steps(steps: list[dict]) -> None:
    init_radar_tables()
    execute_many(
        """INSERT OR REPLACE INTO er_steps
           (step_id, task_id, step_index, tool_name, args_json,
            status, error_code, duration_ms, result_json, token_used, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                s["step_id"],
                s["task_id"],
                s.get("step_index", 0),
                s["tool_name"],
                s.get("args_json", "{}"),
                s.get("status", "ok"),
                s.get("error_code", ""),
                s.get("duration_ms", 0),
                s.get("result_json", "{}"),
                s.get("token_used", 0),
                s["created_at"],
            )
            for s in steps
        ],
    )


def get_tasks_for_date(date_str: str) -> list[dict]:
    init_radar_tables()
    return execute(
        "SELECT * FROM er_tasks WHERE created_at LIKE ?",
        (f"{date_str}%",),
        readonly=True,
    )


def get_tasks_with_steps(date_str: str) -> list[dict]:
    """Return tasks for a date, each enriched with its step list."""
    init_radar_tables()
    tasks = execute(
        "SELECT * FROM er_tasks WHERE created_at LIKE ? ORDER BY created_at",
        (f"{date_str}%",),
        readonly=True,
    )
    if not tasks:
        return []

    task_ids = [t["task_id"] for t in tasks]
    placeholders = ",".join("?" * len(task_ids))
    all_steps = execute(
        f"SELECT * FROM er_steps WHERE task_id IN ({placeholders}) ORDER BY step_index",
        task_ids,
        readonly=True,
    )

    steps_by_task: dict[str, list[dict]] = {}
    for s in all_steps:
        steps_by_task.setdefault(s["task_id"], []).append(s)

    for t in tasks:
        tid = t["task_id"]
        t_steps = steps_by_task.get(tid, [])
        is_success = bool(t.get("success"))

        if is_success and t_steps:
            last_idx_by_tool: dict[str, int] = {}
            for i, s in enumerate(t_steps):
                tool = s.get("tool_name", "")
                if tool:
                    last_idx_by_tool[tool] = i
            effective_indices = set(last_idx_by_tool.values())
            for i, s in enumerate(t_steps):
                s["effective"] = i in effective_indices
            t["effective_count"] = len(effective_indices)
        else:
            for s in t_steps:
                s["effective"] = False
            t["effective_count"] = 0

        t["steps"] = t_steps

    return tasks


# ── er_daily_metrics CRUD ──────────────────────────────────────────


def save_daily_metrics(m: dict) -> None:
    init_radar_tables()
    execute(
        """INSERT OR REPLACE INTO er_daily_metrics
           (date, total_tasks, instrumented_tasks, success_tasks, single_tasks,
            single_hits, single_hit_rate, single_avg_attempts,
            multi_tasks, multi_hits, multi_hit_rate, multi_avg_attempts,
            multi_avg_effective, avg_attempts, avg_tokens,
            top_error_codes, top_tools, report_text,
            avg_removed_steps, candidates_generated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            m["date"],
            m.get("total_tasks", 0),
            m.get("instrumented_tasks", 0),
            m.get("success_tasks", 0),
            m.get("single_tasks", 0),
            m.get("single_hits", 0),
            m.get("single_hit_rate", 0.0),
            m.get("single_avg_attempts", 0.0),
            m.get("multi_tasks", 0),
            m.get("multi_hits", 0),
            m.get("multi_hit_rate", 0.0),
            m.get("multi_avg_attempts", 0.0),
            m.get("multi_avg_effective", 0.0),
            m.get("avg_attempts", 0.0),
            m.get("avg_tokens", 0),
            json.dumps(m.get("top_error_codes", []), ensure_ascii=False),
            json.dumps(m.get("top_tools", []), ensure_ascii=False),
            m.get("report_text", ""),
            m.get("avg_removed_steps", 0.0),
            m.get("candidates_generated", 0),
        ),
    )


def get_daily_metrics(date_str: str) -> dict | None:
    init_radar_tables()
    rows = execute(
        "SELECT * FROM er_daily_metrics WHERE date = ?",
        (date_str,),
        readonly=True,
    )
    if not rows:
        return None
    row = rows[0]
    row["top_error_codes"] = _safe_json(row.get("top_error_codes", "[]"))
    row["top_tools"] = _safe_json(row.get("top_tools", "[]"))
    return row


def get_metrics_range(start_date: str, end_date: str) -> list[dict]:
    init_radar_tables()
    rows = execute(
        "SELECT * FROM er_daily_metrics WHERE date >= ? AND date <= ? ORDER BY date",
        (start_date, end_date),
        readonly=True,
    )
    for r in rows:
        r["top_error_codes"] = _safe_json(r.get("top_error_codes", "[]"))
        r["top_tools"] = _safe_json(r.get("top_tools", "[]"))
    return rows


def get_exec_steps_for_date(date_str: str) -> list[dict]:
    """Fetch raw exec_steps logged on a given local date.

    Uses ``local_date`` column (exact match) with fallback to ``created_at``
    prefix match for rows written before the column was added.
    """
    try:
        rows = execute(
            """SELECT * FROM exec_steps
               WHERE local_date = ? OR (local_date = '' AND created_at LIKE ?)
               ORDER BY created_at""",
            (date_str, f"{date_str}%"),
            readonly=True,
        )
        return rows
    except Exception:
        try:
            return execute(
                "SELECT * FROM exec_steps WHERE created_at LIKE ? ORDER BY created_at",
                (f"{date_str}%",),
                readonly=True,
            )
        except Exception:
            return []


def get_top_tools(date_str: str, limit: int = 10) -> list[dict]:
    """Aggregate top tools by call count for a date from er_steps."""
    init_radar_tables()
    return execute(
        """SELECT tool_name, COUNT(*) as cnt,
                  SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) as fail_cnt
           FROM er_steps
           WHERE created_at LIKE ?
           GROUP BY tool_name ORDER BY cnt DESC LIMIT ?""",
        (f"{date_str}%", limit),
        readonly=True,
    )


def _safe_json(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    return val


# ── golden_candidates CRUD ─────────────────────────────────────────


def upsert_candidates(candidates: list[dict]) -> None:
    """Batch-insert candidate golden paths."""
    if not candidates:
        return
    init_radar_tables()
    execute_many(
        """INSERT OR REPLACE INTO golden_candidates
           (candidate_id, case_key, source_run_id, candidate_plan_json,
            quality_score, removed_steps, original_steps, user_text,
            created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                c["candidate_id"],
                c["case_key"],
                c["source_run_id"],
                c.get("candidate_plan_json", "[]"),
                c.get("quality_score", 0.0),
                c.get("removed_steps", 0),
                c.get("original_steps", 0),
                c.get("user_text", "")[:200],
                c["created_at"],
                c.get("status", "new"),
            )
            for c in candidates
        ],
    )


def get_candidates_for_date(date_str: str) -> list[dict]:
    """Return all candidates created on *date_str*."""
    init_radar_tables()
    rows = execute(
        "SELECT * FROM golden_candidates WHERE created_at LIKE ? ORDER BY quality_score DESC",
        (f"{date_str}%",),
        readonly=True,
    )
    for r in rows:
        r["candidate_plan_json"] = _safe_json(r.get("candidate_plan_json", "[]"))
    return rows


def get_top_candidates(limit: int = 10) -> list[dict]:
    """Return top candidates globally by quality_score (status = 'new' or 'used')."""
    init_radar_tables()
    rows = execute(
        """SELECT * FROM golden_candidates
           WHERE status IN ('new', 'used', 'promoted')
           ORDER BY quality_score DESC LIMIT ?""",
        (limit,),
        readonly=True,
    )
    for r in rows:
        r["candidate_plan_json"] = _safe_json(r.get("candidate_plan_json", "[]"))
    return rows


def get_candidate_by_case_key(case_key: str) -> dict | None:
    """Return the best candidate matching *case_key*."""
    init_radar_tables()
    rows = execute(
        """SELECT * FROM golden_candidates
           WHERE case_key = ? AND status IN ('new', 'used', 'promoted')
           ORDER BY quality_score DESC LIMIT 1""",
        (case_key,),
        readonly=True,
    )
    if not rows:
        return None
    r = rows[0]
    r["candidate_plan_json"] = _safe_json(r.get("candidate_plan_json", "[]"))
    return r


def update_candidate_status(candidate_id: str, status: str) -> None:
    init_radar_tables()
    execute(
        "UPDATE golden_candidates SET status = ? WHERE candidate_id = ?",
        (status, candidate_id),
    )
