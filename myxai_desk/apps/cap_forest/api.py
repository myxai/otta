"""Flask Blueprint for the Capability Forest application.

Prefix: ``/api/apps/cap_forest``

Provides capability lifecycle APIs — overview, registry, enable/disable,
recommendations, trial stats, wake-once, pruning, and event stream.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from myxai_desk.apps.cap_forest.dao import (
    disable_cap,
    enable_cap,
    get_overview,
    get_registry_item,
    get_state,
    insert_reco,
    list_events,
    list_recos,
    list_registry,
    list_states,
    set_state,
    update_reco_status,
    update_state_fields,
)

log = logging.getLogger("myxai.cap_forest")

bp = Blueprint(
    "apps_cap_forest",
    __name__,
    url_prefix="/api/apps/cap_forest",
)


# ── Overview ──────────────────────────────────────────────────────


@bp.route("/overview")
def forest_overview():
    """Return active / trial / candidate / dormant lists + KPI."""
    return jsonify(get_overview())


# ── Registry ─────────────────────────────────────────────────────


@bp.route("/registry")
def forest_registry():
    """Full capability catalogue (admin view)."""
    cap_type = request.args.get("type")
    return jsonify({"registry": list_registry(cap_type)})


# ── Enable / Disable ─────────────────────────────────────────────


@bp.route("/cap/enable", methods=["POST"])
def forest_cap_enable():
    data = request.get_json(silent=True) or {}
    cap_id = data.get("cap_id", "")
    mode = data.get("mode", "active")
    if not cap_id:
        return jsonify({"error": "cap_id required"}), 400
    if mode not in ("active", "trial"):
        return jsonify({"error": "mode must be 'active' or 'trial'"}), 400
    reg = get_registry_item(cap_id)
    if not reg:
        return jsonify({"error": "capability not found in registry"}), 404
    enable_cap(cap_id, mode)
    return jsonify({"ok": True, "cap_id": cap_id, "mode": mode})


@bp.route("/cap/disable", methods=["POST"])
def forest_cap_disable():
    data = request.get_json(silent=True) or {}
    cap_id = data.get("cap_id", "")
    if not cap_id:
        return jsonify({"error": "cap_id required"}), 400
    disable_cap(cap_id)
    return jsonify({"ok": True, "cap_id": cap_id, "state": "dormant"})


# ── Recommendations ───────────────────────────────────────────────


@bp.route("/reco/compute", methods=["POST"])
def forest_reco_compute():
    """Trigger recommendation computation and return Top-N."""
    data = request.get_json(silent=True) or {}
    top_n = data.get("top_n", 3)
    from myxai_desk.apps.cap_forest.recommender import compute_recommendations
    results = compute_recommendations(top_n=top_n)
    return jsonify({"ok": True, "recommendations": results})


@bp.route("/reco/accept", methods=["POST"])
def forest_reco_accept():
    data = request.get_json(silent=True) or {}
    reco_id = data.get("reco_id", "")
    if not reco_id:
        return jsonify({"error": "reco_id required"}), 400
    update_reco_status(reco_id, "accepted")
    recos = list_recos()
    matched = next((r for r in recos if r.get("reco_id") == reco_id), None)
    if matched:
        enable_cap(matched["cap_id"], "trial")
    return jsonify({"ok": True})


@bp.route("/reco/dismiss", methods=["POST"])
def forest_reco_dismiss():
    data = request.get_json(silent=True) or {}
    reco_id = data.get("reco_id", "")
    if not reco_id:
        return jsonify({"error": "reco_id required"}), 400
    update_reco_status(reco_id, "dismissed")
    return jsonify({"ok": True})


# ── Trial ─────────────────────────────────────────────────────────


@bp.route("/cap/promote", methods=["POST"])
def forest_cap_promote():
    """Manually promote a trial capability to active."""
    data = request.get_json(silent=True) or {}
    cap_id = data.get("cap_id", "")
    if not cap_id:
        return jsonify({"error": "cap_id required"}), 400
    state_row = get_state(cap_id)
    if not state_row or state_row["state"] != "trial":
        return jsonify({"error": "capability is not in trial"}), 400
    set_state(cap_id, "active", enabled=1)
    return jsonify({"ok": True, "cap_id": cap_id, "state": "active"})


@bp.route("/cap/<cap_id>/trial_stats")
def forest_trial_stats(cap_id: str):
    """Return trial-period effectiveness data with baseline comparison."""
    from myxai_desk.apps.cap_forest.trial import get_trial_stats
    stats = get_trial_stats(cap_id)
    if "error" in stats:
        return jsonify(stats), 404
    return jsonify(stats)


@bp.route("/trial/evaluate", methods=["POST"])
def forest_trial_evaluate():
    """Evaluate all trial capabilities and auto-promote or demote."""
    from myxai_desk.apps.cap_forest.trial import evaluate_trials
    results = evaluate_trials()
    return jsonify({"ok": True, "results": results})


# ── Wake once ─────────────────────────────────────────────────────


@bp.route("/cap/wake_once", methods=["POST"])
def forest_cap_wake_once():
    """Temporarily wake a dormant capability for the current execution only."""
    data = request.get_json(silent=True) or {}
    cap_id = data.get("cap_id", "")
    if not cap_id:
        return jsonify({"error": "cap_id required"}), 400
    from myxai_desk.apps.cap_forest.router import add_wake_once
    add_wake_once(cap_id)
    return jsonify({"ok": True, "cap_id": cap_id})


@bp.route("/wake_suggestions")
def forest_wake_suggestions():
    """Check if any dormant caps match the current task context."""
    user_text = request.args.get("text", "")
    from myxai_desk.apps.cap_forest.router import suggest_wake
    suggestions = suggest_wake(user_text, intent_result=None)
    return jsonify({"suggestions": suggestions})


# ── Pruning ───────────────────────────────────────────────────────


@bp.route("/prune/run", methods=["POST"])
def forest_prune():
    """Manually trigger pruning of stale capabilities."""
    from myxai_desk.apps.cap_forest.pruner import run_prune
    data = request.get_json(silent=True) or {}
    days = data.get("days", 30)
    summary = run_prune(prune_days=days)
    return jsonify({"ok": True, **summary})


# ── Aggregation ───────────────────────────────────────────────────


@bp.route("/aggregate", methods=["POST"])
def forest_aggregate():
    """Trigger behavioural signal aggregation from ie_runs + er_steps."""
    data = request.get_json(silent=True) or {}
    days = data.get("days", 30)
    from myxai_desk.apps.cap_forest.aggregator import aggregate_signals
    summary = aggregate_signals(days=days)
    return jsonify({"ok": True, **summary})


# ── Events ────────────────────────────────────────────────────────


@bp.route("/events")
def forest_events():
    limit = request.args.get("limit", 100, type=int)
    event_type = request.args.get("type")
    return jsonify({"events": list_events(limit=limit, event_type=event_type)})
