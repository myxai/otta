"""Flask Blueprint for the Strategy Hub application.

Prefix: ``/api/apps/strategy_hub``

Provides asset governance APIs for golden templates, instances, and candidates.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from myxai_desk.apps.strategy_hub.dao import (
    delete_candidate,
    delete_instance,
    delete_template,
    generate_templates_for_intent,
    get_abstraction_suggestions,
    get_golden_metrics,
    get_instance_detail,
    get_intent_labels,
    get_template_detail,
    invalidate_instance,
    list_candidates,
    list_instances,
    list_templates,
    promote_candidate_to_instance,
)

log = logging.getLogger("myxai")

bp = Blueprint(
    "apps_strategy_hub",
    __name__,
    url_prefix="/api/apps/strategy_hub",
)


# ── Health overview ──────────────────────────────────────────────────


@bp.route("/metrics")
def hub_metrics():
    """Return aggregate health metrics for all golden assets."""
    return jsonify(get_golden_metrics())


# ── Templates ────────────────────────────────────────────────────────


@bp.route("/templates")
def hub_templates():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    intent = request.args.get("intent")
    rows = list_templates(limit=limit, offset=offset, intent_filter=intent)
    return jsonify({"templates": rows})


@bp.route("/templates/<template_id>")
def hub_template_detail(template_id):
    detail = get_template_detail(template_id)
    if not detail:
        return jsonify({"error": "template not found"}), 404
    return jsonify(detail)


@bp.route("/templates/<template_id>/delete", methods=["POST"])
def hub_template_delete(template_id):
    ok = delete_template(template_id)
    return jsonify({"ok": ok})


# ── Instances ────────────────────────────────────────────────────────


@bp.route("/instances")
def hub_instances():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    intent = request.args.get("intent")
    template = request.args.get("template")
    rows = list_instances(
        limit=limit, offset=offset,
        intent_filter=intent, template_filter=template,
    )
    return jsonify({"instances": rows})


@bp.route("/instances/<case_key>")
def hub_instance_detail(case_key):
    detail = get_instance_detail(case_key)
    if not detail:
        return jsonify({"error": "instance not found"}), 404
    return jsonify(detail)


@bp.route("/instances/<case_key>/invalidate", methods=["POST"])
def hub_instance_invalidate(case_key):
    ok = invalidate_instance(case_key)
    return jsonify({"ok": ok})


@bp.route("/instances/<case_key>/delete", methods=["POST"])
def hub_instance_delete(case_key):
    ok = delete_instance(case_key)
    return jsonify({"ok": ok})


# ── Candidates ───────────────────────────────────────────────────────


@bp.route("/candidates")
def hub_candidates():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    status = request.args.get("status")
    rows = list_candidates(limit=limit, offset=offset, status_filter=status)
    return jsonify({"candidates": rows})


@bp.route("/candidates/<candidate_id>/promote", methods=["POST"])
def hub_candidate_promote(candidate_id):
    result = promote_candidate_to_instance(candidate_id)
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/candidates/<candidate_id>/delete", methods=["POST"])
def hub_candidate_delete(candidate_id):
    ok = delete_candidate(candidate_id)
    return jsonify({"ok": ok})


# ── Analysis ─────────────────────────────────────────────────────────


@bp.route("/suggestions")
def hub_suggestions():
    """Return template abstraction suggestions."""
    return jsonify({"suggestions": get_abstraction_suggestions()})


@bp.route("/intents")
def hub_intents():
    """Return all distinct intent labels."""
    return jsonify({"intents": get_intent_labels()})


# ── Template Generation ──────────────────────────────────────────────


@bp.route("/generate_templates", methods=["POST"])
def hub_generate_templates():
    """Manually trigger template generation.
    
    Optional JSON body:
      - intent_label: str (optional) — generate only for this intent
      - force: bool (default: false) — regenerate even if template exists
    
    Returns:
      - templates_created: int — number of templates created
      - templates: list — details of created templates
    """
    body = request.get_json() or {}
    intent_label = body.get("intent_label")
    force = body.get("force", False)
    
    result = generate_templates_for_intent(
        intent_label=intent_label,
        force=force,
    )
    
    return jsonify(result)
