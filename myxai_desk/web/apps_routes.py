"""Apps 基础路由 — 应用列表、安装、卸载、启用、禁用、收藏、配置.

迁移自 app.py 的 /api/apps 基础路由。
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

log = logging.getLogger("myxai.web.apps_routes")

from myxai_desk.web.apps_helpers import (
    APP_CATALOG,
    DEFAULT_DIGEST_CONFIG,
    DEFAULT_EMAIL_CONFIG,
    _t,
    load_apps_prefs,
    load_apps_registry,
    save_apps_prefs,
    save_apps_registry,
)
from myxai_desk.web.migration_guards import mark

bp = Blueprint("apps", __name__, url_prefix="/api/apps")


@bp.get("")
def list_apps():
    """返回所有应用：目录 + 安装状态 + 自定义应用."""
    mark("[NEW] apps/list")
    registry = load_apps_registry()
    prefs = load_apps_prefs()
    result = []
    for app_id, catalog in APP_CATALOG.items():
        entry = {**catalog}
        entry["type"] = "builtin"
        installed = registry.get(app_id)
        entry["installed"] = installed is not None
        entry["enabled"] = installed.get("enabled", False) if installed else False
        entry["config"] = installed.get("config", {}) if installed else {}
        entry["last_run"] = installed.get("last_run") if installed else None
        p = prefs.get(app_id, {})
        entry["favorite"] = p.get("favorite", False)
        entry["run_count"] = p.get("run_count", 0)
        entry["created_at"] = installed.get("installed_at", "") if installed else ""
        result.append(entry)
    import re as _re

    from apps.custom_app import list_apps as _list_custom

    for capp in _list_custom():
        _tpl = capp.get("prompt_template", "")
        _pg = capp.get("param_groups") or []
        _pv = _pg[0] if _pg else capp.get("param_values", {})
        _desc = _re.sub(
            r"\{\{(.+?)\}\}",
            lambda m: _pv.get(m.group(1).strip(), m.group(0)),
            _tpl,
        )[:60]
        if len(_pg) > 1:
            _desc += f" (+{len(_pg) - 1})"
        _desc += "…"
        p = prefs.get(capp["id"], {})
        result.append(
            {
                "id": capp["id"],
                "name": capp["name"],
                "name_en": capp["name"],
                "icon": capp.get("icon", "🤖"),
                "description": _desc,
                "description_en": _desc,
                "version": "1.0.0",
                "author": "custom",
                "category": "custom",
                "type": "custom",
                "installed": True,
                "enabled": capp.get("schedule", {}).get("enabled", False),
                "config": {},
                "last_run": capp.get("last_run"),
                "favorite": p.get("favorite", False),
                "run_count": p.get("run_count", 0),
                "created_at": capp.get("created_at", ""),
                "security_mode": capp.get("security_mode", ""),
            }
        )
    return jsonify(result)


@bp.post("/<app_id>/install")
def install(app_id):
    mark("[NEW] apps/install")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    if app_id not in APP_CATALOG:
        return jsonify({"error": _t("error.app_not_found")}), 404
    registry = load_apps_registry()
    if app_id in registry:
        return jsonify({"error": _t("error.app_already_installed")}), 400
    default_configs = {
        "daily_digest": DEFAULT_DIGEST_CONFIG,
        "email_summary": DEFAULT_EMAIL_CONFIG,
    }
    registry[app_id] = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "config": default_configs.get(app_id, {}),
    }
    save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="app.install",
            args={"app_id": app_id},
            action_id="",
            result_summary="installed",
        )
    except Exception:
        log.warning("Failed to append audit entry for app install", exc_info=True)
    return jsonify({"success": True})


@bp.post("/<app_id>/uninstall")
def uninstall(app_id):
    mark("[NEW] apps/uninstall")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 404
    del registry[app_id]
    save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="app.uninstall",
            args={"app_id": app_id},
            action_id="",
            result_summary="uninstalled",
        )
    except Exception:
        log.warning("Failed to append audit entry for app uninstall", exc_info=True)
    return jsonify({"success": True})


@bp.post("/<app_id>/enable")
def enable(app_id):
    mark("[NEW] apps/enable")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 404
    registry[app_id]["enabled"] = True
    save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="app.enable",
            args={"app_id": app_id},
            action_id="",
            result_summary="enabled",
        )
    except Exception:
        log.warning("Failed to append audit entry for app enable", exc_info=True)
    return jsonify({"success": True})


@bp.post("/<app_id>/disable")
def disable(app_id):
    mark("[NEW] apps/disable")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 404
    registry[app_id]["enabled"] = False
    save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="app.disable",
            args={"app_id": app_id},
            action_id="",
            result_summary="disabled",
        )
    except Exception:
        log.warning("Failed to append audit entry for app disable", exc_info=True)
    return jsonify({"success": True})


@bp.post("/<app_id>/favorite")
def favorite(app_id):
    """切换收藏状态."""
    mark("[NEW] apps/favorite")
    prefs = load_apps_prefs()
    p = prefs.setdefault(app_id, {})
    p["favorite"] = not p.get("favorite", False)
    save_apps_prefs(prefs)
    return jsonify({"success": True, "favorite": p["favorite"]})


@bp.post("/<app_id>/record-run")
def record_run(app_id):
    """记录运行次数."""
    mark("[NEW] apps/record-run")
    prefs = load_apps_prefs()
    p = prefs.setdefault(app_id, {})
    p["run_count"] = p.get("run_count", 0) + 1
    save_apps_prefs(prefs)
    return jsonify({"success": True, "run_count": p["run_count"]})


@bp.get("/<app_id>/config")
def get_config(app_id):
    mark("[NEW] apps/config/get")
    registry = load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 404
    return jsonify(registry[app_id].get("config", {}))


@bp.post("/<app_id>/config")
def save_config(app_id):
    mark("[NEW] apps/config/save")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": _t("error.app_not_installed")}), 404
    new_config = request.json or {}
    registry[app_id]["config"] = new_config
    save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="app.config.save",
            args={"app_id": app_id},
            action_id="",
            result_summary="config_updated",
        )
    except Exception:
        log.warning("Failed to append audit entry for app config save", exc_info=True)
    return jsonify({"success": True})
