"""Automatic pruning logic for Capability Forest.

Moves active capabilities to dormant when they haven't been used in
a configurable window (default 30 days).

Seasonal capabilities (tagged with "seasonal" or "annual") get a
longer threshold (90 days) before pruning.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from myxai_desk.apps.cap_forest.dao import (
    _log_event,
    init_cap_forest_tables,
    list_states,
    set_state,
)
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai.cap_forest.pruner")

DEFAULT_PRUNE_DAYS = 30
SEASONAL_PRUNE_DAYS = 90
_SEASONAL_TAGS = {"seasonal", "annual", "yearly", "quarterly", "tax", "year_end"}


def run_prune(prune_days: int = DEFAULT_PRUNE_DAYS) -> dict:
    """Prune stale active capabilities to dormant.

    Returns a summary dict with the list of pruned cap_ids.
    """
    init_cap_forest_tables()
    now = datetime.now(timezone.utc)
    pruned: list[str] = []
    skipped: list[str] = []

    for row in list_states("active"):
        cap_id = row["cap_id"]
        use_count = row.get("use_count_30d", 0) or 0
        last_used = row.get("last_used_at", "")

        if use_count > 0:
            continue

        if not last_used:
            continue

        try:
            last_dt = datetime.fromisoformat(last_used)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age_days = (now - last_dt).days
        except Exception:
            continue

        threshold = _get_threshold(cap_id, prune_days)

        if age_days < threshold:
            skipped.append(cap_id)
            continue

        # Core capabilities are never auto-pruned
        cap_type_rows = execute(
            "SELECT cap_type FROM cap_registry WHERE cap_id = ?",
            (cap_id,),
            readonly=True,
        )
        if cap_type_rows and cap_type_rows[0].get("cap_type") == "core":
            skipped.append(cap_id)
            continue

        set_state(cap_id, "dormant", enabled=0)
        _log_event("prune_to_dormant", cap_id, {
            "age_days": age_days,
            "threshold": threshold,
            "use_count_30d": use_count,
        })
        pruned.append(cap_id)

    summary = {
        "pruned": pruned,
        "count": len(pruned),
        "skipped": len(skipped),
        "threshold_days": prune_days,
    }
    if pruned:
        log.info("[pruner] pruned %d capabilities: %s", len(pruned), pruned)
    return summary


def _get_threshold(cap_id: str, default: int) -> int:
    """Return the prune threshold in days, longer for seasonal capabilities."""
    rows = execute(
        "SELECT tags_json FROM cap_registry WHERE cap_id = ?",
        (cap_id,),
        readonly=True,
    )
    if not rows:
        return default
    try:
        tags = set(json.loads(rows[0].get("tags_json", "[]") or "[]"))
    except Exception:
        tags = set()
    if tags & _SEASONAL_TAGS:
        return max(default, SEASONAL_PRUNE_DAYS)
    return default
