"""Intent Engine configuration — switches and thresholds.

All config is stored in ``desk_settings.json`` under the ``intent_engine`` key.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

log = logging.getLogger("myxai")

_SETTINGS_FILE = Path.home() / ".nanobot" / "desk_settings.json"
_lock = Lock()

_DEFAULTS: dict[str, Any] = {
    "routing_enabled": True,
    "golden_enabled": True,
    "base_tools_always_included": ["exec", "read_file", "list_dir"],
    "route_conf_low": 0.4,
    "hints_max_length": 600,
    "high_risk_tools": ["exec"],
    "router_model": "",  # cheap/fast model for LLM arbitration; empty = use main model
    # Nightly semantic learning
    "nightly_learning_enabled": False,
    "nightly_learning_use_llm": True,
    "nightly_learning_sanitize_pii": True,
    "nightly_learning_max_samples": 200,
    "nightly_learning_min_runs": 20,
    "nightly_learning_min_misroutes": 5,
}


def _load_all_settings() -> dict:
    try:
        if _SETTINGS_FILE.exists():
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        log.warning("[ie_config] failed to load desk_settings.json", exc_info=True)
    return {}


def _save_all_settings(data: dict) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        log.warning("[ie_config] failed to save desk_settings.json", exc_info=True)


def get(key: str | None = None) -> Any:
    """Return a single config value or the whole intent_engine section."""
    all_cfg = _load_all_settings()
    ie = {**_DEFAULTS, **all_cfg.get("intent_engine", {})}
    # Migrate legacy split keys → unified golden_enabled
    if "golden_enabled" not in ie or "golden_enabled" not in all_cfg.get("intent_engine", {}):
        if "golden_replay_enabled" in ie or "golden_v2_enabled" in ie:
            ie["golden_enabled"] = ie.pop("golden_replay_enabled", True) and ie.pop("golden_v2_enabled", True)
    ie.pop("golden_replay_enabled", None)
    ie.pop("golden_v2_enabled", None)
    if key is None:
        return ie
    if key in ("golden_replay_enabled", "golden_v2_enabled"):
        return ie.get("golden_enabled", True)
    return ie.get(key, _DEFAULTS.get(key))


def set_values(updates: dict[str, Any]) -> dict:
    """Merge *updates* into the intent_engine config and persist."""
    # Map legacy split keys to unified key
    if "golden_replay_enabled" in updates or "golden_v2_enabled" in updates:
        val = updates.pop("golden_replay_enabled", None)
        if val is None:
            val = updates.pop("golden_v2_enabled", None)
        else:
            updates.pop("golden_v2_enabled", None)
        if val is not None:
            updates["golden_enabled"] = bool(val)
    with _lock:
        all_cfg = _load_all_settings()
        ie = all_cfg.setdefault("intent_engine", {})
        ie.update(updates)
        # Clean up legacy keys on write
        ie.pop("golden_replay_enabled", None)
        ie.pop("golden_v2_enabled", None)
        _save_all_settings(all_cfg)
    return get()


def routing_enabled() -> bool:
    return bool(get("routing_enabled"))


def golden_enabled() -> bool:
    return bool(get("golden_enabled"))


# Backward-compatible aliases
golden_replay_enabled = golden_enabled
golden_v2_enabled = golden_enabled
