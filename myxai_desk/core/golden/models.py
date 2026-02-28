"""Data models for the Golden 2.0 three-layer system."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Slot types ────────────────────────────────────────────────────


@dataclass
class SlotSchema:
    """Describes one slot placeholder in a template."""

    name: str            # e.g. "DIR", "QUERY", "URL"
    type: str            # "path" | "string" | "number" | "url"
    required: bool = True
    normalize: str = "none"  # "path_canonical" | "lowercase" | "none"

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type,
                "required": self.required, "normalize": self.normalize}

    @classmethod
    def from_dict(cls, d: dict) -> SlotSchema:
        return cls(
            name=d["name"], type=d.get("type", "string"),
            required=d.get("required", True),
            normalize=d.get("normalize", "none"),
        )


@dataclass
class SlotResult:
    """Output of the slot extraction layer."""

    intent_label: str = ""
    slots: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    extraction_mode: str = "rule"  # "rule" | "llm"


# ── Layer 1: Template ────────────────────────────────────────────


@dataclass
class GoldenTemplate:
    """An abstract, reusable plan with slot placeholders."""

    template_id: str
    intent_label: str
    version: int = 1
    plan_template_json: str = "[]"
    slot_schema_json: str = "[]"
    constraints_json: str = "{}"
    stats_json: str = "{}"
    created_at: str = ""
    last_used_at: Optional[str] = None

    @property
    def plan_template(self) -> list[dict]:
        return _safe_json_list(self.plan_template_json)

    @property
    def slot_schemas(self) -> list[SlotSchema]:
        raw = _safe_json_list(self.slot_schema_json)
        return [SlotSchema.from_dict(d) for d in raw if isinstance(d, dict)]

    @property
    def constraints(self) -> dict[str, Any]:
        return _safe_json_dict(self.constraints_json)

    @property
    def stats(self) -> dict[str, Any]:
        return _safe_json_dict(self.stats_json)


# ── Layer 2: Instance ────────────────────────────────────────────


@dataclass
class GoldenInstance:
    """A fully resolved plan for a specific slot combination."""

    case_key: str
    template_id: Optional[str] = None
    intent_label: str = ""
    slot_values_json: str = "{}"
    resolved_plan_json: str = "[]"
    stats_json: str = "{}"
    created_at: str = ""
    last_used_at: Optional[str] = None

    @property
    def slot_values(self) -> dict[str, str]:
        return _safe_json_dict(self.slot_values_json)

    @property
    def resolved_plan(self) -> list[dict]:
        return _safe_json_list(self.resolved_plan_json)

    @property
    def stats(self) -> dict[str, Any]:
        return _safe_json_dict(self.stats_json)


# ── Match / Validation results ───────────────────────────────────


@dataclass
class MatchResult:
    """Output of template matching."""

    template_id: str
    intent_label: str
    filled_plan: list[dict]
    slot_values: dict[str, str]
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Output of replay validation."""

    ok: bool = True
    reason: str = ""


# ── Helpers ───────────────────────────────────────────────────────


def _safe_json_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            r = json.loads(val)
            return r if isinstance(r, list) else []
        except Exception:
            return []
    return []


def _safe_json_dict(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            r = json.loads(val)
            return r if isinstance(r, dict) else {}
        except Exception:
            return {}
    return {}
