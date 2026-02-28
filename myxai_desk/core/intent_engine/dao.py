"""Data access layer for Intent Engine tables (ie_runs, ie_cases)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
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
    _backfill_ie_runs_columns()
    _backfill_golden_hit_from_plan_source()
    _TABLES_READY = True


def _backfill_ie_runs_columns() -> None:
    """Add PR-2+ columns to ie_runs if missing."""
    extras = [
        ("case_key", "TEXT"),
        ("candidate_id", "TEXT"),
        ("removed_steps", "INTEGER"),
        ("plan_source", "TEXT"),
        ("attempts_count", "INTEGER"),
        ("llm_attempts", "INTEGER"),
        ("golden_version", "INTEGER"),
        ("golden_hit", "INTEGER"),
        ("latency_ms", "REAL"),
        ("effective_steps", "INTEGER"),
        ("total_tokens", "INTEGER"),
    ]
    for col, typedef in extras:
        try:
            execute(f"SELECT {col} FROM ie_runs LIMIT 1", readonly=True)
        except Exception:
            try:
                with connect() as conn:
                    conn.execute(f"ALTER TABLE ie_runs ADD COLUMN {col} {typedef}")
            except Exception:
                pass


def _backfill_golden_hit_from_plan_source() -> None:
    """One-time backfill: derive golden_hit from plan_source for legacy rows."""
    try:
        execute(
            """UPDATE ie_runs
               SET golden_hit = 1
               WHERE golden_hit IS NULL
                 AND plan_source IN (
                    'golden_v2_instance','golden_v2_template',
                    'golden_replay','golden_candidate')""",
        )
        execute(
            """UPDATE ie_runs
               SET golden_hit = 0
               WHERE golden_hit IS NULL
                 AND plan_source IS NOT NULL
                 AND plan_source NOT IN (
                    'golden_v2_instance','golden_v2_template',
                    'golden_replay','golden_candidate')""",
        )
    except Exception:
        pass


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


_UPDATABLE_IE_RUN_FIELDS = frozenset({
    "case_key", "candidate_id", "removed_steps", "plan_source",
    "attempts_count", "llm_attempts", "golden_version", "outcome",
    "golden_hit", "latency_ms", "effective_steps", "total_tokens",
})


def update_ie_run(run_id: str, **fields: Any) -> None:
    """Flexible update for ie_runs — only touches columns in *fields*."""
    if not run_id or not fields:
        return
    safe = {k: v for k, v in fields.items() if k in _UPDATABLE_IE_RUN_FIELDS}
    if not safe:
        return
    try:
        init_ie_tables()
        set_clause = ", ".join(f"{k} = ?" for k in safe)
        values = list(safe.values()) + [run_id]
        execute(f"UPDATE ie_runs SET {set_clause} WHERE id = ?", tuple(values))
    except Exception:
        log.warning("[ie_dao] update_ie_run failed: %s", list(safe.keys()), exc_info=True)


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


# ── Visualization metrics ──────────────────────────────────────────


def get_ie_metrics(days: int = 7) -> dict:
    """Aggregate health metrics for the Intent Engine dashboard.

    ``golden_hit`` is the authoritative source (written by execution layer).
    ``plan_source`` provides backward-compat for rows written before the column
    existed.  Rows where neither is populated are treated as "unknown".
    """
    init_ie_tables()
    rows = execute(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) AS success,
             SUM(CASE WHEN outcome='fail' THEN 1 ELSE 0 END) AS fail,
             AVG(CASE WHEN tools_before > 0
                 THEN (tools_before - tools_after) * 1.0 / tools_before
                 ELSE 0 END) AS avg_tool_reduction,
             SUM(CASE WHEN golden_hit = 1
                 OR plan_source IN (
                    'golden_v2_instance','golden_v2_template',
                    'golden_replay','golden_candidate')
                 THEN 1 ELSE 0 END) AS golden_hits,
             AVG(COALESCE(llm_attempts, 1)) AS avg_llm_calls,
             AVG(CASE WHEN latency_ms > 0 THEN latency_ms END) AS avg_latency_ms,
             SUM(CASE WHEN decision_mode='case_reuse' THEN 1 ELSE 0 END) AS reuse_count
           FROM ie_runs
           WHERE local_date >= date('now', ?)""",
        (f"-{days} days",),
        readonly=True,
    )
    r = rows[0] if rows else {}
    total = r.get("total", 0) or 0
    golden_total = r.get("golden_hits", 0) or 0
    success = r.get("success", 0) or 0

    golden_hit_rate = golden_total / total if total else 0
    success_rate = success / total if total else 0
    avg_reduction = r.get("avg_tool_reduction", 0) or 0
    avg_llm = r.get("avg_llm_calls", 1) or 1
    llm_call_ratio = min(avg_llm, 5) / 5

    score = round(
        (0.4 * golden_hit_rate
         + 0.2 * avg_reduction
         + 0.2 * (1 - llm_call_ratio)
         + 0.2 * success_rate) * 100,
        1,
    )

    return {
        "total_runs": total,
        "success_count": success,
        "fail_count": r.get("fail", 0) or 0,
        "success_rate": round(success_rate * 100, 1),
        "avg_tool_reduction": round(avg_reduction * 100, 1),
        "golden_hit_rate": round(golden_hit_rate * 100, 1),
        "golden_hits": golden_total,
        "avg_llm_calls": round(avg_llm, 2),
        "avg_latency_ms": round(r.get("avg_latency_ms", 0) or 0, 1),
        "reuse_count": r.get("reuse_count", 0) or 0,
        "routing_health_score": score,
        "days": days,
    }


def get_ie_trends(days: int = 7) -> dict:
    """Daily trend data for charts."""
    init_ie_tables()
    rows = execute(
        """SELECT
             local_date,
             COUNT(*) AS total,
             SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) AS success,
             AVG(CASE WHEN tools_before > 0
                 THEN (tools_before - tools_after) * 1.0 / tools_before
                 ELSE 0 END) AS tool_reduction,
             SUM(CASE WHEN golden_hit = 1
                 OR plan_source IN (
                    'golden_v2_instance','golden_v2_template',
                    'golden_replay','golden_candidate')
                 THEN 1 ELSE 0 END) AS golden_hits,
             AVG(COALESCE(llm_attempts, 1)) AS avg_llm_calls,
             AVG(CASE WHEN latency_ms > 0 THEN latency_ms END) AS avg_latency_ms
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY local_date
           ORDER BY local_date""",
        (f"-{days} days",),
        readonly=True,
    )
    dates = []
    tool_reduction_rates: list[float] = []
    golden_hit_rates: list[float] = []
    llm_calls: list[float] = []
    success_rates: list[float] = []
    latencies: list[float] = []

    for r in rows:
        dates.append(r["local_date"])
        total = r["total"] or 1
        tool_reduction_rates.append(round((r.get("tool_reduction", 0) or 0) * 100, 1))
        golden_hit_rates.append(round((r.get("golden_hits", 0) or 0) / total * 100, 1))
        llm_calls.append(round(r.get("avg_llm_calls", 1) or 1, 2))
        success_rates.append(round((r.get("success", 0) or 0) / total * 100, 1))
        latencies.append(round(r.get("avg_latency_ms", 0) or 0, 1))

    return {
        "days": days,
        "dates": dates,
        "tool_reduction_rates": tool_reduction_rates,
        "golden_hit_rates": golden_hit_rates,
        "llm_calls": llm_calls,
        "success_rates": success_rates,
        "latencies": latencies,
    }


def get_ie_distribution(days: int = 7) -> dict:
    """Route label distribution and tool pruning analysis."""
    init_ie_tables()

    # Route label distribution
    label_rows = execute(
        """SELECT route_label, COUNT(*) AS cnt
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY route_label
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )

    label_dist: dict[str, int] = {}
    for r in label_rows:
        labels = (r.get("route_label") or "default").split(",")
        for lb in labels:
            lb = lb.strip() or "default"
            label_dist[lb] = label_dist.get(lb, 0) + r["cnt"]

    # Tool pruning analysis: count how often each tool appears in allowed set
    tool_rows = execute(
        """SELECT tool_group FROM ie_runs
           WHERE local_date >= date('now', ?)
             AND tool_group IS NOT NULL AND tool_group != '[]'""",
        (f"-{days} days",),
        readonly=True,
    )
    tool_kept: dict[str, int] = {}
    total_runs_with_tools = len(tool_rows)
    for r in tool_rows:
        raw = r.get("tool_group", "[]")
        try:
            tools = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if isinstance(tools, list):
            for t in tools:
                tool_kept[t] = tool_kept.get(t, 0) + 1

    tool_analysis = []
    for name, kept_count in sorted(tool_kept.items(), key=lambda x: -x[1]):
        pruned_count = total_runs_with_tools - kept_count
        tool_analysis.append({
            "tool": name,
            "kept_count": kept_count,
            "pruned_count": pruned_count,
            "kept_rate": round(kept_count / total_runs_with_tools * 100, 1)
            if total_runs_with_tools else 0,
        })

    # Decision mode distribution
    mode_rows = execute(
        """SELECT decision_mode, COUNT(*) AS cnt
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY decision_mode
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )

    return {
        "days": days,
        "route_labels": label_dist,
        "tool_analysis": tool_analysis,
        "decision_modes": {r["decision_mode"]: r["cnt"] for r in mode_rows},
        "total_runs_with_tools": total_runs_with_tools,
    }


def get_ie_misroutes(days: int = 7) -> dict:
    """Heuristic detection of *suspected* misroutes.

    A run is flagged as a suspected misroute when ALL of:
      - outcome is 'fail'
      - golden was not hit (golden_hit != 1, plan_source not golden_*)
      - tool reduction actually happened (tools_before > tools_after)

    This is NOT hard evidence — it requires manual review.  The returned
    ``suspected_misroutes`` count should be shown as "疑似" in the UI and
    must NOT feed into the Routing Health Score.
    """
    init_ie_tables()
    rows = execute(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) AS total_fail,
             SUM(CASE
               WHEN outcome = 'fail'
                 AND COALESCE(golden_hit, 0) != 1
                 AND COALESCE(plan_source, '') NOT IN (
                    'golden_v2_instance','golden_v2_template',
                    'golden_replay','golden_candidate')
                 AND tools_before > tools_after
               THEN 1 ELSE 0 END) AS suspected
           FROM ie_runs
           WHERE local_date >= date('now', ?)""",
        (f"-{days} days",),
        readonly=True,
    )
    r = rows[0] if rows else {}
    total = r.get("total", 0) or 0
    total_fail = r.get("total_fail", 0) or 0
    suspected = r.get("suspected", 0) or 0
    return {
        "total": total,
        "total_fail": total_fail,
        "suspected_misroutes": suspected,
        "suspected_rate": round(suspected / total * 100, 1) if total else 0,
        "heuristic": True,
    }


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
