"""Update engine — orchestrates layer updates with confidence gating.

Responsibilities:
  1. Collect fresh events from all sources
  2. Decide which layers are due for an update (cadence check)
  3. Run the appropriate layer engine
  4. Apply confidence gating for stable layers (>0.7)
  5. Persist the updated profile and write audit entries
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from myxai_desk.core.profile.events import EventStore
from myxai_desk.core.profile.persona_model import (
    PersonaProfile,
    LAYER_NAMES,
    LAYER_UPDATE_CADENCE,
    STABLE_LAYERS,
)
from myxai_desk.core.profile import persona_store, persona_audit
from myxai_desk.core.profile.layers import (
    interest_layer,
    identity_layer,
    goal_layer,
    capability_layer,
    decision_layer,
    behavior_layer,
)

CONFIDENCE_THRESHOLD = 0.7

_LAYER_ENGINES = {
    "identity": identity_layer,
    "goals": goal_layer,
    "interests": interest_layer,
    "capabilities": capability_layer,
    "decision": decision_layer,
    "behavior": behavior_layer,
}


def _is_due(layer_name: str, profile: PersonaProfile) -> bool:
    """Check whether *layer_name* is due for an update based on its cadence."""
    layer = profile.get_layer(layer_name)
    if not layer.last_updated:
        return True
    try:
        last = datetime.fromisoformat(layer.last_updated.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True
    cadence_days = LAYER_UPDATE_CADENCE.get(layer_name, 7)
    return datetime.now(timezone.utc) - last >= timedelta(days=cadence_days)


def _collect_events(store: EventStore, days: int = 7) -> list[dict]:
    """Run all enabled collectors and return accumulated events."""
    try:
        from myxai_desk.core.capabilities.profile import Profile
        settings = Profile().get_collection_settings()
    except Exception:
        settings = {}

    collect_days = min(days, 7)

    if settings.get("browser_history", True):
        try:
            from myxai_desk.core.profile.collectors.browser import collect_to_events
            collect_to_events(hours=collect_days * 24, store=store)
        except Exception as e:
            print(f"[update_engine] Browser collect failed: {e}")

    if settings.get("chat_history", True):
        try:
            from myxai_desk.core.profile.collectors.chat import collect_to_events as chat_collect
            chat_collect(hours=collect_days * 24, store=store)
        except Exception as e:
            print(f"[update_engine] Chat collect failed: {e}")

    if settings.get("file_history") and settings.get("watch_paths"):
        try:
            from myxai_desk.core.profile.collectors.file_scanner import scan_file_changes
            scan_file_changes(settings["watch_paths"], days=collect_days, store=store)
        except Exception as e:
            print(f"[update_engine] File scan failed: {e}")

    return store.recent(n=500)


def run_full_update(
    *,
    force: bool = False,
    store: EventStore | None = None,
) -> dict[str, Any]:
    """Run a full persona update cycle.

    Returns a summary dict with per-layer results.
    """
    store = store or EventStore()
    profile = persona_store.load()

    store.clear()
    events = _collect_events(store)

    if not events:
        return {"updated_layers": [], "skipped": list(LAYER_NAMES), "reason": "no_events"}

    results: dict[str, Any] = {"updated_layers": [], "skipped": [], "gated": []}

    for name in LAYER_NAMES:
        if not force and not _is_due(name, profile):
            results["skipped"].append(name)
            continue

        engine = _LAYER_ENGINES.get(name)
        if not engine:
            results["skipped"].append(name)
            continue

        current_layer = profile.get_layer(name)
        new_layer = engine.update(events, current_layer)

        if name in STABLE_LAYERS and new_layer.confidence < CONFIDENCE_THRESHOLD:
            if current_layer.last_updated:
                results["gated"].append({
                    "layer": name,
                    "confidence": new_layer.confidence,
                    "threshold": CONFIDENCE_THRESHOLD,
                })
                continue

        old_dict = {k: v for k, v in current_layer.__dict__.items()
                    if k not in ("confidence", "last_updated", "signal_count")}
        new_dict = {k: v for k, v in new_layer.__dict__.items()
                    if k not in ("confidence", "last_updated", "signal_count")}

        changed_fields = [k for k in new_dict if new_dict.get(k) != old_dict.get(k)]

        profile.set_layer(name, new_layer)
        results["updated_layers"].append(name)

        if changed_fields:
            persona_audit.record(
                layer=name,
                fields=changed_fields,
                source="auto_update",
                confidence=new_layer.confidence,
                old_values={k: old_dict.get(k) for k in changed_fields},
                new_values={k: new_dict.get(k) for k in changed_fields},
            )

    browser_events = len([e for e in events if e.get("event_type") == "browser_visited"])
    chat_events = len([e for e in events if e.get("event_type") == "chat_message"])
    file_events = len([e for e in events if e.get("event_type") == "file_touched"])
    total = browser_events + chat_events + file_events or 1

    profile.update_meta.source_distribution = {
        "browser_metadata": round(browser_events / total, 2),
        "conversation_signal": round(chat_events / total, 2),
        "file_change_metadata": round(file_events / total, 2),
    }

    version = persona_store.save(profile, reason="full_update")
    results["version"] = version
    results["total_events"] = len(events)
    return results


def run_layer_update(
    layer_name: str,
    *,
    store: EventStore | None = None,
) -> dict[str, Any]:
    """Update a single layer (force, ignoring cadence)."""
    if layer_name not in LAYER_NAMES:
        return {"error": f"Unknown layer: {layer_name}"}

    store = store or EventStore()
    events = store.recent(n=500)
    if not events:
        store.clear()
        events = _collect_events(store)

    profile = persona_store.load()
    engine = _LAYER_ENGINES.get(layer_name)
    if not engine:
        return {"error": f"No engine for layer: {layer_name}"}

    current_layer = profile.get_layer(layer_name)
    new_layer = engine.update(events, current_layer)
    profile.set_layer(layer_name, new_layer)
    version = persona_store.save(profile, reason=f"layer_update:{layer_name}")

    persona_audit.record(
        layer=layer_name,
        fields=list(new_layer.__dict__.keys()),
        source="manual_layer_update",
        confidence=new_layer.confidence,
    )

    return {"layer": layer_name, "confidence": new_layer.confidence, "version": version}


def manual_update_layer(
    layer_name: str,
    patch: dict,
) -> dict[str, Any]:
    """Manually set fields on a layer (user-driven edits)."""
    if layer_name not in LAYER_NAMES:
        return {"error": f"Unknown layer: {layer_name}"}

    profile = persona_store.load()
    layer = profile.get_layer(layer_name)

    old_values = {}
    new_values = {}
    for key, value in patch.items():
        if hasattr(layer, key) and key not in ("confidence", "last_updated", "signal_count"):
            old_values[key] = getattr(layer, key)
            setattr(layer, key, value)
            new_values[key] = value

    layer.last_updated = datetime.now(timezone.utc).isoformat()
    profile.set_layer(layer_name, layer)
    version = persona_store.save(profile, reason=f"manual_edit:{layer_name}")

    if new_values:
        persona_audit.record(
            layer=layer_name,
            fields=list(new_values.keys()),
            source="manual",
            confidence=1.0,
            old_values=old_values,
            new_values=new_values,
            reason="user manual edit",
        )

    return {"layer": layer_name, "version": version, "updated_fields": list(new_values.keys())}
