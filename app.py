"""Otta — 桌面可视化客户端.

This file serves as the backward-compatible entry point.  New modules live
under ``myxai_desk/`` and are progressively taking over responsibility.
"""

import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

# Import the new package so its subsystems are initialised on startup.
import asyncio
import json
import logging
import queue
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("myxai")

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

import myxai_desk  # noqa: F401
from myxai_desk.core.storage import paths as _paths  # noqa: F401
from myxai_desk.core.timeutil import local_date_str
from myxai_desk.core.i18n import init_i18n

# ---------------------------------------------------------------------------
# nanobot availability
# ---------------------------------------------------------------------------
NANOBOT_AVAILABLE = False
try:
    import nanobot  # noqa: F401

    NANOBOT_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
flask_app = Flask(__name__, static_folder="frontend", static_url_path="/static")
flask_app.config["JSON_AS_ASCII"] = False
flask_app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


_NO_STORE_PATHS = frozenset({"/", "/static/app.js", "/static/i18n.js"})


@flask_app.after_request
def _no_cache_critical(response):
    """Prevent caching of index.html and critical JS files."""
    if request.path in _NO_STORE_PATHS:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


_ALLOWED_HOSTS = frozenset()


@flask_app.before_request
def _check_host_header():
    """Block requests whose Host header does not match the local server.

    This is the primary defence against DNS-rebinding attacks: even if an
    attacker resolves their domain to 127.0.0.1, the browser will send
    ``Host: evil.com`` which will be rejected here.
    """
    if _ALLOWED_HOSTS and request.host not in _ALLOWED_HOSTS:
        log.warning("Rejected request with unexpected Host header: %s", request.host)
        return jsonify({"error": "Forbidden"}), 403


@flask_app.before_request
def _check_api_token():
    """Reject /api/* requests that lack a valid X-MyxAI-Token header.

    Protects the localhost Flask server against DNS-rebinding and
    localhost-CSRF attacks by requiring a per-session random token that
    is injected into the webview at startup.

    OPTIONS (CORS preflight) is exempt because browsers send preflights
    without custom headers; the actual request that follows will still
    be validated.
    """
    if not request.path.startswith("/api/"):
        return None
    if request.method == "OPTIONS":
        return None
    token = flask_app.config.get("MYXAI_API_TOKEN")
    if not token:
        return None
    req_token = request.headers.get("X-MyxAI-Token")
    if req_token and req_token == token:
        return None
    has_hdr = req_token is not None
    ref = request.headers.get("Referer", "-")
    ua = (request.headers.get("User-Agent") or "")[:80]
    log.warning(
        "Rejected API request: %s %s | has_token_header=%s referer=%s ua=%s",
        request.method, request.path, has_hdr, ref, ua,
    )
    return jsonify({"error": "Forbidden"}), 403


# 初始化 i18n
flask_app.i18n = init_i18n()

# 初始化 extensions 字典（用于后续状态管理）
if not hasattr(flask_app, 'extensions'):
    flask_app.extensions = {}

# ---------------------------------------------------------------------------
# Register blueprints (新架构路由)
# ---------------------------------------------------------------------------
from myxai_desk.web.gateway_routes import bp as gateway_bp
from myxai_desk.web.scheduler_routes import bp as scheduler_bp
from myxai_desk.web.config_routes import bp as config_bp
from myxai_desk.web.security_routes import bp as security_bp
from myxai_desk.web.mcp_routes import bp as mcp_bp
from myxai_desk.web.i18n_routes import bp as i18n_bp
from myxai_desk.web.profile_routes import bp as profile_bp
from myxai_desk.web.apps_routes import bp as apps_bp
from myxai_desk.web.apps_digest_routes import bp as apps_digest_bp
from myxai_desk.web.apps_email_routes import bp as apps_email_bp
from myxai_desk.web.apps_custom_routes import bp as apps_custom_bp
from myxai_desk.web.reports_routes import bp as reports_bp
from myxai_desk.apps.execution_radar.api import bp as execution_radar_bp
from myxai_desk.apps.intent_engine.api import bp as intent_engine_bp
from myxai_desk.apps.strategy_hub.api import bp as strategy_hub_bp
from myxai_desk.apps.cap_forest.api import bp as cap_forest_bp

flask_app.register_blueprint(gateway_bp)
flask_app.register_blueprint(scheduler_bp)
flask_app.register_blueprint(config_bp)
flask_app.register_blueprint(security_bp)
flask_app.register_blueprint(mcp_bp)
flask_app.register_blueprint(i18n_bp)
flask_app.register_blueprint(profile_bp)
flask_app.register_blueprint(apps_bp)
flask_app.register_blueprint(apps_digest_bp)
flask_app.register_blueprint(apps_email_bp)
flask_app.register_blueprint(apps_custom_bp)
flask_app.register_blueprint(reports_bp)
flask_app.register_blueprint(execution_radar_bp)
flask_app.register_blueprint(intent_engine_bp)
flask_app.register_blueprint(strategy_hub_bp)
flask_app.register_blueprint(cap_forest_bp)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_async_loop: asyncio.AbstractEventLoop | None = None
_async_thread: threading.Thread | None = None
_agent = None
_agent_lock = threading.Lock()
_session_epoch = int(time.time())
_session_counter = 0
_gateway_process: subprocess.Popen | None = None
_cron_service = None

_mcp_log: list[dict] = []
_mcp_log_lock = threading.Lock()

_notifications: list[dict] = []
_notifications_lock = threading.Lock()

_last_tools_used: dict[str, list[str]] = {}
_last_tools_lock = threading.Lock()

_last_usage: dict[str, dict] = {}
_last_usage_lock = threading.Lock()

_last_turn_audit: dict[str, dict] = {}
_last_turn_audit_lock = threading.Lock()

_last_decision_meta: dict[str, dict] = {}
_last_decision_meta_lock = threading.Lock()


def _mcp_record(server: str, level: str, message: str):
    """Append an MCP diagnostic entry (thread-safe)."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "server": server,
        "level": level,
        "message": message,
    }
    with _mcp_log_lock:
        _mcp_log.append(entry)
        if len(_mcp_log) > 200:
            _mcp_log[:] = _mcp_log[-100:]
    print(f"[MCP][{level}] {server}: {message}", flush=True)


def _win_fix_cmd(command: str, args: list[str]) -> tuple[str, list[str]]:
    """On Windows, .cmd/.bat files cannot be spawned directly by
    ``asyncio.create_subprocess_exec``.  Wrap them with ``cmd /c``."""
    if sys.platform != "win32":
        return command, args
    exe = shutil.which(command)
    if exe and exe.lower().endswith((".cmd", ".bat")):
        return "cmd", ["/c", command, *args]
    return command, args


def _ensure_loop():
    global _async_loop, _async_thread
    if _async_loop is None or not _async_loop.is_running():
        if sys.platform == "win32":
            _async_loop = asyncio.ProactorEventLoop()
        else:
            _async_loop = asyncio.new_event_loop()
        _async_thread = threading.Thread(target=_async_loop.run_forever, daemon=True)
        _async_thread.start()


# ---------------------------------------------------------------------------
# nanobot bridge
# ---------------------------------------------------------------------------


def _resolve_api_key(raw_key: str | None, provider_name: str | None) -> str | None:
    """Resolve <<KEYRING>> placeholder to the real key from secret storage."""
    if not raw_key or raw_key == "<<KEYRING>>":
        if provider_name:
            from myxai_desk.core.storage.secrets import retrieve_provider_key
            real = retrieve_provider_key(provider_name)
            if real:
                return real
        return None if raw_key == "<<KEYRING>>" else raw_key
    return raw_key


def _make_provider(config):
    from nanobot.providers.custom_provider import CustomProvider
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    api_key = _resolve_api_key(p.api_key if p else None, provider_name)

    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    if provider_name == "custom":
        return CustomProvider(
            api_key=api_key or "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    return LiteLLMProvider(
        api_key=api_key,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )


def _reset_agent():
    """Destroy the current agent, properly closing MCP connections."""
    from myxai_desk.web.state import get_state
    
    global _agent, _cron_service
    state = get_state(flask_app)
    
    if _cron_service is not None:
        _cron_service.stop()
        _cron_service = None
        state.cron_service = None
    
    with _agent_lock:
        old = _agent
        _agent = None
        state.agent = None
    
    if old and hasattr(old, "_mcp_stack") and old._mcp_stack is not None:

        async def _close():
            try:
                await old._mcp_stack.aclose()
            except Exception:
                log.debug("MCP stack close failed", exc_info=True)

        _ensure_loop()
        asyncio.run_coroutine_threadsafe(_close(), _async_loop)
    
    with _mcp_log_lock:
        _mcp_log.clear()


def _push_notification(title: str, content: str, level: str = "info"):
    """Push a notification to the frontend queue."""
    entry = {
        "id": f"n-{int(time.time() * 1000)}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "content": content,
        "level": level,
        "read": False,
    }
    with _notifications_lock:
        _notifications.append(entry)
        if len(_notifications) > 100:
            _notifications[:] = _notifications[-50:]


import contextlib
import re as _re

# ---------------------------------------------------------------------------
# i18n helper
# ---------------------------------------------------------------------------
def _t(key: str, **kwargs) -> str:
    """Shorthand for translation with lazy initialization."""
    try:
        from myxai_desk.core.i18n import get_translator
        return get_translator().t(key, **kwargs)
    except:
        # Fallback if i18n not initialized
        return key


# ---------------------------------------------------------------------------
# Execution mode detection
# ---------------------------------------------------------------------------
_EXEC_TRIGGER = _re.compile(
    r"提醒|定时|闹钟|计划|取消|删除|清除|移除|搜索|查找|查询|"
    r"打开|访问|下载|安装|执行|运行|创建|新建|添加|设置|修改|"
    r"编辑|写入|保存|发送|列出|查看任务|查看提醒|有哪些",
)
_FAKE_EXEC = _re.compile(
    r"已成功|已设置|已创建|已删除|已取消|已清除|已移除|已完成|已执行|"
    r"设置成功|创建成功|删除成功|取消成功|任务已|提醒已|"
    r"Executed tools|Created job|Removed job",
)


def _is_exec_mode(user_msg: str) -> bool:
    """Determine if the user's request requires tool execution (EXEC mode)."""
    return bool(_EXEC_TRIGGER.search(user_msg))


def _is_fake_execution(reply: str) -> bool:
    """Detect if the LLM's response simulates a tool action in plain text."""
    return bool(_FAKE_EXEC.search(reply))


def _compress_history(messages: list[dict], keep_recent: int = 4) -> list[dict]:
    """Compress older history into a brief summary to reduce LLM pattern mimicking.

    Keeps the most recent ``keep_recent`` messages verbatim.  Older messages
    are collapsed into a single system-style summary that provides factual
    context without the original wording that the LLM might copy.
    """
    if len(messages) <= keep_recent:
        return messages

    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    summaries = []
    for m in old:
        role = m["role"]
        text = (m.get("content") or "")[:80]
        if text:
            summaries.append(f"- {role}: {text}")

    if summaries:
        summary_text = "[Earlier]\n" + "\n".join(summaries[-4:])
        return [{"role": "assistant", "content": summary_text}] + recent
    return recent


def _tool_to_capability(tool_name: str, arguments: dict) -> tuple[str, str]:
    """Map a nanobot tool name to a (capability, operation) pair for policy.

    Uses ToolRegistry metadata when available, falls back to string matching.
    """
    # Try metadata first (new way)
    try:
        from myxai_desk.core.capabilities.metadata import get_tool_registry

        registry = get_tool_registry()
        metadata = registry.get(tool_name)

        if metadata:
            return metadata.capability.value, metadata.operation.value
    except Exception:
        log.debug("Tool registry lookup failed, falling back to string matching", exc_info=True)

    # Fallback: string matching (legacy, gradually being replaced)
    tn = tool_name.lower()
    if any(
        k in tn
        for k in (
            "file",
            "read_file",
            "write_file",
            "list_dir",
            "create_file",
            "move_file",
            "copy_file",
        )
    ):
        if "read" in tn or "list" in tn:
            return "fs", "read"
        if "write" in tn or "create" in tn:
            return "fs", "write_text"
        if "move" in tn or "rename" in tn:
            return "fs", "move"
        if "copy" in tn:
            return "fs", "copy"
        if "remove" in tn or "delete" in tn:
            return "fs", "remove"
        return "fs", tn

    if any(
        k in tn
        for k in ("exec", "run", "shell", "command", "bash", "powershell", "terminal", "subprocess")
    ):
        return "proc", "execute"

    if any(k in tn for k in ("search", "web_search", "brave", "baidu")):
        return "search", "search"

    if any(k in tn for k in ("http", "fetch", "download", "request", "curl")):
        return "net", "http_get"

    if "mcp" in tn:
        return "mcp", tn

    if "profile" in tn:
        return "profile", tn

    # Unknown tools default to proc (safest to gate)
    if arguments.get("command") or arguments.get("cmd"):
        return "proc", "execute"

    return "proc", tn


_DENY_SUGGEST_MODE: dict[str, str | None] = {
    "PROC_NOT_ALLOWED_IN_MODE": "Assistant",
    "PROC_DANGEROUS": "Operator",
    "NET_HTTP_NOT_ALLOWED": "Assistant",
    "MCP_NOT_ALLOWED_IN_MODE": "Assistant",
    "FS_OUT_OF_WRITE_SCOPE": "Operator",
    "FS_SYSTEM_WRITE_BLOCKED": None,
    "FS_UNSAFE_PATH": None,
}


def _suggest_mode_for_deny(reason_code: str) -> str:
    """Return the minimum mode name that would allow this operation, or ''."""
    base = reason_code.split(":")[0]
    return _DENY_SUGGEST_MODE.get(base) or ""


_CONFIRM_RE = _re.compile(
    r"^\s*(确认|是的|好的|执行|执行吧|同意|可以|没问题|好|行|"
    r"yes|confirm|go ahead|ok|do it|proceed|sure)\s*[!！。.]*\s*$",
    _re.IGNORECASE,
)


def _try_execute_pending() -> str | None:
    """If there is a pending action, execute it and return the result string.

    Returns ``None`` if no pending actions exist.
    """
    try:
        from myxai_desk.core.orchestrator.planner import get_plan_manager

        pm = get_plan_manager()
        pending = pm.list_pending()
        if not pending:
            return None
        pa = pm.confirm_pending(pending[0]["action_id"])
        if not pa:
            return None
        agent = _get_or_create_agent()
        _ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            agent.tools.execute(pa.tool_name, pa.tool_args),
            _async_loop,
        )
        result = future.result(timeout=120)
        from myxai_desk.core.capabilities.governance import (
            post_execution_audit,
            post_execution_undo,
        )

        post_execution_audit(pa.capability, pa.op, pa.tool_args, result, None)
        post_execution_undo(pa.capability, pa.op, pa.tool_args, result)
        try:
            from myxai_desk.core.execution_log.event_writer import record_step
            record_step(
                session_id="pending_confirm", tool_name=pa.tool_name,
                args_json=pa.tool_args, status="ok", action="EXEC_CONFIRMED",
                result_preview=str(result)[:500],
            )
        except Exception:
            pass
        print(f"[policy] Confirmed via chat → executed {pa.tool_name}")
        return _t("policy.tool_executed", 
                  tool_name=pa.tool_name,
                  args=str(pa.tool_args)[:300],
                  result=str(result)[:2000])
    except Exception as exc:
        log.exception("[policy] Pending execution error")
        try:
            from myxai_desk.core.execution_log.event_writer import record_step
            from myxai_desk.core.execution_log.error_codes import classify_error as _cls_err
            record_step(
                session_id="pending_confirm", tool_name="__pending__",
                status="hard_fail", error_code=_cls_err(exc=exc),
                action="HARD_FAIL", result_preview=str(exc)[:500],
            )
        except Exception:
            pass
        return _t("policy.exec_failed", error=str(exc))


_TOOLS_FS = {"exec", "read_file", "list_dir", "write_file", "edit_file"}
_TOOLS_SEARCH = {"web_search", "web_fetch", "smart_fetch"}
_TOOLS_SCHEDULE = {"cron"}
_TOOLS_COMM = {"message", "spawn"}

_TRIGGER_SEARCH = _re.compile(
    r"搜索|查找|查询|搜一下|谷歌|百度|google|search|bing|"
    r"新闻|资讯|最新|天气|汇率|股价",
    _re.IGNORECASE,
)
_TRIGGER_FETCH = _re.compile(
    r"https?://\S|www\.\S|抓取|获取.*(?:网页|页面|内容)|打开.*链接|简报|摘要|fetch\b",
    _re.IGNORECASE,
)
_TRIGGER_SCHEDULE = _re.compile(
    r"提醒|定时|闹钟|计划|cron|schedule|remind|timer|"
    r"每天|每周|每月|分钟后|小时后",
    _re.IGNORECASE,
)
_TRIGGER_COMM = _re.compile(
    r"发送|消息|通知|message|send|notify|后台|子任务|spawn",
    _re.IGNORECASE,
)
_TRIGGER_MCP = _re.compile(
    r"浏览器|网页|打开.*页面|截图|screenshot|browser|playwright|"
    r"点击.*按钮|填写.*表单|click|navigate|scroll|fill|type.*input|"
    r"自动化|爬取|抓取|scrape|crawl",
    _re.IGNORECASE,
)


def _filter_tool_defs_for_message(
    user_msg: str,
    all_defs: list[dict],
) -> list[dict]:
    """Select only relevant tools based on user intent to minimize tokens."""
    needed = set(_TOOLS_FS)

    if _TRIGGER_SEARCH.search(user_msg):
        needed |= _TOOLS_SEARCH
    if _TRIGGER_FETCH.search(user_msg):
        needed |= _TOOLS_SEARCH
    if _TRIGGER_SCHEDULE.search(user_msg):
        needed |= _TOOLS_SCHEDULE
    if _TRIGGER_COMM.search(user_msg):
        needed |= _TOOLS_COMM

    include_mcp = bool(_TRIGGER_MCP.search(user_msg))

    return [
        d
        for d in all_defs
        if d.get("function", {}).get("name", "") in needed
        or (include_mcp and d.get("function", {}).get("name", "").startswith("mcp_"))
    ]


def _patch_agent_tool_history(agent):
    """Monkey-patch the agent's _process_message for execution governance."""
    import types as _types

    from nanobot.bus.events import OutboundMessage

    _orig_build_system_prompt = agent.context.build_system_prompt

    def _enhanced_system_prompt(skill_names=None):
        base = _orig_build_system_prompt(skill_names)

        from myxai_desk.core.policy.modes import SecurityMode, get_current_mode

        mode = get_current_mode()

        style_hint = (
            "\nRESPONSE STYLE: Adapt verbosity to the task type. "
            "For tool/command execution (delete, create, run, search, etc.): "
            "report the result in 1-2 short sentences, no safety disclaimers, "
            "no follow-up menus, no repeated explanations. "
            "Example: '✅ D:\\download\\3.jpg 已移入回收站。' "
            "For discussions, analysis, planning, or Q&A: "
            "respond with appropriate detail and structure."
        )

        if mode in (SecurityMode.OPERATOR, SecurityMode.DEVELOPER):
            mode_hint = (
                f"\n[Mode:{mode.value}] "
                "All ops authorized. Call tools directly, no confirmation needed. "
                'File deletion: use exec with `del "path"` (Win) or `rm "path"` (Linux). '
                "NEVER use PowerShell COM or complex scripts for basic file ops." + style_hint
            )
        else:
            mode_hint = (
                f"\n[Mode:{mode.value}] "
                "Destructive ops restricted; suggest switching to Operator mode if needed."
                + style_hint
            )

        persona_block = ""
        try:
            from myxai_desk.core.capabilities.profile import Profile

            profile = Profile()
            settings = profile.get_collection_settings()
            if settings.get("persona_in_digest", False):
                persona_text = profile.get_persona_prompt()
                if persona_text:
                    persona_block = "\n" + persona_text
        except Exception:
            log.warning("Failed to load persona/profile for system prompt", exc_info=True)

        fetch_rules = (
            "\n\nURL FETCH RULES (MANDATORY):\n"
            "A) To fetch content from any URL, ALWAYS use smart_fetch(url) first.\n"
            "B) NEVER use exec with curl/wget/Invoke-WebRequest to fetch web pages.\n"
            "C) If smart_fetch returns blocked=true or ok=false, STOP and tell the user. "
            "Do NOT fabricate content or try alternative shell commands.\n"
            "D) NEVER write a report/digest/summary if you have no valid source text. "
            "If all fetches failed, inform the user and suggest alternatives.\n"
            "E) For each URL, attempt smart_fetch at most 2 times. If still failing, stop."
        )

        cap_summary = ""
        if hasattr(agent, "_cap_manager"):
            cap_summary = "\n[CAPABILITIES] " + agent._cap_manager.get_prompt_summary()

        return base + mode_hint + persona_block + fetch_rules + cap_summary

    agent.context.build_system_prompt = _enhanced_system_prompt

    async def _patched_process_message(self, msg, session_key=None, on_progress=None):
        import json as _json

        if msg.channel == "system":
            return await self._process_system_message(msg)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        cmd = msg.content.strip().lower()
        if cmd == "/new":
            messages_to_archive = session.messages.copy()
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            import asyncio as _aio

            from nanobot.session.manager import Session

            async def _consolidate():
                temp = Session(key=session.key)
                temp.messages = messages_to_archive
                await self._consolidate_memory(temp, archive_all=True)

            _aio.create_task(_consolidate())
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="New session started. Memory consolidation in progress.",
            )
        if cmd == "/help":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="\U0001f408 nanobot commands:\n/new \u2014 Start a new conversation\n/help \u2014 Show available commands",
            )

        if len(session.messages) > self.memory_window:
            import asyncio as _aio

            _aio.create_task(self._consolidate_memory(session))

        self._set_tool_context(msg.channel, msg.chat_id)

        is_cron = key.startswith("cron:")
        exec_mode = not is_cron and _is_exec_mode(msg.content)

        _keep = 2 if exec_mode else 4
        raw_history = session.get_history(max_messages=self.memory_window)
        clean_history = [m for m in raw_history if m["role"] != "tool" and "tool_calls" not in m]
        clean_history = _compress_history(clean_history, keep_recent=_keep)
        initial_messages = self.context.build_messages(
            history=clean_history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        async def _bus_progress(content):
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                    metadata=msg.metadata or {},
                )
            )

        # --- Run the agent loop with EXEC governance ---
        messages = list(initial_messages)
        n_initial = len(messages)
        iteration = 0
        final_content = None
        tools_used = []
        _turn_events: list[dict] = []
        progress = on_progress or _bus_progress
        nudge_count = 0
        from myxai_desk.core.policy.modes import SecurityMode as _SM
        from myxai_desk.core.policy.modes import get_current_mode as _gcm

        max_nudges = 0 if _gcm() in (_SM.OPERATOR, _SM.DEVELOPER) else 1

        all_tool_defs = self.tools.get_definitions()
        _ie_result = None
        try:
            from myxai_desk.core.intent_engine.config import routing_enabled as _ie_routing_enabled
            if _ie_routing_enabled():
                from myxai_desk.core.intent_engine import predict as _ie_predict
                _mcp_names = [d.get("function", {}).get("name", "") for d in all_tool_defs
                              if d.get("function", {}).get("name", "").startswith("mcp_")]
                _ie_result = _ie_predict(
                    msg.content,
                    context={"session_id": key, "exec_mode": exec_mode,
                             "history_len": len(clean_history)},
                    all_tool_defs=all_tool_defs,
                    mcp_tool_names=_mcp_names,
                )
                tool_defs = _ie_result.filter_tools(all_tool_defs)
                _ie_result.save(session_id=key, user_text=msg.content,
                                context={"exec_mode": exec_mode})
            else:
                tool_defs = _filter_tool_defs_for_message(msg.content, all_tool_defs)
        except Exception:
            tool_defs = _filter_tool_defs_for_message(msg.content, all_tool_defs)

        # ── Capability Forest: override tool routing if enabled ──
        try:
            from myxai_desk.apps.cap_forest.router import cap_forest_enabled, capability_router, clear_wake_once
            if cap_forest_enabled():
                tool_defs = capability_router(msg.content, _ie_result, all_tool_defs)
                clear_wake_once()
        except Exception:
            pass
        # ── Intent Engine: inject case hints into system message ──
        if _ie_result and _ie_result.hints:
            _hint_block = f"\n\n[EXPERIENCE HINTS]\n{_ie_result.hints}"
            if messages and messages[0].get("role") == "system":
                messages[0] = {**messages[0], "content": messages[0]["content"] + _hint_block}

        print(
            f"[agent] exec_mode={exec_mode}, tools={len(tool_defs)}/{len(all_tool_defs)}, "
            f"ie={'on' if _ie_result else 'off'}, "
            f"hints={'yes' if (_ie_result and _ie_result.hints) else 'no'}, "
            f"history={n_initial}, model={self.model}"
        )

        _turn_input = 0
        _turn_output = 0
        _turn_search = 0

        from apps.smart_fetch import FetchGuard

        _fetch_guard = FetchGuard()
        _cap_guard = None
        if hasattr(self, "_cap_manager"):
            from apps.capabilities import CapabilityGuard

            _cap_guard = CapabilityGuard(self._cap_manager)

        # ── Golden 2.0 + PR-2: deterministic replay (no LLM) ──
        _skip_llm_loop = False
        _plan_source: str | None = None
        _case_key: str | None = None
        _candidate_id: str | None = None
        _removed_steps: int | None = None
        _attempts_count = 0
        _llm_attempts = 0
        _golden_version: int | None = None

        # ── Priority 1 & 2: Golden 2.0 (Instance / Template) ──
        if _ie_result:
            try:
                from myxai_desk.core.intent_engine.config import golden_v2_enabled as _gv2_on
                if _gv2_on():
                    from myxai_desk.core.golden.slot_extractor import extract_slots as _extract_slots
                    from myxai_desk.core.golden.store import GoldenV2Store as _GV2Store, compute_instance_key as _compute_ikey
                    from myxai_desk.core.golden.template_matcher import match as _template_match
                    from myxai_desk.core.golden.replay_validator import validate as _replay_validate
                    from myxai_desk.core.golden.models import GoldenInstance as _GI
                    from myxai_desk.core.intent_engine.plan_runner import run_plan as _run_plan
                    from myxai_desk.core.golden_store import parse_candidate_plan as _parse_candidate_plan

                    _slot_result = _extract_slots(msg.content)
                    _gv2_store = _GV2Store()

                    if _slot_result.intent_label and _slot_result.confidence >= 0.3:
                        _instance_key = _compute_ikey(
                            _slot_result.intent_label,
                            _slot_result.slots,
                        )

                        # Priority 1: Instance hit (exact match, fastest)
                        _inst = _gv2_store.get_instance(_instance_key)
                        if _inst and _inst.resolved_plan:
                            _v = _replay_validate(_inst.resolved_plan, _slot_result.slots)
                            if _v.ok:
                                _inst_steps = _parse_candidate_plan(
                                    _inst.resolved_plan_json
                                    if isinstance(_inst.resolved_plan_json, str)
                                    else json.dumps(_inst.resolved_plan)
                                )
                                if _inst_steps:
                                    _inst_result = await _run_plan(_inst_steps, self.tools, key, progress)
                                    _attempts_count += _inst_result.steps_executed
                                    if _inst_result.success:
                                        _gv2_store.record_instance_use(
                                            _instance_key, ok=True,
                                            duration_ms=_inst_result.total_duration_ms,
                                            run_id=getattr(_ie_result, "run_id", None),
                                        )
                                        tools_used = [s["tool_name"] for s in _inst_result.results if s.get("tool_name")]
                                        final_content = _inst_result.final_summary
                                        _plan_source = "golden_v2_instance"
                                        _case_key = _instance_key
                                        _skip_llm_loop = True
                                        print(f"[agent] golden_v2 instance hit: key={_instance_key[:12]}, steps={_inst_result.steps_executed}")
                                    else:
                                        _gv2_store.record_instance_use(_instance_key, ok=False)
                                        print(f"[agent] golden_v2 instance FAILED at step {_inst_result.failed_at}, falling through")

                        # Priority 2: Template hit (slot filling)
                        if not _skip_llm_loop:
                            _tmatch = _template_match(_slot_result.intent_label, _slot_result.slots)
                            if _tmatch and _tmatch.filled_plan:
                                _v = _replay_validate(_tmatch.filled_plan, _slot_result.slots, _tmatch.constraints)
                                if _v.ok:
                                    _tpl_steps = _parse_candidate_plan(json.dumps(_tmatch.filled_plan, ensure_ascii=False))
                                    if _tpl_steps:
                                        _tpl_result = await _run_plan(_tpl_steps, self.tools, key, progress)
                                        _attempts_count += _tpl_result.steps_executed
                                        if _tpl_result.success:
                                            _gv2_store.save_instance(
                                                case_key=_instance_key,
                                                template_id=_tmatch.template_id,
                                                intent_label=_slot_result.intent_label,
                                                slot_values=_slot_result.slots,
                                                resolved_plan=_tmatch.filled_plan,
                                            )
                                            _gv2_store.record_template_use(_tmatch.template_id, ok=True)
                                            tools_used = [s["tool_name"] for s in _tpl_result.results if s.get("tool_name")]
                                            final_content = _tpl_result.final_summary
                                            _plan_source = "golden_v2_template"
                                            _case_key = _instance_key
                                            _skip_llm_loop = True
                                            print(f"[agent] golden_v2 template hit: tpl={_tmatch.template_id[:16]}, steps={_tpl_result.steps_executed}")
                                        else:
                                            _gv2_store.record_template_use(_tmatch.template_id, ok=False)
                                            print(f"[agent] golden_v2 template FAILED, falling through")
            except Exception:
                log.warning("[agent] golden_v2 replay skipped", exc_info=True)

        # ── Priority 3: Candidate replay → promote to v2 Instance ──
        if not _skip_llm_loop and _ie_result:
            try:
                from myxai_desk.core.intent_engine.config import golden_enabled as _golden_on
                if not _golden_on():
                    raise RuntimeError("golden replay disabled by config")

                from myxai_desk.core.golden_store import (
                    GoldenStore as _GoldenStore,
                    compute_case_key as _compute_case_key,
                    parse_candidate_plan as _parse_candidate_plan,
                )
                from myxai_desk.core.intent_engine.dao import update_ie_run as _update_ie_run
                from myxai_desk.core.intent_engine.plan_runner import run_plan as _run_plan

                _sec_mode = ""
                try:
                    _sec_mode = _gcm().value
                except Exception:
                    pass
                _case_key = _compute_case_key(
                    msg.content,
                    route_labels=_ie_result.route_labels,
                    security_mode=_sec_mode,
                )

                if _ie_result.run_id:
                    _update_ie_run(_ie_result.run_id, case_key=_case_key)

                _store = _GoldenStore()
                _cand = _store.get_best_candidate(_case_key)
                if _cand:
                    _candidate_id = _cand.candidate_id
                    _removed_steps = _cand.removed_steps
                    if _ie_result.run_id:
                        _update_ie_run(
                            _ie_result.run_id,
                            candidate_id=_candidate_id,
                            removed_steps=_removed_steps,
                        )
                    _cand_steps = _parse_candidate_plan(_cand.candidate_plan_json)
                    if _cand_steps:
                        _cand_result = await _run_plan(_cand_steps, self.tools, key, progress)
                        _attempts_count += _cand_result.steps_executed
                        _store.mark_candidate_used(_cand.candidate_id, ok=_cand_result.success)

                        if _cand_result.success:
                            # Save as v2 Instance instead of legacy golden_plan
                            try:
                                from myxai_desk.core.golden.store import GoldenV2Store as _GV2Promote
                                _GV2Promote().save_instance(
                                    case_key=_case_key,
                                    template_id=None,
                                    intent_label=",".join(_ie_result.route_labels) if _ie_result.route_labels else "",
                                    slot_values={},
                                    resolved_plan=_cand_steps,
                                )
                            except Exception:
                                log.debug("[agent] candidate→v2 instance save failed", exc_info=True)
                            tools_used = [s["tool_name"] for s in _cand_result.results if s.get("tool_name")]
                            final_content = _cand_result.final_summary
                            _plan_source = "golden_candidate"
                            _skip_llm_loop = True
                            print(f"[agent] golden_candidate: promoted to v2 instance, steps={_cand_result.steps_executed}")
                        else:
                            print(f"[agent] candidate {_cand.candidate_id[:8]} FAILED, falling through")
            except Exception:
                log.warning("[agent] candidate replay skipped", exc_info=True)

        # ── PlanRunner — reuse cached plan from ie_cases, skip LLM ──
        if not _skip_llm_loop and _ie_result and _ie_result.decision == "reuse_plan" and _ie_result.plan_steps:
            try:
                from myxai_desk.core.intent_engine.plan_runner import run_plan as _run_plan
                _plan_result = await _run_plan(
                    _ie_result.plan_steps, self.tools, key, progress,
                )
                _attempts_count += _plan_result.steps_executed
                tools_used = [
                    s["tool_name"] for s in _plan_result.results if s.get("tool_name")
                ]
                final_content = _plan_result.final_summary
                _plan_source = "reuse_plan"
                _skip_llm_loop = True
                print(f"[agent] plan_runner: success={_plan_result.success}, steps={_plan_result.steps_executed}")
            except Exception:
                log.warning("[agent] plan_runner failed, falling through to LLM", exc_info=True)

        try:
            while not _skip_llm_loop and iteration < self.max_iterations:
                iteration += 1
                _llm_attempts += 1
                response = await self.provider.chat(
                    messages=messages,
                    tools=tool_defs,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                _usage = getattr(response, "usage", None) or {}
                if _usage:
                    _pi = _usage.get("prompt_tokens", 0)
                    _co = _usage.get("completion_tokens", 0)
                    _turn_input += _pi
                    _turn_output += _co
                    from apps.llm_utils import record_tokens

                    record_tokens(prompt_tokens=_pi, completion_tokens=_co)

                if response.has_tool_calls:
                    if progress:
                        clean = self._strip_think(response.content)
                        if clean:
                            await progress(clean)

                    tc_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": _json.dumps(tc.arguments)},
                        }
                        for tc in response.tool_calls
                    ]
                    messages = self.context.add_assistant_message(
                        messages,
                        response.content,
                        tc_dicts,
                        reasoning_content=response.reasoning_content,
                    )
                    for tc in response.tool_calls:
                        tools_used.append(tc.name)
                        _attempts_count += 1
                        if "search" in tc.name.lower():
                            _turn_search += 1
                        print(f"[agent] tool: {tc.name}({str(tc.arguments)[:100]})")
                        import time as _time_mod
                        _step_start_ts = _time_mod.time()

                        # ── CapabilityGuard: environment/network/policy check ──
                        if _cap_guard:
                            _cap_block = await _cap_guard.check(tc.name, tc.arguments)
                            if _cap_block:
                                result = _cap_block
                                _turn_events.append(
                                    {"tool": tc.name, "cap": "capability", "action": "CAP_BLOCK"}
                                )
                                print(f"[cap] {tc.name}: {_cap_block[:80]}")
                                if progress:
                                    await progress(_json.dumps({
                                        "__tool_call__": True,
                                        "name": tc.name,
                                        "arguments": tc.arguments,
                                    }, ensure_ascii=False))
                                print(f"[agent] result(cap): {str(result)[:100]}")
                                try:
                                    from myxai_desk.core.execution_log.event_writer import record_step_from_event
                                    record_step_from_event(
                                        session_id=key, tool_name=tc.name, args=tc.arguments,
                                        result=str(result)[:500], turn_event=_turn_events[-1],
                                        started_at=_step_start_ts,
                                    )
                                except Exception:
                                    pass
                                messages = self.context.add_tool_result(
                                    messages, tc.id, tc.name, result,
                                )
                                continue

                        # ── FetchGuard: attempt limiter + no-source-no-write ──
                        _guard_block = _fetch_guard.pre_execute(tc.name, tc.arguments)
                        if _guard_block:
                            result = _guard_block
                            _turn_events.append(
                                {"tool": tc.name, "cap": "guard", "action": "GUARD_BLOCK"}
                            )
                            print(f"[guard] {tc.name}: {_guard_block[:80]}")
                            if progress:
                                await progress(_json.dumps({
                                    "__tool_call__": True,
                                    "name": tc.name,
                                    "arguments": tc.arguments,
                                }, ensure_ascii=False))
                            print(f"[agent] result(guard): {str(result)[:100]}")
                            try:
                                from myxai_desk.core.execution_log.event_writer import record_step_from_event
                                record_step_from_event(
                                    session_id=key, tool_name=tc.name, args=tc.arguments,
                                    result=str(result)[:500], turn_event=_turn_events[-1],
                                    started_at=_step_start_ts,
                                )
                            except Exception:
                                pass
                            messages = self.context.add_tool_result(
                                messages, tc.id, tc.name, result,
                            )
                            continue

                        # ── Phase 1: Policy gate (pre-execution) ──
                        from myxai_desk.core.policy.engine import decide as _policy_decide

                        _cap, _op = _tool_to_capability(tc.name, tc.arguments)
                        _decision = _policy_decide(
                            capability=_cap,
                            op=_op,
                            args=tc.arguments,
                            context={"workspace": getattr(self, "workspace", None)},
                        )
                        if _decision.action == "DENY":
                            _suggest = _suggest_mode_for_deny(_decision.reason_code)
                            _upgrade_hint = (
                                _t("policy.blocked",
                                   explain=_decision.explain,
                                   suggest=_suggest,
                                   mode=_decision.evidence.get('mode', ''),
                                   code=_decision.reason_code)
                                if _suggest
                                else ""
                            )
                            result = (
                                f"[BLOCKED] {_decision.explain}{_upgrade_hint}\n"
                                f"(当前模式={_decision.evidence.get('mode', '')}, "
                                f"code={_decision.reason_code})"
                            )
                            _turn_events.append(
                                {
                                    "tool": tc.name,
                                    "cap": _cap,
                                    "action": "DENY",
                                    "code": _decision.reason_code,
                                }
                            )
                            print(f"[policy] DENIED: {_decision.reason_code}")

                        elif _decision.action == "REQUIRE_CONFIRM":
                            from myxai_desk.core.orchestrator.planner import get_plan_manager

                            _pm = get_plan_manager()
                            _pending_id = _pm.store_pending(
                                tool_name=tc.name,
                                tool_args=tc.arguments,
                                capability=_cap,
                                op=_op,
                                risk=_decision.risk,
                                explain=_decision.explain,
                                evidence=_decision.evidence,
                                ui=_decision.ui,
                            )
                            _args_brief = str(tc.arguments)[:200]
                            result = (
                                f"[NEEDS CONFIRM] 此操作需要用户确认后才能执行。\n"
                                f"操作: {tc.name}({_args_brief})\n"
                                f"原因: {_decision.explain}\n"
                                f"风险等级: {_decision.risk}/100\n"
                                f"请在对话中向用户说明要执行的操作内容和风险，"
                                f"并询问用户是否确认执行。用户回复「确认」后将自动执行。"
                            )
                            _turn_events.append(
                                {
                                    "tool": tc.name,
                                    "cap": _cap,
                                    "action": "CONFIRM",
                                    "risk": _decision.risk,
                                }
                            )
                            print(f"[policy] REQUIRE_CONFIRM → pending {_pending_id}")

                        elif _decision.action == "REQUIRE_SANDBOX":
                            from myxai_desk.core.runtime.sandbox import Sandbox as _Sandbox

                            _sbx = _Sandbox(
                                app_id="agent", workspace=getattr(self, "workspace", None)
                            )
                            _path_arg = tc.arguments.get("path", tc.arguments.get("file_path", ""))
                            if _path_arg and not _sbx.is_path_allowed(_path_arg):
                                result = _t("policy.sandbox_deny",
                                           path=_path_arg,
                                           risk=_decision.risk,
                                           code=_decision.reason_code)
                                _turn_events.append(
                                    {"tool": tc.name, "cap": _cap, "action": "SANDBOX_DENY"}
                                )
                                print(f"[policy] SANDBOX blocked path: {_path_arg}")
                            else:
                                result = await self.tools.execute(tc.name, tc.arguments)
                                from myxai_desk.core.capabilities.governance import (
                                    post_execution_audit,
                                    post_execution_undo,
                                )

                                post_execution_audit(_cap, _op, tc.arguments, result, _decision)
                                post_execution_undo(_cap, _op, tc.arguments, result)
                                _turn_events.append(
                                    {"tool": tc.name, "cap": _cap, "action": "EXEC", "ok": True}
                                )
                                print("[policy] SANDBOX: passed, executed")

                        elif _decision.action == "REQUIRE_COOLDOWN":
                            result = await self.tools.execute(tc.name, tc.arguments)
                            _cooldown_secs = _decision.ui.get("cooldown_seconds", 5)
                            from myxai_desk.core.capabilities.governance import (
                                post_execution_audit,
                                post_execution_undo,
                            )

                            post_execution_audit(_cap, _op, tc.arguments, result, _decision)
                            post_execution_undo(
                                _cap,
                                _op,
                                tc.arguments,
                                result,
                                cooldown_seconds=_cooldown_secs,
                            )
                            _turn_events.append(
                                {
                                    "tool": tc.name,
                                    "cap": _cap,
                                    "action": "EXEC",
                                    "ok": True,
                                    "cooldown": _cooldown_secs,
                                }
                            )
                            print(f"[policy] COOLDOWN: executed with {_cooldown_secs}s cooldown")

                        else:
                            # ── Phase 2: nanobot executes (ALLOW) ──
                            result = await self.tools.execute(tc.name, tc.arguments)

                            # ── Phase 3: Post-execution governance ──
                            from myxai_desk.core.capabilities.governance import (
                                post_execution_audit,
                                post_execution_undo,
                            )

                            post_execution_audit(
                                _cap,
                                _op,
                                tc.arguments,
                                result,
                                _decision,
                            )
                            post_execution_undo(
                                _cap,
                                _op,
                                tc.arguments,
                                result,
                            )
                            _turn_events.append(
                                {"tool": tc.name, "cap": _cap, "action": "EXEC", "ok": True}
                            )

                        # ── FetchGuard: update state after execution ──
                        _fetch_guard.post_execute(
                            tc.name, tc.arguments, str(result) if result else ""
                        )

                        # ── CapabilityManager: implicit network confirmation ──
                        if (
                            _cap_guard
                            and tc.name in {"smart_fetch", "web_fetch", "web_search"}
                            and result
                            and "error" not in str(result)[:200].lower()
                        ):
                            self._cap_manager.mark_network_ok()

                        if progress:
                            await progress(_json.dumps({
                                "__tool_call__": True,
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }, ensure_ascii=False))
                        print(f"[agent] result: {str(result)[:100]}")

                        # ── Step event logging (unified point for EXEC/DENY/CONFIRM/SANDBOX branches) ──
                        try:
                            from myxai_desk.core.execution_log.event_writer import record_step_from_event
                            record_step_from_event(
                                session_id=key, tool_name=tc.name, args=tc.arguments,
                                result=str(result)[:500] if result else "",
                                turn_event=_turn_events[-1] if _turn_events else {"action": "UNKNOWN"},
                                started_at=_step_start_ts,
                            )
                        except Exception:
                            pass

                        messages = self.context.add_tool_result(
                            messages,
                            tc.id,
                            tc.name,
                            result,
                        )
                else:
                    text = self._strip_think(response.content)
                    if exec_mode and nudge_count < max_nudges and _is_fake_execution(text):
                        nudge_count += 1
                        print("[agent] nudge: fake exec detected, retrying")
                        messages.append({"role": "assistant", "content": text})
                        messages.append({"role": "user", "content": _t("policy.exec_nudge")})
                        continue
                    final_content = text
                    break
        except Exception as _loop_err:
            log.exception("[agent] error during message processing loop")
            try:
                from myxai_desk.core.execution_log.event_writer import record_step
                from myxai_desk.core.execution_log.error_codes import classify_error as _cls_err
                record_step(
                    session_id=key, tool_name="__loop__",
                    status="hard_fail",
                    error_code=_cls_err(exc=_loop_err),
                    action="HARD_FAIL",
                    result_preview=str(_loop_err)[:500],
                )
            except Exception:
                pass
            if final_content is None:
                final_content = f"Error during processing: {_loop_err}"

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        if exec_mode and not tools_used and nudge_count >= max_nudges:
            print(f"[agent] EXEC fallback: {max_nudges} nudges exhausted, no tool calls")
            final_content = _t("policy.exec_fallback")

        from apps.llm_utils import record_task_usage

        record_task_usage("chat", _turn_input, _turn_output, _turn_search)

        # ── Intent Engine: write back outcome + collect case ──
        if _ie_result is not None:
            try:
                _has_hard_fail = any(
                    e.get("action") == "HARD_FAIL" for e in _turn_events
                )
                if _has_hard_fail:
                    _ie_outcome = "fail"
                elif tools_used:
                    _ie_outcome = "success"
                else:
                    _ie_outcome = "unknown"
                _ie_result.write_outcome(_ie_outcome)

                # PR-2: write back plan_source and observability fields
                if _ie_result.run_id:
                    try:
                        from myxai_desk.core.intent_engine.dao import update_ie_run as _update_ie_run
                        # Determine plan_source: only mark as llm_free if NO LLM was called
                        if _plan_source:
                            _final_source = _plan_source
                        elif tools_used and _llm_attempts == 0:
                            _final_source = "llm_free"
                        elif tools_used:
                            _final_source = None  # Will not be recorded, means standard LLM flow
                        else:
                            _final_source = None
                        
                        _run_fields: dict = {}
                        if _final_source:
                            _run_fields["plan_source"] = _final_source
                        if _attempts_count:
                            _run_fields["attempts_count"] = _attempts_count
                        if _llm_attempts:
                            _run_fields["llm_attempts"] = _llm_attempts
                        if _golden_version is not None:
                            _run_fields["golden_version"] = _golden_version
                        _run_fields["golden_hit"] = 1 if _plan_source in (
                            "golden_v2_instance", "golden_v2_template",
                            "golden_candidate",
                        ) else 0
                        
                        # Calculate effective_steps (last occurrence of each tool in successful runs)
                        if _ie_outcome == "success" and tools_used:
                            last_idx_by_tool: dict[str, int] = {}
                            for i, tool in enumerate(tools_used):
                                if tool:
                                    last_idx_by_tool[tool] = i
                            _run_fields["effective_steps"] = len(set(last_idx_by_tool.values()))
                        else:
                            _run_fields["effective_steps"] = 0
                        
                        # Calculate total_tokens
                        _run_fields["total_tokens"] = _turn_input + _turn_output
                        
                        _update_ie_run(_ie_result.run_id, **_run_fields)
                    except Exception:
                        log.debug("[agent] ie_run field writeback failed", exc_info=True)

                # Golden 2.0: save successful LLM runs as instances
                if _ie_outcome == "success" and tools_used and _plan_source is None:
                    try:
                        from myxai_desk.core.intent_engine.config import golden_v2_enabled as _gv2_chk
                        if _gv2_chk():
                            from myxai_desk.core.golden.slot_extractor import extract_slots as _ext2
                            from myxai_desk.core.golden.store import GoldenV2Store as _GV2S2, compute_instance_key as _cik2
                            _sr2 = _ext2(msg.content)
                            if _sr2.intent_label and _sr2.confidence >= 0.3:
                                _ik2 = _cik2(_sr2.intent_label, _sr2.slots)
                                _plan2 = [
                                    {"tool_name": e.get("tool", ""), "args": e.get("args", {})}
                                    for e in _turn_events if e.get("tool")
                                ]
                                if _plan2:
                                    _GV2S2().save_instance(
                                        case_key=_ik2,
                                        template_id=None,
                                        intent_label=_sr2.intent_label,
                                        slot_values=_sr2.slots,
                                        resolved_plan=_plan2,
                                    )
                    except Exception:
                        log.debug("[agent] golden_v2 instance save failed", exc_info=True)
            except Exception:
                pass

        session.add_message("user", msg.content)
        session.add_message(
            "assistant", final_content, tools_used=tools_used if tools_used else None
        )

        self.sessions.save(session)

        # Write to legacy global dict (backward compatibility)
        with _last_tools_lock:
            _last_tools_used[key] = list(tools_used)

        with _last_usage_lock:
            _last_usage[key] = {
                "input": _turn_input,
                "output": _turn_output,
                "search": _turn_search,
            }

        # PR-2: decision_meta for frontend badge
        if _plan_source or _case_key:
            _dm: dict = {}
            if _plan_source:
                _dm["plan_source"] = _plan_source
            if _case_key:
                _dm["case_key"] = _case_key
            if _candidate_id:
                _dm["candidate_id"] = _candidate_id
            if _golden_version is not None:
                _dm["golden_version"] = _golden_version
            if _removed_steps is not None and _removed_steps > 0:
                _dm["removed_steps"] = _removed_steps
            _dm["attempts_count"] = _attempts_count
            _dm["llm_attempts"] = _llm_attempts
            _dm["promoted"] = bool(_plan_source == "golden_candidate")
            with _last_decision_meta_lock:
                _last_decision_meta[key] = _dm

        # NEW: Also write to ContextStore (gradual migration)
        try:
            from myxai_desk.core.integration import migrate_legacy_dict_to_context

            migrate_legacy_dict_to_context(
                key,
                tools_used=list(tools_used),
                usage={
                    "input": _turn_input,
                    "output": _turn_output,
                    "search": _turn_search,
                },
            )
        except Exception:
            log.warning("Legacy dict migration failed", exc_info=True)

        # ── Turn-level audit: minimal key events + fingerprint + ref ──
        if _turn_events:
            try:
                import hashlib as _hl

                _events_json = json.dumps(
                    _turn_events, sort_keys=True, ensure_ascii=False, default=str
                )
                _fingerprint = _hl.sha256(_events_json.encode("utf-8")).hexdigest()[:16]
                from myxai_desk.core.audit.ledger import AuditLedger

                _audit_hash = AuditLedger().append_entry(
                    capability="chat.turn",
                    args={"session": key, "events": _turn_events, "fingerprint": _fingerprint},
                    result_summary=f"tools={len(tools_used)},tokens_in={_turn_input},tokens_out={_turn_output}",
                    source="chat",
                )
                with _last_turn_audit_lock:
                    _last_turn_audit[key] = {
                        "fingerprint": _fingerprint,
                        "events": _turn_events,
                        "audit_hash": _audit_hash,
                        "session_id": key,
                    }
                print(
                    f"[audit] chat.turn fp={_fingerprint} events={len(_turn_events)} hash={_audit_hash[:12]}…"
                )
            except Exception as _ae:
                log.exception("[audit] turn audit failed")

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
        )

    agent._process_message = _types.MethodType(_patched_process_message, agent)


def _get_or_create_agent():
    global _agent, _cron_service
    with _agent_lock:
        if _agent is not None:
            return _agent

        from loguru import logger
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus
        from nanobot.config.loader import get_data_dir, load_config
        from nanobot.cron.service import CronService

        logger.disable("nanobot")

        config = load_config()
        bus = MessageBus()

        provider = _make_provider(config)
        _agent_model = config.agents.defaults.model

        cron_store = get_data_dir() / "cron" / "jobs.json"
        cron = CronService(cron_store)
        _cron_service = cron

        _agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=config.workspace_path,
            model=_agent_model,
            temperature=config.agents.defaults.temperature,
            max_tokens=config.agents.defaults.max_tokens,
            max_iterations=config.agents.defaults.max_tool_iterations,
            memory_window=config.agents.defaults.memory_window,
            brave_api_key=config.tools.web.search.api_key or None,
            exec_config=config.tools.exec,
            cron_service=cron,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            mcp_servers=config.tools.mcp_servers,
        )

        _patch_agent_tool_history(_agent)

        try:
            from nanobot.config.loader import get_config_path as _gcp

            from apps.web_search import EnhancedWebSearchTool
            from apps.web_search import quota as _quota

            _raw_cfg = {}
            with contextlib.suppress(Exception):
                _raw_cfg = json.loads(_gcp().read_text(encoding="utf-8"))
            _search_cfg = _raw_cfg.get("tools", {}).get("web", {}).get("search", {})
            _baidu_key = _search_cfg.get("baiduApiKey") or None
            _brave_key = config.tools.web.search.api_key or None
            _agent.tools.register(
                EnhancedWebSearchTool(
                    brave_api_key=_brave_key,
                    baidu_api_key=_baidu_key,
                )
            )
            _quota.set_quota_only(_search_cfg.get("quotaOnly", True))
            limits = {}
            if _search_cfg.get("baiduDailyLimit"):
                limits["baidu"] = int(_search_cfg["baiduDailyLimit"])
            if _search_cfg.get("braveDailyLimit"):
                limits["brave"] = int(_search_cfg["braveDailyLimit"])
            if limits:
                _quota.set_limits(limits)
            _active = [
                n for n in ["Baidu" if _baidu_key else None, "Brave" if _brave_key else None] if n
            ]
            print(f"[agent] web_search: API engines = {_active or ['none (no keys)']}")
        except Exception as _ws_err:
            log.exception("[agent] failed to replace web_search")

        try:
            from apps.smart_fetch import SmartFetchTool

            _agent.tools.register(SmartFetchTool())
            print("[agent] smart_fetch tool registered")
        except Exception as _sf_err:
            log.exception("[agent] failed to register smart_fetch")

        # Wrap exec tool: intercept deletion commands → safe_remove (recoverable)
        _exec_tool = _agent.tools._tools.get("exec")
        if _exec_tool and hasattr(_exec_tool, "execute"):
            import re as _wrap_re

            _orig_exec_execute = _exec_tool.execute
            _DEL_INTENT = _wrap_re.compile(
                r"\b(?:del|erase|rm|rmdir|rd|remove-item|remove|delete|"
                r"unlink|trash|recycle|\.Delete\b)",
                _wrap_re.IGNORECASE,
            )
            _PATH_QUOTED = _wrap_re.compile(r"""['"]([^'"]{3,})['"]\s*""")
            _PATH_DRIVE = _wrap_re.compile(r'([A-Z]:\\[^\s"\'<>|*?]+)', _wrap_re.IGNORECASE)
            _NET_FETCH = _wrap_re.compile(
                r"\b(?:curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b",
                _wrap_re.IGNORECASE,
            )

            def _extract_paths(cmd: str) -> list[str]:
                paths = _PATH_QUOTED.findall(cmd)
                if not paths:
                    paths = _PATH_DRIVE.findall(cmd)
                return [
                    p
                    for p in paths
                    if "." in p.split("\\")[-1]
                    or "." in p.split("/")[-1]
                    or p.endswith(("\\", "/"))
                ]

            async def _safe_exec_wrapper(**kwargs):
                command = kwargs.get("command", "")
                if _NET_FETCH.search(command):
                    return (
                        "[REDIRECT] 请使用 smart_fetch(url) 工具抓取网页内容，"
                        "它能自动处理反爬检测和内容提取。"
                        "禁止通过 exec 执行 curl/wget/Invoke-WebRequest 等网络抓取命令。"
                    )
                if _DEL_INTENT.search(command):
                    paths = _extract_paths(command)
                    if paths:
                        from apps.safe_fs import safe_remove

                        results = []
                        for p in paths:
                            dest = safe_remove(p)
                            if dest is None:
                                results.append(f"Not found: {p}")
                            else:
                                results.append(f"Moved to trash: {dest}")
                        return "\n".join(results)
                return await _orig_exec_execute(**kwargs)

            _exec_tool.execute = _safe_exec_wrapper
            print("[agent] exec tool wrapped: deletion commands → safe_remove (trash)")

        # ── CapabilityManager: probe environment + network + tools ──
        try:
            from apps.capabilities import CapabilityManager

            _cap_mgr = CapabilityManager(workspace=str(config.workspace_path))
            _cap_mgr.probe_static()
            _cap_mgr.probe_tools(set(_agent.tools._tools.keys()))
            _cap_mgr.probe_network_sync()
            _agent._cap_manager = _cap_mgr
            print(f"[agent] capabilities: {_cap_mgr.get_prompt_summary()}")
        except Exception as _cap_err:
            log.exception("[agent] CapabilityManager init failed")

        async def _on_cron_job(job):
            """Cron callback: directly push notification without LLM processing.

            Passing cron messages through the LLM causes it to misinterpret
            notifications as user requests, creating new tasks in a loop.
            """
            print(f"[cron] on_job: '{job.name}' ({job.id})")
            _push_notification(
                title=job.name,
                content=job.payload.message,
                level="info",
            )
            return job.payload.message

        cron.on_job = _on_cron_job

        _orig_add_job = cron.add_job
        _orig_arm_timer = cron._arm_timer
        _orig_execute_job = cron._execute_job

        def _traced_add_job(*args, **kwargs):
            print(f"[cron] add_job called: args={args}, kwargs_keys={list(kwargs.keys())}")
            job = _orig_add_job(*args, **kwargs)
            print(
                f"[cron] add_job result: id={job.id}, schedule={job.schedule.kind}, "
                f"at_ms={job.schedule.at_ms}, next_run={job.state.next_run_at_ms}, "
                f"delete_after={job.delete_after_run}"
            )
            return job

        cron.add_job = _traced_add_job

        def _traced_arm_timer():
            nw = cron._get_next_wake_ms()
            if nw:
                delay = max(0, nw - int(time.time() * 1000))
                print(f"[cron] _arm_timer: next_wake in {delay}ms, running={cron._running}")
            else:
                print(f"[cron] _arm_timer: no next wake, running={cron._running}")
            _orig_arm_timer()

        async def _traced_execute_job(job):
            print(
                f"[cron] executing job '{job.name}' ({job.id}), delete_after={job.delete_after_run}"
            )
            await _orig_execute_job(job)
            print(
                f"[cron] job '{job.name}' done, status={job.state.last_status}, error={job.state.last_error}"
            )

        cron._arm_timer = _traced_arm_timer
        cron._execute_job = _traced_execute_job

        cron._running = True
        cron._load_store()

        _ensure_loop()
        asyncio.run_coroutine_threadsafe(cron.start(), _async_loop)
        print(
            f"[cron] service initialized, store={cron.store_path}, jobs={len(cron._store.jobs if cron._store else [])}"
        )

        # 同步到 AppState
        from myxai_desk.web.state import get_state
        state = get_state(flask_app)
        state.agent = _agent
        state.cron_service = _cron_service
        state.async_loop = _async_loop

        return _agent


async def _connect_mcp_safe(agent, progress_cb=None):
    """Connect MCP with per-server error reporting and retry support.

    Replaces the opaque ``agent._connect_mcp()`` whose errors are silenced
    by ``logger.disable("nanobot")``.  We call ``connect_mcp_servers``
    ourselves with detailed logging so failures are visible in the UI.
    """
    if not agent._mcp_servers:
        return
    if agent._mcp_connected:
        mcp_tools = [n for n in agent.tools._tools if n.startswith("mcp_")]
        if mcp_tools:
            return

        _mcp_record("*", "warn", "Flag says connected but 0 MCP tools — retrying")
        agent._mcp_connected = False
        if agent._mcp_stack is not None:
            with contextlib.suppress(Exception):
                await agent._mcp_stack.aclose()
            agent._mcp_stack = None

    agent._mcp_connected = True

    from contextlib import AsyncExitStack

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    stack = AsyncExitStack()
    await stack.__aenter__()
    agent._mcp_stack = stack

    total_registered = 0
    for name, cfg in agent._mcp_servers.items():
        if progress_cb:
            await progress_cb(_t("progress.mcp_connecting", name=name))
        try:
            if cfg.command:
                exe = shutil.which(cfg.command)
                if not exe:
                    _mcp_record(name, "error", f"Command not found: {cfg.command}")
                    continue
                cmd, args = _win_fix_cmd(cfg.command, list(cfg.args))
                _mcp_record(name, "info", f"Starting: {cmd} {' '.join(args)}")
                params = StdioServerParameters(
                    command=cmd,
                    args=args,
                    env=cfg.env or None,
                )
                read, write = await asyncio.wait_for(
                    stack.enter_async_context(stdio_client(params)),
                    timeout=90,
                )
            elif cfg.url:
                _mcp_record(name, "info", f"Connecting HTTP: {cfg.url}")
                from mcp.client.streamable_http import streamable_http_client

                read, write, _ = await asyncio.wait_for(
                    stack.enter_async_context(streamable_http_client(cfg.url)),
                    timeout=30,
                )
            else:
                _mcp_record(name, "warn", "No command or url configured, skipping")
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            from nanobot.agent.tools.mcp import MCPToolWrapper

            for tool_def in tools.tools:
                wrapper = MCPToolWrapper(session, name, tool_def)
                agent.tools.register(wrapper)
                total_registered += 1

            _mcp_record(name, "ok", f"Connected — {len(tools.tools)} tools registered")
        except asyncio.TimeoutError:
            _mcp_record(name, "error", "Connection timed out")
        except Exception as e:
            log.warning("MCP server %s connection error: %s", name, e, exc_info=True)
            _mcp_record(name, "error", f"{type(e).__name__}: {e}")

    if total_registered:
        _mcp_record("*", "ok", f"Total MCP tools registered: {total_registered}")
    else:
        _mcp_record("*", "warn", "No MCP tools were registered")


# ---------------------------------------------------------------------------
# Policy-based tool filtering for app execution
# ---------------------------------------------------------------------------

# Tool name → (capability, operation) classification
_TOOL_CAP_MAP = {
    "web_search": ("search", "web"),
    "search": ("search", "web"),
    "brave_search": ("search", "web"),
    "baidu_search": ("search", "web"),
    "google_search": ("search", "web"),
    "bing_search": ("search", "web"),
    "duckduckgo_search": ("search", "web"),
    "web_fetch": ("net", "http_get"),
    "smart_fetch": ("net", "http_get"),
    "read_file": ("fs", "read"),
    "write_file": ("fs", "write_text"),
    "edit_file": ("fs", "write_text"),
    "list_dir": ("fs", "read"),
    "exec": ("proc", "execute"),
    "execute_command": ("proc", "execute"),
    "run_command": ("proc", "execute"),
    "http_get": ("net", "http_get"),
    "http_post": ("net", "http_post"),
}


def _classify_tool(tool_name: str) -> tuple[str, str]:
    """Classify a nanobot tool name → (capability, op)."""
    lower = tool_name.lower()
    for prefix, cap_op in _TOOL_CAP_MAP.items():
        if lower.startswith(prefix):
            return cap_op
    if lower.startswith("mcp_"):
        return ("mcp", "call")
    return ("unknown", "")


def _filter_tools_by_policy(
    all_tools: dict,
    app_id: str = "",
    source: str = "official",
    app_permissions: list | None = None,
) -> dict:
    """Filter agent tools based on Policy Engine decisions.

    Only tools whose capability+op is ALLOW or REQUIRE_COOLDOWN are kept.
    DENY or REQUIRE_CONFIRM tools are excluded (REQUIRE_CONFIRM for apps
    is treated as DENY since there's no interactive confirmation mid-stream).
    """
    try:
        from myxai_desk.core.policy.engine import decide
    except ImportError:
        return all_tools

    allowed: dict = {}
    perms_set = set(app_permissions or [])

    for name, tool in all_tools.items():
        cap, op = _classify_tool(name)

        if perms_set:
            perm_key = f"{cap}.{op}" if op else cap
            if not any(perm_key.startswith(p) for p in perms_set):
                continue

        try:
            d = decide(
                app_id=app_id,
                source=source,
                capability=cap,
                op=op,
                args={},
            )
            if d.action in ("ALLOW", "REQUIRE_COOLDOWN", "REQUIRE_SANDBOX"):
                allowed[name] = tool
        except Exception:
            log.warning("Policy decision failed for tool %s", name, exc_info=True)

    return allowed


def _build_safety_prompt(app_id: str, available_tools: dict) -> str:
    """Build a system-level safety prompt based on actually available tools."""
    tool_names = list(available_tools.keys())
    if not tool_names:
        return (
            "[System: This is a custom app task. No tools are available "
            "in the current security mode. Generate text-only output.]\n\n"
        )
    tool_list = ", ".join(tool_names[:20])
    return (
        f"[System: This is a custom app task. You may only use the "
        f"following tools: {tool_list}. If the task requires capabilities "
        f"beyond these tools, explain that it's not permitted in the "
        f"current security mode.]\n\n"
    )


# ---------------------------------------------------------------------------
# Agent execution helper (for custom apps, scheduled tasks, etc.)
# ---------------------------------------------------------------------------


def _run_agent_with_prompt(
    prompt: str,
    session_key: str,
    progress_cb=None,
    timeout: int = 300,
) -> dict:
    """Run the nanobot agent with a prompt and return {content, tools_used}.

    This is the universal entry point for programmatically invoking the agent
    from background threads (custom apps, scheduled tasks, etc.).
    """
    if not NANOBOT_AVAILABLE:
        return {"content": _t("error.nanobot_not_installed"), "tools_used": []}

    result_holder: dict = {"content": "", "tools_used": []}
    error_holder: list = []

    async def _execute():
        try:
            agent = _get_or_create_agent()
            need_mcp = bool(agent._mcp_servers)
            has_mcp = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp:
                await _connect_mcp_safe(agent)

            async def _progress(content):
                if progress_cb:
                    progress_cb(content)

            response = await agent.process_direct(
                prompt,
                session_key=session_key,
                on_progress=_progress,
            )
            result_holder["content"] = response or ""
            with _last_tools_lock:
                result_holder["tools_used"] = list(_last_tools_used.pop(session_key, []))
            with _last_usage_lock:
                result_holder["usage"] = _last_usage.pop(session_key, {})
        except Exception as exc:
            log.exception("[agent] direct execution failed")
            error_holder.append(exc)

    _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(_execute(), _async_loop)
    try:
        future.result(timeout=timeout)
    except Exception as exc:
        log.exception("[agent] direct execution future timed out or failed")
        error_holder.append(exc)

    if error_holder:
        return {
            "content": _t("policy.exec_failed", error=error_holder[0]),
            "tools_used": result_holder.get("tools_used", []),
        }
    return result_holder


# ---------------------------------------------------------------------------
# Routes — static
# ---------------------------------------------------------------------------


def _compute_build_hash() -> str:
    """SHA-256 of frontend assets — stable within the same version."""
    import hashlib
    h = hashlib.sha256()
    _fe = Path(__file__).parent / "frontend"
    for name in ("app.js", "i18n.js", "style.css"):
        p = _fe / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:12]


_BUILD_HASH = _compute_build_hash()


@flask_app.route("/")
def index():
    token = flask_app.config.get("MYXAI_API_TOKEN", "")
    if not token:
        return send_from_directory("frontend", "index.html")
    html = (Path(__file__).parent / "frontend" / "index.html").read_text(encoding="utf-8")
    bootstrap = (
        "<script>"
        f"window.__myxai_token={json.dumps(token)};"
        f"window.__myxai_expected_build={json.dumps(_BUILD_HASH)};"
        "</script>"
    )
    import re as _re_idx
    html = _re_idx.sub(r"(?i)</head>", f"{bootstrap}\n</head>", html, count=1)
    html = html.replace("/static/app.js", f"/static/app.js?v={_BUILD_HASH}")
    html = html.replace("/static/i18n.js", f"/static/i18n.js?v={_BUILD_HASH}")
    html = html.replace("/static/style.css", f"/static/style.css?v={_BUILD_HASH}")
    return html


# ---------------------------------------------------------------------------
# Routes — system check
# ---------------------------------------------------------------------------


@flask_app.route("/api/check")
def api_check():
    config_exists = False
    config_path = ""
    if NANOBOT_AVAILABLE:
        try:
            from nanobot.config.loader import get_config_path

            cp = get_config_path()
            config_path = str(cp)
            config_exists = cp.exists()
        except Exception:
            log.debug("Config path check failed", exc_info=True)
    return jsonify(
        {
            "nanobot_installed": NANOBOT_AVAILABLE,
            "config_exists": config_exists,
            "config_path": config_path,
        }
    )


# ---------------------------------------------------------------------------
# Routes — onboard
# ---------------------------------------------------------------------------


@flask_app.route("/api/onboard", methods=["POST"])
def api_onboard():
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": _t("error.nanobot_not_installed")}), 400
    try:
        from nanobot.config.loader import get_config_path, save_config
        from nanobot.config.schema import Config
        from nanobot.utils.helpers import get_workspace_path

        config_path = get_config_path()
        if not config_path.exists():
            save_config(Config())
        workspace = get_workspace_path()
        workspace.mkdir(parents=True, exist_ok=True)
        return jsonify(
            {"success": True, "config_path": str(config_path), "workspace": str(workspace)}
        )
    except Exception as e:
        log.exception("[api] onboard failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Config 路由已迁移到 myxai_desk/web/config_routes.py
# 配置服务已抽取到 myxai_desk/core/config_service.py
# 旧路由定义已删除（PR-3）：
#   - api_get_config()
#   - api_save_config()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Security 路由已迁移到 myxai_desk/web/security_routes.py
# 旧路由定义已删除（PR-5）：
#   - api_security_mode_get()
#   - api_security_mode_set()
#   - api_security_modes_list()
#   - api_app_mode_get()
#   - api_app_mode_set()
#   - api_app_mode_preview()
#   - api_dev_mode_status()
#   - api_dev_mode_enable()
#   - api_dev_mode_disable()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Profile 路由已迁移到 myxai_desk/web/profile_routes.py (PR-7)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Plan Confirmation API
# ---------------------------------------------------------------------------


@flask_app.route("/api/plan/pending")
def api_plan_pending():
    """Return pending actions waiting for user confirmation."""
    from myxai_desk.core.orchestrator.planner import get_plan_manager

    pm = get_plan_manager()
    return jsonify(pm.list_pending())


@flask_app.route("/api/plan/confirm/<action_id>", methods=["POST"])
def api_plan_confirm(action_id):
    """Confirm a pending action. Executes the tool call and returns the result."""
    from myxai_desk.core.orchestrator.planner import get_plan_manager

    pm = get_plan_manager()
    pa = pm.confirm_pending(action_id)
    if not pa:
        return jsonify({"error": "Action not found, expired, or already handled"}), 404

    try:
        agent = _get_or_create_agent()
        _ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            agent.tools.execute(pa.tool_name, pa.tool_args),
            _async_loop,
        )
        result = future.result(timeout=60)
        from myxai_desk.core.capabilities.governance import (
            post_execution_audit,
            post_execution_undo,
        )

        post_execution_audit(pa.capability, pa.op, pa.tool_args, result, None)
        post_execution_undo(pa.capability, pa.op, pa.tool_args, result)
        try:
            from myxai_desk.core.execution_log.event_writer import record_step
            record_step(
                session_id="plan_confirm", tool_name=pa.tool_name,
                args_json=pa.tool_args, status="ok", action="EXEC_CONFIRMED",
                result_preview=str(result)[:500],
            )
        except Exception:
            pass
        return jsonify({"success": True, "result": str(result)[:500]})
    except Exception as e:
        log.exception("[api] plan approve/execute failed")
        try:
            from myxai_desk.core.execution_log.event_writer import record_step
            from myxai_desk.core.execution_log.error_codes import classify_error as _cls_err
            record_step(
                session_id="plan_confirm", tool_name=pa.tool_name if pa else "__plan__",
                args_json=pa.tool_args if pa else {}, status="hard_fail",
                error_code=_cls_err(exc=e), action="HARD_FAIL",
                result_preview=str(e)[:500],
            )
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/plan/reject/<action_id>", methods=["POST"])
def api_plan_reject(action_id):
    """Reject a pending action."""
    from myxai_desk.core.orchestrator.planner import get_plan_manager

    pm = get_plan_manager()
    if pm.reject_pending(action_id):
        return jsonify({"success": True})
    return jsonify({"error": "Action not found or already handled"}), 404


# ---------------------------------------------------------------------------
# Audit & Undo API
# ---------------------------------------------------------------------------


@flask_app.route("/api/audit/recent")
def api_audit_recent():
    """Return recent audit entries."""
    from myxai_desk.core.audit.ledger import AuditLedger

    n = request.args.get("n", 50, type=int)
    ledger = AuditLedger()
    return jsonify(ledger.recent(n))


@flask_app.route("/api/audit/verify")
def api_audit_verify():
    """Verify the integrity of the audit chain."""
    from myxai_desk.core.audit.ledger import AuditLedger

    ledger = AuditLedger()
    ok, count, error = ledger.verify_chain()
    return jsonify({"valid": ok, "entries_checked": count, "error": error})


@flask_app.route("/api/audit/export")
def api_audit_export():
    """Export the full audit chain."""
    from myxai_desk.core.audit.ledger import AuditLedger

    fmt = request.args.get("format", "json")
    ledger = AuditLedger()
    data = ledger.export(format=fmt)
    return Response(
        data,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_chain.json"},
    )


@flask_app.route("/api/undo/actions")
def api_undo_actions():
    """Return recent undoable actions."""
    from myxai_desk.core.audit.undo import get_undo_registry

    registry = get_undo_registry()
    undoable = request.args.get("undoable", "false").lower() == "true"
    return jsonify(registry.list_actions(undoable_only=undoable))


@flask_app.route("/api/undo/<action_id>", methods=["POST"])
def api_undo_action(action_id):
    """Undo a specific action."""
    from myxai_desk.core.audit.undo import get_undo_registry

    registry = get_undo_registry()
    result = registry.undo(action_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@flask_app.route("/api/search/quota_config", methods=["GET", "POST"])
def api_search_quota_config():
    """搜索 API 额度配置 API（GET/POST）."""
    from myxai_desk.core.search_quota_service import get_search_quota_config, save_search_quota_config
    
    if request.method == "GET":
        return jsonify(get_search_quota_config())
    
    # POST
    try:
        config = request.get_json()
        save_search_quota_config(config)
        
        # Update the quota manager limits
        from apps.web_search import quota
        quota.set_limits(config)
        
        return jsonify({"success": True})
    except Exception as e:
        log.exception("[api] Failed to save search quota config")
        return jsonify({"success": False, "error": str(e)}), 500


@flask_app.route("/api/search/usage")
def api_search_usage():
    """Return today's search API usage stats, with key availability."""
    try:
        from apps.web_search import quota

        data = quota.get_usage()
        mcfg = _get_model_config()
        key_map = {
            "brave": bool(mcfg.get("brave_api_key")),
            "baidu": bool(mcfg.get("baidu_api_key")),
        }
        for eng in list(data.get("engines", {})):
            data["engines"][eng]["has_key"] = key_map.get(eng, False)
        return jsonify(data)
    except Exception as e:
        log.exception("[api] search usage query failed")
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/token/cost_config", methods=["GET", "POST"])
def api_token_cost_config():
    """Token 成本配置 API（GET/POST）."""
    from myxai_desk.core.token_cost_service import get_token_cost_config, save_token_cost_config
    
    if request.method == "GET":
        return jsonify(get_token_cost_config())
    
    # POST
    try:
        config = request.get_json()
        save_token_cost_config(config)
        return jsonify({"success": True})
    except Exception as e:
        log.exception("[api] Failed to save token cost config")
        return jsonify({"success": False, "error": str(e)}), 500


@flask_app.route("/api/token/usage")
def api_token_usage():
    from apps.llm_utils import get_token_usage_with_cost
    from myxai_desk.core.token_cost_service import get_token_cost_config

    cost_config = get_token_cost_config()
    # Wrap in a dict structure compatible with get_token_usage_with_cost
    config_wrapper = {"tokenCost": cost_config}
    
    return jsonify(get_token_usage_with_cost(config_wrapper))


@flask_app.route("/api/token/history")
def api_token_history():
    days = request.args.get("days", 30, type=int)
    from apps.llm_utils import get_token_history, get_cost_history
    from myxai_desk.core.token_cost_service import get_token_cost_config

    cost_config = get_token_cost_config()
    config_wrapper = {"tokenCost": cost_config}
    
    history = get_token_history(min(days, 90))
    cost_history = get_cost_history(min(days, 90), config_wrapper)
    total = sum(d["tokens"] for d in history)
    total_cost = sum(d["cost"] for d in cost_history)
    
    return jsonify({
        "days": len(history),
        "total": total,
        "total_cost": round(total_cost, 2),
        "history": history,
        "cost_history": cost_history
    })


@flask_app.route("/api/usage/categories")
def api_usage_categories():
    days = request.args.get("days", 7, type=int)
    from apps.llm_utils import get_category_usage

    return jsonify(get_category_usage(min(days, 90)))


@flask_app.route("/api/search/history")
def api_search_history():
    days = request.args.get("days", 30, type=int)
    from apps.web_search import quota

    history = quota.get_history(min(days, 90))
    total = sum(d["calls"] for d in history)
    return jsonify({"days": len(history), "total": total, "history": history})


# ---------------------------------------------------------------------------
# Routes — status
# ---------------------------------------------------------------------------


@flask_app.route("/api/status")
def api_status():
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": _t("error.nanobot_not_installed")}), 400
    try:
        from nanobot.config.loader import get_config_path, load_config
        from nanobot.providers.registry import PROVIDERS

        from myxai_desk.core.scheduler_service import get_scheduler_health
        from myxai_desk.core.system_info import get_system_monitor

        cp = get_config_path()
        config = load_config()
        workspace = config.workspace_path

        from myxai_desk.core.storage import secrets as _sec
        providers = []
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            is_oauth = getattr(spec, "is_oauth", False)
            api_key = p.api_key or ""
            # If stored as keyring ref, check whether real key exists
            if api_key == _sec.SECRET_REF:
                api_key = _sec.retrieve_provider_key(spec.name) or ""
            if not api_key and not is_oauth:
                continue
            providers.append(
                {
                    "name": spec.name,
                    "label": getattr(spec, "display_name", spec.name),
                }
            )

        channels = []
        for name in (
            "telegram",
            "discord",
            "whatsapp",
            "feishu",
            "mochat",
            "dingtalk",
            "email",
            "slack",
            "qq",
        ):
            ch = getattr(config.channels, name, None)
            # Only include channels that are explicitly enabled
            if ch and ch.enabled:
                channels.append({"name": name})

        mcp_status = []
        for name, srv in config.tools.mcp_servers.items():
            mcp_status.append(
                {
                    "name": name,
                    "type": "http" if srv.url else "stdio",
                    "detail": srv.url or (srv.command + " " + " ".join(srv.args)),
                }
            )

        mcp_connected = False
        mcp_tool_count = 0
        mcp_tool_names = []
        if _agent is not None:
            mcp_connected = getattr(_agent, "_mcp_connected", False)
            mcp_tool_names = [n for n in _agent.tools._tools if n.startswith("mcp_")]
            mcp_tool_count = len(mcp_tool_names)

        with _mcp_log_lock:
            mcp_log_copy = list(_mcp_log)

        _display_model = config.agents.defaults.model
        
        # Include scheduler health
        scheduler_health = get_scheduler_health()
        
        # Include system monitoring data
        system_monitor = get_system_monitor()

        return jsonify(
            {
                "config_path": str(cp),
                "config_exists": cp.exists(),
                "workspace": str(workspace),
                "workspace_exists": workspace.exists(),
                "model": _display_model,
                "providers": providers,
                "channels": channels,
                "mcp_servers": mcp_status,
                "mcp_connected": mcp_connected,
                "mcp_tool_count": mcp_tool_count,
                "mcp_tool_names": mcp_tool_names,
                "mcp_log": mcp_log_copy,
                "scheduler": scheduler_health,
                "monitor": system_monitor,
            }
        )
    except Exception as e:
        log.exception("[api] agent status query failed")
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/monitor")
def api_monitor():
    """Lightweight endpoint for real-time system monitoring (CPU/Memory/Disk/Network)."""
    from myxai_desk.core.system_info import get_system_monitor
    return jsonify(get_system_monitor())


# ---------------------------------------------------------------------------
# Routes — agent tools info
# ---------------------------------------------------------------------------


@flask_app.route("/api/tools")
def api_tools():
    """Return registered tools (for diagnostics)."""
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": _t("error.nanobot_not_installed")}), 400
    if _agent is None:
        return jsonify({"connected": False, "tools": [], "message": "Agent not yet created"})
    tool_names = list(_agent.tools._tools.keys())
    mcp_tools = [n for n in tool_names if n.startswith("mcp_")]
    return jsonify(
        {
            "connected": _agent._mcp_connected,
            "total": len(tool_names),
            "mcp_count": len(mcp_tools),
            "mcp_tools": mcp_tools,
            "all_tools": tool_names,
        }
    )


# ---------------------------------------------------------------------------
# Routes — MCP diagnostics
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MCP 路由已迁移到 myxai_desk/web/mcp_routes.py
# 旧路由定义已删除（PR-6）：
#   - api_mcp_test()
#   - api_mcp_reconnect()
#   - api_mcp_log()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Routes — notifications (cron reminders, etc.)
# ---------------------------------------------------------------------------


@flask_app.route("/api/notifications", methods=["POST"])
def api_notifications():
    """Return unread notifications and mark them read.

    Uses POST because reading notifications has a side effect (mark-as-read).
    """
    with _notifications_lock:
        unread = [n for n in _notifications if not n["read"]]
        for n in unread:
            n["read"] = True
    return jsonify(unread)


@flask_app.route("/api/notifications/all")
def api_notifications_all():
    with _notifications_lock:
        return jsonify(list(_notifications))


# ---------------------------------------------------------------------------
# Routes — chat (SSE streaming)
# ---------------------------------------------------------------------------


@flask_app.route("/api/chat", methods=["POST"])
def api_chat():
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": _t("error.nanobot_not_installed")}), 400

    message = (request.json or {}).get("message", "").strip()
    session_id = (request.json or {}).get(
        "session_id", f"desktop:{_session_epoch}_{_session_counter}"
    )
    if not message:
        return jsonify({"error": _t("error.message_empty")}), 400

    # ── Inline confirmation: execute pending action via chat ──
    if _CONFIRM_RE.match(message):
        _confirmed_result = _try_execute_pending()
        if _confirmed_result is not None:
            message = _t("policy.user_confirmed", result=_confirmed_result)

    q: queue.Queue[str] = queue.Queue()

    # Generate request_id for tracking
    import uuid

    request_id = f"req_{uuid.uuid4().hex[:12]}"

    async def _process():
        try:
            agent = _get_or_create_agent()

            async def on_progress(content):
                q.put(
                    json.dumps(
                        {"type": "progress", "content": content, "request_id": request_id},
                        ensure_ascii=False,
                    )
                )

            # Send initial event with request_id
            q.put(json.dumps({"type": "start", "request_id": request_id}, ensure_ascii=False))

            need_mcp = bool(agent._mcp_servers)
            has_mcp_tools = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp_tools:
                await _connect_mcp_safe(agent, progress_cb=on_progress)

            has_mcp_tools_after = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp_tools_after:
                errors = [e for e in _mcp_log if e["level"] == "error"]
                hint = errors[-1]["message"] if errors else "unknown"
                q.put(
                    json.dumps(
                        {
                            "type": "progress",
                            "content": _t("notification.mcp_failed", hint=hint),
                            "request_id": request_id,
                        },
                        ensure_ascii=False,
                    )
                )

            response = await agent.process_direct(
                message,
                session_key=session_id,
                on_progress=on_progress,
            )
            with _last_usage_lock:
                _usage_data = _last_usage.pop(session_id, {})
            with _last_turn_audit_lock:
                _audit_data = _last_turn_audit.pop(session_id, None)
            with _last_decision_meta_lock:
                _dm_data = _last_decision_meta.pop(session_id, None)
            _done_payload = {"type": "done", "content": response or "", "request_id": request_id}
            if _usage_data:
                _done_payload["usage"] = _usage_data
            if _audit_data:
                _done_payload["audit"] = {
                    "fingerprint": _audit_data["fingerprint"],
                    "events": _audit_data["events"],
                    "hash": _audit_data["audit_hash"][:16],
                }
            if _dm_data:
                _done_payload["decision_meta"] = _dm_data
            q.put(json.dumps(_done_payload, ensure_ascii=False))
        except Exception as exc:
            log.exception("[chat] streaming message processing failed")
            q.put(json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False))

    _ensure_loop()
    asyncio.run_coroutine_threadsafe(_process(), _async_loop)

    _sse_timeout = 300

    def generate():
        while True:
            try:
                data = q.get(timeout=_sse_timeout)
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


@flask_app.route("/api/chat/new", methods=["POST"])
def api_new_chat():
    global _session_counter
    _session_counter += 1
    return jsonify({"success": True, "session_id": f"desktop:{_session_epoch}_{_session_counter}"})


@flask_app.route("/api/ie/last_run")
def api_ie_last_run():
    """Return decision_meta from the most recent ie_run (for debugging / page refresh)."""
    try:
        from myxai_desk.core.intent_engine.dao import get_runs
        rows = get_runs(limit=1)
        if not rows:
            return jsonify({})
        r = rows[0]
        return jsonify({
            "run_id": r.get("id"),
            "case_key": r.get("case_key"),
            "plan_source": r.get("plan_source"),
            "candidate_id": r.get("candidate_id"),
            "golden_version": r.get("golden_version"),
            "removed_steps": r.get("removed_steps"),
            "attempts_count": r.get("attempts_count"),
            "llm_attempts": r.get("llm_attempts"),
            "outcome": r.get("outcome"),
            "route_label": r.get("route_label"),
            "created_at": r.get("created_at"),
        })
    except Exception:
        return jsonify({})


@flask_app.route("/api/ie/golden_config", methods=["GET", "POST"])
def api_ie_golden_config():
    """Read or update intent engine config."""
    try:
        from myxai_desk.core.intent_engine import config as ie_config
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            updates = {}
            if "routing_enabled" in body:
                updates["routing_enabled"] = bool(body["routing_enabled"])
            if "golden_enabled" in body:
                updates["golden_enabled"] = bool(body["golden_enabled"])
            # Backward compat: map legacy keys
            elif "golden_replay_enabled" in body:
                updates["golden_enabled"] = bool(body["golden_replay_enabled"])
            elif "golden_v2_enabled" in body:
                updates["golden_enabled"] = bool(body["golden_v2_enabled"])
            if updates:
                ie_config.set_values(updates)
            return jsonify({"ok": True, **ie_config.get()})
        return jsonify(ie_config.get())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@flask_app.route("/api/ie/golden_stats")
def api_ie_golden_stats():
    """Aggregate golden/candidate usage stats for radar KPI cards."""
    try:
        from myxai_desk.core.storage.sqlite import execute as _sql
        rows = _sql(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN plan_source IN ('golden_v2_instance','golden_v2_template','golden_replay') THEN 1 ELSE 0 END) AS golden_instance,
                 SUM(CASE WHEN plan_source='golden_candidate' THEN 1 ELSE 0 END) AS golden_candidate,
                 SUM(CASE WHEN plan_source='reuse_plan' THEN 1 ELSE 0 END) AS reuse_plan,
                 SUM(CASE WHEN plan_source='llm_free' THEN 1 ELSE 0 END) AS llm_free,
                 AVG(CASE WHEN llm_attempts IS NOT NULL THEN llm_attempts END) AS avg_llm_attempts,
                 AVG(CASE WHEN attempts_count IS NOT NULL THEN attempts_count END) AS avg_attempts_count,
                 AVG(CASE WHEN removed_steps IS NOT NULL AND removed_steps > 0 THEN removed_steps END) AS avg_removed_steps
               FROM ie_runs
               WHERE local_date >= date('now', '-7 days')
                 AND plan_source IS NOT NULL""",
            readonly=True,
        )
        if not rows:
            return jsonify({})
        r = rows[0]
        total = r.get("total", 0) or 0
        golden_inst = r.get("golden_instance", 0) or 0
        golden_cand = r.get("golden_candidate", 0) or 0
        return jsonify({
            "total": total,
            "golden_replay": golden_inst,
            "golden_candidate": golden_cand,
            "reuse_plan": r.get("reuse_plan", 0) or 0,
            "llm_free": r.get("llm_free", 0) or 0,
            "golden_replay_rate": round(golden_inst / total * 100, 1) if total else 0,
            "golden_candidate_rate": round(golden_cand / total * 100, 1) if total else 0,
            "avg_llm_attempts": round(r.get("avg_llm_attempts", 0) or 0, 1),
            "avg_attempts_count": round(r.get("avg_attempts_count", 0) or 0, 1),
            "avg_removed_steps": round(r.get("avg_removed_steps", 0) or 0, 1),
        })
    except Exception:
        return jsonify({})


# ---------------------------------------------------------------------------
# Routes — chat history persistence
# ---------------------------------------------------------------------------

_HISTORY_DIR = Path.home() / ".nanobot" / "desktop_history"


def _history_file() -> Path:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return _HISTORY_DIR / "sessions.json"


def _load_all_history() -> dict:
    f = _history_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Failed to load session history from %s", f, exc_info=True)
            return {}
    return {}


def _save_all_history(data: dict) -> None:
    f = _history_file()
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@flask_app.route("/api/history")
def api_history_list():
    """Return session list sorted by most recently updated."""
    data = _load_all_history()
    sessions = []
    for sid, sess in data.items():
        sessions.append(
            {
                "id": sid,
                "title": sess.get("title", ""),
                "updated_at": sess.get("updated_at", ""),
                "message_count": len(sess.get("messages", [])),
            }
        )
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return jsonify(sessions)


@flask_app.route("/api/history/<path:session_id>")
def api_history_get(session_id):
    data = _load_all_history()
    sess = data.get(session_id)
    if not sess:
        return jsonify({"messages": []})
    return jsonify({"messages": sess.get("messages", [])})


@flask_app.route("/api/history/<path:session_id>", methods=["POST"])
def api_history_save(session_id):
    body = request.json or {}
    messages = body.get("messages", [])
    title = body.get("title", "")

    data = _load_all_history()
    now = datetime.now(timezone.utc).isoformat()

    if session_id in data:
        data[session_id]["messages"] = messages
        data[session_id]["updated_at"] = now
        if title:
            data[session_id]["title"] = title
    else:
        data[session_id] = {
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": messages,
        }

    _save_all_history(data)
    return jsonify({"success": True})


@flask_app.route("/api/history/<path:session_id>/rename", methods=["POST"])
def api_history_rename(session_id):
    body = request.json or {}
    title = body.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    data = _load_all_history()
    if session_id not in data:
        return jsonify({"error": "session not found"}), 404
    data[session_id]["title"] = title
    _save_all_history(data)
    return jsonify({"success": True})


@flask_app.route("/api/history/<path:session_id>", methods=["DELETE"])
def api_history_delete(session_id):
    data = _load_all_history()
    if session_id in data:
        del data[session_id]
        _save_all_history(data)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Apps 路由已迁移到以下 Blueprint 模块 (PR-8a/b/c/d):
#   - myxai_desk/web/apps_helpers.py     (共享常量/工具)
#   - myxai_desk/web/apps_routes.py      (基础: 列表/安装/卸载/启用/禁用/收藏/配置)
#   - myxai_desk/web/apps_digest_routes.py (Daily Digest)
#   - myxai_desk/web/apps_email_routes.py  (Email Summary)
#   - myxai_desk/web/apps_custom_routes.py (Custom Apps)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Apps scheduler (background timer) + catch-up scheduling
# ---------------------------------------------------------------------------


def _get_model_config() -> dict:
    """Read model/api_key/api_base/brave_api_key/baidu_api_key from nanobot config.

    Uses ``config_service.get_config()`` for the API key so that
    ``<<KEYRING>>`` placeholders are resolved to real secrets.
    """
    if not NANOBOT_AVAILABLE:
        return {}
    try:
        from nanobot.config.loader import load_config

        config = load_config()
        model = config.agents.defaults.model
        provider_name = config.get_provider_name(model)
        api_base = config.get_api_base(model) or None
        brave_key = config.tools.web.search.api_key if config.tools.web.search else None

        api_key = None
        baidu_key = None
        try:
            from myxai_desk.core.config_service import get_config
            merged = get_config()
            if provider_name:
                p_cfg = merged.get("providers", {}).get(provider_name, {})
                api_key = p_cfg.get("apiKey") or None
                if api_key == "<<KEYRING>>":
                    api_key = _resolve_api_key(api_key, provider_name)
            baidu_key = (
                merged.get("tools", {}).get("web", {}).get("search", {}).get("baiduApiKey") or None
            )
        except Exception:
            p = config.get_provider(model)
            api_key = _resolve_api_key(p.api_key if p else None, provider_name)
            log.debug("config_service unavailable, fell back to nanobot loader", exc_info=True)

        return {
            "model": model,
            "api_key": api_key,
            "api_base": api_base,
            "brave_api_key": brave_key or None,
            "baidu_api_key": baidu_key or None,
        }
    except Exception:
        log.warning("Failed to load model config", exc_info=True)
        return {}







_app_scheduler_timer = None

from myxai_desk.core.scheduler_service import (
    DueSlot as _DueSlot,
)
from myxai_desk.core.scheduler_service import (
    TaskDescriptor as _TaskDescriptor,
)
from myxai_desk.core.scheduler_service import (
    scheduler_service as _scheduler_svc,
)
from myxai_desk.web.apps_helpers import (
    digest_task_lock,
    digest_task_status,
    inc_run_count,
    load_apps_registry,
    save_apps_registry,
)


def _load_official_tasks() -> list["_TaskDescriptor"]:
    """Build TaskDescriptors for official scheduled apps (daily_digest, email_summary)."""
    descriptors: list[_TaskDescriptor] = []
    registry = load_apps_registry()

    for app_id, app in registry.items():
        if not app.get("enabled"):
            continue
        config = app.get("config", {})

        if app_id == "daily_digest":
            schedule_time = config.get("schedule_time")
            if not schedule_time:
                continue
            hh, mm = schedule_time.split(":")[:2]
            cron_expr = f"{mm} {hh} * * *"
            catchup_cfg = config.get("catchup", {})
            descriptors.append(
                _TaskDescriptor(
                    task_id="daily_digest",
                    schedule={"enabled": True, "mode": "daily", "time": schedule_time},
                    cron_expr=cron_expr,
                    created_at=app.get("installed_at", "2024-01-01T00:00:00"),
                    last_success_at=app.get("last_run"),
                    catchup_policy=catchup_cfg.get("catchup_policy", "LATEST_ONLY"),
                    catchup_window_hours=catchup_cfg.get("catchup_window_hours", 24),
                    max_catchup_runs=catchup_cfg.get("max_catchup_runs", 1),
                    extra={"kind": "daily_digest", "config": config, "registry_app": app},
                )
            )

        elif app_id == "email_summary":
            schedule_time = config.get("schedule_time")
            if not schedule_time:
                continue
            if not config.get("imap_host") or not config.get("imap_user"):
                continue
            hh, mm = schedule_time.split(":")[:2]
            cron_expr = f"{mm} {hh} * * *"
            catchup_cfg = config.get("catchup", {})
            descriptors.append(
                _TaskDescriptor(
                    task_id="email_summary",
                    schedule={"enabled": True, "mode": "daily", "time": schedule_time},
                    cron_expr=cron_expr,
                    created_at=app.get("installed_at", "2024-01-01T00:00:00"),
                    last_success_at=app.get("last_run"),
                    catchup_policy=catchup_cfg.get("catchup_policy", "LATEST_ONLY"),
                    catchup_window_hours=catchup_cfg.get("catchup_window_hours", 24),
                    max_catchup_runs=catchup_cfg.get("max_catchup_runs", 1),
                    extra={"kind": "email_summary", "config": config, "registry_app": app},
                )
            )

    return descriptors


def _load_custom_tasks() -> list["_TaskDescriptor"]:
    """Build TaskDescriptors for custom (prompt) apps."""
    from apps.custom_app import build_task_descriptor
    from apps.custom_app import list_apps as _list_custom

    descriptors: list[_TaskDescriptor] = []
    for capp in _list_custom():
        td = build_task_descriptor(capp, "schedule")
        if td:
            descriptors.append(td)
        td_sum = build_task_descriptor(capp, "summary")
        if td_sum:
            descriptors.append(td_sum)
    return descriptors


# ── Executor callbacks for each app kind ──────────────────────────────


def _exec_daily_digest(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    config = task.extra["config"]
    with digest_task_lock:
        if digest_task_status.get("status") == "running":
            return

    from myxai_desk.core.runtime.app_governance import gate_app_run

    _gate = gate_app_run("daily_digest")
    if not _gate["allowed"]:
        print(f"[scheduler] daily_digest blocked: {_gate['reason']}")
        return

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(f"[scheduler] triggering daily_digest (scheduled_for={sched_for}, trigger={trigger})")
    from apps.daily_digest import run_daily_digest
    from apps.llm_utils import record_task_usage, snapshot_today_tokens

    model_cfg = _get_model_config()
    merged = {**config, **model_cfg}
    _snap_before = snapshot_today_tokens()
    result = run_daily_digest(merged)
    _snap_after = snapshot_today_tokens()
    _d_in = _snap_after["input"] - _snap_before["input"]
    _d_out = _snap_after["output"] - _snap_before["output"]
    _d_search = result.get("stats", {}).get("search_results", 0)
    record_task_usage(f"app_{_t('app.daily_digest.name')}", _d_in, _d_out, min(_d_search, 1) if _d_search else 0)
    if result["status"] == "ok":
        today = slot.scheduled_for.strftime("%Y-%m-%d")
        registry = load_apps_registry()
        if "daily_digest" in registry:
            registry["daily_digest"]["last_run"] = today
            save_apps_registry(registry)
        stats = result.get("stats", {})
        catchup_note = ""
        if trigger in ("startup", "resume"):
            catchup_note = _t("notification.daily_digest.catchup", scheduled=sched_for)
        _push_notification(
            title=_t("notification.daily_digest.updated") + catchup_note,
            content=_t("notification.daily_digest.content",
                      filtered=stats.get('filtered_count', 0),
                      results=stats.get('search_results', 0)),
            level="info",
        )
    else:
        raise RuntimeError(f"daily_digest returned status={result.get('status')}")


def _exec_email_summary(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    config = dict(task.extra["config"])
    from myxai_desk.core.storage import secrets as _sec
    if _sec.is_secret_ref(config.get("imap_password")):
        real = _sec.retrieve_app_secret("email_summary", "imap_password")
        if real:
            config["imap_password"] = real
    from myxai_desk.core.runtime.app_governance import gate_app_run

    _gate = gate_app_run("email_summary")
    if not _gate["allowed"]:
        print(f"[scheduler] email_summary blocked: {_gate['reason']}")
        return

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(f"[scheduler] triggering email_summary (scheduled_for={sched_for}, trigger={trigger})")
    from apps.email_summary import run_email_summary
    from apps.llm_utils import record_task_usage, snapshot_today_tokens

    model_cfg = _get_model_config()
    _snap_before = snapshot_today_tokens()
    result = run_email_summary(config, model_config=model_cfg)
    _snap_after = snapshot_today_tokens()
    _d_in = _snap_after["input"] - _snap_before["input"]
    _d_out = _snap_after["output"] - _snap_before["output"]
    record_task_usage(f"app_{_t('app.email_summary.name')}", _d_in, _d_out, 0)
    if result.get("success"):
        today = slot.scheduled_for.strftime("%Y-%m-%d")
        registry = load_apps_registry()
        if "email_summary" in registry:
            registry["email_summary"]["last_run"] = today
            save_apps_registry(registry)
        catchup_note = ""
        if trigger in ("startup", "resume"):
            catchup_note = _t("notification.email_summary.catchup", scheduled=sched_for)
        _push_notification(
            title=_t("notification.email_summary.generated") + catchup_note,
            content=_t("notification.email_summary.content", count=result.get('email_count', 0)),
            level="info",
        )
    else:
        raise RuntimeError("email_summary failed")


def _exec_custom_app(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    capp = task.extra["app"]
    capp_id = capp["id"]
    from apps.custom_app import (
        build_message,
        mark_triggered,
        save_report,
        set_last_run,
    )
    from myxai_desk.core.runtime.app_governance import finish_app_run, gate_app_run

    _gate = gate_app_run(capp_id, source="user")
    if not _gate["allowed"]:
        print(f"[scheduler] custom app '{capp['name']}' blocked: {_gate['reason']}")
        return

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(
        f"[scheduler] triggering custom app '{capp['name']}' (scheduled_for={sched_for}, trigger={trigger})"
    )
    try:
        defaults = {p["name"]: p.get("default", "") for p in capp.get("parameters", [])}
        groups = capp.get("param_groups")
        if not groups or not isinstance(groups, list):
            groups = [capp.get("param_values", defaults)]
        _sched_in = 0
        _sched_out = 0
        _sched_search = 0
        for pv in groups:
            message = build_message(capp, pv)
            import uuid as _uuid_sched

            session_key = f"capp_{_uuid_sched.uuid4().hex[:12]}"
            result = _run_agent_with_prompt(message, session_key=session_key)
            _ru = result.get("usage", {})
            _sched_in += _ru.get("input", 0)
            _sched_out += _ru.get("output", 0)
            _sched_search += _ru.get("search", 0)
            save_report(capp_id, content=result["content"], params_used=pv)
        _sched_cat = f"app_{capp.get('name', capp_id)}"
        from apps.llm_utils import record_task_usage as _rec_task

        _rec_task(_sched_cat, _sched_in, _sched_out, _sched_search)
        set_last_run(capp_id)
        inc_run_count(capp_id)
        mark_triggered(capp_id, "schedule")
        finish_app_run(capp_id, success=True)
        catchup_note = ""
        if trigger in ("startup", "resume"):
            catchup_note = _t("notification.daily_digest.catchup", scheduled=sched_for)
        _push_notification(
            title=_t("notification.custom_app.completed",
                    icon=capp.get('icon', '🤖'),
                    name=capp['name']) + catchup_note,
            content=_t("notification.custom_app.content", groups=len(groups)),
            level="info",
        )
    except Exception as exc:
        log.exception("[scheduler] custom app '%s' error", capp['name'])
        finish_app_run(capp_id, success=False, error=str(exc))
        raise


def _exec_custom_summary(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    capp = task.extra["app"]
    capp_id = capp["id"]
    from apps.custom_app import build_summary_prompt, mark_triggered, save_report

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(
        f"[scheduler] triggering summary for '{capp['name']}' (scheduled_for={sched_for}, trigger={trigger})"
    )
    prompt = build_summary_prompt(capp)
    if not prompt:
        return
    mcfg = _get_model_config()
    if not mcfg.get("model") or not mcfg.get("api_key"):
        return
    import os as _os

    import litellm as _lt

    _os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    _KNOWN = (
        "openai/",
        "azure/",
        "anthropic/",
        "cohere/",
        "huggingface/",
        "ollama/",
        "deepseek/",
        "groq/",
        "together_ai/",
        "openrouter/",
        "gemini/",
        "mistral/",
    )
    _m = mcfg["model"]
    if not any(_m.startswith(p) for p in _KNOWN) and mcfg.get("api_base"):
        _m = f"openai/{_m}"
    resp = _lt.completion(
        model=_m,
        messages=[{"role": "user", "content": prompt}],
        api_key=mcfg["api_key"],
        api_base=mcfg.get("api_base"),
        temperature=0.5,
        max_tokens=4096,
    )
    _u = getattr(resp, "usage", None)
    if _u:
        _s_pi = getattr(_u, "prompt_tokens", 0)
        _s_co = getattr(_u, "completion_tokens", 0)
        from apps.llm_utils import record_tokens as _rec

        _rec(prompt_tokens=_s_pi, completion_tokens=_s_co)
        from apps.llm_utils import record_task_usage as _rec_t

        _rec_t(f"app_{capp.get('name', capp_id)}", _s_pi, _s_co, 0)
    content = resp.choices[0].message.content or ""
    save_report(capp_id, content=content, params_used={}, report_type="summary")
    mark_triggered(capp_id, "summary")
    _push_notification(
        title=_t("notification.custom_app.summary", name=capp['name']),
        content=_t("notification.custom_app.summary_content"),
        level="info",
    )


def _load_execution_radar_tasks() -> list["_TaskDescriptor"]:
    """Build a single TaskDescriptor for the daily execution radar pipeline."""
    registry = load_apps_registry()
    app = registry.get("execution_radar", {})
    if not app.get("enabled"):
        return []
    config = app.get("config", {})
    schedule_time = config.get("schedule_time", "02:00")
    hh, mm = schedule_time.split(":")[:2]
    cron_expr = f"{mm} {hh} * * *"
    return [
        _TaskDescriptor(
            task_id="daily_execution_radar",
            schedule={"enabled": True, "mode": "daily", "time": schedule_time},
            cron_expr=cron_expr,
            created_at=app.get("installed_at", "2025-01-01T00:00:00"),
            last_success_at=app.get("last_run"),
            catchup_policy="LATEST_ONLY",
            catchup_window_hours=48,
            max_catchup_runs=1,
            extra={"kind": "execution_radar"},
        )
    ]


def _exec_execution_radar(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    from apps.execution_radar_runner import run_execution_radar
    run_execution_radar(task, slot, trigger)


def _init_scheduler_service():
    """Register task loaders and executors with the global SchedulerService."""
    _scheduler_svc.register_task_loader(_load_official_tasks)
    _scheduler_svc.register_task_loader(_load_custom_tasks)
    _scheduler_svc.register_task_loader(_load_execution_radar_tasks)
    _scheduler_svc.register_executor("daily_digest", _exec_daily_digest)
    _scheduler_svc.register_executor("email_summary", _exec_email_summary)
    _scheduler_svc.register_executor("custom", _exec_custom_app)
    _scheduler_svc.register_executor("custom_summary", _exec_custom_summary)
    _scheduler_svc.register_executor("execution_radar", _exec_execution_radar)


def _start_app_scheduler():
    """Start the catch-up scheduler and a background heartbeat timer."""
    global _app_scheduler_timer
    _init_scheduler_service()

    from myxai_desk.core.scheduler_service import cleanup_stale_running

    cleaned = cleanup_stale_running()
    if cleaned:
        print(f"[scheduler] cleaned up {cleaned} stale running task(s) from previous session")

    def _tick():
        global _app_scheduler_timer
        try:
            _scheduler_svc.tick()
        except Exception as exc:
            log.exception("[scheduler] tick error")
        _app_scheduler_timer = threading.Timer(60, _tick)
        _app_scheduler_timer.daemon = True
        _app_scheduler_timer.start()

    _app_scheduler_timer = threading.Timer(60, _tick)
    _app_scheduler_timer.daemon = True
    _app_scheduler_timer.start()
    print("[scheduler] started (catch-up enabled)")


# ---------------------------------------------------------------------------
# Scheduler 路由已迁移到 myxai_desk/web/scheduler_routes.py
# 旧路由定义已删除（PR-2）：
#   - api_scheduler_trigger()
#   - api_scheduler_runs()
#   - api_scheduler_status()
#   - api_scheduler_today()
# 常量 _OFFICIAL_APP_META 已移至 scheduler_routes.py
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Routes — feedback & cases
# ---------------------------------------------------------------------------

_CASES_DIR = Path.home() / ".nanobot" / "desktop_cases"


def _cases_file(rating: str) -> Path:
    _CASES_DIR.mkdir(parents=True, exist_ok=True)
    return _CASES_DIR / f"cases_{'positive' if rating == 'like' else 'negative'}.jsonl"


@flask_app.route("/api/feedback", methods=["POST"])
def api_feedback():
    body = request.json or {}
    rating = body.get("rating")
    if rating not in ("like", "dislike"):
        return jsonify({"error": _t("error.field_required", field="rating (like/dislike)")}), 400

    case = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": body.get("session_id", ""),
        "prompt": body.get("prompt", ""),
        "answer": body.get("answer", ""),
        "rating": rating,
        "comment": body.get("comment", ""),
        "tags": body.get("tags", []),
    }

    fp = _cases_file(rating)
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")

    return jsonify({"success": True})


@flask_app.route("/api/cases/stats")
def api_cases_stats():
    pos_file = _CASES_DIR / "cases_positive.jsonl"
    neg_file = _CASES_DIR / "cases_negative.jsonl"

    def _count(fp: Path) -> int:
        if not fp.exists():
            return 0
        return sum(1 for line in fp.read_text(encoding="utf-8").splitlines() if line.strip())

    def _recent(fp: Path, n: int = 5) -> list[dict]:
        if not fp.exists():
            return []
        lines = [l for l in fp.read_text(encoding="utf-8").splitlines() if l.strip()]
        result = []
        for line in lines[-n:]:
            try:
                obj = json.loads(line)
                result.append(
                    {
                        "ts": obj.get("ts", ""),
                        "prompt": (obj.get("prompt", "") or "")[:80],
                        "comment": obj.get("comment", ""),
                    }
                )
            except Exception:
                log.debug("Skipping malformed feedback line", exc_info=True)
        result.reverse()
        return result

    return jsonify(
        {
            "positive_count": _count(pos_file),
            "negative_count": _count(neg_file),
            "recent_positive": _recent(pos_file),
            "recent_negative": _recent(neg_file),
        }
    )


# ---------------------------------------------------------------------------
# Routes — gateway
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gateway 辅助函数和路由已迁移到 myxai_desk/web/gateway_routes.py
# 旧函数定义已删除（PR-1）：
#   - _find_nanobot_cmd()
#   - _kill_process_tree()
#   - _cleanup_gateway()
#   - api_gateway_start()
#   - api_gateway_stop()
#   - api_gateway_status()
#   - api_gateway_logs()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Desk Manager (tray) — shared reference set by main()
# ---------------------------------------------------------------------------

_desk_manager = None


@flask_app.route("/api/desk/lang", methods=["POST"])
def api_desk_lang():
    """Let the frontend sync its language preference to the tray menu."""
    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "").strip().lower()
    if lang not in ("zh", "en"):
        lang = "zh" if lang.startswith("zh") else "en"
    if _desk_manager is not None:
        _desk_manager.lang = lang
    return jsonify({"ok": True, "lang": lang})


@flask_app.route("/api/desk/settings", methods=["GET"])
def api_desk_settings_get():
    """Return desktop app preferences (close_action, etc.)."""
    from myxai_desk.core.storage.paths import DESK_SETTINGS_FILE
    settings = {"close_action": "minimize"}
    if DESK_SETTINGS_FILE.exists():
        try:
            settings.update(json.loads(DESK_SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            log.debug("Failed to read desk_settings.json", exc_info=True)
    return jsonify(settings)


@flask_app.route("/api/desk/settings", methods=["POST"])
def api_desk_settings_post():
    """Save desktop app preferences."""
    from myxai_desk.core.storage.paths import DESK_SETTINGS_FILE
    data = request.get_json(silent=True) or {}
    close_action = data.get("close_action", "minimize")
    if close_action not in ("minimize", "quit"):
        close_action = "minimize"
    settings = {"close_action": close_action}
    try:
        DESK_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DESK_SETTINGS_FILE.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        log.exception("Failed to save desk_settings.json")
        return jsonify({"error": "save failed"}), 500
    if _desk_manager is not None:
        _desk_manager.close_action = close_action
    return jsonify({"ok": True, **settings})


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def _shutdown():
    """Terminate all background resources before exit."""
    global _gateway_process, _agent, _async_loop, _cron_service, _app_scheduler_timer

    # 0a. Stop app scheduler
    if _app_scheduler_timer is not None:
        _app_scheduler_timer.cancel()
        _app_scheduler_timer = None

    # 0. Stop cron service
    if _cron_service is not None:
        _cron_service.stop()
        _cron_service = None

    # 1. Stop gateway subprocess
    if _gateway_process is not None:
        try:
            _kill_process_tree(_gateway_process.pid)
            _gateway_process.wait(timeout=3)
        except Exception:
            log.debug("Gateway process cleanup failed", exc_info=True)
        _gateway_process = None

    # 2. Close MCP connections & async loop
    if _agent is not None and getattr(_agent, "_mcp_stack", None) is not None:
        if _async_loop is not None and _async_loop.is_running():

            async def _close_mcp():
                with contextlib.suppress(Exception):
                    await _agent._mcp_stack.aclose()

            try:
                f = asyncio.run_coroutine_threadsafe(_close_mcp(), _async_loop)
                f.result(timeout=5)
            except Exception:
                log.debug("MCP close during shutdown failed", exc_info=True)
    _agent = None

    if _async_loop is not None and _async_loop.is_running():
        _async_loop.call_soon_threadsafe(_async_loop.stop)
    _async_loop = None

    print("[Otta] Shutdown complete.", flush=True)


import atexit

atexit.register(_shutdown)


# ---------------------------------------------------------------------------
# Entry‑point
# ---------------------------------------------------------------------------


def main():
    global _desk_manager

    # Migrate tokenCost from config.json to separate file (one-time migration)
    try:
        from myxai_desk.core.migrate_token_cost import migrate_token_cost_config
        migrate_token_cost_config()
    except Exception:
        log.debug("[app] Token cost config migration skipped", exc_info=True)

    # --- Localhost API token guard ---------------------------------------- #
    _api_token = secrets.token_hex(32)
    flask_app.config["MYXAI_API_TOKEN"] = _api_token

    _start_app_scheduler()

    # Run catch-up check in background so missed tasks are compensated on startup
    threading.Thread(target=_scheduler_svc.on_app_start, daemon=True).start()

    # --- Route dedup guard ------------------------------------------------ #
    from myxai_desk.web.migration_guards import assert_no_duplicate_routes
    assert_no_duplicate_routes(flask_app)

    port = 19280

    # --- Host header allowlist (DNS-rebinding defence) -------------------- #
    global _ALLOWED_HOSTS
    _ALLOWED_HOSTS = frozenset({
        f"127.0.0.1:{port}",
        f"localhost:{port}",
    })

    # --- fallback: no pywebview ------------------------------------------- #
    try:
        import webview  # noqa: F401
    except ImportError:
        print("pywebview 未安装，将在浏览器中打开。")
        print("安装方法：pip install pywebview")
        import webbrowser

        threading.Thread(
            target=lambda: flask_app.run(
                host="127.0.0.1", port=port, threaded=True, use_reloader=False
            ),
            daemon=True,
        ).start()
        time.sleep(1)
        _dev_mode = os.environ.get("MYXAI_DEV") == "1"
        if _dev_mode:
            log.warning("[security] DEV MODE: API token exposed via URL param")
            webbrowser.open(f"http://127.0.0.1:{port}/?token={_api_token}")
        else:
            print("⚠ 浏览器模式下 API 受 token 保护，功能受限。")
            print("  如需完整功能请安装 pywebview，或设置 MYXAI_DEV=1 以开发模式运行。")
            webbrowser.open(f"http://127.0.0.1:{port}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        _shutdown()
        return

    # --- start Flask in background ---------------------------------------- #
    threading.Thread(
        target=lambda: flask_app.run(
            host="127.0.0.1", port=port, threaded=True, use_reloader=False
        ),
        daemon=True,
    ).start()

    import urllib.request

    _health_req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/check",
        headers={"X-MyxAI-Token": _api_token},
    )
    for _attempt in range(80):
        try:
            urllib.request.urlopen(_health_req, timeout=1)
            break
        except Exception:
            if _attempt == 79:
                log.warning("Flask server did not become ready after 80 attempts")
            time.sleep(0.05)

    # --- DeskManager (tray) ------------------------------------------------ #
    from desk_manager import DeskManager

    _desk_manager = DeskManager(port=port, api_token=_api_token)

    def _unread_count():
        total = 0
        # Notification queue
        with _notifications_lock:
            total += sum(1 for n in _notifications if not n["read"])
        # Reports from all app types
        try:
            from apps.custom_app import all_unread_counts

            total += sum(all_unread_counts().values())
        except Exception:
            log.debug("Failed to get custom app unread counts", exc_info=True)
        try:
            from apps.daily_digest import list_reports as _dl

            total += sum(1 for r in _dl(limit=60) if not r.get("read"))
        except Exception:
            log.debug("Failed to get daily digest unread counts", exc_info=True)
        try:
            from apps.email_summary import list_reports as _el

            total += sum(1 for r in _el() if not r.get("read"))
        except Exception:
            log.debug("Failed to get email summary unread counts", exc_info=True)
        return total

    _desk_manager._get_unread_count = _unread_count

    try:
        from apps.llm_utils import get_token_usage_with_cost
        from myxai_desk.core.token_cost_service import get_token_cost_config

        def _get_token_usage_wrapper():
            cost_config = get_token_cost_config()
            config_wrapper = {"tokenCost": cost_config}
            return get_token_usage_with_cost(config_wrapper)
        
        _desk_manager._get_token_usage = _get_token_usage_wrapper
    except ImportError:
        pass

    _desk_manager._on_resume = _scheduler_svc.on_resume

    # Load saved desk preferences (close_action, etc.)
    from myxai_desk.core.storage.paths import DESK_SETTINGS_FILE
    if DESK_SETTINGS_FILE.exists():
        try:
            _ds = json.loads(DESK_SETTINGS_FILE.read_text(encoding="utf-8"))
            _desk_manager.close_action = _ds.get("close_action", "minimize")
        except Exception:
            log.debug("Failed to load desk_settings.json at startup", exc_info=True)

    def _grant_media_permissions(win):
        """Auto-allow microphone/camera permissions in WebView2."""
        win.events.loaded.wait(30)
        try:
            from System import Func, Type
            from webview.platforms.winforms import BrowserView

            bv = BrowserView.instances.get(win.uid)
            if not bv or not getattr(bv, "browser", None):
                return

            def _setup():
                core = bv.browser.webview.CoreWebView2
                if not core:
                    return
                from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState

                def _on_perm(sender, args):
                    args.State = CoreWebView2PermissionState.Allow

                core.PermissionRequested += _on_perm

            bv.Invoke(Func[Type](_setup))
        except Exception as e:
            log.warning("[webview] auto-allow permissions failed: %s", e)

    _desk_manager.run(start_func=_grant_media_permissions)
    _shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
