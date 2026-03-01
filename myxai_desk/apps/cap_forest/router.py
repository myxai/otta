"""Capability Forest router — advisory mode.

Instead of directly overriding ``tool_defs``, the forest now produces
*recommendations* that the main pipeline can evaluate and optionally
apply.  This preserves the Intent Engine's authority over routing while
letting the forest contribute optimisation signals.

Public API
----------
- ``cap_forest_enabled()`` — feature gate
- ``capability_advise()`` — returns a ``CapAdvice`` with recommended caps / tools
- ``capability_router()`` — **legacy wrapper**, calls ``capability_advise``
  and filters tools only when ``advisory_only=False`` (default: True now)
- ``add_wake_once()`` / ``clear_wake_once()`` — per-turn wake mechanism
- ``suggest_wake()`` — find dormant caps matching the current intent
- ``on_tool_used()`` — feedback loop for usage recording
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from myxai_desk.apps.cap_forest.dao import (
    _log_event,
    get_state,
    init_cap_forest_tables,
    record_usage,
)
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai.cap_forest.router")

_wake_once_lock = threading.Lock()
_wake_once_caps: set[str] = set()

_TRIAL_CONF_THRESHOLD = 0.75


@dataclass
class CapAdvice:
    """Advisory output — what the forest *recommends* but does not enforce."""

    recommended_caps: list[dict] = field(default_factory=list)
    suggested_tools: set[str] = field(default_factory=set)
    wake_suggestions: list[dict] = field(default_factory=list)
    advisory_only: bool = True

    @property
    def has_suggestions(self) -> bool:
        return bool(self.suggested_tools) or bool(self.wake_suggestions)


def cap_forest_enabled() -> bool:
    """Check whether the Capability Forest app is active."""
    try:
        from myxai_desk.web.apps_helpers import load_apps_registry
        reg = load_apps_registry()
        entry = reg.get("cap_forest")
        if not entry:
            return False
        return entry.get("enabled", False)
    except Exception:
        return False


def capability_advise(
    user_text: str,
    intent_result: Any | None,
    all_tool_defs: list[dict] | None = None,
) -> CapAdvice:
    """Produce an advisory recommendation without mutating tool_defs.

    The caller decides whether to honour the advice.
    """
    init_cap_forest_tables()

    advice = CapAdvice()

    rows = execute(
        """SELECT s.cap_id, s.state, s.enabled, r.name,
                  r.entrypoints_json, r.intents_json
           FROM cap_state s
           JOIN cap_registry r ON s.cap_id = r.cap_id
           WHERE s.enabled = 1""",
        readonly=True,
    )

    route_conf = 0.0
    route_labels: set[str] = set()
    if intent_result:
        if hasattr(intent_result, "confidence"):
            route_conf = intent_result.confidence or 0.0
        if hasattr(intent_result, "route_labels"):
            route_labels = set(intent_result.route_labels or [])

    for row in rows:
        state = row["state"]
        try:
            eps = json.loads(row.get("entrypoints_json", "[]") or "[]")
        except Exception:
            eps = []
        try:
            intents = set(json.loads(row.get("intents_json", "[]") or "[]"))
        except Exception:
            intents = set()

        relevance = len(intents & route_labels) if route_labels else 0

        if state == "active":
            advice.recommended_caps.append({
                "cap_id": row["cap_id"],
                "name": row.get("name", row["cap_id"]),
                "state": state,
                "tools": eps,
                "relevance": relevance,
            })
            advice.suggested_tools.update(eps)
        elif state == "trial" and route_conf >= _TRIAL_CONF_THRESHOLD:
            advice.recommended_caps.append({
                "cap_id": row["cap_id"],
                "name": row.get("name", row["cap_id"]),
                "state": state,
                "tools": eps,
                "relevance": relevance,
            })
            advice.suggested_tools.update(eps)

    # Wake-once
    with _wake_once_lock:
        for cap_id in _wake_once_caps:
            cap_row = execute(
                "SELECT name, entrypoints_json FROM cap_registry WHERE cap_id = ?",
                (cap_id,),
                readonly=True,
            )
            if cap_row:
                try:
                    eps = json.loads(cap_row[0].get("entrypoints_json", "[]") or "[]")
                    advice.suggested_tools.update(eps)
                    advice.recommended_caps.append({
                        "cap_id": cap_id,
                        "name": cap_row[0].get("name", cap_id),
                        "state": "wake_once",
                        "tools": eps,
                        "relevance": 0,
                    })
                except Exception:
                    pass

    # Dormant wake suggestions
    advice.wake_suggestions = suggest_wake(user_text, intent_result)

    return advice


def capability_router(
    user_text: str,
    intent_result: Any | None,
    all_tool_defs: list[dict],
) -> list[dict]:
    """Legacy compatibility wrapper.

    Now runs in advisory mode: returns *all_tool_defs* unmodified and
    logs the advice.  This ensures the Intent Engine retains authority.
    """
    advice = capability_advise(user_text, intent_result, all_tool_defs)

    if advice.suggested_tools:
        log.info(
            "[cap_forest] advisory: %d caps recommend %d tools (not enforced)",
            len(advice.recommended_caps),
            len(advice.suggested_tools),
        )
        _log_event("advise", "router", {
            "recommended_count": len(advice.recommended_caps),
            "suggested_tool_count": len(advice.suggested_tools),
        })

    return all_tool_defs


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
