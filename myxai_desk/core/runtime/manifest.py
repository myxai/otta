"""Prompt App manifest (app.yaml) parser and validation.

A Prompt App package is a directory containing:
  - ``app.yaml`` — manifest describing the app, permissions, triggers, etc.
  - ``prompt.md`` — the prompt template
  - (optional) additional assets
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass
class TriggerSpec:
    type: str  # "cron" | "manual" | "event"
    cron: str = ""
    event: str = ""


@dataclass
class BudgetSpec:
    tokens_per_day: int = 0
    search_calls_per_day: int = 0


@dataclass
class DataPolicySpec:
    allow_raw_history: bool = False
    allow_network_exfiltration: bool = False


@dataclass
class OutputSpec:
    type: str = "report.html"
    path: str = ""


@dataclass
class UISpec:
    icon: str = ""
    category: str = "general"


@dataclass
class AppManifest:
    id: str
    name: str
    version: str = "1.0.0"
    source: Literal["official", "user", "third_party"] = "official"
    entry: str = "prompt"
    prompt_file: str = "prompt.md"
    description: str = ""
    description_en: str = ""
    author: str = ""
    triggers: list[TriggerSpec] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    budgets: BudgetSpec = field(default_factory=BudgetSpec)
    mode_requirements: dict[str, str] = field(default_factory=lambda: {"min_mode": "Observer"})
    data_policy: DataPolicySpec = field(default_factory=DataPolicySpec)
    outputs: list[OutputSpec] = field(default_factory=list)
    ui: UISpec = field(default_factory=UISpec)

    # Runtime-resolved paths
    package_dir: Path | None = None
    prompt_content: str = ""


def load_manifest(package_dir: Path) -> AppManifest:
    """Load and validate an ``app.yaml`` from *package_dir*."""
    yaml_path = package_dir / "app.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No app.yaml in {package_dir}")

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid app.yaml: expected dict, got {type(raw).__name__}")

    manifest = AppManifest(
        id=raw["id"],
        name=raw.get("name", raw["id"]),
        version=raw.get("version", "1.0.0"),
        source=raw.get("source", "user"),
        entry=raw.get("entry", "prompt"),
        prompt_file=raw.get("prompt_file", "prompt.md"),
        description=raw.get("description", ""),
        description_en=raw.get("description_en", ""),
        author=raw.get("author", ""),
    )

    # Triggers
    for t in raw.get("triggers", []):
        manifest.triggers.append(TriggerSpec(
            type=t.get("type", "manual"),
            cron=t.get("cron", ""),
            event=t.get("event", ""),
        ))

    # Permissions
    manifest.permissions = raw.get("permissions", [])

    # Budgets
    b = raw.get("budgets", {})
    manifest.budgets = BudgetSpec(
        tokens_per_day=b.get("tokens_per_day", 0),
        search_calls_per_day=b.get("search_calls_per_day", 0),
    )

    # Mode requirements
    manifest.mode_requirements = raw.get("mode_requirements", {"min_mode": "Observer"})

    # Data policy
    dp = raw.get("data_policy", {})
    manifest.data_policy = DataPolicySpec(
        allow_raw_history=dp.get("allow_raw_history", False),
        allow_network_exfiltration=dp.get("allow_network_exfiltration", False),
    )

    # Outputs
    for o in raw.get("outputs", []):
        manifest.outputs.append(OutputSpec(
            type=o.get("type", "report.html"),
            path=o.get("path", ""),
        ))

    # UI
    ui = raw.get("ui", {})
    manifest.ui = UISpec(
        icon=ui.get("icon", ""),
        category=ui.get("category", "general"),
    )

    manifest.package_dir = package_dir

    # Load prompt file
    prompt_path = package_dir / manifest.prompt_file
    if prompt_path.exists():
        manifest.prompt_content = prompt_path.read_text(encoding="utf-8")

    return manifest


def manifest_to_dict(m: AppManifest) -> dict:
    """Serialise a manifest for API responses."""
    return {
        "id": m.id,
        "name": m.name,
        "version": m.version,
        "source": m.source,
        "entry": m.entry,
        "description": m.description,
        "description_en": m.description_en,
        "author": m.author,
        "permissions": m.permissions,
        "triggers": [{"type": t.type, "cron": t.cron} for t in m.triggers],
        "budgets": {"tokens_per_day": m.budgets.tokens_per_day,
                    "search_calls_per_day": m.budgets.search_calls_per_day},
        "mode_requirements": m.mode_requirements,
        "data_policy": {"allow_raw_history": m.data_policy.allow_raw_history,
                        "allow_network_exfiltration": m.data_policy.allow_network_exfiltration},
        "outputs": [{"type": o.type, "path": o.path} for o in m.outputs],
        "ui": {"icon": m.ui.icon, "category": m.ui.category},
    }
