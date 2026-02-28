"""Rule-based recommendation engine for Capability Forest.

Scoring formula:  score = 0.45 * demand + 0.35 * lift - 0.20 * penalty

Components:
  DemandMatch    (0~1)  — intent / entity / tag overlap with user activity
  ExpectedLift   (0~1)  — predicted improvement (step reduction, fallback reduction)
  CostRiskPenalty(0~1)  — setup friction + permission risk

Anti-disturbance:
  - At most 1 recommendation per day (or 2 per week)
  - Only surface Top 1~3
  - 3 consecutive dismissals of the same tag => 14-day cooldown
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from myxai_desk.apps.cap_forest.aggregator import (
    compute_intent_distribution,
    compute_tool_frequency,
)
from myxai_desk.apps.cap_forest.dao import (
    get_overview,
    get_state,
    init_cap_forest_tables,
    insert_reco,
    list_recos,
    list_registry,
    update_state_fields,
)
from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai.cap_forest.recommender")

_W_DEMAND = 0.45
_W_LIFT = 0.35
_W_PENALTY = 0.20

_MAX_DAILY_RECOS = 1
_DISMISS_COOLDOWN_DAYS = 14
_DISMISS_THRESHOLD = 3


def compute_recommendations(top_n: int = 3, days: int = 30) -> list[dict]:
    """Produce up to *top_n* capability recommendations.

    Only candidates (state == 'candidate' or not in cap_state at all)
    that are not blocked or already active/trial are considered.
    """
    init_cap_forest_tables()

    # Rate limit: skip if we already emitted today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recent = list_recos(status="shown", limit=5)
    today_count = sum(1 for r in recent if (r.get("created_at") or "")[:10] == today)
    if today_count >= _MAX_DAILY_RECOS:
        log.debug("[recommender] daily limit reached (%d)", today_count)
        return []

    # Build user activity profile
    intent_dist = compute_intent_distribution(days)
    tool_freq = compute_tool_frequency(days)

    # Compute per-intent average metrics for lift estimation
    intent_metrics = _compute_intent_metrics(days)

    # Dismissed tag cooldown
    cooled_tags = _get_cooled_tags()

    # Enumerate candidate capabilities
    registry = list_registry()
    overview = get_overview()
    active_ids = {c["cap_id"] for c in overview["active"]}
    trial_ids = {c["cap_id"] for c in overview["trial"]}
    blocked_ids = {c["cap_id"] for c in overview.get("blocked", [])}
    exclude = active_ids | trial_ids | blocked_ids

    scored: list[tuple[float, dict, dict]] = []

    for cap in registry:
        cap_id = cap["cap_id"]
        if cap_id in exclude:
            continue

        demand = _demand_match(cap, intent_dist, tool_freq)
        lift = _expected_lift(cap, intent_metrics)
        penalty = _cost_risk_penalty(cap)

        # Tag cooldown suppression
        try:
            tags = set(json.loads(cap.get("tags_json", "[]") or "[]"))
        except Exception:
            tags = set()
        if tags & cooled_tags:
            penalty = min(penalty + 0.5, 1.0)

        score = _W_DEMAND * demand + _W_LIFT * lift - _W_PENALTY * penalty
        score = max(0.0, min(1.0, score))

        breakdown = {
            "demand": round(demand, 3),
            "lift": round(lift, 3),
            "penalty": round(penalty, 3),
            "score": round(score, 3),
        }

        reason = _build_reason(cap, intent_dist, demand, lift)

        scored.append((score, {**cap, "reco_score": score}, {
            "reason": reason,
            "breakdown": breakdown,
        }))

    scored.sort(key=lambda x: -x[0])
    results: list[dict] = []

    for score, cap, meta in scored[:top_n]:
        if score < 0.05:
            continue
        reco_id = insert_reco(
            cap["cap_id"],
            reason=meta["reason"],
            score_breakdown=meta["breakdown"],
        )
        update_state_fields(cap["cap_id"], score=round(score, 4))
        results.append({
            "reco_id": reco_id,
            "cap_id": cap["cap_id"],
            "name": cap.get("name", ""),
            "cap_type": cap.get("cap_type", ""),
            "description": cap.get("description", ""),
            "score": round(score, 3),
            "reason": meta["reason"],
            "breakdown": meta["breakdown"],
        })

    return results


# ── Scoring helpers ───────────────────────────────────────────────


def _demand_match(cap: dict, intent_dist: dict, tool_freq: dict) -> float:
    """How much user activity overlaps with this capability (0~1)."""
    try:
        intents = set(json.loads(cap.get("intents_json", "[]") or "[]"))
    except Exception:
        intents = set()
    try:
        tags = set(json.loads(cap.get("tags_json", "[]") or "[]"))
    except Exception:
        tags = set()

    total_runs = sum(intent_dist.values()) or 1

    # Intent overlap: fraction of user runs that match
    intent_score = sum(intent_dist.get(i, 0) for i in intents) / total_runs

    # Tag overlap heuristic: if any tag appears as an intent key
    tag_score = 0.0
    if tags:
        tag_hits = sum(1 for t in tags if t in intent_dist)
        tag_score = tag_hits / len(tags)

    return min(1.0, 0.7 * intent_score + 0.3 * tag_score)


def _expected_lift(cap: dict, intent_metrics: dict) -> float:
    """Predict how much this capability could improve execution (0~1)."""
    try:
        intents = json.loads(cap.get("intents_json", "[]") or "[]")
    except Exception:
        intents = []

    if not intents:
        return 0.0

    total_lift = 0.0
    count = 0
    for intent in intents:
        m = intent_metrics.get(intent)
        if not m:
            continue
        # High effective_steps -> room for improvement via structured capability
        step_lift = min(1.0, (m.get("avg_steps", 0) - 2.0) / 5.0)
        step_lift = max(0.0, step_lift)
        # High LLM fallback -> room for improvement via API/MCP capability
        fb_lift = min(1.0, m.get("avg_fallback", 0) / 3.0)
        fb_lift = max(0.0, fb_lift)
        total_lift += 0.5 * step_lift + 0.5 * fb_lift
        count += 1

    return min(1.0, total_lift / count) if count else 0.0


def _cost_risk_penalty(cap: dict) -> float:
    """Penalise capabilities that require complex setup or risky permissions (0~1)."""
    try:
        setup = json.loads(cap.get("setup_json", "{}") or "{}")
    except Exception:
        setup = {}
    try:
        perms = json.loads(cap.get("permissions_json", "[]") or "[]")
    except Exception:
        perms = []

    penalty = 0.0

    kind = setup.get("kind", "")
    if kind in ("oauth", "api_key"):
        penalty += 0.3
    minutes = setup.get("minutes", 0)
    if minutes > 5:
        penalty += 0.2

    high_risk = {"write_issue", "delete_file", "exec_command", "network"}
    if set(perms) & high_risk:
        penalty += 0.3

    return min(1.0, penalty)


def _compute_intent_metrics(days: int = 30) -> dict[str, dict]:
    """Per-intent averages of effective_steps and llm_attempts."""
    rows = execute(
        """SELECT route_label,
                  AVG(CASE WHEN effective_steps > 0 THEN effective_steps END) AS avg_steps,
                  AVG(COALESCE(llm_attempts, 1)) AS avg_fallback
           FROM ie_runs
           WHERE local_date >= date('now', ?)
           GROUP BY route_label""",
        (f"-{days} days",),
        readonly=True,
    )
    result: dict[str, dict] = {}
    for r in rows:
        labels = (r.get("route_label") or "fs").split(",")
        for lb in labels:
            lb = lb.strip() or "fs"
            result[lb] = {
                "avg_steps": r.get("avg_steps") or 0,
                "avg_fallback": r.get("avg_fallback") or 0,
            }
    return result


def _get_cooled_tags() -> set[str]:
    """Tags that should be suppressed due to repeated dismissals."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_DISMISS_COOLDOWN_DAYS)).isoformat()
    dismissed = execute(
        """SELECT r.cap_id, COUNT(*) AS cnt
           FROM cap_reco r
           WHERE r.status = 'dismissed' AND r.created_at >= ?
           GROUP BY r.cap_id
           HAVING cnt >= ?""",
        (cutoff, _DISMISS_THRESHOLD),
        readonly=True,
    )
    cooled: set[str] = set()
    for row in dismissed:
        cap = execute(
            "SELECT tags_json FROM cap_registry WHERE cap_id = ?",
            (row["cap_id"],),
            readonly=True,
        )
        if cap:
            try:
                cooled |= set(json.loads(cap[0].get("tags_json", "[]") or "[]"))
            except Exception:
                pass
    return cooled


def _build_reason(cap: dict, intent_dist: dict, demand: float, lift: float) -> dict:
    """Build a human-readable reason dict for the recommendation."""
    try:
        intents = json.loads(cap.get("intents_json", "[]") or "[]")
    except Exception:
        intents = []
    matched = {i: intent_dist.get(i, 0) for i in intents if intent_dist.get(i, 0) > 0}
    return {
        "matched_intents": matched,
        "demand_score": round(demand, 2),
        "lift_score": round(lift, 2),
        "summary": f"Your recent activity matches {len(matched)} intent(s) covered by this capability.",
    }
