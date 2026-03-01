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


# =====================================================================
# Nightly Semantic Learning — Control Panel
# =====================================================================


# ── Learning Config & Status ──────────────────────────────────────

@bp.route("/learning/config", methods=["GET"])
def get_learning_config():
    """Get nightly learning configuration and current status."""
    from myxai_desk.core.intent_engine.config import get as ie_get
    cfg = ie_get()
    return jsonify({
        "enabled": cfg.get("nightly_learning_enabled", False),
        "use_llm": cfg.get("nightly_learning_use_llm", True),
        "sanitize_pii": cfg.get("nightly_learning_sanitize_pii", True),
        "max_samples": cfg.get("nightly_learning_max_samples", 200),
        "min_runs": cfg.get("nightly_learning_min_runs", 20),
        "min_misroutes": cfg.get("nightly_learning_min_misroutes", 5),
    })


@bp.route("/learning/config", methods=["POST"])
def update_learning_config():
    """Update nightly learning configuration."""
    data = request.get_json(force=True) or {}
    from myxai_desk.core.intent_engine.config import set_values

    allowed = {
        "nightly_learning_enabled", "nightly_learning_use_llm",
        "nightly_learning_sanitize_pii", "nightly_learning_max_samples",
        "nightly_learning_min_runs", "nightly_learning_min_misroutes",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "no valid fields provided"}), 400
    set_values(updates)
    return get_learning_config()


@bp.route("/learning/stats", methods=["GET"])
def get_learning_stats():
    """Get daily stats and trigger decision for nightly learning."""
    from myxai_desk.core.intent_engine.nightly_learner import (
        get_daily_stats, LearningTrigger,
    )
    from myxai_desk.core.intent_engine.config import get as ie_get
    from datetime import date, timedelta

    date_str = request.args.get("date")
    target = date.fromisoformat(date_str) if date_str else date.today() - timedelta(days=1)

    stats = get_daily_stats(target)
    cfg = ie_get()
    trigger = LearningTrigger(
        new_runs_min=cfg.get("nightly_learning_min_runs", 20),
        misroute_min=cfg.get("nightly_learning_min_misroutes", 5),
    )
    should_run, reason = trigger.should_trigger(stats)

    return jsonify({**stats, "should_trigger": should_run, "trigger_reason": reason})


# ── Run Learning ──────────────────────────────────────────────────

@bp.route("/learning/run", methods=["POST"])
def trigger_learning():
    """Manually trigger nightly learning."""
    data = request.get_json(force=True) or {}
    dry_run = data.get("dry_run", False)
    force = data.get("force", False)

    from myxai_desk.core.intent_engine.nightly_learner import run_nightly_learning
    from datetime import date, timedelta

    date_str = data.get("date")
    target = date.fromisoformat(date_str) if date_str else date.today() - timedelta(days=1)

    result = run_nightly_learning(target_date=target, dry_run=dry_run, force=force)
    return jsonify(result)


# ── Learning History (Audit Trail) ────────────────────────────────

@bp.route("/learning/runs", methods=["GET"])
def list_learning_runs():
    """List nightly learning run history."""
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    from myxai_desk.core.intent_engine.nightly_learner import get_learning_runs
    return jsonify(get_learning_runs(limit=limit, offset=offset))


@bp.route("/learning/runs/<run_id>", methods=["GET"])
def get_learning_run(run_id):
    """Get full audit detail of a learning run.

    Shows exactly what was sent to LLM and what was learned.
    """
    from myxai_desk.core.intent_engine.nightly_learner import get_learning_run_detail
    detail = get_learning_run_detail(run_id)
    if not detail:
        return jsonify({"error": "run not found"}), 404
    return jsonify(detail)


# ── User Lexicon (Version Control) ────────────────────────────────

@bp.route("/learning/lexicon/versions", methods=["GET"])
def list_lexicon_versions():
    """List all user lexicon versions."""
    from myxai_desk.core.intent_engine.user_lexicon import list_lexicon_versions as _list
    return jsonify(_list(limit=request.args.get("limit", 20, type=int)))


@bp.route("/learning/lexicon/current", methods=["GET"])
def get_current_lexicon():
    """Get the currently active lexicon with full content."""
    from myxai_desk.core.intent_engine.user_lexicon import get_lexicon_detail
    detail = get_lexicon_detail()
    if not detail:
        return jsonify({"active": False, "synonyms": {}, "verb_map": {}, "stop_phrases": []})
    return jsonify(detail)


@bp.route("/learning/lexicon/<int:version>", methods=["GET"])
def get_lexicon_version(version):
    """Get a specific lexicon version with full content."""
    from myxai_desk.core.intent_engine.user_lexicon import get_lexicon_detail
    detail = get_lexicon_detail(version=version)
    if not detail:
        return jsonify({"error": f"version {version} not found"}), 404
    return jsonify(detail)


@bp.route("/learning/lexicon/rollback", methods=["POST"])
def rollback_lexicon():
    """Rollback to a previous lexicon version."""
    data = request.get_json(force=True) or {}
    target_version = data.get("version")
    if target_version is None:
        return jsonify({"error": "version required"}), 400

    from myxai_desk.core.intent_engine.user_lexicon import rollback_lexicon as _rollback
    result = _rollback(int(target_version))
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/learning/lexicon/diff", methods=["GET"])
def diff_lexicon():
    """Compare two lexicon versions. Shows added/removed/changed entries."""
    v1 = request.args.get("v1", type=int)
    v2 = request.args.get("v2", type=int)
    if v1 is None or v2 is None:
        return jsonify({"error": "v1 and v2 parameters required"}), 400

    from myxai_desk.core.intent_engine.user_lexicon import diff_lexicon_versions
    result = diff_lexicon_versions(v1, v2)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/learning/lexicon/save", methods=["POST"])
def save_manual_lexicon():
    """Manually save a new lexicon (for user edits)."""
    data = request.get_json(force=True) or {}
    synonyms = data.get("synonyms", {})
    verb_map = data.get("verb_map", {})
    stop_phrases = data.get("stop_phrases", [])

    if not synonyms and not verb_map and not stop_phrases:
        return jsonify({"error": "at least one field required"}), 400

    from myxai_desk.core.intent_engine.user_lexicon import save_lexicon
    lid = save_lexicon(
        synonyms=synonyms, verb_map=verb_map,
        stop_phrases=stop_phrases, source="manual",
    )
    if lid:
        return jsonify({"status": "ok", "lexicon_id": lid})
    return jsonify({"error": "save failed"}), 500


# ── Case Key Aliases ──────────────────────────────────────────────

@bp.route("/learning/aliases", methods=["GET"])
def list_aliases():
    """List active case-key aliases."""
    from myxai_desk.core.intent_engine.user_lexicon import list_case_key_aliases
    return jsonify(list_case_key_aliases(
        limit=request.args.get("limit", 50, type=int),
    ))


@bp.route("/learning/aliases", methods=["POST"])
def add_manual_alias():
    """Manually add a case-key alias mapping."""
    data = request.get_json(force=True) or {}
    alias = data.get("alias", "").strip()
    canonical = data.get("canonical", "").strip()
    if not alias or not canonical:
        return jsonify({"error": "alias and canonical required"}), 400

    from myxai_desk.core.intent_engine.user_lexicon import save_case_key_aliases
    count = save_case_key_aliases(
        [{"canonical": canonical, "aliases": [alias], "confidence": 1.0}],
        source="manual",
    )
    return jsonify({"status": "ok", "saved": count})


@bp.route("/learning/aliases/<alias>", methods=["DELETE"])
def remove_alias(alias):
    """Deactivate a case-key alias."""
    from myxai_desk.core.intent_engine.user_lexicon import delete_case_key_alias
    ok = delete_case_key_alias(alias)
    if ok:
        return jsonify({"status": "ok"})
    return jsonify({"error": "delete failed"}), 500


# ── Privacy Audit ─────────────────────────────────────────────────

@bp.route("/learning/privacy", methods=["GET"])
def get_privacy_info():
    """Get privacy info: what data is sent and learned, plus controls."""
    from myxai_desk.core.intent_engine.config import get as ie_get
    from myxai_desk.core.intent_engine.nightly_learner import get_learning_runs

    cfg = ie_get()
    recent_runs = get_learning_runs(limit=5)

    return jsonify({
        "controls": {
            "enabled": cfg.get("nightly_learning_enabled", False),
            "use_llm": cfg.get("nightly_learning_use_llm", True),
            "sanitize_pii": cfg.get("nightly_learning_sanitize_pii", True),
            "max_samples": cfg.get("nightly_learning_max_samples", 200),
        },
        "data_policy": {
            "what_is_sent": [
                "Sanitized user queries (PII removed: emails, paths, phones, IPs, URLs)",
                "Case keys (intent identifiers, no user data)",
                "Route labels (category names only)",
                "Statistical aggregates (counts, rates)",
            ],
            "what_is_never_sent": [
                "Raw file contents or paths",
                "Email addresses, phone numbers",
                "API keys or credentials",
                "Full conversation history",
            ],
            "what_is_learned": [
                "Synonym mappings (user abbreviations → standard forms)",
                "Verb mappings (colloquial verbs → standard verbs)",
                "Stop phrases (user-specific filler words)",
                "Case key aliases (equivalent intent groupings)",
            ],
            "storage": "All learned data stored locally only. Versioned and rollback-able.",
        },
        "recent_runs": recent_runs,
    })


@bp.route("/learning/preview-sanitization", methods=["POST"])
def preview_sanitization():
    """Preview how PII sanitization would transform sample text.

    Useful for user to verify what data *would* be sent to LLM.
    """
    data = request.get_json(force=True) or {}
    samples = data.get("samples", [])
    if not samples:
        return jsonify({"error": "samples array required"}), 400

    from myxai_desk.core.intent_engine.nightly_learner import sanitize_text
    results = []
    for s in samples[:20]:
        results.append({"original": s, "sanitized": sanitize_text(str(s))})
    return jsonify(results)
