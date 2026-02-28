"""Intent Engine API Blueprint.

Prefix: ``/api/apps/intent_engine``
"""

from __future__ import annotations

import logging
import threading

from flask import Blueprint, jsonify, request

log = logging.getLogger("myxai")

bp = Blueprint("intent_engine", __name__, url_prefix="/api/apps/intent_engine")

_run_lock = threading.Lock()
_run_status: dict = {"running": False, "last_result": None}


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


# ── Training ───────────────────────────────────────────────────────

@bp.route("/train", methods=["POST"])
def trigger_train():
    if not _run_lock.acquire(blocking=False):
        return jsonify({"error": "training already in progress"}), 409
    _run_status["running"] = True
    _run_status["last_result"] = None

    def _do_train():
        try:
            from myxai_desk.core.intent_engine.trainer.dataset_builder import build_dataset
            from myxai_desk.core.intent_engine.trainer.train_fasttext import train

            ds_path, ds_stats = build_dataset()
            if ds_path is None:
                _run_status["last_result"] = {"status": "skip", "reason": "insufficient data", "stats": ds_stats}
                return

            result = train(ds_path)
            _run_status["last_result"] = {"status": "ok", "result": result, "dataset": ds_stats}
        except Exception as e:
            _run_status["last_result"] = {"status": "error", "error": str(e)}
            log.warning("[ie_api] training failed", exc_info=True)
        finally:
            _run_status["running"] = False
            _run_lock.release()

    threading.Thread(target=_do_train, daemon=True).start()
    return jsonify({"status": "started"})


# ── Evaluation ─────────────────────────────────────────────────────

@bp.route("/eval", methods=["POST"])
def trigger_eval():
    try:
        from myxai_desk.core.intent_engine.trainer.eval_runner import run_eval
        result = run_eval()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/eval/history", methods=["GET"])
def eval_history():
    limit = request.args.get("limit", 10, type=int)
    from myxai_desk.core.intent_engine.trainer.eval_runner import get_eval_history
    return jsonify(get_eval_history(limit=limit))


# ── Models ─────────────────────────────────────────────────────────

@bp.route("/models", methods=["GET"])
def list_models():
    from myxai_desk.core.intent_engine.trainer.train_fasttext import list_versions, get_current_model_path
    current = get_current_model_path()
    return jsonify({
        "current": str(current) if current else None,
        "versions": list_versions(),
    })


@bp.route("/models/rollback", methods=["POST"])
def rollback_model():
    data = request.get_json(force=True) or {}
    version = data.get("version")
    if not version:
        return jsonify({"error": "version required"}), 400
    from myxai_desk.core.intent_engine.trainer.train_fasttext import rollback
    result = rollback(int(version))
    if result is None:
        return jsonify({"error": f"version {version} not found"}), 404
    return jsonify(result)


# ── Status ─────────────────────────────────────────────────────────

@bp.route("/status", methods=["GET"])
def run_status():
    return jsonify(_run_status)


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
