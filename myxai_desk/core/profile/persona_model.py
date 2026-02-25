"""Six-layer persona model — the structured representation of user cognition.

Each layer captures a different facet of the user and evolves at its own
cadence (daily / weekly / biweekly / monthly).  The full ``PersonaProfile``
is persisted as versioned JSON and compressed into Prompt summaries by
the ``prompt_builder`` module.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any


# ── Layer base ────────────────────────────────────────────────────

@dataclass
class _LayerBase:
    confidence: float = 0.0
    last_updated: str = ""
    signal_count: int = 0


# ── Layer 1: Identity (stable, weekly) ────────────────────────────

@dataclass
class IdentityLayer(_LayerBase):
    role_type: str = ""
    industry_focus: list[str] = field(default_factory=list)
    product_stage: str = ""
    work_mode: str = ""
    primary_device: str = ""


# ── Layer 2: Goals (weekly / manual confirmation) ─────────────────

@dataclass
class GoalLayer(_LayerBase):
    long_term_goal: str = ""
    mid_term_goal: str = ""
    current_focus: list[str] = field(default_factory=list)


# ── Layer 3: Interests (dynamic, daily) ──────────────────────────

@dataclass
class InterestLayer(_LayerBase):
    topic_weight: dict[str, float] = field(default_factory=dict)
    trend_shift: dict[str, float] = field(default_factory=dict)
    window: str = "7_day"


# ── Layer 4: Capabilities (biweekly) ─────────────────────────────

@dataclass
class CapabilityLayer(_LayerBase):
    technical_level: str = ""
    coding_stack: list[str] = field(default_factory=list)
    architecture_thinking: str = ""
    product_design: str = ""
    marketing_ops: str = ""


# ── Layer 5: Decision Profile (monthly) ──────────────────────────

@dataclass
class DecisionLayer(_LayerBase):
    risk_preference: str = ""
    structure_preference: str = ""
    noise_tolerance: str = ""
    execution_bias: str = ""
    dislike: list[str] = field(default_factory=list)


# ── Layer 6: Behavior Patterns (daily) ───────────────────────────

@dataclass
class BehaviorLayer(_LayerBase):
    active_hours: str = ""
    deep_work_pattern: str = ""
    project_focus_map: dict[str, float] = field(default_factory=dict)
    context_switching: str = ""


# ── Update metadata ──────────────────────────────────────────────

@dataclass
class UpdateMeta:
    last_updated: str = ""
    source_distribution: dict[str, float] = field(default_factory=dict)
    update_count: int = 0


# ── Full profile ─────────────────────────────────────────────────

LAYER_NAMES = (
    "identity", "goals", "interests",
    "capabilities", "decision", "behavior",
)

LAYER_UPDATE_CADENCE: dict[str, int] = {
    "identity": 7,
    "goals": 7,
    "interests": 1,
    "capabilities": 14,
    "decision": 30,
    "behavior": 1,
}

STABLE_LAYERS = {"identity", "goals", "capabilities", "decision"}
DYNAMIC_LAYERS = {"interests", "behavior"}


@dataclass
class PersonaProfile:
    version: str = "1.0"
    schema_version: int = 1
    confidence_score: float = 0.0
    identity: IdentityLayer = field(default_factory=IdentityLayer)
    goals: GoalLayer = field(default_factory=GoalLayer)
    interests: InterestLayer = field(default_factory=InterestLayer)
    capabilities: CapabilityLayer = field(default_factory=CapabilityLayer)
    decision: DecisionLayer = field(default_factory=DecisionLayer)
    behavior: BehaviorLayer = field(default_factory=BehaviorLayer)
    update_meta: UpdateMeta = field(default_factory=UpdateMeta)

    def get_layer(self, name: str) -> _LayerBase:
        if name not in LAYER_NAMES:
            raise ValueError(f"Unknown layer: {name}")
        return getattr(self, name)

    def set_layer(self, name: str, layer: _LayerBase) -> None:
        if name not in LAYER_NAMES:
            raise ValueError(f"Unknown layer: {name}")
        setattr(self, name, layer)

    def overall_confidence(self) -> float:
        layers = [self.get_layer(n) for n in LAYER_NAMES]
        confs = [l.confidence for l in layers if l.confidence > 0]
        return sum(confs) / len(confs) if confs else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence_score"] = self.overall_confidence()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PersonaProfile":
        p = cls()
        if not data:
            return p
        p.version = data.get("version", "1.0")
        p.schema_version = data.get("schema_version", 1)

        layer_cls_map = {
            "identity": IdentityLayer,
            "goals": GoalLayer,
            "interests": InterestLayer,
            "capabilities": CapabilityLayer,
            "decision": DecisionLayer,
            "behavior": BehaviorLayer,
        }
        for name, klass in layer_cls_map.items():
            layer_data = data.get(name, {})
            if isinstance(layer_data, dict):
                safe = {k: v for k, v in layer_data.items()
                        if k in klass.__dataclass_fields__}
                setattr(p, name, klass(**safe))

        meta = data.get("update_meta", {})
        if isinstance(meta, dict):
            safe = {k: v for k, v in meta.items()
                    if k in UpdateMeta.__dataclass_fields__}
            p.update_meta = UpdateMeta(**safe)
        return p
