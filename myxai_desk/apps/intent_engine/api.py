"""Intent Engine API Blueprint.

Prefix: ``/api/apps/intent_engine``
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

log = logging.getLogger("myxai")

bp = Blueprint("intent_engine", __name__, url_prefix="/api/apps/intent_engine")


# ── Config ─────────────────────────────────────────────────────────

@bp.route("/config", methods=["GET"])
def get_config():
    from myxai_desk.core.intent_engine.config import get
    return jsonify(get())


@bp.route("/config", methods=["POST"])
def update_config():
    updates = request.get_json(force=True) or {}
    from myxai_desk.core.intent_engine.config import set_values
    result = set_values(updates)
    return jsonify(result)


# ── Stats ──────────────────────────────────────────────────────────

@bp.route("/stats", methods=["GET"])
def get_stats():
    days = request.args.get("days", 7, type=int)
    from myxai_desk.core.intent_engine.dao import get_runs_stats
    return jsonify(get_runs_stats(days=days))


# ── Visualization APIs ─────────────────────────────────────────────

@bp.route("/metrics", methods=["GET"])
def get_metrics():
    days = request.args.get("days", 7, type=int)
    from myxai_desk.core.intent_engine.dao import get_ie_metrics
    return jsonify(get_ie_metrics(days=days))


@bp.route("/trends", methods=["GET"])
def get_trends():
    days = request.args.get("days", 7, type=int)
    from myxai_desk.core.intent_engine.dao import get_ie_trends
    return jsonify(get_ie_trends(days=days))


@bp.route("/distribution", methods=["GET"])
def get_distribution():
    days = request.args.get("days", 7, type=int)
    from myxai_desk.core.intent_engine.dao import get_ie_distribution
    return jsonify(get_ie_distribution(days=days))


@bp.route("/misroutes", methods=["GET"])
def get_misroutes():
    days = request.args.get("days", 7, type=int)
    from myxai_desk.core.intent_engine.dao import get_ie_misroutes
    return jsonify(get_ie_misroutes(days=days))


# ── Runs ───────────────────────────────────────────────────────────

@bp.route("/runs", methods=["GET"])
def get_runs():
    date = request.args.get("date")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    from myxai_desk.core.intent_engine.dao import get_runs
    rows = get_runs(local_date=date, limit=limit, offset=offset)
    return jsonify(rows)


# ── Cases ──────────────────────────────────────────────────────────

@bp.route("/cases", methods=["GET"])
def get_cases():
    outcome = request.args.get("outcome")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    from myxai_desk.core.intent_engine.dao import get_cases as dao_get_cases
    rows = dao_get_cases(outcome=outcome, limit=limit, offset=offset)
    return jsonify(rows)


# ── Corrections ────────────────────────────────────────────────────

@bp.route("/correct", methods=["POST"])
def correct_category():
    """Record a user category correction for a specific run."""
    data = request.get_json(force=True) or {}
    run_id = data.get("run_id", "")
    corrected = data.get("corrected_category", "")
    if not run_id or not corrected:
        return jsonify({"error": "run_id and corrected_category required"}), 400

    from myxai_desk.core.intent_engine.dao import get_runs as dao_get_runs
    rows = dao_get_runs(limit=1, offset=0)
    run = None
    for r in rows:
        if r.get("id") == run_id:
            run = r
            break

    if run is None:
        from myxai_desk.core.storage.sqlite import execute
        found = execute(
            "SELECT route_label FROM ie_runs WHERE id = ?",
            (run_id,), readonly=True,
        )
        original = found[0]["route_label"] if found else ""
    else:
        original = run.get("route_label", "")

    from myxai_desk.core.intent_engine.dao import insert_correction
    fb_id = insert_correction(
        run_id=run_id,
        original_category=original,
        corrected_category=corrected,
    )
    if fb_id:
        return jsonify({"status": "ok", "feedback_id": fb_id})
    return jsonify({"error": "correction failed"}), 500


@bp.route("/corrections", methods=["GET"])
def get_corrections():
    """List recent user corrections."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    from myxai_desk.core.intent_engine.dao import get_corrections as dao_get_corrections
    return jsonify(dao_get_corrections(limit=limit, offset=offset))


# ── Data Repair ────────────────────────────────────────────────────

@bp.route("/repair/llm_free", methods=["POST"])
def repair_llm_free_misclassification():
    """Fix historical llm_free rows where llm_attempts > 0."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            """UPDATE ie_runs
               SET plan_source = NULL
               WHERE plan_source = 'llm_free'
                 AND llm_attempts > 0""",
        )
        affected = rows if isinstance(rows, int) else 0
        return jsonify({"status": "ok", "affected": affected})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/repair/llm_free/check", methods=["GET"])
def check_llm_free_misclassification():
    """Check how many llm_free rows have llm_attempts > 0."""
    try:
        from myxai_desk.core.storage.sqlite import query_all
        rows = query_all(
            """SELECT id, user_text, plan_source, llm_attempts, outcome, created_at
               FROM ie_runs
               WHERE plan_source = 'llm_free'
                 AND llm_attempts > 0
               ORDER BY created_at DESC
               LIMIT 20""",
        )
        return jsonify({"count": len(rows), "samples": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
