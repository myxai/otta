"""Unified Reports 路由 — 聚合所有应用的报告.

迁移自 app.py 的 /api/reports/* 路由。
"""

from flask import Blueprint, jsonify, request

from myxai_desk.web.apps_helpers import _t
from myxai_desk.web.migration_guards import mark

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _html_to_summary(html: str, max_len: int = 60) -> str:
    import re as _re

    text = _re.sub(r"<[^>]+>", " ", html)
    text = _re.sub(r"\s+", " ", text).strip()
    for prefix in ("📅", "📧", "🎯"):
        text = text.lstrip(prefix).strip()
    text = _re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", text).strip()
    for skip in (_t("app.daily_digest.name"), "每日资讯", "Daily"):
        if text.startswith(skip):
            text = text[len(skip):].strip()
    return text[:max_len] if text else ""


@bp.get("")
def all_reports():
    """聚合所有应用的报告列表."""
    mark("[NEW] reports/list")
    result: list[dict] = []

    try:
        from apps.daily_digest import list_reports as digest_list
        from apps.daily_digest import load_report as digest_load

        for r in digest_list(limit=60):
            date = r.get("date", "")
            summary = ""
            try:
                rpt = digest_load(date)
                if rpt and rpt.get("content"):
                    summary = _html_to_summary(rpt["content"])
            except Exception:
                pass
            result.append({
                "app_id": "daily_digest",
                "app_name": _t("app.daily_digest.name"),
                "app_icon": "🎯", "date": date,
                "generated_at": r.get("generated_at", ""),
                "key": date, "type": "digest",
                "read": r.get("read", False), "summary": summary,
            })
    except Exception:
        pass

    try:
        from apps.email_summary import get_report as email_get
        from apps.email_summary import list_reports as email_list

        for r in email_list():
            date = r.get("date", "")
            summary = ""
            email_count = r.get("email_count", 0)
            if email_count:
                summary = _t("notification.email_summary.content", count=email_count)
            else:
                try:
                    rpt = email_get(date)
                    if rpt and rpt.get("content"):
                        summary = _html_to_summary(rpt["content"])
                except Exception:
                    pass
            result.append({
                "app_id": "email_summary",
                "app_name": _t("app.email_summary.name"),
                "app_icon": "📧", "date": date,
                "generated_at": r.get("generated_at", ""),
                "key": date, "type": "email",
                "read": r.get("read", False), "summary": summary,
            })
    except Exception:
        pass

    try:
        from apps.custom_app import get_report as custom_get
        from apps.custom_app import list_apps as _list_custom
        from apps.custom_app import list_reports as custom_list

        for app in _list_custom():
            app_id = app["id"]
            app_name = app.get("name", app_id)
            app_icon = app.get("icon", "🧩")
            for r in custom_list(app_id):
                key = r.get("key", "")
                summary = ""
                try:
                    rpt = custom_get(app_id, key)
                    if rpt and rpt.get("content"):
                        summary = _html_to_summary(rpt["content"])
                except Exception:
                    pass
                result.append({
                    "app_id": app_id, "app_name": app_name,
                    "app_icon": app_icon, "date": r.get("date", ""),
                    "generated_at": r.get("generated_at", ""),
                    "key": key, "type": r.get("type", "run"),
                    "read": r.get("read", True), "summary": summary,
                })
    except Exception:
        pass

    result.sort(key=lambda x: x.get("generated_at") or x.get("date") or "", reverse=True)
    return jsonify(result)


@bp.get("/unread_count")
def unread_count():
    """所有报告来源的未读总数."""
    mark("[NEW] reports/unread_count")
    total = 0
    try:
        from apps.custom_app import all_unread_counts
        total += sum(all_unread_counts().values())
    except Exception:
        pass
    try:
        from apps.daily_digest import list_reports as _dl
        total += sum(1 for r in _dl(limit=60) if not r.get("read"))
    except Exception:
        pass
    try:
        from apps.email_summary import list_reports as _el
        total += sum(1 for r in _el() if not r.get("read"))
    except Exception:
        pass
    return jsonify({"total": total})


@bp.post("/mark_all_read")
def mark_all_read():
    mark("[NEW] reports/mark_all_read")
    try:
        from apps.custom_app import list_apps as _list_custom
        from apps.custom_app import list_reports as custom_list
        from apps.custom_app import mark_report_read

        for app in _list_custom():
            for r in custom_list(app["id"]):
                if not r.get("read"):
                    mark_report_read(app["id"], r.get("key", ""))
    except Exception:
        pass
    try:
        from apps.daily_digest import list_reports as digest_list
        from apps.daily_digest import mark_report_read as digest_mark

        for r in digest_list(limit=200):
            if not r.get("read"):
                digest_mark(r.get("date", ""))
    except Exception:
        pass
    try:
        from apps.email_summary import list_reports as email_list
        from apps.email_summary import mark_report_read as email_mark

        for r in email_list():
            if not r.get("read"):
                email_mark(r.get("date", ""))
    except Exception:
        pass
    return jsonify({"ok": True})


@bp.delete("/<app_id>/<path:key>")
def delete_report(app_id, key):
    mark("[NEW] reports/delete")
    ok = False
    if app_id == "daily_digest":
        from apps.daily_digest import delete_report
        ok = delete_report(key)
    elif app_id == "email_summary":
        from apps.email_summary import delete_report
        ok = delete_report(key)
    else:
        from apps.custom_app import delete_report
        ok = delete_report(app_id, key)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@bp.get("/<app_id>/<path:key>")
def report_content(app_id, key):
    """获取单个报告的完整内容."""
    mark("[NEW] reports/content")
    if app_id == "daily_digest":
        from apps.daily_digest import load_report
        from apps.daily_digest import mark_report_read as digest_mark

        report = load_report(key)
        if not report:
            return jsonify({"error": "not found"}), 404
        digest_mark(key)
        return jsonify(report)
    elif app_id == "email_summary":
        from apps.email_summary import get_report
        from apps.email_summary import mark_report_read as email_mark

        report = get_report(key)
        if not report:
            return jsonify({"error": "not found"}), 404
        email_mark(key)
        return jsonify(report)
    else:
        from apps.custom_app import get_report, mark_report_read

        report = get_report(app_id, key)
        if not report:
            return jsonify({"error": "not found"}), 404
        mark_report_read(app_id, key)
        return jsonify(report)
