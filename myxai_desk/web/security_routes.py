"""Security 路由 — 安全模式和权限管理.

迁移自 app.py 的 /api/security/* 路由。
"""

import logging

from flask import Blueprint, jsonify, request

log = logging.getLogger("myxai.web.security_routes")
bp = Blueprint("security", __name__, url_prefix="/api/security")


# ── Global Security Mode ──────────────────────────────────────────


@bp.get("/mode")
def mode_get():
    """获取当前安全模式及其策略摘要."""
    from myxai_desk.core.policy.modes import get_current_mode, mode_policy_as_dict

    return jsonify(mode_policy_as_dict(get_current_mode()))


@bp.post("/mode")
def mode_set():
    """切换全局安全模式（仅限 1-3 级，Dev 模式需系统配置）."""
    from myxai_desk.core.policy.modes import (
        USER_SELECTABLE_MODES,
        SecurityMode,
        is_dev_mode_valid,
        mode_policy_as_dict,
        set_current_mode,
    )

    data = request.json or {}
    mode_str = data.get("mode", "")
    try:
        mode = SecurityMode(mode_str)
    except ValueError:
        return jsonify(
            {"error": f"Invalid mode: {mode_str}", "valid": [m.value for m in SecurityMode]}
        ), 400

    if mode == SecurityMode.DEVELOPER and not is_dev_mode_valid():
        return jsonify(
            {
                "error": "Developer 模式只能通过系统配置开启，且需要设置失效策略",
                "hint": "请使用 /api/security/dev/enable 端点",
            }
        ), 403

    if mode not in USER_SELECTABLE_MODES and mode != SecurityMode.DEVELOPER:
        return jsonify({"error": f"模式 {mode_str} 不可直接选择"}), 400

    set_current_mode(mode)
    log.info("Global mode switched to %s", mode.value)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="security.mode.switch",
            args={"mode": mode.value},
            action_id="",
            result_summary=f"global → {mode.value}",
        )
    except Exception:
        log.warning("Failed to append audit entry for security mode switch", exc_info=True)
    return jsonify(mode_policy_as_dict(mode))


@bp.get("/modes")
def modes_list():
    """返回所有可用模式及其策略."""
    from myxai_desk.core.policy.modes import (
        USER_SELECTABLE_MODES,
        SecurityMode,
        get_dev_mode_status,
        mode_policy_as_dict,
    )

    result = []
    for m in SecurityMode:
        d = mode_policy_as_dict(m)
        d["user_selectable"] = m in USER_SELECTABLE_MODES
        d["requires_system_config"] = m == SecurityMode.DEVELOPER
        result.append(d)
    dev_status = get_dev_mode_status()
    return jsonify({"modes": result, "dev_mode": dev_status})


# ── Per-App Mode ──────────────────────────────────────────────────


@bp.get("/app/<app_id>/mode")
def app_mode_get(app_id):
    """返回单个应用的模式覆盖（如果使用全局则为 null）."""
    from myxai_desk.core.policy.modes import (
        get_app_mode,
        get_current_mode,
        get_effective_mode,
    )

    app_mode = get_app_mode(app_id)
    return jsonify(
        {
            "app_id": app_id,
            "app_mode": app_mode.value if app_mode else None,
            "global_mode": get_current_mode().value,
            "effective_mode": get_effective_mode(app_id).value,
        }
    )


@bp.post("/app/<app_id>/mode")
def app_mode_set(app_id):
    """设置单个应用的模式覆盖。如果权限升级需要确认."""
    from myxai_desk.core.policy.modes import (
        USER_SELECTABLE_MODES,
        SecurityMode,
        assess_escalation,
        clear_app_mode,
        get_effective_mode,
        is_dev_mode_valid,
        set_app_mode,
    )

    data = request.json or {}
    mode_str = data.get("mode", "")
    confirmed = data.get("confirmed", False)

    if not mode_str or mode_str == "inherit":
        clear_app_mode(app_id)
        return jsonify(
            {
                "app_id": app_id,
                "app_mode": None,
                "effective_mode": get_effective_mode(app_id).value,
            }
        )

    try:
        target = SecurityMode(mode_str)
    except ValueError:
        return jsonify({"error": f"无效的模式: {mode_str}"}), 400

    if target == SecurityMode.DEVELOPER and not is_dev_mode_valid():
        return jsonify(
            {
                "error": "Developer 模式未通过系统配置开启",
                "hint": "请先通过 /api/security/dev/enable 启用 Developer 模式",
            }
        ), 403

    if target not in USER_SELECTABLE_MODES and target != SecurityMode.DEVELOPER:
        return jsonify({"error": f"模式 {mode_str} 不可选择"}), 400

    assessment = assess_escalation(app_id, target)

    if assessment["escalation"] and not confirmed:
        return jsonify(
            {
                "requires_confirm": True,
                "assessment": assessment,
            }
        ), 200

    set_app_mode(app_id, target)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="security.app_mode.set",
            args={"app_id": app_id, "mode": target.value, "escalation": assessment["escalation"]},
            action_id="",
            result_summary=f"{app_id} → {target.value}",
        )
    except Exception:
        log.warning("Failed to append audit entry for app mode set", exc_info=True)
    return jsonify(
        {
            "app_id": app_id,
            "app_mode": target.value,
            "effective_mode": get_effective_mode(app_id).value,
            "assessment": assessment,
        }
    )


@bp.post("/app/_preview/mode")
def app_mode_preview():
    """预览权限升级评估，不持久化任何数据."""
    from myxai_desk.core.policy.modes import SecurityMode, assess_escalation

    data = request.json or {}
    mode_str = data.get("mode", "")
    try:
        target = SecurityMode(mode_str)
    except ValueError:
        return jsonify({"error": f"无效的模式: {mode_str}"}), 400
    assessment = assess_escalation("_preview", target)
    return jsonify({"assessment": assessment})


# ── Developer Mode System Config ──────────────────────────────────


@bp.get("/dev/status")
def dev_status():
    """获取 Developer 模式状态."""
    from myxai_desk.core.policy.modes import DEV_EXPIRY_POLICIES, get_dev_mode_status

    return jsonify(
        {
            **get_dev_mode_status(),
            "available_policies": DEV_EXPIRY_POLICIES,
        }
    )


@bp.post("/dev/enable")
def dev_enable():
    """启用 Developer 模式，必须指定失效策略."""
    from myxai_desk.core.policy.modes import enable_dev_mode

    data = request.json or {}
    expiry_policy = data.get("expiry_policy", "")
    if not expiry_policy:
        return jsonify(
            {
                "error": "必须选择失效策略",
                "available_policies": {
                    "on_app_close": "关闭应用后失效",
                    "duration_1h": "1 小时后失效",
                    "duration_24h": "24 小时后失效",
                },
            }
        ), 400
    result = enable_dev_mode(expiry_policy)
    if "error" in result:
        return jsonify(result), 400
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="security.dev_mode.enable",
            args={"expiry_policy": expiry_policy},
            action_id="",
            result_summary=f"dev enabled, policy={expiry_policy}",
        )
    except Exception:
        log.warning("Failed to append audit entry for dev mode enable", exc_info=True)
    return jsonify(result)


@bp.post("/dev/disable")
def dev_disable():
    """禁用 Developer 模式，恢复为 Operator."""
    from myxai_desk.core.policy.modes import disable_dev_mode

    result = disable_dev_mode()
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="security.dev_mode.disable",
            args={},
            action_id="",
            result_summary=f"dev disabled, reverted to {result.get('reverted_to', '')}",
        )
    except Exception:
        log.warning("Failed to append audit entry for dev mode disable", exc_info=True)
    return jsonify(result)
