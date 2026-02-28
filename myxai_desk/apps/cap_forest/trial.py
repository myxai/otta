"""Trial evaluation logic for Capability Forest.

A capability in 'trial' state is observed for 7 days or 10 invocations.
If it passes the evaluation criteria, it is promoted to 'active';
otherwise it moves to 'dormant'.

Trial participation rule:
  Only activated when intent_confidence >= 0.75 AND intent matches.

Promotion criteria (any 2 of 4):
  1. Success rate improvement >= 10%
  2. Average effective steps decrease >= 1.0
  3. LLM fallback decrease >= 20%
  4. User actively retained (not manually stopped + has sustained usage)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from myxai_desk.apps.cap_forest.dao import (
    _log_event,
    get_state,
    init_cap_forest_tables,
    list_states,
    set_state,
    update_state_fields,
)
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai.cap_forest.trial")

TRIAL_MAX_DAYS = 7
TRIAL_MAX_USES = 10

_SUCCESS_RATE_THRESHOLD = 0.10
_STEPS_DECREASE_THRESHOLD = 1.0
_FALLBACK_DECREASE_THRESHOLD = 0.20
_MIN_CRITERIA_PASS = 2


def evaluate_trials() -> list[dict]:
    """Evaluate all capabilities in 'trial' state.

    Returns a list of dicts describing the outcome for each capability.
    """
    init_cap_forest_tables()
    results: list[dict] = []
    now = datetime.now(timezone.utc)

    for row in list_states("trial"):
        cap_id = row["cap_id"]
        trial_start = row.get("trial_started_at", "")
        use_count = row.get("use_count_30d", 0) or 0

        # Check if trial window has elapsed
        window_expired = False
        if trial_start:
            try:
                started = datetime.fromisoformat(trial_start)
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                window_expired = (now - started).days >= TRIAL_MAX_DAYS
            except Exception:
                window_expired = False

        usage_expired = use_count >= TRIAL_MAX_USES

        if not (window_expired or usage_expired):
            results.append({
                "cap_id": cap_id,
                "action": "continue",
                "reason": "trial window not yet complete",
                "days_elapsed": _days_since(trial_start),
                "use_count": use_count,
            })
            continue

        outcome = _evaluate_single(cap_id, row)
        results.append(outcome)

    return results


def _evaluate_single(cap_id: str, state_row: dict) -> dict:
    """Evaluate one trial capability against promotion criteria."""
    criteria_met = 0
    details: dict[str, bool] = {}

    baseline = _get_baseline_metrics(cap_id)
    trial_metrics = _get_trial_metrics(cap_id, state_row.get("trial_started_at", ""))

    # Criterion 1: Success rate improvement
    base_sr = baseline.get("success_rate", 0)
    trial_sr = trial_metrics.get("success_rate", 0)
    sr_improved = (trial_sr - base_sr) >= _SUCCESS_RATE_THRESHOLD
    details["success_rate_improved"] = sr_improved
    if sr_improved:
        criteria_met += 1

    # Criterion 2: Effective steps decrease
    base_steps = baseline.get("avg_steps", 0)
    trial_steps = trial_metrics.get("avg_steps", 0)
    steps_decreased = (base_steps - trial_steps) >= _STEPS_DECREASE_THRESHOLD if base_steps > 0 else False
    details["steps_decreased"] = steps_decreased
    if steps_decreased:
        criteria_met += 1

    # Criterion 3: LLM fallback decrease
    base_fb = baseline.get("avg_fallback", 0)
    trial_fb = trial_metrics.get("avg_fallback", 0)
    fb_decreased = (base_fb - trial_fb) / base_fb >= _FALLBACK_DECREASE_THRESHOLD if base_fb > 0 else False
    details["fallback_decreased"] = fb_decreased
    if fb_decreased:
        criteria_met += 1

    # Criterion 4: User actively retained
    use_count = state_row.get("use_count_30d", 0) or 0
    retained = use_count >= 3
    details["user_retained"] = retained
    if retained:
        criteria_met += 1

    promoted = criteria_met >= _MIN_CRITERIA_PASS
    new_state = "active" if promoted else "dormant"
    set_state(cap_id, new_state, enabled=1 if promoted else 0)

    _log_event(
        "trial_promote" if promoted else "trial_demote",
        cap_id,
        {
            "criteria_met": criteria_met,
            "details": details,
            "baseline": baseline,
            "trial_metrics": trial_metrics,
        },
    )

    return {
        "cap_id": cap_id,
        "action": "promote" if promoted else "dormant",
        "criteria_met": criteria_met,
        "details": details,
        "baseline": baseline,
        "trial_metrics": trial_metrics,
    }


def get_trial_stats(cap_id: str) -> dict:
    """Return trial-period statistics for a specific capability."""
    init_cap_forest_tables()
    state_row = get_state(cap_id)
    if not state_row:
        return {"error": "not found"}

    trial_start = state_row.get("trial_started_at", "")
    baseline = _get_baseline_metrics(cap_id)
    trial_metrics = _get_trial_metrics(cap_id, trial_start)

    return {
        "cap_id": cap_id,
        "state": state_row["state"],
        "trial_started_at": trial_start,
        "days_elapsed": _days_since(trial_start),
        "use_count": state_row.get("use_count_30d", 0),
        "baseline": baseline,
        "trial_metrics": trial_metrics,
        "window": {"max_days": TRIAL_MAX_DAYS, "max_uses": TRIAL_MAX_USES},
    }


# ── Internal helpers ──────────────────────────────────────────────


def _get_baseline_metrics(cap_id: str) -> dict:
    """Metrics before trial started (overall system averages)."""
    rows = execute(
        """SELECT
             AVG(CASE WHEN outcome='success' THEN 1.0 ELSE 0.0 END) AS success_rate,
             AVG(CASE WHEN effective_steps > 0 THEN effective_steps END) AS avg_steps,
             AVG(COALESCE(llm_attempts, 1)) AS avg_fallback
           FROM ie_runs
           WHERE local_date >= date('now', '-60 days')""",
        readonly=True,
    )
    r = rows[0] if rows else {}
    return {
        "success_rate": round(r.get("success_rate", 0) or 0, 3),
        "avg_steps": round(r.get("avg_steps", 0) or 0, 2),
        "avg_fallback": round(r.get("avg_fallback", 0) or 0, 2),
    }


def _get_trial_metrics(cap_id: str, trial_start: str) -> dict:
    """Metrics since the trial started, scoped to the cap's intents."""
    if not trial_start:
        return {"success_rate": 0, "avg_steps": 0, "avg_fallback": 0}

    cap_row = execute(
        "SELECT intents_json FROM cap_registry WHERE cap_id = ?",
        (cap_id,),
        readonly=True,
    )
    if not cap_row:
        return {"success_rate": 0, "avg_steps": 0, "avg_fallback": 0}

    try:
        intents = json.loads(cap_row[0].get("intents_json", "[]") or "[]")
    except Exception:
        intents = []

    if not intents:
        return {"success_rate": 0, "avg_steps": 0, "avg_fallback": 0}

    # Build a WHERE clause for matching route_labels
    like_clauses = " OR ".join(
        f"route_label LIKE '%{intent}%'" for intent in intents
    )

    rows = execute(
        f"""SELECT
              AVG(CASE WHEN outcome='success' THEN 1.0 ELSE 0.0 END) AS success_rate,
              AVG(CASE WHEN effective_steps > 0 THEN effective_steps END) AS avg_steps,
              AVG(COALESCE(llm_attempts, 1)) AS avg_fallback
            FROM ie_runs
            WHERE created_at >= ? AND ({like_clauses})""",
        (trial_start,),
        readonly=True,
    )
    r = rows[0] if rows else {}
    return {
        "success_rate": round(r.get("success_rate", 0) or 0, 3),
        "avg_steps": round(r.get("avg_steps", 0) or 0, 2),
        "avg_fallback": round(r.get("avg_fallback", 0) or 0, 2),
    }


def _days_since(iso_ts: str) -> int:
    if not iso_ts:
        return 0
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0
