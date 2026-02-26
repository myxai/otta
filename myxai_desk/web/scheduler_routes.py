"""Scheduler 路由 — 任务调度和运行历史.

迁移自 app.py 的 /api/scheduler/* 路由。
"""

from flask import Blueprint, jsonify, request, current_app

from myxai_desk.web.state import get_state

bp = Blueprint("scheduler", __name__, url_prefix="/api/scheduler")

# Official app display names / icons
_OFFICIAL_APP_META = {
    "daily_digest": {"name_zh": "每日私享", "name_en": "Daily Briefing", "icon": "🎯"},
    "email_summary": {"name_zh": "邮件简报", "name_en": "Email Briefing", "icon": "📧"},
}


@bp.post("/trigger/<task_id>")
def trigger(task_id):
    """手动触发定时任务."""
    state = get_state(current_app)
    
    # 访问 scheduler service（从 app.py 导入）
    from app import _scheduler_svc
    
    ok, msg = _scheduler_svc.trigger_now(task_id)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 404


@bp.get("/runs/<task_id>")
def runs(task_id):
    """返回任务的最近运行历史（用于 UI 显示）."""
    from myxai_desk.core.scheduler_service import get_recent_runs
    
    limit = request.args.get("limit", 20, type=int)
    runs = get_recent_runs(task_id, limit=limit)
    return jsonify({"runs": runs})


@bp.get("/status")
def status():
    """快速概览：列出所有定时任务及其下次/上次运行信息."""
    from myxai_desk.core.scheduler_service import compute_due_slots
    from myxai_desk.core.timeutil import now_local
    from app import _load_official_tasks, _load_custom_tasks
    
    tasks = _load_official_tasks() + _load_custom_tasks()
    now = now_local()
    items = []
    for t in tasks:
        due = compute_due_slots(t, now)
        items.append(
            {
                "task_id": t.task_id,
                "catchup_policy": t.catchup_policy,
                "last_success_at": t.last_success_at,
                "pending_catchup": len(due),
                "pending_slots": [
                    {
                        "scheduled_for": s.scheduled_for.isoformat(),
                        "idempotency_key": s.idempotency_key,
                    }
                    for s in due
                ],
            }
        )
    return jsonify({"tasks": items})


@bp.get("/today")
def today():
    """返回今天的任务时间表（用于侧边栏任务面板）.
    
    每个项目包括：task_id, name, icon, scheduled_time, status, finished_at.
    状态: planned | running | success | failed
    """
    from myxai_desk.core.scheduler_service import (
        compute_due_slots,
        get_running_tasks,
        get_today_runs,
    )
    from myxai_desk.core.timeutil import local_date_str, now_local
    from app import _load_official_tasks, _load_custom_tasks
    
    now = now_local()
    today_str = local_date_str()
    
    # Collect all task descriptors
    tasks = _load_official_tasks() + _load_custom_tasks()
    
    # Build a lookup: task_id -> (name_zh, name_en, icon, schedule_time)
    task_meta: dict[str, dict] = {}
    for t in tasks:
        meta = _OFFICIAL_APP_META.get(t.task_id)
        if meta:
            name_zh = meta["name_zh"]
            name_en = meta["name_en"]
            icon = meta["icon"]
        else:
            app_data = t.extra.get("app", {})
            base_name = app_data.get("name", t.task_id)
            icon = app_data.get("icon", "🤖")
            kind = t.extra.get("kind", "")
            if kind == "custom_summary":
                name_zh = base_name + " (总结)"
                name_en = base_name + " (Summary)"
                icon = "📊"
            else:
                name_zh = base_name
                name_en = base_name
        sched_time = t.schedule.get("time", "")
        task_meta[t.task_id] = {
            "name_zh": name_zh,
            "name_en": name_en,
            "icon": icon,
            "time": sched_time,
            "mode": t.schedule.get("mode", "daily"),
            "catchup_policy": t.catchup_policy,
        }
    
    # Collect today's runs from DB
    today_runs = get_today_runs()
    running_tasks = get_running_tasks()
    
    run_by_task: dict[str, list[dict]] = {}
    for r in today_runs:
        run_by_task.setdefault(r["task_id"], []).append(r)
    
    running_ids = {r["task_id"] for r in running_tasks}
    
    # Build the result list
    items = []
    seen_tasks = set()
    
    # 1) Tasks with existing runs today
    for task_id, runs in run_by_task.items():
        seen_tasks.add(task_id)
        meta = task_meta.get(
            task_id,
            {"name_zh": task_id, "name_en": task_id, "icon": "🤖", "time": "", "mode": "daily"},
        )
        latest = runs[-1]
        items.append(
            {
                "task_id": task_id,
                "name_zh": meta["name_zh"],
                "name_en": meta["name_en"],
                "icon": meta["icon"],
                "scheduled_time": meta["time"],
                "status": latest["status"],
                "started_at": latest.get("started_at", ""),
                "finished_at": latest.get("finished_at", ""),
                "error": latest.get("error", ""),
                "trigger": latest.get("trigger", ""),
            }
        )
    
    # 2) Tasks that are due but haven't run yet
    for t in tasks:
        if t.task_id in seen_tasks:
            continue
        if t.task_id in running_ids:
            continue
        due = compute_due_slots(t, now)
        if not due:
            sched_time = t.schedule.get("time", "")
            sched_mode = t.schedule.get("mode", "daily")
            show_planned = False
            if sched_time and sched_time > now.strftime("%H:%M"):
                if sched_mode == "daily":
                    show_planned = True
                elif sched_mode == "weekly":
                    if now.weekday() == t.schedule.get("day_of_week", 0):
                        show_planned = True
                elif sched_mode == "monthly":
                    if now.day == t.schedule.get("day_of_month", 1):
                        show_planned = True
                elif sched_mode == "interval":
                    show_planned = True
            if show_planned:
                meta = task_meta.get(
                    t.task_id,
                    {"name_zh": t.task_id, "name_en": t.task_id, "icon": "🤖", "time": ""},
                )
                items.append(
                    {
                        "task_id": t.task_id,
                        "name_zh": meta["name_zh"],
                        "name_en": meta["name_en"],
                        "icon": meta["icon"],
                        "scheduled_time": sched_time,
                        "status": "planned",
                        "started_at": "",
                        "finished_at": "",
                        "error": "",
                        "trigger": "",
                    }
                )
        else:
            meta = task_meta.get(
                t.task_id, {"name_zh": t.task_id, "name_en": t.task_id, "icon": "🤖", "time": ""}
            )
            items.append(
                {
                    "task_id": t.task_id,
                    "name_zh": meta["name_zh"],
                    "name_en": meta["name_en"],
                    "icon": meta["icon"],
                    "scheduled_time": meta["time"],
                    "status": "pending_catchup",
                    "started_at": "",
                    "finished_at": "",
                    "error": "",
                    "trigger": "",
                }
            )
    
    # Sort: running first, then pending_catchup, then planned, then success, then failed
    status_order = {"running": 0, "pending_catchup": 1, "planned": 2, "success": 3, "failed": 4}
    items.sort(key=lambda x: (status_order.get(x["status"], 9), x.get("scheduled_time", "")))
    
    return jsonify({"tasks": items, "date": today_str})
