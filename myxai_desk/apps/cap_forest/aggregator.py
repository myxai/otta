"""Behavioural signal aggregator for Capability Forest.

Collects statistics from ie_runs and er_steps, maps them back
to registered capabilities via intent labels and tool entrypoints,
then updates cap_state metrics (use_count_30d, success_count_30d, …).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict

from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai.cap_forest.aggregator")


def aggregate_signals(days: int = 30) -> dict:
    """Aggregate the last *days* of ie_runs + er_steps into cap_state.

    Returns a summary dict for diagnostics / API response.
    """
    from myxai_desk.apps.cap_forest.dao import (
        init_cap_forest_tables,
        list_registry,
        update_state_fields,
    )

    init_cap_forest_tables()

    # 1. Build lookup: intent_label -> cap_id, entrypoint -> cap_id
    intent_to_cap: dict[str, str] = {}
    tool_to_cap: dict[str, str] = {}
    registry = list_registry()
    for cap in registry:
        cap_id = cap["cap_id"]
        try:
            intents = json.loads(cap.get("intents_json", "[]") or "[]")
        except Exception:
            intents = []
        for intent in intents:
            intent_to_cap[intent] = cap_id
        try:
            eps = json.loads(cap.get("entrypoints_json", "[]") or "[]")
        except Exception:
            eps = []
        for ep in eps:
            tool_to_cap[ep] = cap_id

    # 2. Aggregate ie_runs for the last N days
    ie_rows = execute(
        """SELECT route_label, outcome, effective_steps, llm_attempts
           FROM ie_runs
           WHERE local_date >= date('now', ?)""",
        (f"-{days} days",),
        readonly=True,
    )

    cap_stats: dict[str, dict] = defaultdict(lambda: {
        "use": 0, "success": 0,
        "steps_sum": 0.0, "steps_count": 0,
        "fallback_sum": 0.0, "fallback_count": 0,
    })

    for row in ie_rows:
        labels = (row.get("route_label") or "fs").split(",")
        for lb in labels:
            lb = lb.strip() or "fs"
            cap_id = intent_to_cap.get(lb)
            if not cap_id:
                continue
            s = cap_stats[cap_id]
            s["use"] += 1
            if row.get("outcome") == "success":
                s["success"] += 1
            eff = row.get("effective_steps")
            if eff is not None and eff > 0:
                s["steps_sum"] += eff
                s["steps_count"] += 1
            llm = row.get("llm_attempts")
            if llm is not None:
                s["fallback_sum"] += llm
                s["fallback_count"] += 1

    # 3. Aggregate er_steps for tool-level usage
    er_rows = execute(
        """SELECT tool_name, status FROM er_steps
           WHERE created_at >= datetime('now', ?)""",
        (f"-{days} days",),
        readonly=True,
    )

    for row in er_rows:
        tool = row.get("tool_name", "")
        cap_id = tool_to_cap.get(tool)
        if not cap_id:
            continue
        s = cap_stats[cap_id]
        s["use"] += 1
        if row.get("status") == "ok":
            s["success"] += 1

    # 4. Write back to cap_state
    updated: list[str] = []
    for cap_id, s in cap_stats.items():
        avg_steps = (s["steps_sum"] / s["steps_count"]) if s["steps_count"] else 0
        avg_fallback = (s["fallback_sum"] / s["fallback_count"]) if s["fallback_count"] else 0
        update_state_fields(
            cap_id,
            use_count_30d=s["use"],
            success_count_30d=s["success"],
            avg_effective_steps_30d=round(avg_steps, 2),
            avg_llm_fallback_30d=round(avg_fallback, 2),
        )
        updated.append(cap_id)

    summary = {
        "days": days,
        "ie_runs_scanned": len(ie_rows),
        "er_steps_scanned": len(er_rows),
        "caps_updated": updated,
    }
    log.info("[aggregator] %s", summary)
    return summary


def compute_intent_distribution(days: int = 30) -> dict[str, int]:
    """Return route_label frequency distribution for the last N days."""
    rows = execute(
        """SELECT route_label, COUNT(*) AS cnt
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY route_label
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )
    dist: dict[str, int] = {}
    for r in rows:
        labels = (r.get("route_label") or "fs").split(",")
        for lb in labels:
            lb = lb.strip() or "fs"
            dist[lb] = dist.get(lb, 0) + r["cnt"]
    return dist


def compute_tool_frequency(days: int = 30) -> dict[str, int]:
    """Return tool call frequency from er_steps for the last N days."""
    rows = execute(
        """SELECT tool_name, COUNT(*) AS cnt
           FROM er_steps
           WHERE created_at >= datetime('now', ?)
           GROUP BY tool_name
           ORDER BY cnt DESC""",
        (f"-{days} days",),
        readonly=True,
    )
    return {r["tool_name"]: r["cnt"] for r in rows}
