"""Profile 路由 — 用户画像、偏好和 Persona 管理.

迁移自 app.py 的 /api/profile/* 路由。
"""

from flask import Blueprint, jsonify, request

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


# ── Profile Core ──────────────────────────────────────────────────


@bp.get("/summary")
def summary():
    """返回用户画像摘要."""
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_summary())


@bp.get("/topics")
def topics():
    """返回提取的兴趣主题."""
    from myxai_desk.core.capabilities.profile import Profile

    days = request.args.get("days", 30, type=int)
    return jsonify(Profile().get_topics(days=days))


@bp.get("/preferences")
def preferences_get():
    """返回用户偏好."""
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_preferences())


@bp.post("/preferences")
def preferences_update():
    """更新用户偏好."""
    from myxai_desk.core.capabilities.profile import Profile

    action_id = Profile().update_preferences(request.json or {})
    return jsonify({"success": True, "action_id": action_id})


@bp.get("/collection")
def collection_get():
    """返回数据收集设置."""
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_collection_settings())


@bp.post("/collection")
def collection_update():
    """更新数据收集设置."""
    from myxai_desk.core.capabilities.profile import Profile

    settings = request.json or {}
    action_id = Profile().update_collection_settings(settings)
    return jsonify({"success": True, "action_id": action_id})


@bp.get("/export")
def export():
    """导出所有画像数据."""
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().export_all())


@bp.post("/clear")
def clear():
    """清除所有画像数据."""
    from myxai_desk.core.capabilities.profile import Profile

    action_id = Profile().clear_all()
    return jsonify({"success": True, "action_id": action_id})


@bp.post("/refresh")
def refresh():
    """强制刷新画像摘要."""
    from myxai_desk.core.capabilities.profile import Profile

    summary = Profile().refresh_summary()
    return jsonify(summary)


# ── Persona Engine ────────────────────────────────────────────────


@bp.get("/persona")
def persona_get():
    """返回 stable + recent persona 数据."""
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_persona())


@bp.get("/persona/prompt")
def persona_prompt():
    """生成 persona 增强的 LLM 提示词."""
    from myxai_desk.core.capabilities.profile import Profile

    task_context = request.args.get("task_context", "")
    prompt = Profile().get_persona_prompt(task_context)
    return jsonify({"prompt": prompt})


@bp.post("/persona/edit/<part>")
def persona_edit(part):
    """手动编辑 stable 或 recent persona 字段."""
    from myxai_desk.core.capabilities.profile import Profile

    patch = request.get_json(force=True) or {}
    if part == "stable":
        result = Profile().edit_persona_stable(patch)
    elif part == "recent":
        result = Profile().edit_persona_recent(patch)
    else:
        return jsonify({"error": f"Unknown part: {part}, use 'stable' or 'recent'"}), 400
    return jsonify(result)


@bp.post("/persona/update")
def persona_update():
    """触发完整的 persona 更新周期."""
    from myxai_desk.core.capabilities.profile import Profile

    import app as _app
    model_cfg = _app._get_model_config()
    result = Profile().run_persona_update(
        model=model_cfg.get("model", ""),
        api_key=model_cfg.get("api_key", ""),
        api_base=model_cfg.get("api_base"),
    )
    return jsonify(result)


# ── Secrets management ─────────────────────────────────────────────


@bp.get("/secrets/info")
def secrets_info():
    """Return secrets backend status and stored key names."""
    from myxai_desk.core.storage import secrets

    info = secrets.backend_info()
    info["stored_keys"] = secrets.list_keys()
    return jsonify(info)


@bp.post("/secrets/clear")
def secrets_clear():
    """Wipe all stored secrets (API keys, passwords)."""
    from myxai_desk.core.storage import secrets

    secrets.clear_all()
    return jsonify({"success": True})
