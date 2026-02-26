"""Profile 路由 — 用户画像、偏好和 Persona 管理.

迁移自 app.py 的 /api/profile/* 路由。
"""

from flask import Blueprint, jsonify, request

from myxai_desk.web.migration_guards import mark

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


# ── Profile Core ──────────────────────────────────────────────────


@bp.get("/summary")
def summary():
    """返回用户画像摘要."""
    mark("[NEW] profile/summary")
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_summary())


@bp.get("/topics")
def topics():
    """返回提取的兴趣主题."""
    mark("[NEW] profile/topics")
    from myxai_desk.core.capabilities.profile import Profile

    days = request.args.get("days", 30, type=int)
    return jsonify(Profile().get_topics(days=days))


@bp.get("/preferences")
def preferences_get():
    """返回用户偏好."""
    mark("[NEW] profile/preferences/get")
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_preferences())


@bp.post("/preferences")
def preferences_update():
    """更新用户偏好."""
    mark("[NEW] profile/preferences/update")
    from myxai_desk.core.capabilities.profile import Profile

    action_id = Profile().update_preferences(request.json or {})
    return jsonify({"success": True, "action_id": action_id})


@bp.get("/collection")
def collection_get():
    """返回数据收集设置."""
    mark("[NEW] profile/collection/get")
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_collection_settings())


@bp.post("/collection")
def collection_update():
    """更新数据收集设置."""
    mark("[NEW] profile/collection/update")
    from myxai_desk.core.capabilities.profile import Profile

    settings = request.json or {}
    action_id = Profile().update_collection_settings(settings)
    return jsonify({"success": True, "action_id": action_id})


@bp.get("/export")
def export():
    """导出所有画像数据."""
    mark("[NEW] profile/export")
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().export_all())


@bp.post("/clear")
def clear():
    """清除所有画像数据."""
    mark("[NEW] profile/clear")
    from myxai_desk.core.capabilities.profile import Profile

    action_id = Profile().clear_all()
    return jsonify({"success": True, "action_id": action_id})


@bp.post("/refresh")
def refresh():
    """强制刷新画像摘要."""
    mark("[NEW] profile/refresh")
    from myxai_desk.core.capabilities.profile import Profile

    summary = Profile().refresh_summary()
    return jsonify(summary)


# ── Persona Engine ────────────────────────────────────────────────


@bp.get("/persona")
def persona_get():
    """返回 stable + recent persona 数据."""
    mark("[NEW] profile/persona/get")
    from myxai_desk.core.capabilities.profile import Profile

    return jsonify(Profile().get_persona())


@bp.get("/persona/prompt")
def persona_prompt():
    """生成 persona 增强的 LLM 提示词."""
    mark("[NEW] profile/persona/prompt")
    from myxai_desk.core.capabilities.profile import Profile

    task_context = request.args.get("task_context", "")
    prompt = Profile().get_persona_prompt(task_context)
    return jsonify({"prompt": prompt})


@bp.post("/persona/edit/<part>")
def persona_edit(part):
    """手动编辑 stable 或 recent persona 字段."""
    mark("[NEW] profile/persona/edit")
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
    mark("[NEW] profile/persona/update")
    from myxai_desk.core.capabilities.profile import Profile

    import app as _app
    model_cfg = _app._get_model_config()
    result = Profile().run_persona_update(
        model=model_cfg.get("model", ""),
        api_key=model_cfg.get("api_key", ""),
        api_base=model_cfg.get("api_base"),
    )
    return jsonify(result)
