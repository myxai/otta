"""Strategy Hub DAO — data access layer for golden asset governance.

Reads from:
  - golden_templates   (templates)
  - golden_instances   (instances)
  - golden_candidates  (Execution Prism)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai")


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_json(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}


def _stats_fields(stats: dict) -> dict:
    """Extract common stat fields from a stats_json dict."""
    sc = stats.get("success_count", 0)
    fc = stats.get("fail_count", 0)
    total = sc + fc
    return {
        "use_count": total,
        "success_count": sc,
        "fail_count": fc,
        "success_rate": round(sc / total * 100, 1) if total else 0,
        "avg_duration_ms": stats.get("avg_duration_ms"),
        "last_outcome": stats.get("last_outcome"),
        "disabled": bool(stats.get("disabled")),
        "disabled_reason": stats.get("disabled_reason", ""),
    }


def _asset_status(sf: dict) -> str:
    """Derive display status from stats fields."""
    if sf.get("disabled"):
        return "disabled"
    if sf["fail_count"] >= 3 or (sf["use_count"] >= 3 and sf["success_rate"] < 60):
        return "stale"
    return "active"


# ── Aggregate metrics ────────────────────────────────────────────────


def get_golden_metrics() -> dict:
    """Compute health overview metrics across all golden asset types."""

    template_count = _count("golden_templates")
    instance_count = _count("golden_instances")
    candidate_count = _count_safe("golden_candidates", "status IN ('new','used')")

    # Aggregate usage stats
    t_stats = _aggregate_stats("golden_templates")
    i_stats = _aggregate_stats("golden_instances")

    total_use = t_stats["total_use"] + i_stats["total_use"]
    total_success = t_stats["total_success"] + i_stats["total_success"]
    total_fail = t_stats["total_fail"] + i_stats["total_fail"]
    hit_rate = round(total_success / total_use * 100, 1) if total_use else 0
    fail_rate = round(total_fail / total_use * 100, 1) if total_use else 0

    # Stale detection
    stale_instances = _count_stale_instances()
    stale_templates = _count_stale_templates()

    # Health score: 0.4*hit_rate + 0.3*success_rate - 0.2*fail_rate - 0.1*staleness
    success_rate = hit_rate
    staleness = 0
    total_assets = template_count + instance_count
    if total_assets:
        staleness = round((stale_instances + stale_templates) / total_assets * 100, 1)

    health_score = round(
        0.4 * (hit_rate / 100)
        + 0.3 * (success_rate / 100)
        - 0.2 * (fail_rate / 100)
        - 0.1 * (staleness / 100),
        2,
    )
    health_score = max(0, min(1, health_score))
    health_int = round(health_score * 100)

    if health_int >= 80:
        health_label = "Healthy"
    elif health_int >= 60:
        health_label = "Stable"
    elif health_int >= 40:
        health_label = "Degraded"
    else:
        health_label = "Critical"

    return {
        "template_count": template_count,
        "instance_count": instance_count,
        "candidate_count": candidate_count,
        "total_use": total_use,
        "hit_rate": hit_rate,
        "fail_rate": fail_rate,
        "avg_replay_ms": i_stats["avg_duration"],
        "stale_instances": stale_instances,
        "stale_templates": stale_templates,
        "health_score": health_int,
        "health_label": health_label,
    }


def _count(table: str) -> int:
    try:
        rows = execute(f"SELECT COUNT(*) as c FROM {table}", readonly=True)
        return rows[0]["c"] if rows else 0
    except Exception:
        return 0


def _count_safe(table: str, where: str) -> int:
    try:
        rows = execute(
            f"SELECT COUNT(*) as c FROM {table} WHERE {where}",
            readonly=True,
        )
        return rows[0]["c"] if rows else 0
    except Exception:
        return 0


def _aggregate_stats(table: str) -> dict:
    """Aggregate success/fail counts from stats_json column."""
    try:
        rows = execute(f"SELECT stats_json FROM {table}", readonly=True)
    except Exception:
        return {"total_use": 0, "total_success": 0, "total_fail": 0, "avg_duration": None}

    total_s, total_f = 0, 0
    dur_sum, dur_count = 0.0, 0
    for r in rows:
        stats = _safe_json(r.get("stats_json", "{}"))
        total_s += stats.get("success_count", 0)
        total_f += stats.get("fail_count", 0)
        d = stats.get("avg_duration_ms")
        if d is not None:
            dur_sum += d
            dur_count += 1

    return {
        "total_use": total_s + total_f,
        "total_success": total_s,
        "total_fail": total_f,
        "avg_duration": round(dur_sum / dur_count, 1) if dur_count else None,
    }


def _count_unhealthy(table: str) -> int:
    """Count stale or disabled assets in a golden table."""
    try:
        rows = execute(f"SELECT stats_json FROM {table}", readonly=True)
    except Exception:
        return 0

    count = 0
    for r in rows:
        stats = _safe_json(r.get("stats_json", "{}"))
        if stats.get("disabled"):
            count += 1
            continue
        sc = stats.get("success_count", 0)
        fc = stats.get("fail_count", 0)
        total = sc + fc
        if fc >= 3 or (total >= 3 and sc / total < 0.6):
            count += 1
    return count


def _count_stale_instances() -> int:
    return _count_unhealthy("golden_instances")


def _count_stale_templates() -> int:
    return _count_unhealthy("golden_templates")


# ── Templates CRUD ───────────────────────────────────────────────────


def list_templates(
    limit: int = 50,
    offset: int = 0,
    intent_filter: Optional[str] = None,
) -> list[dict]:
    where = ""
    params: tuple = ()
    if intent_filter:
        where = "WHERE intent_label = ?"
        params = (intent_filter,)

    try:
        rows = execute(
            f"""SELECT * FROM golden_templates {where}
                ORDER BY last_used_at DESC NULLS LAST
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
            readonly=True,
        )
    except Exception:
        return []

    result = []
    for r in rows:
        stats = _safe_json(r.get("stats_json", "{}"))
        sf = _stats_fields(stats)

        result.append({
            "template_id": r["template_id"],
            "intent_label": r["intent_label"],
            "version": r.get("version", 1),
            "use_count": sf["use_count"],
            "success_rate": sf["success_rate"],
            "last_used_at": r.get("last_used_at"),
            "created_at": r.get("created_at", ""),
            "status": _asset_status(sf),
        })
    return result


def get_template_detail(template_id: str) -> Optional[dict]:
    try:
        rows = execute(
            "SELECT * FROM golden_templates WHERE template_id = ?",
            (template_id,),
            readonly=True,
        )
    except Exception:
        return None

    if not rows:
        return None

    r = rows[0]
    stats = _safe_json(r.get("stats_json", "{}"))
    sf = _stats_fields(stats)

    # Related instances
    try:
        inst_rows = execute(
            "SELECT case_key, intent_label, stats_json, last_used_at FROM golden_instances WHERE template_id = ? ORDER BY last_used_at DESC LIMIT 20",
            (template_id,),
            readonly=True,
        )
    except Exception:
        inst_rows = []

    instances = []
    for ir in inst_rows:
        ist = _safe_json(ir.get("stats_json", "{}"))
        isf = _stats_fields(ist)
        instances.append({
            "case_key": ir["case_key"],
            "intent_label": ir.get("intent_label", ""),
            "use_count": isf["use_count"],
            "success_rate": isf["success_rate"],
            "last_used_at": ir.get("last_used_at"),
        })

    return {
        "template_id": r["template_id"],
        "intent_label": r["intent_label"],
        "version": r.get("version", 1),
        "plan_template": _safe_json(r.get("plan_template_json", "[]")),
        "slot_schema": _safe_json(r.get("slot_schema_json", "[]")),
        "constraints": _safe_json(r.get("constraints_json", "{}")),
        "stats": sf,
        "created_at": r.get("created_at", ""),
        "last_used_at": r.get("last_used_at"),
        "status": _asset_status(sf),
        "instances": instances,
    }


def delete_template(template_id: str) -> bool:
    try:
        execute("DELETE FROM golden_templates WHERE template_id = ?", (template_id,))
        execute(
            "UPDATE golden_instances SET template_id = NULL WHERE template_id = ?",
            (template_id,),
        )
        return True
    except Exception:
        log.warning("Failed to delete template %s", template_id, exc_info=True)
        return False


# ── Instances CRUD ───────────────────────────────────────────────────


def list_instances(
    limit: int = 50,
    offset: int = 0,
    intent_filter: Optional[str] = None,
    template_filter: Optional[str] = None,
) -> list[dict]:
    conditions: list[str] = []
    params: list = []

    if intent_filter:
        conditions.append("intent_label = ?")
        params.append(intent_filter)
    if template_filter:
        conditions.append("template_id = ?")
        params.append(template_filter)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    try:
        rows = execute(
            f"""SELECT * FROM golden_instances {where}
                ORDER BY last_used_at DESC NULLS LAST
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
            readonly=True,
        )
    except Exception:
        return []

    result = []
    for r in rows:
        stats = _safe_json(r.get("stats_json", "{}"))
        sf = _stats_fields(stats)

        result.append({
            "case_key": r["case_key"],
            "template_id": r.get("template_id"),
            "intent_label": r.get("intent_label", ""),
            "use_count": sf["use_count"],
            "success_rate": sf["success_rate"],
            "last_used_at": r.get("last_used_at"),
            "created_at": r.get("created_at", ""),
            "status": _asset_status(sf),
        })
    return result


def get_instance_detail(case_key: str) -> Optional[dict]:
    try:
        rows = execute(
            "SELECT * FROM golden_instances WHERE case_key = ?",
            (case_key,),
            readonly=True,
        )
    except Exception:
        return None

    if not rows:
        return None

    r = rows[0]
    stats = _safe_json(r.get("stats_json", "{}"))
    sf = _stats_fields(stats)

    return {
        "case_key": r["case_key"],
        "template_id": r.get("template_id"),
        "intent_label": r.get("intent_label", ""),
        "slot_values": _safe_json(r.get("slot_values_json", "{}")),
        "resolved_plan": _safe_json(r.get("resolved_plan_json", "[]")),
        "stats": sf,
        "created_at": r.get("created_at", ""),
        "last_used_at": r.get("last_used_at"),
        "status": _asset_status(sf),
    }


def invalidate_instance(case_key: str) -> bool:
    """Disable an instance — replay will skip it immediately."""
    try:
        rows = execute(
            "SELECT stats_json FROM golden_instances WHERE case_key = ?",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return False

        stats = _safe_json(rows[0].get("stats_json", "{}"))
        stats["fail_count"] = max(stats.get("fail_count", 0), 3)
        stats["last_outcome"] = "invalidated"
        stats["disabled"] = True
        stats["disabled_reason"] = "manual invalidation"

        execute(
            "UPDATE golden_instances SET stats_json = ? WHERE case_key = ?",
            (json.dumps(stats, ensure_ascii=False), case_key),
        )
        return True
    except Exception:
        log.warning("Failed to invalidate instance %s", case_key, exc_info=True)
        return False


def delete_instance(case_key: str) -> bool:
    try:
        execute("DELETE FROM golden_instances WHERE case_key = ?", (case_key,))
        return True
    except Exception:
        log.warning("Failed to delete instance %s", case_key, exc_info=True)
        return False


# ── Candidates ───────────────────────────────────────────────────────


def list_candidates(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> list[dict]:
    where = ""
    params: tuple = ()
    if status_filter:
        where = "WHERE status = ?"
        params = (status_filter,)

    try:
        rows = execute(
            f"""SELECT * FROM golden_candidates {where}
                ORDER BY quality_score DESC, created_at DESC
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
            readonly=True,
        )
    except Exception:
        return []

    result = []
    for c in rows:
        plan = c.get("candidate_plan_json", "[]")
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except Exception:
                plan = []
        result.append({
            "candidate_id": c["candidate_id"],
            "case_key": c.get("case_key", ""),
            "user_text": c.get("user_text", ""),
            "quality_score": c.get("quality_score", 0),
            "original_steps": c.get("original_steps", 0),
            "removed_steps": c.get("removed_steps", 0),
            "effective_steps": len(plan) if isinstance(plan, list) else 0,
            "used_count": c.get("used_count", 0),
            "fail_count": c.get("fail_count", 0),
            "status": c.get("status", "new"),
            "created_at": c.get("created_at", ""),
            "last_used_at": c.get("last_used_at"),
        })
    return result


def promote_candidate_to_instance(candidate_id: str) -> dict:
    """Promote a candidate to a golden v2 instance."""
    try:
        rows = execute(
            "SELECT * FROM golden_candidates WHERE candidate_id = ?",
            (candidate_id,),
            readonly=True,
        )
        if not rows:
            return {"ok": False, "error": "candidate not found"}

        c = rows[0]
        plan_json = c.get("candidate_plan_json", "[]")

        from myxai_desk.core.golden.store import GoldenV2Store
        from myxai_desk.core.golden_store import parse_candidate_plan

        v2 = GoldenV2Store()
        resolved = parse_candidate_plan(plan_json)
        v2.save_instance(
            case_key=c["case_key"],
            template_id=None,
            intent_label="",
            slot_values={},
            resolved_plan=resolved,
        )

        # Mark candidate as promoted
        try:
            execute(
                "UPDATE golden_candidates SET status = 'promoted' WHERE candidate_id = ?",
                (candidate_id,),
            )
        except Exception:
            pass

        return {"ok": True, "case_key": c["case_key"]}
    except Exception as e:
        log.warning("Failed to promote candidate %s", candidate_id, exc_info=True)
        return {"ok": False, "error": str(e)}


def delete_candidate(candidate_id: str) -> bool:
    try:
        execute("DELETE FROM golden_candidates WHERE candidate_id = ?", (candidate_id,))
        return True
    except Exception:
        log.warning("Failed to delete candidate %s", candidate_id, exc_info=True)
        return False


# ── Template abstraction suggestions ─────────────────────────────────


def get_abstraction_suggestions() -> list[dict]:
    """Find groups of 3+ instances with same intent_label but no template.

    These are candidates for template abstraction.
    """
    try:
        rows = execute(
            """SELECT intent_label, COUNT(*) as cnt
               FROM golden_instances
               WHERE (template_id IS NULL OR template_id = '')
               GROUP BY intent_label
               HAVING cnt >= 3
               ORDER BY cnt DESC
               LIMIT 10""",
            readonly=True,
        )
    except Exception:
        return []

    return [
        {"intent_label": r["intent_label"], "instance_count": r["cnt"]}
        for r in rows
    ]


# ── Distinct intent labels ───────────────────────────────────────────


def get_intent_labels() -> list[str]:
    """Get all distinct intent labels across templates and instances."""
    labels = set()
    try:
        for r in execute("SELECT DISTINCT intent_label FROM golden_templates", readonly=True):
            if r.get("intent_label"):
                labels.add(r["intent_label"])
    except Exception:
        pass
    try:
        for r in execute("SELECT DISTINCT intent_label FROM golden_instances", readonly=True):
            if r.get("intent_label"):
                labels.add(r["intent_label"])
    except Exception:
        pass
    return sorted(labels)
