"""Daily Digest 路由 — 每日资讯摘要应用.

迁移自 app.py 的 /api/apps/daily_digest/* 路由。
"""

import logging
import threading

from flask import Blueprint, jsonify, request

log = logging.getLogger("myxai.web.apps_digest_routes")

from myxai_desk.web.apps_helpers import (
    _t,
    digest_task_lock,
    digest_task_status,
    inc_run_count,
    load_apps_registry,
    save_apps_registry,
)
from myxai_desk.web.migration_guards import mark

bp = Blueprint("apps_digest", __name__, url_prefix="/api/apps/daily_digest")


@bp.post("/run")
def run():
    """后台启动每日摘要."""
    mark("[NEW] apps/daily_digest/run")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run("daily_digest")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = load_apps_registry()
    if "daily_digest" not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 400

    with digest_task_lock:
        if digest_task_status.get("status") == "running":
            return jsonify({"error": _t("error.task_running", task=_t("app.daily_digest.name"))}), 409
        digest_task_status.update({"status": "running", "progress": _t("progress.collecting_history")})

    def _run():
        import app as _app
        try:
            from apps.daily_digest import run_daily_digest
            from myxai_desk.core.timeutil import local_date_str

            app_config = registry["daily_digest"].get("config", {})
            model_cfg = _app._get_model_config()
            merged = {**app_config, **model_cfg}

            def _progress(msg):
                with digest_task_lock:
                    digest_task_status["progress"] = msg

            result = run_daily_digest(merged, progress_cb=_progress)

            if result["status"] == "ok":
                reg = load_apps_registry()
                if "daily_digest" in reg:
                    reg["daily_digest"]["last_run"] = local_date_str()
                    save_apps_registry(reg)
                inc_run_count("daily_digest")

                stats = result.get("stats", {})
                _app._push_notification(
                    title=_t("notification.daily_digest.updated"),
                    content=_t("notification.daily_digest.content",
                              filtered=stats.get('filtered_count', 0),
                              results=stats.get('search_results', 0)),
                    level="info",
                )

            from myxai_desk.core.runtime.app_governance import finish_app_run
            finish_app_run("daily_digest", success=(result["status"] == "ok"))

            with digest_task_lock:
                digest_task_status.update(
                    {"status": "done" if result["status"] == "ok" else "error", "result": result}
                )
        except Exception as exc:
            log.exception("Daily digest run error: %s", exc)
            try:
                from myxai_desk.core.runtime.app_governance import finish_app_run
                finish_app_run("daily_digest", success=False, error=str(exc))
            except Exception:
                log.warning("Failed to finish_app_run after digest error", exc_info=True)
            with digest_task_lock:
                digest_task_status.update({"status": "error", "result": {"message": str(exc)}})

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "running"})


@bp.get("/status")
def status():
    mark("[NEW] apps/daily_digest/status")
    with digest_task_lock:
        return jsonify(dict(digest_task_status) if digest_task_status else {"status": "idle"})


@bp.get("/reports")
def reports():
    mark("[NEW] apps/daily_digest/reports")
    from apps.daily_digest import list_reports
    return jsonify(list_reports())


@bp.get("/report/<date_str>")
def report(date_str):
    mark("[NEW] apps/daily_digest/report")
    from apps.daily_digest import load_report

    report = load_report(date_str)
    if not report:
        return jsonify({"error": _t("error.report_not_found")}), 404
    return jsonify(report)


@bp.get("/browsers")
def browsers():
    mark("[NEW] apps/daily_digest/browsers")
    from apps.daily_digest import find_browser_history_paths
    return jsonify(find_browser_history_paths())


@bp.get("/preview")
def preview():
    """快速预览：读取历史+提取兴趣，不生成完整报告."""
    mark("[NEW] apps/daily_digest/preview")
    import app as _app

    registry = load_apps_registry()
    if "daily_digest" not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 400

    from apps.daily_digest import (
        classify_interests,
        extract_keywords,
        filter_history,
        llm_analyze_interests,
        read_browser_history,
        read_chat_history,
    )

    app_config = registry["daily_digest"].get("config", {})
    browser = app_config.get("browser", "auto")
    hours = app_config.get("history_hours", 24)

    raw = read_browser_history(hours=hours, browser=browser)
    filtered = filter_history(raw)

    chat_hours = app_config.get("chat_hours", 72)
    chat_sessions = read_chat_history(hours=chat_hours)
    chat_msg_count = sum(len(s.get("messages", [])) for s in chat_sessions)

    model_cfg = _app._get_model_config()
    model = model_cfg.get("model")
    api_key = model_cfg.get("api_key")
    api_base = model_cfg.get("api_base")
    analysis_method = "rule"

    if model and api_key:
        llm_result = llm_analyze_interests(
            filtered, model, api_key, api_base, chat_sessions=chat_sessions,
        )
        if llm_result:
            analysis_method = "llm"
            interests = {
                cat: [{"keyword": kw, "count": 0} for kw in entry["interests"]]
                for cat, entry in llm_result.items()
            }
            queries = {cat: entry["queries"] for cat, entry in llm_result.items()}
            return jsonify({
                "raw_count": len(raw), "filtered_count": len(filtered),
                "chat_sessions": len(chat_sessions), "chat_messages": chat_msg_count,
                "keyword_count": sum(len(v) for v in interests.values()),
                "interests": interests, "queries": queries, "method": analysis_method,
            })

    keywords = extract_keywords(filtered)
    categories = classify_interests(keywords)
    interests = {
        cat: [{"keyword": i["keyword"], "count": i["count"]} for i in items[:10]]
        for cat, items in categories.items()
    }
    return jsonify({
        "raw_count": len(raw), "filtered_count": len(filtered),
        "chat_sessions": len(chat_sessions), "chat_messages": chat_msg_count,
        "keyword_count": len(keywords), "interests": interests, "method": analysis_method,
    })


@bp.post("/explore")
def explore():
    """为摘要中的特定内容构建探索提示词."""
    mark("[NEW] apps/daily_digest/explore")
    body = request.json or {}
    item = body.get("item")
    date_str = body.get("date")
    if not item or not isinstance(item, dict):
        return jsonify({"error": "item is required"}), 400

    interests = None
    if date_str:
        from apps.daily_digest import load_report
        report = load_report(date_str)
        if report:
            interests = report.get("interests")

    from apps.daily_digest import build_explore_prompt
    prompt = build_explore_prompt(item, interests=interests)
    return jsonify({"prompt": prompt})
