"""Data access layer for Capability Forest tables.

Tables:
  cap_registry  — static capability catalogue (core / mcp / md_skill)
  cap_state     — per-user forest state (candidate / trial / active / dormant / blocked)
  cap_reco      — recommendation records
  cap_events    — audit event stream
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from myxai_desk.core.storage.sqlite import connect, ensure_table, execute

log = logging.getLogger("myxai.cap_forest")

_TABLES_READY = False


# ── Table initialisation ──────────────────────────────────────────


def init_cap_forest_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return

    ensure_table(
        "cap_registry",
        """
        cap_id TEXT PRIMARY KEY,
        cap_type TEXT NOT NULL DEFAULT 'core',
        name TEXT NOT NULL DEFAULT '',
        description TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        intents_json TEXT DEFAULT '[]',
        entities_json TEXT DEFAULT '[]',
        permissions_json TEXT DEFAULT '[]',
        setup_json TEXT DEFAULT '{}',
        entrypoints_json TEXT DEFAULT '[]',
        source TEXT DEFAULT 'official',
        created_at TEXT NOT NULL DEFAULT ''
        """,
    )

    ensure_table(
        "cap_state",
        """
        cap_id TEXT PRIMARY KEY,
        state TEXT NOT NULL DEFAULT 'candidate',
        enabled INTEGER NOT NULL DEFAULT 0,
        trial_started_at TEXT DEFAULT '',
        last_used_at TEXT DEFAULT '',
        use_count_30d INTEGER DEFAULT 0,
        success_count_30d INTEGER DEFAULT 0,
        avg_effective_steps_30d REAL DEFAULT 0.0,
        avg_llm_fallback_30d REAL DEFAULT 0.0,
        score REAL DEFAULT 0.0,
        block_reason TEXT DEFAULT ''
        """,
    )

    ensure_table(
        "cap_reco",
        """
        reco_id TEXT PRIMARY KEY,
        cap_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        reason_json TEXT DEFAULT '{}',
        score_breakdown_json TEXT DEFAULT '{}',
        status TEXT DEFAULT 'shown',
        expires_at TEXT DEFAULT ''
        """,
    )

    ensure_table(
        "cap_events",
        """
        event_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        event_type TEXT NOT NULL,
        cap_id TEXT NOT NULL DEFAULT '',
        meta_json TEXT DEFAULT '{}'
        """,
    )

    _seed_core_capabilities()
    _TABLES_READY = True


# ── Seed built-in core capabilities ──────────────────────────────


_CORE_CAPS: list[dict[str, Any]] = [
    {
        "cap_id": "core.fs",
        "cap_type": "core",
        "name": "File System",
        "description": "Read, write, edit, list and delete files; execute shell commands",
        "tags_json": '["file", "directory", "shell"]',
        "intents_json": '["fs"]',
        "entrypoints_json": '["exec", "read_file", "list_dir", "write_file", "edit_file"]',
        "source": "official",
    },
    {
        "cap_id": "core.search",
        "cap_type": "core",
        "name": "Web Search",
        "description": "Search the web, fetch pages, smart content extraction",
        "tags_json": '["search", "web", "fetch"]',
        "intents_json": '["search"]',
        "entrypoints_json": '["web_search", "web_fetch", "smart_fetch"]',
        "source": "official",
    },
    {
        "cap_id": "core.browser",
        "cap_type": "core",
        "name": "Browser Automation",
        "description": "Control a headless browser via MCP for scraping and UI automation",
        "tags_json": '["browser", "automation", "scrape"]',
        "intents_json": '["browser"]',
        "entrypoints_json": '[]',
        "source": "official",
    },
    {
        "cap_id": "core.schedule",
        "cap_type": "core",
        "name": "Scheduler",
        "description": "Create timed tasks, reminders and cron jobs",
        "tags_json": '["schedule", "cron", "reminder"]',
        "intents_json": '["schedule"]',
        "entrypoints_json": '["cron"]',
        "source": "official",
    },
    {
        "cap_id": "core.comm",
        "cap_type": "core",
        "name": "Communication",
        "description": "Send messages, notifications and spawn background tasks",
        "tags_json": '["message", "notification", "spawn"]',
        "intents_json": '["comm"]',
        "entrypoints_json": '["message", "spawn"]',
        "source": "official",
    },
]


def _seed_core_capabilities() -> None:
    """Insert core capabilities if not already present."""
    now = datetime.now(timezone.utc).isoformat()
    for cap in _CORE_CAPS:
        try:
            existing = execute(
                "SELECT cap_id FROM cap_registry WHERE cap_id = ?",
                (cap["cap_id"],),
                readonly=True,
            )
            if existing:
                continue
            execute(
                """INSERT INTO cap_registry
                   (cap_id, cap_type, name, description, tags_json,
                    intents_json, entrypoints_json, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cap["cap_id"],
                    cap["cap_type"],
                    cap["name"],
                    cap.get("description", ""),
                    cap.get("tags_json", "[]"),
                    cap.get("intents_json", "[]"),
                    cap.get("entrypoints_json", "[]"),
                    cap.get("source", "official"),
                    now,
                ),
            )
            execute(
                """INSERT OR IGNORE INTO cap_state (cap_id, state, enabled)
                   VALUES (?, 'active', 1)""",
                (cap["cap_id"],),
            )
        except Exception:
            log.debug("seed cap %s skipped", cap["cap_id"], exc_info=True)


# ── cap_registry operations ──────────────────────────────────────


def upsert_registry(cap: dict[str, Any]) -> None:
    """Insert or update a capability in the registry."""
    init_cap_forest_tables()
    now = datetime.now(timezone.utc).isoformat()
    execute(
        """INSERT INTO cap_registry
           (cap_id, cap_type, name, description, tags_json,
            intents_json, entities_json, permissions_json,
            setup_json, entrypoints_json, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(cap_id) DO UPDATE SET
             cap_type=excluded.cap_type, name=excluded.name,
             description=excluded.description, tags_json=excluded.tags_json,
             intents_json=excluded.intents_json, entities_json=excluded.entities_json,
             permissions_json=excluded.permissions_json, setup_json=excluded.setup_json,
             entrypoints_json=excluded.entrypoints_json, source=excluded.source""",
        (
            cap["cap_id"],
            cap.get("cap_type", "core"),
            cap.get("name", ""),
            cap.get("description", ""),
            cap.get("tags_json", "[]"),
            cap.get("intents_json", "[]"),
            cap.get("entities_json", "[]"),
            cap.get("permissions_json", "[]"),
            cap.get("setup_json", "{}"),
            cap.get("entrypoints_json", "[]"),
            cap.get("source", "official"),
            now,
        ),
    )


def list_registry(cap_type: str | None = None) -> list[dict]:
    init_cap_forest_tables()
    if cap_type:
        return execute(
            "SELECT * FROM cap_registry WHERE cap_type = ? ORDER BY cap_id",
            (cap_type,),
            readonly=True,
        )
    return execute("SELECT * FROM cap_registry ORDER BY cap_id", readonly=True)


def get_registry_item(cap_id: str) -> dict | None:
    init_cap_forest_tables()
    rows = execute(
        "SELECT * FROM cap_registry WHERE cap_id = ?", (cap_id,), readonly=True
    )
    return rows[0] if rows else None


# ── cap_state operations ─────────────────────────────────────────


def get_state(cap_id: str) -> dict | None:
    init_cap_forest_tables()
    rows = execute(
        "SELECT * FROM cap_state WHERE cap_id = ?", (cap_id,), readonly=True
    )
    return rows[0] if rows else None


def list_states(state: str | None = None) -> list[dict]:
    init_cap_forest_tables()
    if state:
        return execute(
            "SELECT * FROM cap_state WHERE state = ? ORDER BY score DESC",
            (state,),
            readonly=True,
        )
    return execute("SELECT * FROM cap_state ORDER BY score DESC", readonly=True)


def set_state(cap_id: str, new_state: str, enabled: int | None = None) -> None:
    """Transition a capability to *new_state*; auto-sets enabled flag."""
    init_cap_forest_tables()
    if enabled is None:
        enabled = 1 if new_state in ("active", "trial") else 0
    now = datetime.now(timezone.utc).isoformat()
    existing = get_state(cap_id)
    if existing:
        execute(
            "UPDATE cap_state SET state = ?, enabled = ? WHERE cap_id = ?",
            (new_state, enabled, cap_id),
        )
    else:
        execute(
            """INSERT INTO cap_state (cap_id, state, enabled) VALUES (?, ?, ?)""",
            (cap_id, new_state, enabled),
        )
    _log_event(
        "state_change",
        cap_id,
        {"from": existing["state"] if existing else "new", "to": new_state},
    )


def enable_cap(cap_id: str, mode: str = "active") -> None:
    """Enable a capability as *active* or *trial*."""
    init_cap_forest_tables()
    now = datetime.now(timezone.utc).isoformat()
    existing = get_state(cap_id)
    if existing:
        updates = {"state": mode, "enabled": 1}
        if mode == "trial":
            updates["trial_started_at"] = now
        set_parts = ", ".join(f"{k} = ?" for k in updates)
        execute(
            f"UPDATE cap_state SET {set_parts} WHERE cap_id = ?",
            (*updates.values(), cap_id),
        )
    else:
        trial_ts = now if mode == "trial" else ""
        execute(
            """INSERT INTO cap_state
               (cap_id, state, enabled, trial_started_at)
               VALUES (?, ?, 1, ?)""",
            (cap_id, mode, trial_ts),
        )
    _log_event("enable", cap_id, {"mode": mode})


def disable_cap(cap_id: str) -> None:
    """Disable a capability → dormant."""
    set_state(cap_id, "dormant", enabled=0)


def update_state_fields(cap_id: str, **fields: Any) -> None:
    """Flexible partial update for cap_state."""
    _ALLOWED = frozenset({
        "state", "enabled", "trial_started_at", "last_used_at",
        "use_count_30d", "success_count_30d",
        "avg_effective_steps_30d", "avg_llm_fallback_30d",
        "score", "block_reason",
    })
    safe = {k: v for k, v in fields.items() if k in _ALLOWED}
    if not safe:
        return
    init_cap_forest_tables()
    set_clause = ", ".join(f"{k} = ?" for k in safe)
    execute(
        f"UPDATE cap_state SET {set_clause} WHERE cap_id = ?",
        (*safe.values(), cap_id),
    )


def record_usage(cap_id: str, success: bool) -> None:
    """Bump usage counters after a capability is invoked."""
    init_cap_forest_tables()
    now = datetime.now(timezone.utc).isoformat()
    execute(
        """UPDATE cap_state
           SET use_count_30d = use_count_30d + 1,
               success_count_30d = success_count_30d + CASE WHEN ? THEN 1 ELSE 0 END,
               last_used_at = ?
           WHERE cap_id = ?""",
        (int(success), now, cap_id),
    )


# ── cap_reco operations ──────────────────────────────────────────


def insert_reco(cap_id: str, reason: dict, score_breakdown: dict, expires_at: str = "") -> str:
    init_cap_forest_tables()
    reco_id = uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    execute(
        """INSERT INTO cap_reco
           (reco_id, cap_id, created_at, reason_json, score_breakdown_json, status, expires_at)
           VALUES (?, ?, ?, ?, ?, 'shown', ?)""",
        (
            reco_id,
            cap_id,
            now,
            json.dumps(reason, ensure_ascii=False, default=str),
            json.dumps(score_breakdown, ensure_ascii=False, default=str),
            expires_at,
        ),
    )
    return reco_id


def update_reco_status(reco_id: str, status: str) -> None:
    init_cap_forest_tables()
    execute("UPDATE cap_reco SET status = ? WHERE reco_id = ?", (status, reco_id))


def list_recos(status: str | None = None, limit: int = 20) -> list[dict]:
    init_cap_forest_tables()
    if status:
        return execute(
            "SELECT * FROM cap_reco WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
            readonly=True,
        )
    return execute(
        "SELECT * FROM cap_reco ORDER BY created_at DESC LIMIT ?",
        (limit,),
        readonly=True,
    )


# ── cap_events operations ────────────────────────────────────────


def _log_event(event_type: str, cap_id: str, meta: dict | None = None) -> None:
    try:
        init_cap_forest_tables()
        execute(
            """INSERT INTO cap_events (event_id, ts, event_type, cap_id, meta_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                uuid4().hex[:16],
                datetime.now(timezone.utc).isoformat(),
                event_type,
                cap_id,
                json.dumps(meta or {}, ensure_ascii=False, default=str),
            ),
        )
    except Exception:
        log.debug("cap_events insert failed", exc_info=True)


def list_events(limit: int = 100, event_type: str | None = None) -> list[dict]:
    init_cap_forest_tables()
    if event_type:
        return execute(
            "SELECT * FROM cap_events WHERE event_type = ? ORDER BY ts DESC LIMIT ?",
            (event_type, limit),
            readonly=True,
        )
    return execute(
        "SELECT * FROM cap_events ORDER BY ts DESC LIMIT ?",
        (limit,),
        readonly=True,
    )


# ── Overview / KPI ────────────────────────────────────────────────


def get_overview() -> dict:
    """Return a structured overview of the forest for the front-end."""
    init_cap_forest_tables()

    rows = execute(
        """SELECT s.*, r.name, r.cap_type, r.description, r.tags_json,
                  r.intents_json, r.entrypoints_json, r.source
           FROM cap_state s
           JOIN cap_registry r ON s.cap_id = r.cap_id
           ORDER BY s.score DESC""",
        readonly=True,
    )

    active = [r for r in rows if r["state"] == "active"]
    trial = [r for r in rows if r["state"] == "trial"]
    dormant = [r for r in rows if r["state"] == "dormant"]
    candidate = [r for r in rows if r["state"] == "candidate"]
    blocked = [r for r in rows if r["state"] == "blocked"]

    total_use = sum(r.get("use_count_30d", 0) or 0 for r in rows)
    total_success = sum(r.get("success_count_30d", 0) or 0 for r in rows)

    return {
        "active": active,
        "trial": trial,
        "dormant": dormant,
        "candidate": candidate,
        "blocked": blocked,
        "kpi": {
            "active_count": len(active),
            "trial_count": len(trial),
            "dormant_count": len(dormant),
            "candidate_count": len(candidate),
            "total_use_30d": total_use,
            "success_rate_30d": round(total_success / total_use * 100, 1) if total_use else 0,
        },
    }
