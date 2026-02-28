"""Capability-based tool router for Capability Forest.

Replaces / wraps the existing ``_filter_tool_defs_for_message()`` and
Intent Engine ``filter_tools()`` with a forest-aware approach:

  Routing set = Core (always) + Active + Trial (high-confidence only)
  Dormant capabilities are excluded by default but may be woken once.

This module is opt-in: enabled only when the cap_forest app is installed
and ``routing_enabled`` is True in its config.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from myxai_desk.apps.cap_forest.dao import (
    _log_event,
    get_state,
    init_cap_forest_tables,
    record_usage,
)
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai.cap_forest.router")

# Per-session wake-once set (cleared after each execution turn)
_wake_once_lock = threading.Lock()
_wake_once_caps: set[str] = set()

# Confidence threshold for trial capabilities to participate
_TRIAL_CONF_THRESHOLD = 0.75


def cap_forest_enabled() -> bool:
    """Check whether the Capability Forest routing is active."""
    try:
        from myxai_desk.web.apps_helpers import load_apps_registry
        reg = load_apps_registry()
        entry = reg.get("cap_forest")
        if not entry:
            return False
        return entry.get("enabled", False)
    except Exception:
        return False


def capability_router(
    user_text: str,
    intent_result: Any | None,
    all_tool_defs: list[dict],
) -> list[dict]:
    """Filter *all_tool_defs* based on the forest state.

    Parameters
    ----------
    user_text : str
        The user's message text.
    intent_result : PredictResult | None
        Output from the Intent Engine's ``predict()``.  May be None.
    all_tool_defs : list[dict]
        Full set of tool definitions from the agent.

    Returns
    -------
    list[dict]
        Filtered tool definitions that should be exposed this turn.
    """
    init_cap_forest_tables()

    allowed_tools = _collect_allowed_tools(intent_result)

    if not allowed_tools:
        return all_tool_defs

    return [
        d for d in all_tool_defs
        if d.get("function", {}).get("name", "") in allowed_tools
    ]


def _collect_allowed_tools(intent_result: Any | None) -> set[str]:
    """Build the set of tool names allowed this turn."""
    rows = execute(
        """SELECT s.cap_id, s.state, s.enabled, r.entrypoints_json
           FROM cap_state s
           JOIN cap_registry r ON s.cap_id = r.cap_id
           WHERE s.enabled = 1""",
        readonly=True,
    )

    route_conf = 0.0
    if intent_result and hasattr(intent_result, "confidence"):
        route_conf = intent_result.confidence or 0.0

    allowed: set[str] = set()

    for row in rows:
        state = row["state"]
        try:
            eps = json.loads(row.get("entrypoints_json", "[]") or "[]")
        except Exception:
            eps = []

        if state == "active":
            allowed.update(eps)
        elif state == "trial":
            if route_conf >= _TRIAL_CONF_THRESHOLD:
                allowed.update(eps)

    # Wake-once additions
    with _wake_once_lock:
        for cap_id in _wake_once_caps:
            cap_row = execute(
                "SELECT entrypoints_json FROM cap_registry WHERE cap_id = ?",
                (cap_id,),
                readonly=True,
            )
            if cap_row:
                try:
                    eps = json.loads(cap_row[0].get("entrypoints_json", "[]") or "[]")
                    allowed.update(eps)
                except Exception:
                    pass

    return allowed


def add_wake_once(cap_id: str) -> None:
    """Mark a dormant capability for one-time participation in this turn."""
    with _wake_once_lock:
        _wake_once_caps.add(cap_id)
    _log_event("wake_once", cap_id, {"reason": "router"})


def clear_wake_once() -> None:
    """Clear the wake-once set after the execution turn completes."""
    with _wake_once_lock:
        _wake_once_caps.clear()


def suggest_wake(
    user_text: str,
    intent_result: Any | None,
) -> list[dict]:
    """Check if any dormant capability strongly matches the current task.

    Returns a list of suggestions (cap_id + name + reason) that the
    front-end can show as a non-intrusive prompt bar.
    """
    init_cap_forest_tables()

    dormant_rows = execute(
        """SELECT s.cap_id, r.name, r.intents_json, r.entities_json, r.tags_json
           FROM cap_state s
           JOIN cap_registry r ON s.cap_id = r.cap_id
           WHERE s.state = 'dormant'""",
        readonly=True,
    )

    if not dormant_rows:
        return []

    route_labels: set[str] = set()
    if intent_result:
        if hasattr(intent_result, "labels"):
            route_labels = set(intent_result.labels or [])
        elif hasattr(intent_result, "route_labels"):
            route_labels = set(intent_result.route_labels or [])

    suggestions: list[dict] = []
    for row in dormant_rows:
        try:
            intents = set(json.loads(row.get("intents_json", "[]") or "[]"))
        except Exception:
            intents = set()

        overlap = intents & route_labels
        if not overlap:
            continue

        suggestions.append({
            "cap_id": row["cap_id"],
            "name": row.get("name", row["cap_id"]),
            "matched_intents": list(overlap),
            "reason": f"Dormant capability matches intent(s): {', '.join(overlap)}",
        })

    return suggestions[:3]


def on_tool_used(tool_name: str, success: bool) -> None:
    """Record tool usage back to the owning capability's state."""
    init_cap_forest_tables()
    cap_row = execute(
        """SELECT r.cap_id
           FROM cap_registry r
           WHERE r.entrypoints_json LIKE ?
           LIMIT 1""",
        (f'%"{tool_name}"%',),
        readonly=True,
    )
    if cap_row:
        record_usage(cap_row[0]["cap_id"], success)
