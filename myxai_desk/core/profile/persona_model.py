"""Simplified two-output persona model.

Only two products:
  - StablePersona  — long-term identity, goals, capabilities, preferences
  - RecentSnapshot — 7-day interest trends, active project, recommendations
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class StablePersona:
    """Long-term stable user profile (signals persisting 7+ days)."""

    identity_role: str = ""
    long_term_goals: list[str] = field(default_factory=list)
    capability_assessment: str = ""
    decision_preference: str = ""
    output_constraints: list[str] = field(default_factory=list)
    prompt_text: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> StablePersona:
        if not data:
            return cls()
        safe = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**safe)

    def is_empty(self) -> bool:
        return not self.prompt_text and not self.identity_role


@dataclass
class TopicEntry:
    topic: str = ""
    trend: str = ""  # "升温" | "稳定"
    evidence: str = ""


@dataclass
class RecentSnapshot:
    """7-day interest snapshot for recommendations."""

    core_topics: list[dict] = field(default_factory=list)
    active_project: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    prompt_text: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> RecentSnapshot:
        if not data:
            return cls()
        safe = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**safe)

    def is_empty(self) -> bool:
        return not self.prompt_text and not self.core_topics
