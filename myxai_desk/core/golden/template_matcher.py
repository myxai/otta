"""Template matcher — lookup, validate slots, fill plan for Golden 2.0."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from myxai_desk.core.golden.models import (
    GoldenTemplate,
    MatchResult,
    SlotSchema,
)
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai")

_SLOT_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def match(intent_label: str, slots: dict[str, str]) -> MatchResult | None:
    """Find a matching template and fill it with slot values.

    Returns None if no template matches or slot validation fails.
    """
    if not intent_label:
        return None

    templates = _fetch_templates(intent_label)
    if not templates:
        return None

    for tpl in templates:
        schemas = tpl.slot_schemas

        if not _validate_slots(slots, schemas):
            continue

        filled = _fill_plan(tpl.plan_template, slots)
        if filled is None:
            continue

        return MatchResult(
            template_id=tpl.template_id,
            intent_label=tpl.intent_label,
            filled_plan=filled,
            slot_values=slots,
            constraints=tpl.constraints,
        )

    return None


# ── Internal helpers ─────────────────────────────────────────────


def _fetch_templates(intent_label: str) -> list[GoldenTemplate]:
    """Load all templates for an intent label, ordered by version desc."""
    try:
        from myxai_desk.core.golden.tables import init_golden_v2_tables
        init_golden_v2_tables()
    except Exception:
        pass

    rows = execute(
        "SELECT * FROM golden_templates WHERE intent_label = ? ORDER BY version DESC",
        (intent_label,),
        readonly=True,
    )
    return [_row_to_template(r) for r in rows]


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


def _validate_slots(
    slots: dict[str, str],
    schemas: list[SlotSchema],
) -> bool:
    """Check that provided slot values satisfy the schema requirements."""
    for schema in schemas:
        if schema.required and schema.name not in slots:
            return False
        val = slots.get(schema.name, "")
        if schema.required and not val:
            return False
        if val and not _type_check(val, schema.type):
            return False
    return True


def _type_check(value: str, slot_type: str) -> bool:
    """Basic type validation for a slot value."""
    if slot_type == "path":
        return len(value) >= 2
    if slot_type == "url":
        return value.startswith(("http://", "https://"))
    if slot_type == "number":
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    return True  # "string" type accepts anything


def _fill_plan(
    plan_template: list[dict],
    slots: dict[str, str],
) -> list[dict] | None:
    """Replace {SLOT} placeholders in a plan template with actual values.

    Returns None if any required placeholder has no corresponding slot value.
    """
    filled: list[dict] = []

    for step in plan_template:
        new_step = {}
        for key, val in step.items():
            new_step[key] = _fill_value(val, slots)
            if new_step[key] is None:
                return None
        filled.append(new_step)

    return filled


def _fill_value(val: Any, slots: dict[str, str]) -> Any:
    """Recursively replace {SLOT} placeholders in a value."""
    if isinstance(val, str):
        def _replacer(m: re.Match) -> str:
            name = m.group(1)
            if name in slots:
                return slots[name]
            return m.group(0)

        result = _SLOT_PLACEHOLDER.sub(_replacer, val)
        # If any unfilled placeholder remains, fail
        if _SLOT_PLACEHOLDER.search(result):
            unfilled = _SLOT_PLACEHOLDER.findall(result)
            log.debug("[template_matcher] unfilled placeholders: %s", unfilled)
            return None
        return result

    if isinstance(val, dict):
        out = {}
        for k, v in val.items():
            filled = _fill_value(v, slots)
            if filled is None:
                return None
            out[k] = filled
        return out

    if isinstance(val, list):
        out_list = []
        for item in val:
            filled = _fill_value(item, slots)
            if filled is None:
                return None
            out_list.append(filled)
        return out_list

    return val
