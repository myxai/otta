"""Gateway API — Flask Blueprint for myxai_desk governance routes.

Thin route layer: request parsing → delegate to core modules → response.
No business logic lives here.

Covers: Security Mode, Profile, Marketplace, Plan Confirmation,
        Audit & Undo, Budget.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, Response

governance_bp = Blueprint("governance", __name__, url_prefix="/api")


# ── helpers ────────────────────────────────────────────────────────

def _get_agent():
    """Import the global agent factory from the compat layer (app.py)."""
    from app import _get_or_create_agent
    return _get_or_create_agent()


def _official_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "marketplace" / "official"


def _search_dirs():
    from myxai_desk.core.storage.paths import (
        MARKETPLACE_USER_DIR, MARKETPLACE_THIRD_PARTY_DIR,
    )
    return [_official_dir(), MARKETPLACE_USER_DIR, MARKETPLACE_THIRD_PARTY_DIR]


# ═══════════════════════════════════════════════════════════════════
# Security Mode
# ═══════════════════════════════════════════════════════════════════

@governance_bp.route("/security/mode", methods=["GET"])
def security_mode_get():
    from myxai_desk.core.policy.modes import get_current_mode, mode_policy_as_dict
    return jsonify(mode_policy_as_dict(get_current_mode()))


@governance_bp.route("/security/mode", methods=["POST"])
def security_mode_set():
    from myxai_desk.core.policy.modes import SecurityMode, set_current_mode, mode_policy_as_dict
    data = request.json or {}
    mode_str = data.get("mode", "")
    try:
        mode = SecurityMode(mode_str)
    except ValueError:
        return jsonify({"error": f"Invalid mode: {mode_str}",
                        "valid": [m.value for m in SecurityMode]}), 400
    set_current_mode(mode)
    return jsonify(mode_policy_as_dict(mode))


@governance_bp.route("/security/modes", methods=["GET"])
def security_modes_list():
    from myxai_desk.core.policy.modes import SecurityMode, mode_policy_as_dict
    return jsonify([mode_policy_as_dict(m) for m in SecurityMode])


# ═══════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════

@governance_bp.route("/profile/summary", methods=["GET"])
def profile_summary():
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_summary())


@governance_bp.route("/profile/topics", methods=["GET"])
def profile_topics():
    from myxai_desk.core.capabilities.profile import Profile
    days = request.args.get("days", 30, type=int)
    return jsonify(Profile().get_topics(days=days))


@governance_bp.route("/profile/preferences", methods=["GET"])
def profile_preferences_get():
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_preferences())


@governance_bp.route("/profile/preferences", methods=["POST"])
def profile_preferences_update():
    from myxai_desk.core.capabilities.profile import Profile
    action_id = Profile().update_preferences(request.json or {})
    return jsonify({"success": True, "action_id": action_id})


@governance_bp.route("/profile/collection", methods=["GET"])
def profile_collection_get():
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_collection_settings())


@governance_bp.route("/profile/collection", methods=["POST"])
def profile_collection_update():
    from myxai_desk.core.capabilities.profile import Profile
    action_id = Profile().update_collection_settings(request.json or {})
    return jsonify({"success": True, "action_id": action_id})


@governance_bp.route("/profile/export", methods=["GET"])
def profile_export():
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().export_all())


@governance_bp.route("/profile/clear", methods=["POST"])
def profile_clear():
    from myxai_desk.core.capabilities.profile import Profile
    action_id = Profile().clear_all()
    return jsonify({"success": True, "action_id": action_id})


@governance_bp.route("/profile/refresh", methods=["POST"])
def profile_refresh():
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().refresh_summary())


# ═══════════════════════════════════════════════════════════════════
# Marketplace
# ═══════════════════════════════════════════════════════════════════

@governance_bp.route("/marketplace/apps", methods=["GET"])
def marketplace_apps():
    from myxai_desk.core.runtime.app_runtime import discover_apps
    from myxai_desk.core.runtime.manifest import manifest_to_dict
    manifests = discover_apps(_search_dirs())
    result = []
    for m in manifests:
        d = manifest_to_dict(m)
        d["installed"] = True
        d["enabled"] = True
        d["type"] = "prompt_app"
        result.append(d)
    return jsonify(result)


@governance_bp.route("/marketplace/app/<app_id>/run", methods=["POST"])
def marketplace_run(app_id):
    from myxai_desk.core.runtime.app_runtime import run_app, discover_apps
    all_apps = discover_apps(_search_dirs())
    manifest = next((m for m in all_apps if m.id == app_id), None)
    if not manifest:
        return jsonify({"error": f"App not found: {app_id}"}), 404

    input_ctx = request.json or {}
    agent = None
    try:
        agent = _get_agent()
    except Exception:
        pass

    r = run_app(manifest, input_ctx, agent=agent)
    return jsonify({
        "app_id": r.app_id, "success": r.success,
        "output": r.output, "output_type": r.output_type, "error": r.error,
    })


# ═══════════════════════════════════════════════════════════════════
# Plan Confirmation
# ═══════════════════════════════════════════════════════════════════

@governance_bp.route("/plan/pending", methods=["GET"])
def plan_pending():
    from myxai_desk.core.orchestrator.planner import get_plan_manager
    return jsonify(get_plan_manager().list_pending())


@governance_bp.route("/plan/confirm/<action_id>", methods=["POST"])
def plan_confirm(action_id):
    from myxai_desk.core.orchestrator.planner import get_plan_manager
    pm = get_plan_manager()
    pa = pm.confirm_pending(action_id)
    if not pa:
        return jsonify({"error": "Action not found, expired, or already handled"}), 404
    try:
        import asyncio
        agent = _get_agent()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    lambda: asyncio.run(agent.tools.execute(pa.tool_name, pa.tool_args))
                ).result(timeout=60)
        else:
            result = loop.run_until_complete(
                agent.tools.execute(pa.tool_name, pa.tool_args))
        from myxai_desk.core.capabilities.governance import (
            post_execution_audit, post_execution_undo,
        )
        post_execution_audit(pa.capability, pa.op, pa.tool_args, result, None)
        post_execution_undo(pa.capability, pa.op, pa.tool_args, result)
        return jsonify({"success": True, "result": str(result)[:500]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@governance_bp.route("/plan/reject/<action_id>", methods=["POST"])
def plan_reject(action_id):
    from myxai_desk.core.orchestrator.planner import get_plan_manager
    pm = get_plan_manager()
    if pm.reject_pending(action_id):
        return jsonify({"success": True})
    return jsonify({"error": "Action not found or already handled"}), 404


# ═══════════════════════════════════════════════════════════════════
# Audit & Undo
# ═══════════════════════════════════════════════════════════════════

@governance_bp.route("/audit/recent", methods=["GET"])
def audit_recent():
    from myxai_desk.core.audit.ledger import AuditLedger
    n = request.args.get("n", 50, type=int)
    return jsonify(AuditLedger().recent(n))


@governance_bp.route("/audit/verify", methods=["GET"])
def audit_verify():
    from myxai_desk.core.audit.ledger import AuditLedger
    ok, count, error = AuditLedger().verify_chain()
    return jsonify({"valid": ok, "entries_checked": count, "error": error})


@governance_bp.route("/audit/export", methods=["GET"])
def audit_export():
    from myxai_desk.core.audit.ledger import AuditLedger
    fmt = request.args.get("format", "json")
    data = AuditLedger().export(format=fmt)
    return Response(data, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=audit_chain.json"})


@governance_bp.route("/undo/actions", methods=["GET"])
def undo_actions():
    from myxai_desk.core.audit.undo import UndoRegistry
    undoable = request.args.get("undoable", "false").lower() == "true"
    return jsonify(UndoRegistry().list_actions(undoable_only=undoable))


@governance_bp.route("/undo/<action_id>", methods=["POST"])
def undo_exec(action_id):
    from myxai_desk.core.audit.undo import UndoRegistry
    return jsonify(UndoRegistry().undo(action_id))


# ═══════════════════════════════════════════════════════════════════
# Budget
# ═══════════════════════════════════════════════════════════════════

@governance_bp.route("/budget/status", methods=["GET"])
def budget_status():
    """Return current budget usage for all tracked dimensions."""
    from myxai_desk.core.capabilities.search import QuotaManager
    qm = QuotaManager()
    return jsonify(qm.get_usage())
