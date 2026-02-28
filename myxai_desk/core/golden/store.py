"""Golden 2.0 Store — unified DB layer for templates and instances.

Handles key computation, CRUD operations, and usage stats for the
three-layer golden system.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from myxai_desk.core.golden.models import GoldenInstance, GoldenTemplate
from myxai_desk.core.golden.tables import init_golden_v2_tables
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai")


# ── Key computation ──────────────────────────────────────────────


def compute_instance_key(
    intent_label: str,
    slot_values: dict[str, str],
    slot_schemas: list | None = None,
) -> str:
    """Deterministic key from intent + normalized slot values.

    Stable across: different word order, different separators, case.
    """
    from myxai_desk.core.golden.slot_extractor import normalize_slot_value

    normalized_pairs: list[str] = []
    for name in sorted(slot_values.keys()):
        val = slot_values[name]
        # Find matching schema for normalization hints
        norm_mode = "none"
        slot_type = "string"
        if slot_schemas:
            for s in slot_schemas:
                schema_name = s.name if hasattr(s, "name") else s.get("name", "")
                if schema_name == name:
                    slot_type = s.type if hasattr(s, "type") else s.get("type", "string")
                    norm_mode = s.normalize if hasattr(s, "normalize") else s.get("normalize", "none")
                    break

        normed = normalize_slot_value(val, slot_type, norm_mode)
        normalized_pairs.append(f"{name}={normed}")

    raw = f"{intent_label}|{'|'.join(normalized_pairs)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ── GoldenV2Store ────────────────────────────────────────────────


class GoldenV2Store:
    """All Golden 2.0 DB operations."""

    def __init__(self) -> None:
        init_golden_v2_tables()

    # ── Instance operations ──────────────────────────────────────

    def get_instance(self, case_key: str) -> Optional[GoldenInstance]:
        rows = execute(
            "SELECT * FROM golden_instances WHERE case_key = ?",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return None
        return _row_to_instance(rows[0])

    def save_instance(
        self,
        *,
        case_key: str,
        template_id: str | None,
        intent_label: str,
        slot_values: dict[str, str],
        resolved_plan: list[dict],
        now_iso: str | None = None,
    ) -> GoldenInstance:
        now = now_iso or _now_iso()
        plan_json = json.dumps(resolved_plan, ensure_ascii=False)
        slots_json = json.dumps(slot_values, ensure_ascii=False)

        execute(
            """INSERT OR REPLACE INTO golden_instances
               (case_key, template_id, intent_label, slot_values_json,
                resolved_plan_json, stats_json, created_at, last_used_at)
               VALUES (?, ?, ?, ?, ?, '{}', ?, ?)""",
            (case_key, template_id, intent_label, slots_json,
             plan_json, now, now),
        )

        return GoldenInstance(
            case_key=case_key,
            template_id=template_id,
            intent_label=intent_label,
            slot_values_json=slots_json,
            resolved_plan_json=plan_json,
            stats_json="{}",
            created_at=now,
            last_used_at=now,
        )

    def record_instance_use(
        self,
        case_key: str,
        *,
        ok: bool,
        duration_ms: int | None = None,
        run_id: str | None = None,
    ) -> None:
        now = _now_iso()
        rows = execute(
            "SELECT stats_json FROM golden_instances WHERE case_key = ?",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return

        stats = _safe_json(rows[0].get("stats_json", "{}"))
        sc = stats.get("success_count", 0)
        fc = stats.get("fail_count", 0)

        if ok:
            stats["success_count"] = sc + 1
        else:
            stats["fail_count"] = fc + 1

        if duration_ms is not None:
            total = sc + fc + 1
            old_dur = stats.get("avg_duration_ms", 0.0)
            stats["avg_duration_ms"] = round(
                old_dur + (duration_ms - old_dur) / total, 2
            )

        stats["last_outcome"] = "success" if ok else "fail"
        if run_id:
            stats["last_run_id"] = run_id

        execute(
            "UPDATE golden_instances SET last_used_at = ?, stats_json = ? WHERE case_key = ?",
            (now, json.dumps(stats, ensure_ascii=False), case_key),
        )

    def get_instances_by_intent(self, intent_label: str) -> list[GoldenInstance]:
        rows = execute(
            "SELECT * FROM golden_instances WHERE intent_label = ? ORDER BY created_at DESC",
            (intent_label,),
            readonly=True,
        )
        return [_row_to_instance(r) for r in rows]

    # ── Template operations ──────────────────────────────────────

    def get_template(self, template_id: str) -> Optional[GoldenTemplate]:
        rows = execute(
            "SELECT * FROM golden_templates WHERE template_id = ?",
            (template_id,),
            readonly=True,
        )
        if not rows:
            return None
        return _row_to_template(rows[0])

    def get_templates_by_intent(self, intent_label: str) -> list[GoldenTemplate]:
        rows = execute(
            "SELECT * FROM golden_templates WHERE intent_label = ? ORDER BY version DESC",
            (intent_label,),
            readonly=True,
        )
        return [_row_to_template(r) for r in rows]

    def save_template(
        self,
        *,
        template_id: str,
        intent_label: str,
        plan_template: list[dict],
        slot_schemas: list[dict],
        constraints: dict[str, Any] | None = None,
        now_iso: str | None = None,
    ) -> GoldenTemplate:
        now = now_iso or _now_iso()

        # Check for existing version
        old_version = 0
        rows = execute(
            "SELECT version FROM golden_templates WHERE template_id = ?",
            (template_id,),
            readonly=True,
        )
        if rows:
            old_version = rows[0].get("version", 0)

        new_version = old_version + 1
        plan_json = json.dumps(plan_template, ensure_ascii=False)
        schema_json = json.dumps(slot_schemas, ensure_ascii=False)
        constraints_json = json.dumps(constraints or {}, ensure_ascii=False)

        execute(
            """INSERT OR REPLACE INTO golden_templates
               (template_id, intent_label, version, plan_template_json,
                slot_schema_json, constraints_json, stats_json, created_at, last_used_at)
               VALUES (?, ?, ?, ?, ?, ?, '{}', ?, ?)""",
            (template_id, intent_label, new_version, plan_json,
             schema_json, constraints_json, now, now),
        )

        log.info(
            "[golden_v2] saved template %s v%d for intent=%s",
            template_id, new_version, intent_label,
        )

        return GoldenTemplate(
            template_id=template_id,
            intent_label=intent_label,
            version=new_version,
            plan_template_json=plan_json,
            slot_schema_json=schema_json,
            constraints_json=constraints_json,
            stats_json="{}",
            created_at=now,
            last_used_at=now,
        )

    def record_template_use(
        self,
        template_id: str,
        *,
        ok: bool,
    ) -> None:
        now = _now_iso()
        rows = execute(
            "SELECT stats_json FROM golden_templates WHERE template_id = ?",
            (template_id,),
            readonly=True,
        )
        if not rows:
            return

        stats = _safe_json(rows[0].get("stats_json", "{}"))
        if ok:
            stats["success_count"] = stats.get("success_count", 0) + 1
        else:
            stats["fail_count"] = stats.get("fail_count", 0) + 1
        stats["last_outcome"] = "success" if ok else "fail"

        execute(
            "UPDATE golden_templates SET last_used_at = ?, stats_json = ? WHERE template_id = ?",
            (now, json.dumps(stats, ensure_ascii=False), template_id),
        )


# ── Row converters ───────────────────────────────────────────────


def _row_to_instance(row: dict) -> GoldenInstance:
    return GoldenInstance(
        case_key=row["case_key"],
        template_id=row.get("template_id"),
        intent_label=row.get("intent_label", ""),
        slot_values_json=row.get("slot_values_json", "{}"),
        resolved_plan_json=row.get("resolved_plan_json", "[]"),
        stats_json=row.get("stats_json", "{}"),
        created_at=row.get("created_at", ""),
        last_used_at=row.get("last_used_at"),
    )


def _row_to_template(row: dict) -> GoldenTemplate:
    return GoldenTemplate(
        template_id=row["template_id"],
        intent_label=row["intent_label"],
        version=row.get("version", 1),
        plan_template_json=row.get("plan_template_json", "[]"),
        slot_schema_json=row.get("slot_schema_json", "[]"),
        constraints_json=row.get("constraints_json", "{}"),
        stats_json=row.get("stats_json", "{}"),
        created_at=row.get("created_at", ""),
        last_used_at=row.get("last_used_at"),
    )


# ── Helpers ──────────────────────────────────────────────────────


def _safe_json(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            r = json.loads(val)
            return r if isinstance(r, dict) else {}
        except Exception:
            return {}
    return {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
