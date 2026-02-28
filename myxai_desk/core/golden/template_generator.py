"""Template generator — auto-abstract instances into reusable templates.

When multiple instances share the same intent_label and tool sequence
(differing only in args), this module extracts the common pattern,
replaces varying arguments with slot placeholders, and creates a template.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from typing import Any

from myxai_desk.core.golden.models import GoldenInstance, GoldenTemplate, SlotSchema
from myxai_desk.core.golden.slot_extractor import normalize_slot_value

log = logging.getLogger("myxai")

MIN_INSTANCES_FOR_TEMPLATE = 3
TOOL_SEQUENCE_MATCH_RATIO = 1.0  # must be exact tool sequence match


def maybe_generate_templates(
    store: Any,
    intent_label: str | None = None,
) -> list[GoldenTemplate]:
    """Scan instances and generate templates where possible.

    If *intent_label* is given, only process that intent.
    Otherwise, process all intent labels with enough instances.
    """
    created: list[GoldenTemplate] = []

    if intent_label:
        labels = [intent_label]
    else:
        labels = _get_intent_labels_with_instances(store)

    for label in labels:
        if not label:
            continue
        existing = store.get_templates_by_intent(label)
        instances = store.get_instances_by_intent(label)

        if len(instances) < MIN_INSTANCES_FOR_TEMPLATE:
            continue

        template = _try_abstract(label, instances, existing)
        if template:
            saved = store.save_template(
                template_id=template["template_id"],
                intent_label=label,
                plan_template=template["plan_template"],
                slot_schemas=template["slot_schemas"],
                constraints=template.get("constraints", {}),
            )
            created.append(saved)
            log.info(
                "[template_gen] created template %s for intent=%s from %d instances",
                saved.template_id, label, len(instances),
            )

    return created


def _get_intent_labels_with_instances(store: Any) -> list[str]:
    """Get distinct intent labels that have enough instances."""
    from myxai_desk.core.storage.sqlite import execute

    rows = execute(
        """SELECT intent_label, COUNT(*) as cnt
           FROM golden_instances
           WHERE intent_label != ''
           GROUP BY intent_label
           HAVING cnt >= ?""",
        (MIN_INSTANCES_FOR_TEMPLATE,),
        readonly=True,
    )
    return [r["intent_label"] for r in rows]


def _try_abstract(
    intent_label: str,
    instances: list[GoldenInstance],
    existing_templates: list[GoldenTemplate],
) -> dict | None:
    """Try to abstract a group of instances into a template.

    Returns a dict with template_id, plan_template, slot_schemas, constraints
    if successful, or None if the instances aren't similar enough.
    """
    # Group by tool sequence signature
    groups = _group_by_tool_sequence(instances)

    for tool_sig, group in groups.items():
        if len(group) < MIN_INSTANCES_FOR_TEMPLATE:
            continue

        # Check if we already have a template for this tool sequence
        template_id = _make_template_id(intent_label, tool_sig)
        if any(t.template_id == template_id for t in existing_templates):
            continue

        # Diff args across instances to find varying positions
        diff_result = _diff_plans(group)
        if diff_result is None:
            continue

        plan_template, slot_schemas = diff_result

        if not slot_schemas:
            continue

        return {
            "template_id": template_id,
            "plan_template": plan_template,
            "slot_schemas": [s.to_dict() for s in slot_schemas],
            "constraints": _infer_constraints(group),
        }

    return None


def _group_by_tool_sequence(
    instances: list[GoldenInstance],
) -> dict[str, list[GoldenInstance]]:
    """Group instances by their tool call sequence (ignoring args)."""
    groups: dict[str, list[GoldenInstance]] = defaultdict(list)

    for inst in instances:
        plan = inst.resolved_plan
        sig = "|".join(
            s.get("tool_name", s.get("tool", ""))
            for s in plan
            if isinstance(s, dict)
        )
        if sig:
            groups[sig].append(inst)

    return dict(groups)


def _diff_plans(
    instances: list[GoldenInstance],
) -> tuple[list[dict], list[SlotSchema]] | None:
    """Compare resolved plans across instances to find varying args.

    Returns (plan_template_with_placeholders, slot_schemas) or None.
    """
    plans = [inst.resolved_plan for inst in instances]
    if not plans:
        return None

    reference = plans[0]
    num_steps = len(reference)
    if any(len(p) != num_steps for p in plans):
        return None

    template_steps: list[dict] = []
    schemas: list[SlotSchema] = []
    seen_slots: set[str] = set()

    for step_idx in range(num_steps):
        ref_step = reference[step_idx]
        tool_name = ref_step.get("tool_name", ref_step.get("tool", ""))

        # Collect all args for this step across instances
        all_args: list[dict] = []
        for plan in plans:
            step = plan[step_idx]
            args = step.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            all_args.append(args if isinstance(args, dict) else {})

        # Diff each arg key
        template_args: dict[str, Any] = {}
        ref_args = all_args[0]

        for key in ref_args:
            values = [a.get(key, "") for a in all_args]
            unique_values = set(str(v) for v in values)

            if len(unique_values) == 1:
                # Constant across all instances — keep as-is
                template_args[key] = ref_args[key]
            else:
                # Varying — replace with slot placeholder
                slot_name = _infer_slot_name(key, values)
                if slot_name in seen_slots:
                    # Same slot already used in a previous step — reuse
                    template_args[key] = f"{{{slot_name}}}"
                else:
                    slot_type = _infer_slot_type(values)
                    normalize = "path_canonical" if slot_type == "path" else "none"
                    schemas.append(SlotSchema(
                        name=slot_name,
                        type=slot_type,
                        required=True,
                        normalize=normalize,
                    ))
                    seen_slots.add(slot_name)
                    template_args[key] = f"{{{slot_name}}}"

        template_steps.append({
            "tool_name": tool_name,
            "args": template_args,
        })

    return template_steps, schemas


def _infer_slot_name(arg_key: str, values: list) -> str:
    """Infer a readable slot name from the arg key and its values."""
    key_upper = arg_key.upper()
    # Common mappings
    mappings = {
        "PATH": "DIR",
        "FILE_PATH": "FILE",
        "FILEPATH": "FILE",
        "DIRECTORY": "DIR",
        "DIR": "DIR",
        "QUERY": "QUERY",
        "URL": "URL",
        "COMMAND": "CMD",
        "CMD": "CMD",
        "TEXT": "TEXT",
        "CONTENT": "CONTENT",
    }
    return mappings.get(key_upper, key_upper)


def _infer_slot_type(values: list) -> str:
    """Infer the slot type from observed values."""
    str_values = [str(v) for v in values if v]

    # Check if all values look like paths
    path_pattern = re.compile(r'^[A-Za-z]:[\\\/]|^[~\/]')
    if all(path_pattern.match(v) for v in str_values):
        return "path"

    # Check if all values are URLs
    if all(v.startswith(("http://", "https://")) for v in str_values):
        return "url"

    # Check if all values are numbers
    try:
        [float(v) for v in str_values]
        return "number"
    except (ValueError, TypeError):
        pass

    return "string"


def _infer_constraints(instances: list[GoldenInstance]) -> dict[str, Any]:
    """Infer constraints from the instance collection."""
    # For now, minimal constraints
    return {}


def _make_template_id(intent_label: str, tool_sig: str) -> str:
    """Deterministic template ID from intent + tool sequence."""
    raw = f"{intent_label}::{tool_sig}"
    return f"tpl_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
