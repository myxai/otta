"""Flask Blueprint for the Execution Radar application.

Prefix: ``/api/apps/healthcheck``
"""

from __future__ import annotations

import logging
import threading
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from myxai_desk.apps.healthcheck.dao import (
    get_daily_metrics,
    get_metrics_range,
    get_tasks_with_steps,
    get_top_errors,
    get_top_tools,
)

log = logging.getLogger("myxai")

bp = Blueprint("apps_healthcheck", __name__, url_prefix="/api/apps/healthcheck")

_run_lock = threading.Lock()
_run_status: dict = {}


@bp.route("/summary")
def healthcheck_summary():
    """Return summary card data for a single day."""
    date_str = request.args.get("date", (date.today() - timedelta(days=1)).isoformat())
    metrics = get_daily_metrics(date_str)
    if not metrics:
        return jsonify({
            "date": date_str,
            "total_tasks": 0,
            "success_tasks": 0,
            "single_tasks": 0,
            "single_hits": 0,
            "multi_tasks": 0,
            "multi_hits": 0,
            "avg_attempts": 0,
            "avg_tokens": 0,
            "top_error_codes": [],
            "top_tools": [],
            "report_text": "",
            "single_hit_rate": 0,
            "multi_hit_rate": 0,
            "success_rate": 0,
        })

    # hit rates are pre-computed and stored by the pipeline
    if "single_hit_rate" not in metrics:
        metrics["single_hit_rate"] = 0
    if "multi_hit_rate" not in metrics:
        metrics["multi_hit_rate"] = 0

    denom = metrics.get("instrumented_tasks") or metrics.get("total_tasks") or 0
    metrics["success_rate"] = (
        round(metrics["success_tasks"] / denom * 100, 1)
        if denom
        else 0
    )
    return jsonify(metrics)


@bp.route("/trends")
def healthcheck_trends():
    """Return trend data for charting (7 or 30 day window)."""
    window = int(request.args.get("window", 7))
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=window - 1)

    rows = get_metrics_range(start.isoformat(), end.isoformat())

    dates = []
    single_hit_rates = []
    multi_hit_rates = []
    avg_attempts_list = []
    avg_tokens_list = []

    for r in rows:
        dates.append(r["date"])
        single_hit_rates.append(r.get("single_hit_rate", 0))
        multi_hit_rates.append(r.get("multi_hit_rate", 0))
        avg_attempts_list.append(r.get("avg_attempts", 0))
        avg_tokens_list.append(r.get("avg_tokens", 0))

    return jsonify({
        "window": window,
        "dates": dates,
        "single_hit_rates": single_hit_rates,
        "multi_hit_rates": multi_hit_rates,
        "avg_attempts": avg_attempts_list,
        "avg_tokens": avg_tokens_list,
    })


@bp.route("/top_errors")
def healthcheck_top_errors():
    """Return top error codes for a given date."""
    date_str = request.args.get("date", (date.today() - timedelta(days=1)).isoformat())
    limit = int(request.args.get("limit", 10))
    errors = get_top_errors(date_str, limit)

    total = sum(e.get("cnt", 0) for e in errors) or 1
    for e in errors:
        e["pct"] = round(e["cnt"] / total * 100, 1) if total else 0

    return jsonify({"date": date_str, "errors": errors})


@bp.route("/top_tools")
def healthcheck_top_tools():
    """Return top tools by call count."""
    date_str = request.args.get("date", (date.today() - timedelta(days=1)).isoformat())
    limit = int(request.args.get("limit", 10))
    tools = get_top_tools(date_str, limit)
    return jsonify({"date": date_str, "tools": tools})


@bp.route("/tasks")
def healthcheck_tasks():
    """Return per-task detail with step-level breakdown for a date."""
    date_str = request.args.get("date", (date.today() - timedelta(days=1)).isoformat())
    tasks = get_tasks_with_steps(date_str)

    result = []
    for t in tasks:
        steps_out = []
        for s in t.get("steps", []):
            steps_out.append({
                "index": s.get("step_index", 0),
                "tool": s.get("tool_name", ""),
                "args": s.get("args_json", "{}"),
                "status": s.get("status", "ok"),
                "error_code": s.get("error_code", ""),
                "effective": bool(s.get("effective", False)),
            })
        n = t.get("total_steps", 0)
        result.append({
            "task_id": t["task_id"],
            "user_text": t.get("user_text", ""),
            "total_steps": n,
            "effective_count": t.get("effective_count", 0),
            "hit_rate": round(t.get("hit_rate", 0) * 100, 1) if isinstance(t.get("hit_rate"), float) and t.get("hit_rate", 0) <= 1 else t.get("hit_rate", 0),
            "success": bool(t.get("success")),
            "steps": steps_out,
        })

    return jsonify({"date": date_str, "tasks": result})


@bp.route("/run", methods=["POST"])
def healthcheck_run():
    """Manually trigger the healthcheck pipeline."""
    global _run_status

    if not _run_lock.acquire(blocking=False):
        return jsonify({"running": True, "message": "Pipeline already running"}), 409

    date_str = (request.json or {}).get(
        "date", (date.today() - timedelta(days=1)).isoformat()
    )
    _run_status = {"running": True, "date": date_str, "error": None}

    def _bg():
        try:
            from myxai_desk.apps.healthcheck.pipeline import run_daily_healthcheck
            run_daily_healthcheck(run_date=date_str)
            _run_status["running"] = False
        except Exception as exc:
            log.exception("[healthcheck] manual run failed")
            _run_status["running"] = False
            _run_status["error"] = str(exc)
        finally:
            _run_lock.release()

    threading.Thread(target=_bg, daemon=True).start()
    return jsonify({"started": True, "date": date_str})


@bp.route("/status")
def healthcheck_run_status():
    """Return status of the current / last manual run."""
    return jsonify(_run_status)
