"""Email Summary 路由 — 邮件摘要应用.

迁移自 app.py 的 /api/apps/email_summary/* 路由。
"""

import threading

from flask import Blueprint, jsonify

from myxai_desk.web.apps_helpers import _t, load_apps_registry, save_apps_registry
from myxai_desk.web.migration_guards import mark

bp = Blueprint("apps_email", __name__, url_prefix="/api/apps/email_summary")


@bp.post("/run")
def run():
    mark("[NEW] apps/email_summary/run")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run("email_summary")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = load_apps_registry()
    if "email_summary" not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 400
    from apps.email_summary import run_email_summary

    app_config = registry["email_summary"].get("config", {})
    if not app_config.get("imap_host") or not app_config.get("imap_user"):
        return jsonify({"error": _t("error.imap_not_configured")}), 400

    import app as _app
    model_cfg = _app._get_model_config()

    def _run():
        result = run_email_summary(app_config, model_config=model_cfg)
        if result.get("success"):
            from myxai_desk.core.timeutil import local_date_str

            reg = load_apps_registry()
            if "email_summary" in reg:
                reg["email_summary"]["last_run"] = local_date_str()
                save_apps_registry(reg)
            _app._push_notification(
                title=_t("notification.email_summary.generated"),
                content=_t("notification.email_summary.content", count=result.get('email_count', 0)),
                level="info",
            )

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "running"})


@bp.get("/status")
def status():
    mark("[NEW] apps/email_summary/status")
    from apps.email_summary import get_status
    return jsonify(get_status())


@bp.get("/reports")
def reports():
    mark("[NEW] apps/email_summary/reports")
    from apps.email_summary import list_reports
    return jsonify(list_reports())


@bp.get("/report/<date_str>")
def report(date_str):
    mark("[NEW] apps/email_summary/report")
    from apps.email_summary import get_report

    report = get_report(date_str)
    if not report:
        return jsonify({"error": _t("error.report_not_found")}), 404
    return jsonify(report)


@bp.post("/test")
def test_connection():
    mark("[NEW] apps/email_summary/test")
    registry = load_apps_registry()
    if "email_summary" not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 400
    from apps.email_summary import test_connection

    app_config = registry["email_summary"].get("config", {})
    return jsonify(test_connection(app_config))


@bp.get("/presets")
def presets():
    mark("[NEW] apps/email_summary/presets")
    from apps.email_summary import IMAP_PRESETS
    return jsonify(IMAP_PRESETS)
