"""Golden 2.0 DB tables — golden_templates and golden_instances.

Additive migration: existing golden_plans / golden_candidates tables
are left untouched for backward compatibility.
"""

from __future__ import annotations

import logging

from myxai_desk.core.storage.sqlite import connect, ensure_table, execute

log = logging.getLogger("myxai")

_TABLES_READY = False


def init_golden_v2_tables() -> None:
    """Create golden_templates and golden_instances if they don't exist."""
    global _TABLES_READY
    if _TABLES_READY:
        return

    ensure_table(
        "golden_templates",
        """
        template_id         TEXT PRIMARY KEY,
        intent_label        TEXT NOT NULL,
        version             INTEGER NOT NULL DEFAULT 1,
        plan_template_json  TEXT NOT NULL,
        slot_schema_json    TEXT NOT NULL DEFAULT '[]',
        constraints_json    TEXT NOT NULL DEFAULT '{}',
        stats_json          TEXT NOT NULL DEFAULT '{}',
        created_at          TEXT NOT NULL,
        last_used_at        TEXT
        """,
    )

    ensure_table(
        "golden_instances",
        """
        case_key            TEXT PRIMARY KEY,
        template_id         TEXT,
        intent_label        TEXT NOT NULL DEFAULT '',
        slot_values_json    TEXT NOT NULL DEFAULT '{}',
        resolved_plan_json  TEXT NOT NULL,
        stats_json          TEXT NOT NULL DEFAULT '{}',
        created_at          TEXT NOT NULL,
        last_used_at        TEXT
        """,
    )

    _ensure_indexes()
    _TABLES_READY = True
    log.info("[golden_v2] tables initialized")


def _ensure_indexes() -> None:
    """Create indexes if missing (idempotent)."""
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_gt_intent ON golden_templates(intent_label)",
        "CREATE INDEX IF NOT EXISTS idx_gi_template ON golden_instances(template_id)",
        "CREATE INDEX IF NOT EXISTS idx_gi_intent ON golden_instances(intent_label)",
    ):
        try:
            with connect() as conn:
                conn.execute(sql)
        except Exception:
            pass


def migrate_golden_plans_to_instances() -> int:
    """One-time migration: copy golden_plans rows into golden_instances.

    Only copies rows whose case_key doesn't already exist in golden_instances.
    Returns the number of rows migrated.
    """
    init_golden_v2_tables()

    try:
        rows = execute(
            """SELECT gp.case_key, gp.golden_plan_json, gp.created_at, gp.last_used_at
               FROM golden_plans gp
               WHERE gp.replayable = 1
                 AND gp.case_key NOT IN (SELECT case_key FROM golden_instances)""",
            readonly=True,
        )
    except Exception:
        return 0

    count = 0
    for r in rows:
        try:
            execute(
                """INSERT OR IGNORE INTO golden_instances
                   (case_key, template_id, intent_label, slot_values_json,
                    resolved_plan_json, stats_json, created_at, last_used_at)
                   VALUES (?, NULL, '', '{}', ?, '{}', ?, ?)""",
                (r["case_key"], r["golden_plan_json"],
                 r["created_at"], r.get("last_used_at")),
            )
            count += 1
        except Exception:
            continue

    if count:
        log.info("[golden_v2] migrated %d golden_plans -> golden_instances", count)
    return count
