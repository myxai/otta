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
    ensure_table(
        "intent_feedback",
        """
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        original_category TEXT DEFAULT '',
        corrected_category TEXT DEFAULT '',
        created_at TEXT NOT NULL
        """,
    )
    
    # Semantic assets tables (for nightly learning)
    ensure_table(
        "semantic_runs",
        """
        id TEXT PRIMARY KEY,
        run_date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        input_stats_json TEXT DEFAULT '{}',
        output_artifacts_json TEXT DEFAULT '{}',
        model_used TEXT DEFAULT '',
        token_cost INTEGER DEFAULT 0,
        error_log TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        completed_at TEXT
        """,
    )
    
    ensure_table(
        "user_lexicon",
        """
        id TEXT PRIMARY KEY,
        version INTEGER NOT NULL,
        synonyms_json TEXT DEFAULT '{}',
        verb_map_json TEXT DEFAULT '{}',
        stop_phrases_json TEXT DEFAULT '[]',
        source TEXT DEFAULT 'manual',
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
        """,
    )
    
    ensure_table(
        "case_key_alias",
        """
        id TEXT PRIMARY KEY,
        alias TEXT NOT NULL UNIQUE,
        canonical TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        source TEXT DEFAULT 'manual',
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
        """,
    )

    _backfill_ie_runs_columns()
    _backfill_ie_cases_columns()
    _backfill_golden_hit_from_plan_source()
    _ensure_fts5_index()
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
        ("decision", "TEXT"),
        # IE 2.0 taxonomy fields
        ("routing_method", "TEXT"),
        ("execution_path", "TEXT"),
        ("risk_level", "TEXT"),
        ("fallback_reason", "TEXT"),
        ("matched_rule_id", "TEXT"),
        ("misroute_suspect", "INTEGER DEFAULT 0"),
        # IE 3.0 confidence calibration fields
        ("rule_conf", "REAL"),
        ("case_id", "TEXT"),
        ("case_conf", "REAL"),
        ("llm_conf", "REAL"),
        ("confidence_source", "TEXT"),
        ("arbiter_reason", "TEXT"),
        ("evidence_json", "TEXT"),
        ("user_corrected", "INTEGER DEFAULT 0"),
        ("final_category", "TEXT"),
        ("final_success", "INTEGER"),
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


def _backfill_ie_cases_columns() -> None:
    """Add IE 3.0 columns to ie_cases if missing."""
    extras = [
        ("case_key", "TEXT"),
        ("text_norm", "TEXT DEFAULT ''"),
        ("norm_hash", "TEXT DEFAULT ''"),
        ("embedding_dim", "INTEGER DEFAULT 0"),
        ("embedding_model", "TEXT DEFAULT ''"),
        ("best_plan_kind", "TEXT"),
        ("plan_success_rate", "REAL DEFAULT 1.0"),
        ("success_count", "INTEGER DEFAULT 1"),
        ("fail_count", "INTEGER DEFAULT 0"),
        ("last_used_at", "TEXT"),
    ]
    for col, typedef in extras:
        try:
            execute(f"SELECT {col} FROM ie_cases LIMIT 1", readonly=True)
        except Exception:
            try:
                with connect() as conn:
                    conn.execute(f"ALTER TABLE ie_cases ADD COLUMN {col} {typedef}")
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


def _ensure_fts5_index() -> None:
    """Create FTS5 virtual table for ie_cases full-text search (BM25).
    
    This enables lexical fallback when semantic embedding is unavailable,
    ensuring case retrieval remains functional even without vector models.
    Uses BM25 ranking for relevance scoring.
    """
    try:
        from myxai_desk.core.storage.sqlite import connect
        with connect() as conn:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS ie_cases_fts
                USING fts5(
                    task_text,
                    route_label,
                    case_key,
                    content='ie_cases',
                    content_rowid='rowid',
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)
            
            # Populate FTS5 index from existing cases (simplified)
            result = conn.execute("SELECT COUNT(*) as cnt FROM ie_cases_fts").fetchone()
            fts_count = result[0] if result else 0
            result = conn.execute("SELECT COUNT(*) as cnt FROM ie_cases").fetchone()
            cases_count = result[0] if result else 0
            
            if fts_count < cases_count:
                # Rebuild FTS5 index
                conn.execute("DELETE FROM ie_cases_fts")
                conn.execute("""
                    INSERT INTO ie_cases_fts(rowid, task_text, route_label, case_key)
                    SELECT rowid, task_text, route_label, COALESCE(case_key, '') 
                    FROM ie_cases
                """)
            
            # Create triggers to keep FTS5 in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS ie_cases_fts_insert AFTER INSERT ON ie_cases BEGIN
                    INSERT INTO ie_cases_fts(rowid, task_text, route_label, case_key)
                    VALUES (new.rowid, new.task_text, new.route_label, COALESCE(new.case_key, ''));
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS ie_cases_fts_update AFTER UPDATE ON ie_cases BEGIN
                    UPDATE ie_cases_fts SET 
                        task_text = new.task_text,
                        route_label = new.route_label,
                        case_key = COALESCE(new.case_key, '')
                    WHERE rowid = new.rowid;
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS ie_cases_fts_delete AFTER DELETE ON ie_cases BEGIN
                    DELETE FROM ie_cases_fts WHERE rowid = old.rowid;
                END
            """)
            
        log.debug("[ie_dao] FTS5 index ready for ie_cases")
    except Exception:
        log.warning("[ie_dao] FTS5 index setup failed (may not be critical)", exc_info=True)


# ── ie_runs operations ────────────────────────────────────────────

def insert_run(
    *,
    session_id: str,
    user_text: str,
    context: dict | None = None,
    route_label: str = "",
    route_conf: float = 0.0,
    decision_mode: str = "rule",
    decision: str = "llm",
    tool_group: list[str] | None = None,
    tools_before: int = 0,
    tools_after: int = 0,
    routing_method: str = "rule",
    risk_level: str = "low",
    matched_rule_id: str = "",
    fallback_reason: str = "",
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
                route_conf, decision_mode, decision, tool_group,
                tools_before, tools_after, outcome, created_at, local_date,
                routing_method, risk_level, matched_rule_id, fallback_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                session_id,
                (user_text or "")[:2000],
                json.dumps(context or {}, ensure_ascii=False, default=str),
                route_label,
                route_conf,
                decision_mode,
                decision,
                json.dumps(tool_group or [], ensure_ascii=False),
                tools_before,
                tools_after,
                now,
                local_date,
                routing_method,
                risk_level,
                matched_rule_id,
                fallback_reason,
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
    "decision",
    "routing_method", "execution_path", "risk_level",
    "fallback_reason", "matched_rule_id", "misroute_suspect",
    # IE 3.0 confidence calibration
    "rule_conf", "case_id", "case_conf", "llm_conf",
    "confidence_source", "arbiter_reason", "evidence_json",
    "user_corrected", "final_category", "final_success",
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
             SUM(CASE WHEN decision='reuse_plan'
                 OR plan_source='reuse_plan' THEN 1 ELSE 0 END) AS reuse_count
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
             SUM(CASE WHEN execution_path = 'plan_reuse'
                       OR decision='reuse_plan'
                       OR plan_source='reuse_plan'
                  THEN 1 ELSE 0 END) AS reuse_count,
             SUM(CASE WHEN COALESCE(misroute_suspect, 0) = 1
                  THEN 1 ELSE 0 END) AS misroute_count,
             SUM(CASE WHEN route_label IN ('general', 'chat')
                       OR route_label LIKE '%%general%%'
                  THEN 1 ELSE 0 END) AS fallback_count
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

    fallback_count = r.get("fallback_count", 0) or 0
    fallback_rate = fallback_count / total if total else 0
    misroute_count = r.get("misroute_count", 0) or 0

    # Routing Health Score (0-100):
    #  + rule/reuse hit & success
    #  + golden hit
    #  - fallback rate
    #  - misroute rate
    score = round(
        (0.3 * golden_hit_rate
         + 0.25 * success_rate
         + 0.2 * avg_reduction
         + 0.15 * (1 - llm_call_ratio)
         + 0.10 * (1 - fallback_rate)) * 100,
        1,
    )

    reuse = r.get("reuse_count", 0) or 0
    reuse_rate = round(reuse / total * 100, 1) if total else 0

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
        "reuse_count": reuse,
        "reuse_rate": reuse_rate,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_rate * 100, 1),
        "misroute_count": misroute_count,
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

    # Routing method distribution (rule / model / case_reuse)
    method_rows = execute(
        """SELECT COALESCE(routing_method, decision_mode, 'rule') AS method,
                  COUNT(*) AS cnt
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY method
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )

    # Execution path distribution (llm_loop / plan_reuse)
    path_rows = execute(
        """SELECT COALESCE(execution_path,
                    CASE WHEN decision = 'reuse_plan' THEN 'plan_reuse'
                         ELSE 'llm_loop' END) AS path,
                  COUNT(*) AS cnt
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY path
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )

    # Risk level distribution
    risk_rows = execute(
        """SELECT COALESCE(risk_level, 'low') AS risk, COUNT(*) AS cnt
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY risk
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )

    # Fallback rate: how often we land on general/chat (weak rule coverage)
    fallback_row = execute(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN route_label IN ('general', 'chat')
                       OR route_label LIKE '%general%'
                  THEN 1 ELSE 0 END) AS fallback_count
           FROM ie_runs
           WHERE local_date >= date('now', ?)""",
        (f"-{days} days",),
        readonly=True,
    )
    fb = fallback_row[0] if fallback_row else {}
    fb_total = fb.get("total", 0) or 0
    fb_count = fb.get("fallback_count", 0) or 0

    return {
        "days": days,
        "route_labels": label_dist,
        "tool_analysis": tool_analysis,
        "routing_methods": {r["method"]: r["cnt"] for r in method_rows},
        "execution_paths": {r["path"]: r["cnt"] for r in path_rows},
        "risk_levels": {r["risk"]: r["cnt"] for r in risk_rows},
        "fallback_rate": round(fb_count / fb_total * 100, 1) if fb_total else 0,
        "fallback_count": fb_count,
        # Legacy compat
        "decision_modes": {r["method"]: r["cnt"] for r in method_rows},
        "decisions": {r["path"]: r["cnt"] for r in path_rows},
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
    case_key: str = "",
    best_plan_kind: str = "",
) -> str | None:
    try:
        init_ie_tables()
        case_id = uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        execute(
            """INSERT INTO ie_cases
               (id, task_text, context_fp, route_label, plan_json,
                pitfalls, fail_reason, outcome, embedding_id, sim_hash,
                created_at, usage_count, case_key, best_plan_kind)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
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
                case_key,
                best_plan_kind,
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


def find_case_by_key(case_key: str) -> dict | None:
    """Find the most recent case matching *case_key*."""
    if not case_key:
        return None
    try:
        init_ie_tables()
        rows = execute(
            "SELECT * FROM ie_cases WHERE case_key = ? ORDER BY created_at DESC LIMIT 1",
            (case_key,),
            readonly=True,
        )
        return dict(rows[0]) if rows else None
    except Exception:
        log.warning("[ie_dao] find_case_by_key failed", exc_info=True)
        return None


def update_case_stats(case_id: str, *, success: bool) -> None:
    """Increment success/fail counts and recompute plan_success_rate."""
    if not case_id:
        return
    try:
        init_ie_tables()
        now = datetime.now(timezone.utc).isoformat()
        if success:
            execute(
                """UPDATE ie_cases
                   SET success_count = COALESCE(success_count, 0) + 1,
                       last_used_at = ?,
                       plan_success_rate = CAST(COALESCE(success_count, 0) + 1 AS REAL)
                           / (COALESCE(success_count, 0) + 1 + COALESCE(fail_count, 0))
                   WHERE id = ?""",
                (now, case_id),
            )
        else:
            execute(
                """UPDATE ie_cases
                   SET fail_count = COALESCE(fail_count, 0) + 1,
                       last_used_at = ?,
                       plan_success_rate = CAST(COALESCE(success_count, 0) AS REAL)
                           / (COALESCE(success_count, 0) + COALESCE(fail_count, 0) + 1)
                   WHERE id = ?""",
                (now, case_id),
            )
    except Exception:
        log.warning("[ie_dao] update_case_stats failed", exc_info=True)


# ── intent_feedback operations ─────────────────────────────────────

def insert_correction(
    *,
    run_id: str,
    original_category: str,
    corrected_category: str,
) -> str | None:
    """Record a user correction and mark the run as corrected."""
    try:
        init_ie_tables()
        fb_id = uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        execute(
            """INSERT INTO intent_feedback
               (id, run_id, original_category, corrected_category, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (fb_id, run_id, original_category, corrected_category, now),
        )
        execute(
            "UPDATE ie_runs SET user_corrected = 1, final_category = ? WHERE id = ?",
            (corrected_category, run_id),
        )
        return fb_id
    except Exception:
        log.warning("[ie_dao] insert_correction failed", exc_info=True)
        return None


def get_corrections(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return recent user corrections."""
    try:
        init_ie_tables()
        return execute(
            """SELECT f.*, r.user_text, r.route_label
               FROM intent_feedback f
               LEFT JOIN ie_runs r ON f.run_id = r.id
               ORDER BY f.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
            readonly=True,
        )
    except Exception:
        log.warning("[ie_dao] get_corrections failed", exc_info=True)
        return []
