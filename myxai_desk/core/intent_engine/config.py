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
    "case_retrieval_enabled": False,
    "plan_reuse_enabled": False,
    "base_tools_always_included": ["exec", "read_file", "list_dir"],
    "route_conf_low": 0.4,
    "case_reuse_sim_threshold": 0.92,
    "hints_max_length": 600,
    "high_risk_tools": ["exec"],
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
    if key is None:
        return ie
    return ie.get(key, _DEFAULTS.get(key))


def set_values(updates: dict[str, Any]) -> dict:
    """Merge *updates* into the intent_engine config and persist."""
    with _lock:
        all_cfg = _load_all_settings()
        ie = all_cfg.setdefault("intent_engine", {})
        ie.update(updates)
        _save_all_settings(all_cfg)
    return get()


def routing_enabled() -> bool:
    return bool(get("routing_enabled"))


def case_retrieval_enabled() -> bool:
    return bool(get("case_retrieval_enabled"))


def plan_reuse_enabled() -> bool:
    return bool(get("plan_reuse_enabled"))
