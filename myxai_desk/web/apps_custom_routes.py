"""Custom Apps 路由 — 自定义应用 CRUD、运行、报告.

迁移自 app.py 的 /api/apps/custom/* 路由。
"""

import asyncio
import json
import queue
import threading

from flask import Blueprint, Response, jsonify, request, stream_with_context

from myxai_desk.web.apps_helpers import _t, inc_run_count
from myxai_desk.web.migration_guards import mark

bp = Blueprint("apps_custom", __name__, url_prefix="/api/apps/custom")


@bp.get("")
def list_all():
    mark("[NEW] apps/custom/list")
    from apps.custom_app import list_apps
    return jsonify(list_apps())


@bp.post("")
def create():
    mark("[NEW] apps/custom/create")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run("custom_app_mgmt", source="user", capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    body = request.json or {}
    name = body.get("name", "").strip()
    prompt_template = body.get("prompt_template", "").strip()
    if not name or not prompt_template:
        return jsonify({"error": _t("error.field_required", field="name and prompt_template")}), 400
    from apps.custom_app import create_app

    app = create_app(
        name=name,
        prompt_template=prompt_template,
        icon=body.get("icon", "🤖"),
        output_format=body.get("output_format", "text"),
        schedule=body.get("schedule"),
        summary=body.get("summary"),
        security_mode=body.get("security_mode"),
    )
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.custom.create", args={"name": name},
            action_id="", result_summary=f"created {app.get('id', '')}",
        )
    except Exception:
        pass
    return jsonify(app)


@bp.get("/meta")
def meta():
    mark("[NEW] apps/custom/meta")
    from apps.custom_app import OUTPUT_FORMATS, SCHEDULE_MODES
    return jsonify({"output_formats": OUTPUT_FORMATS, "schedule_modes": SCHEDULE_MODES})


@bp.get("/unread")
def unread():
    mark("[NEW] apps/custom/unread")
    from apps.custom_app import all_unread_counts
    return jsonify(all_unread_counts())


@bp.get("/<app_id>")
def get(app_id):
    mark("[NEW] apps/custom/get")
    from apps.custom_app import get_app

    app = get_app(app_id)
    if not app:
        return jsonify({"error": _t("error.app_not_found")}), 404
    return jsonify(app)


@bp.put("/<app_id>")
def update(app_id):
    mark("[NEW] apps/custom/update")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run("custom_app_mgmt", source="user", capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    body = request.json or {}
    from apps.custom_app import update_app

    app = update_app(app_id, **body)
    if not app:
        return jsonify({"error": _t("error.app_not_found")}), 404
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.custom.update", args={"app_id": app_id},
            action_id="", result_summary="updated",
        )
    except Exception:
        pass
    return jsonify(app)


@bp.delete("/<app_id>")
def delete(app_id):
    mark("[NEW] apps/custom/delete")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run("custom_app_mgmt", source="user", capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    from apps.custom_app import delete_app

    if delete_app(app_id):
        try:
            from myxai_desk.core.audit.ledger import AuditLedger
            AuditLedger().append_entry(
                capability="app.custom.delete", args={"app_id": app_id},
                action_id="", result_summary="deleted",
            )
        except Exception:
            pass
        return jsonify({"success": True})
    return jsonify({"error": _t("error.app_not_found")}), 404


@bp.post("/<app_id>/run")
def run(app_id):
    """运行自定义应用 — SSE 流式响应."""
    mark("[NEW] apps/custom/run")
    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run(app_id, source="user")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    from apps.custom_app import build_message, get_app, save_report, set_last_run

    import app as _app
    if not _app.NANOBOT_AVAILABLE:
        return jsonify({"error": _t("error.nanobot_not_installed")}), 400

    app_data = get_app(app_id)
    if not app_data:
        return jsonify({"error": _t("error.app_not_found")}), 404

    body = request.json or {}
    param_groups = body.get("param_groups", None)
    if param_groups is None:
        single = body.get("params", {})
        for p in app_data.get("parameters", []):
            if p["name"] not in single:
                single[p["name"]] = p.get("default", "")
        param_groups = [single]

    q: queue.Queue[str] = queue.Queue()

    import uuid as _uuid

    async def _process():
        try:
            agent = _app._get_or_create_agent()

            async def on_progress(content):
                q.put(json.dumps({"type": "progress", "content": content}, ensure_ascii=False))

            need_mcp = bool(agent._mcp_servers)
            has_mcp = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp:
                await _app._connect_mcp_safe(agent, progress_cb=on_progress)

            original_tools = dict(agent.tools._tools)
            safe_tools = _app._filter_tools_by_policy(
                original_tools, app_id=app_id, source="user",
                app_permissions=app_data.get("permissions", []),
            )
            agent.tools._tools = safe_tools

            total = len(param_groups)
            _app_turn_input = 0
            _app_turn_output = 0
            _app_turn_search = 0
            try:
                for idx, pv in enumerate(param_groups):
                    label = ", ".join(str(v) for v in pv.values()) if pv else ""
                    if total > 1:
                        q.put(json.dumps(
                            {"type": "progress", "content": f"[{idx + 1}/{total}] {label}"},
                            ensure_ascii=False,
                        ))

                    message = build_message(app_data, pv)
                    _CAPP_SAFETY = _app._build_safety_prompt(app_id, safe_tools)
                    message = _CAPP_SAFETY + message
                    session_key = f"capp_{_uuid.uuid4().hex[:12]}"

                    response = await agent.process_direct(
                        message, session_key=session_key, on_progress=on_progress,
                    )

                    with _app._last_usage_lock:
                        _run_usage = _app._last_usage.pop(session_key, {})
                    _app_turn_input += _run_usage.get("input", 0)
                    _app_turn_output += _run_usage.get("output", 0)
                    _app_turn_search += _run_usage.get("search", 0)

                    save_report(app_id, content=response or "", params_used=pv)

                    if total > 1:
                        q.put(json.dumps(
                            {"type": "progress", "content": f"[{idx + 1}/{total}] {label}"},
                            ensure_ascii=False,
                        ))
            finally:
                agent.tools._tools = original_tools

            _app_cat = f"app_{app_data.get('name', app_id)}"
            from apps.llm_utils import record_task_usage
            record_task_usage(_app_cat, _app_turn_input, _app_turn_output, _app_turn_search)

            set_last_run(app_id)
            inc_run_count(app_id)
            try:
                from myxai_desk.core.runtime.app_governance import finish_app_run
                finish_app_run(app_id, success=True)
            except Exception:
                pass
            _done_payload = {"type": "done", "content": ""}
            if _app_turn_input or _app_turn_output:
                _done_payload["usage"] = {
                    "input": _app_turn_input, "output": _app_turn_output,
                    "search": _app_turn_search,
                }
            q.put(json.dumps(_done_payload, ensure_ascii=False))
        except Exception as exc:
            if "original_tools" in dir():
                agent.tools._tools = original_tools
            q.put(json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False))

    _app._ensure_loop()
    asyncio.run_coroutine_threadsafe(_process(), _app._async_loop)

    def generate():
        while True:
            try:
                data = q.get(timeout=300)
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'error', 'content': _t('error.request_timeout')})}\n\n"
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.get("/<app_id>/reports")
def reports(app_id):
    mark("[NEW] apps/custom/reports")
    from apps.custom_app import list_reports
    return jsonify(list_reports(app_id))


@bp.get("/<app_id>/report/<path:key>")
def report_get(app_id, key):
    mark("[NEW] apps/custom/report/get")
    from apps.custom_app import get_report, mark_report_read

    report = get_report(app_id, key)
    if not report:
        return jsonify({"error": _t("error.report_not_found")}), 404
    mark_report_read(app_id, key)
    return jsonify(report)


@bp.delete("/<app_id>/report/<path:key>")
def report_delete(app_id, key):
    mark("[NEW] apps/custom/report/delete")
    from apps.custom_app import delete_report

    if delete_report(app_id, key):
        return jsonify({"success": True})
    return jsonify({"error": _t("error.report_not_found")}), 404


@bp.post("/<app_id>/summary")
def summary(app_id):
    """从历史报告生成汇总 — SSE 流式响应."""
    mark("[NEW] apps/custom/summary")
    from apps.custom_app import build_summary_prompt, get_app, mark_triggered, save_report

    app_data = get_app(app_id)
    if not app_data:
        return jsonify({"error": _t("error.app_not_found")}), 404

    prompt = build_summary_prompt(app_data)
    if not prompt:
        return jsonify({"error": _t("error.app_no_prompt")}), 400

    import app as _app
    mcfg = _app._get_model_config()
    if not mcfg.get("model") or not mcfg.get("api_key"):
        return jsonify({"error": _t("error.llm_not_configured")}), 400

    q: queue.Queue[str] = queue.Queue()

    def _run():
        try:
            q.put(json.dumps(
                {"type": "progress", "content": _t("progress.generating_summary")},
                ensure_ascii=False,
            ))
            import os
            import litellm

            os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

            _KNOWN = (
                "openai/", "azure/", "anthropic/", "cohere/", "huggingface/",
                "ollama/", "deepseek/", "groq/", "together_ai/", "openrouter/",
                "gemini/", "mistral/",
            )
            model = mcfg["model"]
            if not any(model.startswith(p) for p in _KNOWN) and mcfg.get("api_base"):
                model = f"openai/{model}"

            resp = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_key=mcfg["api_key"],
                api_base=mcfg.get("api_base"),
                temperature=0.5,
                max_tokens=4096,
            )
            _usage = getattr(resp, "usage", None)
            _sum_pi = _sum_co = 0
            if _usage:
                _sum_pi = getattr(_usage, "prompt_tokens", 0)
                _sum_co = getattr(_usage, "completion_tokens", 0)
                from apps.llm_utils import record_tokens
                record_tokens(prompt_tokens=_sum_pi, completion_tokens=_sum_co)
            from apps.llm_utils import record_task_usage
            record_task_usage(f"app_{app_data.get('name', app_id)}", _sum_pi, _sum_co, 0)
            content = resp.choices[0].message.content or ""

            save_report(app_id, content=content, params_used={}, report_type="summary")
            mark_triggered(app_id, "summary")

            _done_payload = {"type": "done", "content": content}
            if _sum_pi or _sum_co:
                _done_payload["usage"] = {"input": _sum_pi, "output": _sum_co, "search": 0}
            q.put(json.dumps(_done_payload, ensure_ascii=False))
        except Exception as exc:
            q.put(json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False))

    threading.Thread(target=_run, daemon=True).start()

    def generate():
        while True:
            try:
                data = q.get(timeout=300)
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'error', 'content': _t('error.request_timeout')})}\n\n"
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
