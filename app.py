"""MyxAI Desk — 桌面可视化客户端."""

import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import asyncio
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import traceback as _tb
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

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

def _make_provider(config):
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider
    from nanobot.providers.custom_provider import CustomProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )


def _reset_agent():
    """Destroy the current agent, properly closing MCP connections."""
    global _agent, _cron_service
    if _cron_service is not None:
        _cron_service.stop()
        _cron_service = None
    with _agent_lock:
        old = _agent
        _agent = None
    if old and hasattr(old, '_mcp_stack') and old._mcp_stack is not None:
        async def _close():
            try:
                await old._mcp_stack.aclose()
            except Exception:
                pass
        _ensure_loop()
        asyncio.run_coroutine_threadsafe(_close(), _async_loop)
    with _mcp_log_lock:
        _mcp_log.clear()


def _push_notification(title: str, content: str, level: str = "info"):
    """Push a notification to the frontend queue."""
    entry = {
        "id": f"n-{int(time.time()*1000)}",
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


import re as _re

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

_EXEC_NUDGE = (
    "请通过工具调用来完成这个操作。"
)
_EXEC_FALLBACK = (
    "抱歉，本次操作未能通过工具执行。请尝试重新描述您的需求，"
    "或新建一个对话重试。"
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
        summary_text = (
            "[Earlier conversation summary]\n" + "\n".join(summaries[-8:])
        )
        return [{"role": "assistant", "content": summary_text}] + recent
    return recent


def _patch_agent_tool_history(agent):
    """Monkey-patch the agent's _process_message for execution governance.

    1. EXEC mode detection: keyword-based check on user input.
    2. Inline agent loop: runs LLM + tool calls directly so we control the flow.
    3. Fake-execution interception: if EXEC mode and the LLM returns text that
       looks like a simulated result (no actual tool_calls), inject a nudge
       message and retry (up to 2 times).
    4. History compression: older messages are summarized to prevent the LLM
       from pattern-matching past responses.
    5. Plain-text session save: avoids structured tool_calls in history that
       would cause the LLM to skip or mimic.
    """
    import types as _types
    from nanobot.bus.events import OutboundMessage

    _orig_build_system_prompt = agent.context.build_system_prompt

    def _enhanced_system_prompt(skill_names=None):
        base = _orig_build_system_prompt(skill_names)
        return base + (
            "\n\n## Tool Usage Rules\n"
            "1. When the user requests an action (create/cancel/delete/search/modify), "
            "you MUST call the appropriate tool. Do not describe or simulate the result.\n"
            "2. To cancel or modify a previous task, refer to the conversation history "
            "for the relevant job ID, then call the tool with that ID.\n"
            "3. If the user repeats a request that was done before, call the tool again "
            "— the previous result may have expired.\n"
            "4. Keep responses concise and natural.\n"
            "5. NEVER proactively create tasks/reminders unless the user explicitly asks. "
            "If the user asks to 'check' or 'verify', only use list — do NOT create new ones."
        )

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
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started. Memory consolidation in progress.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="\U0001f408 nanobot commands:\n/new \u2014 Start a new conversation\n/help \u2014 Show available commands")

        if len(session.messages) > self.memory_window:
            import asyncio as _aio
            _aio.create_task(self._consolidate_memory(session))

        self._set_tool_context(msg.channel, msg.chat_id)
        raw_history = session.get_history(max_messages=self.memory_window)
        clean_history = [
            m for m in raw_history
            if m["role"] != "tool" and "tool_calls" not in m
        ]
        clean_history = _compress_history(clean_history, keep_recent=10)
        initial_messages = self.context.build_messages(
            history=clean_history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        async def _bus_progress(content):
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content,
                metadata=msg.metadata or {},
            ))

        # --- Run the agent loop with EXEC governance ---
        is_cron = key.startswith("cron:")
        exec_mode = not is_cron and _is_exec_mode(msg.content)
        messages = list(initial_messages)
        n_initial = len(messages)
        iteration = 0
        final_content = None
        tools_used = []
        progress = on_progress or _bus_progress
        nudge_count = 0
        max_nudges = 1

        tool_defs = self.tools.get_definitions()
        print(f"[agent] exec_mode={exec_mode}, tools={len(tool_defs)}, "
              f"history={n_initial}, model={self.model}")

        try:
            while iteration < self.max_iterations:
                iteration += 1
                response = await self.provider.chat(
                    messages=messages,
                    tools=tool_defs,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                if response.has_tool_calls:
                    if progress:
                        clean = self._strip_think(response.content)
                        await progress(clean or self._tool_hint(response.tool_calls))

                    tc_dicts = [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.name,
                                      "arguments": _json.dumps(tc.arguments)}}
                        for tc in response.tool_calls
                    ]
                    messages = self.context.add_assistant_message(
                        messages, response.content, tc_dicts,
                        reasoning_content=response.reasoning_content,
                    )
                    for tc in response.tool_calls:
                        tools_used.append(tc.name)
                        print(f"[agent] tool: {tc.name}({str(tc.arguments)[:100]})")
                        result = await self.tools.execute(tc.name, tc.arguments)
                        print(f"[agent] result: {str(result)[:100]}")
                        messages = self.context.add_tool_result(
                            messages, tc.id, tc.name, result,
                        )
                else:
                    text = self._strip_think(response.content)
                    if (exec_mode
                            and nudge_count < max_nudges
                            and _is_fake_execution(text)):
                        nudge_count += 1
                        print(f"[agent] nudge: fake exec detected, retrying")
                        messages.append({"role": "assistant", "content": text})
                        messages.append({"role": "user", "content": _EXEC_NUDGE})
                        continue
                    final_content = text
                    break
        except Exception as _loop_err:
            print(f"[agent] error: {_loop_err}")
            if final_content is None:
                final_content = f"Error during processing: {_loop_err}"

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        if exec_mode and not tools_used and nudge_count >= max_nudges:
            print(f"[agent] EXEC fallback: {max_nudges} nudges exhausted, no tool calls")
            final_content = _EXEC_FALLBACK

        # --- Save to session: plain text only ---
        # Saving structured tool_calls or text annotations causes the LLM
        # to pattern-match and skip actual tool calls or mimic annotations.
        # Plain text is safest: the system prompt + tool definitions are
        # sufficient for the LLM to know it can/should call tools.
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content,
                            tools_used=tools_used if tools_used else None)

        self.sessions.save(session)

        with _last_tools_lock:
            _last_tools_used[key] = list(tools_used)

        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id,
            content=final_content,
        )

    agent._process_message = _types.MethodType(_patched_process_message, agent)


def _get_or_create_agent():
    global _agent, _cron_service
    with _agent_lock:
        if _agent is not None:
            return _agent

        from nanobot.config.loader import load_config, get_data_dir
        from nanobot.bus.queue import MessageBus
        from nanobot.agent.loop import AgentLoop
        from nanobot.cron.service import CronService
        from loguru import logger

        logger.disable("nanobot")

        config = load_config()
        bus = MessageBus()
        provider = _make_provider(config)

        cron_store = get_data_dir() / "cron" / "jobs.json"
        cron = CronService(cron_store)
        _cron_service = cron

        _agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=config.workspace_path,
            model=config.agents.defaults.model,
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
            from apps.web_search import EnhancedWebSearchTool, quota as _quota
            from nanobot.config.loader import get_config_path as _gcp
            _raw_cfg = {}
            try:
                _raw_cfg = json.loads(_gcp().read_text(encoding="utf-8"))
            except Exception:
                pass
            _search_cfg = _raw_cfg.get("tools", {}).get("web", {}).get("search", {})
            _baidu_key = _search_cfg.get("baiduApiKey") or None
            _brave_key = config.tools.web.search.api_key or None
            _agent.tools.register(EnhancedWebSearchTool(
                brave_api_key=_brave_key,
                baidu_api_key=_baidu_key,
            ))
            _quota.set_quota_only(_search_cfg.get("quotaOnly", True))
            limits = {}
            if _search_cfg.get("baiduDailyLimit"):
                limits["baidu"] = int(_search_cfg["baiduDailyLimit"])
            if _search_cfg.get("braveDailyLimit"):
                limits["brave"] = int(_search_cfg["braveDailyLimit"])
            if limits:
                _quota.set_limits(limits)
            _active = [n for n in ["Baidu" if _baidu_key else None,
                                   "Brave" if _brave_key else None] if n]
            print(f"[agent] web_search: API engines = {_active or ['none (no keys)']}")
        except Exception as _ws_err:
            print(f"[agent] failed to replace web_search: {_ws_err}")

        agent_ref = _agent

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
            print(f"[cron] add_job result: id={job.id}, schedule={job.schedule.kind}, "
                  f"at_ms={job.schedule.at_ms}, next_run={job.state.next_run_at_ms}, "
                  f"delete_after={job.delete_after_run}")
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
            print(f"[cron] executing job '{job.name}' ({job.id}), delete_after={job.delete_after_run}")
            await _orig_execute_job(job)
            print(f"[cron] job '{job.name}' done, status={job.state.last_status}, error={job.state.last_error}")

        cron._arm_timer = _traced_arm_timer
        cron._execute_job = _traced_execute_job

        cron._running = True
        cron._load_store()

        _ensure_loop()
        asyncio.run_coroutine_threadsafe(cron.start(), _async_loop)
        print(f"[cron] service initialized, store={cron.store_path}, jobs={len(cron._store.jobs if cron._store else [])}")

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
            try:
                await agent._mcp_stack.aclose()
            except Exception:
                pass
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
            await progress_cb(f"正在连接 MCP: {name} …")
        try:
            if cfg.command:
                exe = shutil.which(cfg.command)
                if not exe:
                    _mcp_record(name, "error", f"Command not found: {cfg.command}")
                    continue
                cmd, args = _win_fix_cmd(cfg.command, list(cfg.args))
                _mcp_record(name, "info", f"Starting: {cmd} {' '.join(args)}")
                params = StdioServerParameters(
                    command=cmd, args=args, env=cfg.env or None,
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
            _mcp_record(name, "error", f"{type(e).__name__}: {e}")

    if total_registered:
        _mcp_record("*", "ok", f"Total MCP tools registered: {total_registered}")
    else:
        _mcp_record("*", "warn", "No MCP tools were registered")


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
        return {"content": "nanobot 未安装", "tools_used": []}

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
                prompt, session_key=session_key, on_progress=_progress,
            )
            result_holder["content"] = response or ""
            with _last_tools_lock:
                result_holder["tools_used"] = list(
                    _last_tools_used.pop(session_key, [])
                )
        except Exception as exc:
            error_holder.append(exc)

    _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(_execute(), _async_loop)
    try:
        future.result(timeout=timeout)
    except Exception as exc:
        error_holder.append(exc)

    if error_holder:
        return {
            "content": f"执行出错: {error_holder[0]}",
            "tools_used": result_holder.get("tools_used", []),
        }
    return result_holder


# ---------------------------------------------------------------------------
# Routes — static
# ---------------------------------------------------------------------------

@flask_app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


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
            pass
    return jsonify({
        "nanobot_installed": NANOBOT_AVAILABLE,
        "config_exists": config_exists,
        "config_path": config_path,
    })


# ---------------------------------------------------------------------------
# Routes — onboard
# ---------------------------------------------------------------------------

@flask_app.route("/api/onboard", methods=["POST"])
def api_onboard():
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    try:
        from nanobot.config.loader import get_config_path, save_config
        from nanobot.config.schema import Config
        from nanobot.utils.helpers import get_workspace_path

        config_path = get_config_path()
        if not config_path.exists():
            save_config(Config())
        workspace = get_workspace_path()
        workspace.mkdir(parents=True, exist_ok=True)
        return jsonify({"success": True, "config_path": str(config_path), "workspace": str(workspace)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Routes — config
# ---------------------------------------------------------------------------

@flask_app.route("/api/config")
def api_get_config():
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    try:
        from nanobot.config.loader import get_config_path
        cp = get_config_path()
        if not cp.exists():
            return jsonify({"error": "配置文件不存在，请先初始化"}), 404
        with open(cp, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/config", methods=["POST"])
def api_save_config():
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    try:
        from nanobot.config.loader import get_config_path
        cp = get_config_path()
        data = request.json
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _reset_agent()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/token/usage")
def api_token_usage():
    from apps.llm_utils import get_token_usage
    return jsonify(get_token_usage())


@flask_app.route("/api/token/history")
def api_token_history():
    days = request.args.get("days", 30, type=int)
    from apps.llm_utils import get_token_history
    history = get_token_history(min(days, 90))
    total = sum(d["tokens"] for d in history)
    return jsonify({"days": len(history), "total": total, "history": history})


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
        return jsonify({"error": "nanobot 未安装"}), 400
    try:
        from nanobot.config.loader import load_config, get_config_path
        from nanobot.providers.registry import PROVIDERS

        cp = get_config_path()
        config = load_config()
        workspace = config.workspace_path

        providers = []
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            providers.append({
                "name": spec.name,
                "label": getattr(spec, "display_name", spec.name),
                "configured": bool(p.api_key) or getattr(spec, "is_oauth", False),
            })

        channels = []
        for name in ("telegram", "discord", "whatsapp", "feishu", "mochat", "dingtalk", "email", "slack", "qq"):
            ch = getattr(config.channels, name, None)
            if ch:
                channels.append({"name": name, "enabled": ch.enabled})

        mcp_status = []
        for name, srv in config.tools.mcp_servers.items():
            mcp_status.append({
                "name": name,
                "type": "http" if srv.url else "stdio",
                "detail": srv.url or (srv.command + " " + " ".join(srv.args)),
            })

        mcp_connected = False
        mcp_tool_count = 0
        mcp_tool_names = []
        if _agent is not None:
            mcp_connected = getattr(_agent, '_mcp_connected', False)
            mcp_tool_names = [n for n in _agent.tools._tools if n.startswith("mcp_")]
            mcp_tool_count = len(mcp_tool_names)

        with _mcp_log_lock:
            mcp_log_copy = list(_mcp_log)

        return jsonify({
            "config_path": str(cp),
            "config_exists": cp.exists(),
            "workspace": str(workspace),
            "workspace_exists": workspace.exists(),
            "model": config.agents.defaults.model,
            "providers": providers,
            "channels": channels,
            "mcp_servers": mcp_status,
            "mcp_connected": mcp_connected,
            "mcp_tool_count": mcp_tool_count,
            "mcp_tool_names": mcp_tool_names,
            "mcp_log": mcp_log_copy,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Routes — agent tools info
# ---------------------------------------------------------------------------

@flask_app.route("/api/tools")
def api_tools():
    """Return registered tools (for diagnostics)."""
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    if _agent is None:
        return jsonify({"connected": False, "tools": [], "message": "Agent not yet created"})
    tool_names = list(_agent.tools._tools.keys())
    mcp_tools = [n for n in tool_names if n.startswith("mcp_")]
    return jsonify({
        "connected": _agent._mcp_connected,
        "total": len(tool_names),
        "mcp_count": len(mcp_tools),
        "mcp_tools": mcp_tools,
        "all_tools": tool_names,
    })


# ---------------------------------------------------------------------------
# Routes — MCP diagnostics
# ---------------------------------------------------------------------------

@flask_app.route("/api/mcp/test", methods=["POST"])
def api_mcp_test():
    """Test MCP server connections without affecting the running agent."""
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400

    from nanobot.config.loader import load_config
    config = load_config()
    servers = config.tools.mcp_servers
    if not servers:
        return jsonify({"results": [], "message": "No MCP servers configured"})

    results: list[dict] = []

    async def _test():
        from contextlib import AsyncExitStack
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        for name, cfg in servers.items():
            entry = {"name": name, "status": "error", "message": "", "tools": []}
            try:
                if cfg.command:
                    exe = shutil.which(cfg.command)
                    if not exe:
                        entry["message"] = f"Command not found in PATH: {cfg.command}"
                        results.append(entry)
                        continue
                    cmd, args = _win_fix_cmd(cfg.command, list(cfg.args))
                    stack = AsyncExitStack()
                    await stack.__aenter__()
                    params = StdioServerParameters(
                        command=cmd, args=args, env=cfg.env or None,
                    )
                    read, write = await asyncio.wait_for(
                        stack.enter_async_context(stdio_client(params)),
                        timeout=90,
                    )
                elif cfg.url:
                    stack = AsyncExitStack()
                    await stack.__aenter__()
                    from mcp.client.streamable_http import streamable_http_client
                    read, write, _ = await asyncio.wait_for(
                        stack.enter_async_context(streamable_http_client(cfg.url)),
                        timeout=30,
                    )
                else:
                    entry["message"] = "No command or url"
                    results.append(entry)
                    continue

                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                tools = await session.list_tools()
                entry["status"] = "ok"
                entry["tools"] = [t.name for t in tools.tools]
                entry["message"] = f"{len(tools.tools)} tools available"
                try:
                    await stack.aclose()
                except Exception:
                    pass
            except asyncio.TimeoutError:
                entry["message"] = "Connection timed out (90s)"
            except Exception as e:
                entry["message"] = f"{type(e).__name__}: {e}"
            results.append(entry)

    _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(_test(), _async_loop)
    try:
        future.result(timeout=180)
    except Exception as e:
        return jsonify({"error": f"Test timed out: {e}"}), 500

    return jsonify({"results": results})


@flask_app.route("/api/mcp/reconnect", methods=["POST"])
def api_mcp_reconnect():
    """Force reconnect MCP servers on the running agent."""
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    if _agent is None:
        return jsonify({"error": "Agent not yet created — send a message first"}), 400

    agent = _agent
    if agent._mcp_stack is not None:
        async def _close_old():
            try:
                await agent._mcp_stack.aclose()
            except Exception:
                pass
        _ensure_loop()
        f = asyncio.run_coroutine_threadsafe(_close_old(), _async_loop)
        try:
            f.result(timeout=10)
        except Exception:
            pass
        agent._mcp_stack = None

    agent._mcp_connected = False
    for key in list(agent.tools._tools.keys()):
        if key.startswith("mcp_"):
            del agent.tools._tools[key]

    with _mcp_log_lock:
        _mcp_log.clear()

    async def _reconn():
        await _connect_mcp_safe(agent)

    _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(_reconn(), _async_loop)
    try:
        future.result(timeout=180)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    mcp_tools = [n for n in agent.tools._tools if n.startswith("mcp_")]
    with _mcp_log_lock:
        log_copy = list(_mcp_log)
    return jsonify({
        "success": True,
        "mcp_tool_count": len(mcp_tools),
        "mcp_tools": mcp_tools,
        "mcp_log": log_copy,
    })


@flask_app.route("/api/mcp/log")
def api_mcp_log():
    """Return MCP diagnostic log."""
    with _mcp_log_lock:
        return jsonify(list(_mcp_log))


# ---------------------------------------------------------------------------
# Routes — notifications (cron reminders, etc.)
# ---------------------------------------------------------------------------

@flask_app.route("/api/notifications")
def api_notifications():
    """Return unread notifications and mark them read."""
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
        return jsonify({"error": "nanobot 未安装"}), 400

    message = (request.json or {}).get("message", "").strip()
    session_id = (request.json or {}).get("session_id", f"desktop:{_session_epoch}_{_session_counter}")
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    q: queue.Queue[str] = queue.Queue()

    async def _process():
        try:
            agent = _get_or_create_agent()

            async def on_progress(content):
                q.put(json.dumps({"type": "progress", "content": content}, ensure_ascii=False))

            need_mcp = bool(agent._mcp_servers)
            has_mcp_tools = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp_tools:
                await _connect_mcp_safe(agent, progress_cb=on_progress)

            has_mcp_tools_after = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp_tools_after:
                errors = [e for e in _mcp_log if e["level"] == "error"]
                hint = errors[-1]["message"] if errors else "unknown"
                q.put(json.dumps({
                    "type": "progress",
                    "content": f"⚠️ MCP 工具连接失败: {hint}",
                }, ensure_ascii=False))

            response = await agent.process_direct(
                message, session_key=session_id, on_progress=on_progress,
            )
            q.put(json.dumps({"type": "done", "content": response or ""}, ensure_ascii=False))
        except Exception as exc:
            q.put(json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False))

    _ensure_loop()
    asyncio.run_coroutine_threadsafe(_process(), _async_loop)

    def generate():
        while True:
            try:
                data = q.get(timeout=300)
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f'data: {json.dumps({"type": "error", "content": "请求超时"})}\n\n'
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
        sessions.append({
            "id": sid,
            "title": sess.get("title", ""),
            "updated_at": sess.get("updated_at", ""),
            "message_count": len(sess.get("messages", [])),
        })
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
# Routes — Apps management
# ---------------------------------------------------------------------------

_APPS_DIR = Path.home() / ".nanobot" / "apps"
_APPS_REGISTRY = _APPS_DIR / "registry.json"
_APPS_PREFS = _APPS_DIR / "prefs.json"


def _load_apps_prefs() -> dict:
    """Load app preferences (favorites, run_count, etc.)."""
    if _APPS_PREFS.exists():
        try:
            return json.loads(_APPS_PREFS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_apps_prefs(data: dict):
    _APPS_DIR.mkdir(parents=True, exist_ok=True)
    _APPS_PREFS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _inc_run_count(app_id: str):
    prefs = _load_apps_prefs()
    p = prefs.setdefault(app_id, {})
    p["run_count"] = p.get("run_count", 0) + 1
    _save_apps_prefs(prefs)


_digest_task_lock = threading.Lock()
_digest_task_status: dict = {}  # {"status": "idle"|"running"|"done"|"error", ...}


# Built-in app catalog
_APP_CATALOG = {
    "daily_digest": {
        "id": "daily_digest",
        "name": "每日私享会",
        "name_en": "Daily Briefing",
        "icon": "🎯",
        "description": "你的私人资讯策展人——基于浏览和对话，每天精选最值得关注的内容，支持深入探索",
        "description_en": "Your personal curator — daily picks based on your interests, with deep-dive exploration",
        "version": "2.0.0",
        "author": "nanobot",
        "category": "productivity",
    },
    "web_monitor": {
        "id": "web_monitor",
        "name": "网页监控",
        "name_en": "Web Monitor",
        "icon": "🔍",
        "description": "监控指定网页变化，有更新时自动提醒",
        "description_en": "Monitor web pages for changes, notify on updates",
        "version": "1.0.0",
        "author": "nanobot",
        "category": "tools",
    },
    "email_summary": {
        "id": "email_summary",
        "name": "邮件简报",
        "name_en": "Email Briefing",
        "icon": "📧",
        "description": "连接邮箱，AI 分类归纳生成每日邮件简报",
        "description_en": "Connect your inbox, AI categorises and summarises into a daily briefing",
        "version": "1.0.0",
        "author": "nanobot",
        "category": "productivity",
    },
    "focus_timer": {
        "id": "focus_timer",
        "name": "专注计时",
        "name_en": "Focus Timer",
        "icon": "⏱️",
        "description": "番茄钟工作法，自动记录专注时间并统计",
        "description_en": "Pomodoro timer with automatic focus time tracking",
        "version": "1.0.0",
        "author": "nanobot",
        "category": "productivity",
    },
}

_DEFAULT_DIGEST_CONFIG = {
    "browser": "auto",
    "history_hours": 24,
    "schedule_time": "22:00",
    "push_notification": True,
    "push_email": "",
}

_DEFAULT_MONITOR_CONFIG = {
    "check_interval_minutes": 30,
    "default_mode": "hash",
    "schedule_enabled": True,
}

_DEFAULT_EMAIL_CONFIG = {
    "imap_host": "",
    "imap_port": 993,
    "imap_user": "",
    "imap_password": "",
    "imap_ssl": True,
    "imap_folder": "INBOX",
    "hours": 24,
    "max_emails": 50,
    "schedule_time": "08:00",
}

_DEFAULT_FOCUS_CONFIG = {
    "focus_minutes": 25,
    "break_minutes": 5,
    "long_break_minutes": 15,
    "long_break_interval": 4,
    "push_notification": True,
}


def _load_apps_registry() -> dict:
    _APPS_DIR.mkdir(parents=True, exist_ok=True)
    if _APPS_REGISTRY.exists():
        try:
            return json.loads(_APPS_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_apps_registry(data: dict):
    _APPS_DIR.mkdir(parents=True, exist_ok=True)
    _APPS_REGISTRY.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _get_model_config() -> dict:
    """Read model/api_key/api_base/brave_api_key/baidu_api_key from nanobot config."""
    if not NANOBOT_AVAILABLE:
        return {}
    try:
        from nanobot.config.loader import load_config, get_config_path
        config = load_config()
        model = config.agents.defaults.model
        p = config.get_provider(model)
        brave_key = config.tools.web.search.api_key if config.tools.web.search else None
        baidu_key = None
        try:
            raw = json.loads(get_config_path().read_text(encoding="utf-8"))
            baidu_key = (raw.get("tools", {}).get("web", {})
                         .get("search", {}).get("baiduApiKey") or None)
        except Exception:
            pass
        return {
            "model": model,
            "api_key": p.api_key if p else None,
            "api_base": config.get_api_base(model) or None,
            "brave_api_key": brave_key or None,
            "baidu_api_key": baidu_key or None,
        }
    except Exception:
        return {}


@flask_app.route("/api/apps")
def api_apps_list():
    """Return all apps: catalog + installation status + custom apps."""
    registry = _load_apps_registry()
    prefs = _load_apps_prefs()
    result = []
    for app_id, catalog in _APP_CATALOG.items():
        entry = {**catalog}
        entry["type"] = "builtin"
        installed = registry.get(app_id)
        entry["installed"] = installed is not None
        entry["enabled"] = installed.get("enabled", False) if installed else False
        entry["config"] = installed.get("config", {}) if installed else {}
        entry["last_run"] = installed.get("last_run") if installed else None
        p = prefs.get(app_id, {})
        entry["favorite"] = p.get("favorite", False)
        entry["run_count"] = p.get("run_count", 0)
        entry["created_at"] = installed.get("installed_at", "") if installed else ""
        result.append(entry)
    from apps.custom_app import list_apps as _list_custom
    import re as _re
    for capp in _list_custom():
        _tpl = capp.get("prompt_template", "")
        _pg = capp.get("param_groups") or []
        _pv = _pg[0] if _pg else capp.get("param_values", {})
        _desc = _re.sub(
            r"\{\{(.+?)\}\}",
            lambda m: _pv.get(m.group(1).strip(), m.group(0)),
            _tpl,
        )[:60]
        if len(_pg) > 1:
            _desc += f" (+{len(_pg)-1})"
        _desc += "…"
        p = prefs.get(capp["id"], {})
        result.append({
            "id": capp["id"],
            "name": capp["name"],
            "name_en": capp["name"],
            "icon": capp.get("icon", "🤖"),
            "description": _desc,
            "description_en": _desc,
            "version": "1.0.0",
            "author": "custom",
            "category": "custom",
            "type": "custom",
            "installed": True,
            "enabled": capp.get("schedule", {}).get("enabled", False),
            "config": {},
            "last_run": capp.get("last_run"),
            "favorite": p.get("favorite", False),
            "run_count": p.get("run_count", 0),
            "created_at": capp.get("created_at", ""),
        })
    return jsonify(result)


@flask_app.route("/api/apps/<app_id>/install", methods=["POST"])
def api_app_install(app_id):
    if app_id not in _APP_CATALOG:
        return jsonify({"error": "应用不存在"}), 404
    registry = _load_apps_registry()
    if app_id in registry:
        return jsonify({"error": "应用已安装"}), 400
    default_configs = {
        "daily_digest": _DEFAULT_DIGEST_CONFIG,
        "web_monitor": _DEFAULT_MONITOR_CONFIG,
        "email_summary": _DEFAULT_EMAIL_CONFIG,
        "focus_timer": _DEFAULT_FOCUS_CONFIG,
    }
    registry[app_id] = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "config": default_configs.get(app_id, {}),
    }
    _save_apps_registry(registry)
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/uninstall", methods=["POST"])
def api_app_uninstall(app_id):
    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    del registry[app_id]
    _save_apps_registry(registry)
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/enable", methods=["POST"])
def api_app_enable(app_id):
    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    registry[app_id]["enabled"] = True
    _save_apps_registry(registry)
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/disable", methods=["POST"])
def api_app_disable(app_id):
    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    registry[app_id]["enabled"] = False
    _save_apps_registry(registry)
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/favorite", methods=["POST"])
def api_app_favorite(app_id):
    """Toggle favorite status for any app (builtin or custom)."""
    prefs = _load_apps_prefs()
    p = prefs.setdefault(app_id, {})
    p["favorite"] = not p.get("favorite", False)
    _save_apps_prefs(prefs)
    return jsonify({"success": True, "favorite": p["favorite"]})


@flask_app.route("/api/apps/<app_id>/record-run", methods=["POST"])
def api_app_record_run(app_id):
    """Increment run count for an app."""
    prefs = _load_apps_prefs()
    p = prefs.setdefault(app_id, {})
    p["run_count"] = p.get("run_count", 0) + 1
    _save_apps_prefs(prefs)
    return jsonify({"success": True, "run_count": p["run_count"]})


@flask_app.route("/api/apps/<app_id>/config", methods=["GET"])
def api_app_get_config(app_id):
    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    return jsonify(registry[app_id].get("config", {}))


@flask_app.route("/api/apps/<app_id>/config", methods=["POST"])
def api_app_save_config(app_id):
    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    new_config = request.json or {}
    registry[app_id]["config"] = new_config
    _save_apps_registry(registry)
    return jsonify({"success": True})


@flask_app.route("/api/apps/daily_digest/run", methods=["POST"])
def api_digest_run():
    """Start a daily digest run in the background."""
    registry = _load_apps_registry()
    if "daily_digest" not in registry:
        return jsonify({"error": "每日私享会未安装"}), 400

    with _digest_task_lock:
        if _digest_task_status.get("status") == "running":
            return jsonify({"error": "日报正在生成中，请稍候"}), 409
        _digest_task_status.update({"status": "running", "progress": "正在采集浏览器历史…"})

    def _run():
        try:
            from apps.daily_digest import run_daily_digest
            app_config = registry["daily_digest"].get("config", {})
            model_cfg = _get_model_config()
            merged = {**app_config, **model_cfg}

            def _progress(msg):
                with _digest_task_lock:
                    _digest_task_status["progress"] = msg

            result = run_daily_digest(merged, progress_cb=_progress)

            if result["status"] == "ok":
                reg = _load_apps_registry()
                if "daily_digest" in reg:
                    reg["daily_digest"]["last_run"] = datetime.now(timezone.utc).isoformat()
                    _save_apps_registry(reg)
                _inc_run_count("daily_digest")

                stats = result.get("stats", {})
                _push_notification(
                    title="🎯 每日私享会已更新",
                    content=(
                        f"分析 {stats.get('filtered_count', 0)} 条浏览记录，"
                        f"搜索 {stats.get('search_results', 0)} 条推荐内容。"
                    ),
                    level="info",
                )

            with _digest_task_lock:
                _digest_task_status.update({
                    "status": "done" if result["status"] == "ok" else "error",
                    "result": result,
                })
        except Exception as exc:
            print(f"[daily_digest] run error: {exc}")
            with _digest_task_lock:
                _digest_task_status.update({"status": "error", "result": {"message": str(exc)}})

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "running"})


@flask_app.route("/api/apps/daily_digest/status")
def api_digest_status():
    with _digest_task_lock:
        return jsonify(dict(_digest_task_status) if _digest_task_status else {"status": "idle"})


@flask_app.route("/api/apps/daily_digest/reports")
def api_digest_reports():
    from apps.daily_digest import list_reports
    return jsonify(list_reports())


@flask_app.route("/api/apps/daily_digest/report/<date_str>")
def api_digest_report(date_str):
    from apps.daily_digest import load_report
    report = load_report(date_str)
    if not report:
        return jsonify({"error": "报告不存在"}), 404
    return jsonify(report)


@flask_app.route("/api/apps/daily_digest/browsers")
def api_digest_browsers():
    from apps.daily_digest import find_browser_history_paths
    return jsonify(find_browser_history_paths())


@flask_app.route("/api/apps/daily_digest/preview")
def api_digest_preview():
    """Quick preview: read history + extract interests without generating full report.

    Uses LLM analysis when model config is available, falls back to rule-based.
    """
    registry = _load_apps_registry()
    if "daily_digest" not in registry:
        return jsonify({"error": "每日私享会未安装"}), 400

    from apps.daily_digest import (
        read_browser_history, filter_history,
        extract_keywords, classify_interests,
        llm_analyze_interests, read_chat_history,
    )
    app_config = registry["daily_digest"].get("config", {})
    browser = app_config.get("browser", "auto")
    hours = app_config.get("history_hours", 24)

    raw = read_browser_history(hours=hours, browser=browser)
    filtered = filter_history(raw)

    chat_hours = app_config.get("chat_hours", 72)
    chat_sessions = read_chat_history(hours=chat_hours)
    chat_msg_count = sum(len(s.get("messages", [])) for s in chat_sessions)

    model_cfg = _get_model_config()
    model = model_cfg.get("model")
    api_key = model_cfg.get("api_key")
    api_base = model_cfg.get("api_base")
    analysis_method = "rule"

    if model and api_key:
        llm_result = llm_analyze_interests(
            filtered, model, api_key, api_base,
            chat_sessions=chat_sessions,
        )
        if llm_result:
            analysis_method = "llm"
            interests = {
                cat: [{"keyword": kw, "count": 0} for kw in entry["interests"]]
                for cat, entry in llm_result.items()
            }
            queries = {
                cat: entry["queries"]
                for cat, entry in llm_result.items()
            }
            return jsonify({
                "raw_count": len(raw),
                "filtered_count": len(filtered),
                "chat_sessions": len(chat_sessions),
                "chat_messages": chat_msg_count,
                "keyword_count": sum(len(v) for v in interests.values()),
                "interests": interests,
                "queries": queries,
                "method": analysis_method,
            })

    keywords = extract_keywords(filtered)
    categories = classify_interests(keywords)
    interests = {
        cat: [{"keyword": i["keyword"], "count": i["count"]} for i in items[:10]]
        for cat, items in categories.items()
    }
    return jsonify({
        "raw_count": len(raw),
        "filtered_count": len(filtered),
        "chat_sessions": len(chat_sessions),
        "chat_messages": chat_msg_count,
        "keyword_count": len(keywords),
        "interests": interests,
        "method": analysis_method,
    })


@flask_app.route("/api/apps/daily_digest/explore", methods=["POST"])
def api_digest_explore():
    """Build an explore prompt for a specific content item in the digest."""
    body = request.json or {}
    item = body.get("item")
    date_str = body.get("date")
    if not item or not isinstance(item, dict):
        return jsonify({"error": "item is required"}), 400

    interests = None
    if date_str:
        from apps.daily_digest import load_report
        report = load_report(date_str)
        if report:
            interests = report.get("interests")

    from apps.daily_digest import build_explore_prompt
    prompt = build_explore_prompt(item, interests=interests)
    return jsonify({"prompt": prompt})


# ---------------------------------------------------------------------------
# Routes — Unified Reports
# ---------------------------------------------------------------------------

def _html_to_summary(html: str, max_len: int = 60) -> str:
    """Extract plain-text summary from HTML content."""
    import re as _re
    text = _re.sub(r"<[^>]+>", " ", html)
    text = _re.sub(r"\s+", " ", text).strip()
    for prefix in ("📅", "📧", "🎯"):
        text = text.lstrip(prefix).strip()
    text = _re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", text).strip()
    for skip in ("每日私享会", "每日资讯", "Daily"):
        if text.startswith(skip):
            text = text[len(skip):].strip()
    return text[:max_len] if text else ""


@flask_app.route("/api/reports")
def api_all_reports():
    """Aggregate reports from all apps into a single list."""
    result: list[dict] = []

    # Daily Digest
    try:
        from apps.daily_digest import list_reports as digest_list, load_report as digest_load
        for r in digest_list(limit=60):
            date = r.get("date", "")
            summary = ""
            try:
                rpt = digest_load(date)
                if rpt and rpt.get("content"):
                    summary = _html_to_summary(rpt["content"])
            except Exception:
                pass
            result.append({
                "app_id": "daily_digest",
                "app_name": "每日私享会",
                "app_icon": "🎯",
                "date": date,
                "generated_at": r.get("generated_at", ""),
                "key": date,
                "type": "digest",
                "read": True,
                "summary": summary,
            })
    except Exception:
        pass

    # Email Summary
    try:
        from apps.email_summary import list_reports as email_list, get_report as email_get
        for r in email_list():
            date = r.get("date", "")
            summary = ""
            email_count = r.get("email_count", 0)
            if email_count:
                summary = f"{email_count} 封邮件简报"
            else:
                try:
                    rpt = email_get(date)
                    if rpt and rpt.get("content"):
                        summary = _html_to_summary(rpt["content"])
                except Exception:
                    pass
            result.append({
                "app_id": "email_summary",
                "app_name": "邮件简报",
                "app_icon": "📧",
                "date": date,
                "generated_at": r.get("generated_at", ""),
                "key": date,
                "type": "email",
                "read": True,
                "summary": summary,
            })
    except Exception:
        pass

    # Custom Apps
    try:
        from apps.custom_app import (
            list_apps as _list_custom, list_reports as custom_list,
            get_report as custom_get,
        )
        for app in _list_custom():
            app_id = app["id"]
            app_name = app.get("name", app_id)
            app_icon = app.get("icon", "🧩")
            for r in custom_list(app_id):
                key = r.get("key", "")
                summary = ""
                try:
                    rpt = custom_get(app_id, key)
                    if rpt and rpt.get("content"):
                        summary = _html_to_summary(rpt["content"])
                except Exception:
                    pass
                result.append({
                    "app_id": app_id,
                    "app_name": app_name,
                    "app_icon": app_icon,
                    "date": r.get("date", ""),
                    "generated_at": r.get("generated_at", ""),
                    "key": key,
                    "type": r.get("type", "run"),
                    "read": r.get("read", True),
                    "summary": summary,
                })
    except Exception:
        pass

    result.sort(key=lambda x: x.get("generated_at") or x.get("date") or "", reverse=True)
    return jsonify(result)


@flask_app.route("/api/reports/mark_all_read", methods=["POST"])
def api_mark_all_reports_read():
    try:
        from apps.custom_app import list_apps as _list_custom, list_reports as custom_list, mark_report_read
        for app in _list_custom():
            for r in custom_list(app["id"]):
                if not r.get("read"):
                    mark_report_read(app["id"], r.get("key", ""))
    except Exception:
        pass
    return jsonify({"ok": True})


@flask_app.route("/api/reports/<app_id>/<path:key>", methods=["DELETE"])
def api_delete_report(app_id, key):
    ok = False
    if app_id == "daily_digest":
        from apps.daily_digest import delete_report
        ok = delete_report(key)
    elif app_id == "email_summary":
        from apps.email_summary import delete_report
        ok = delete_report(key)
    else:
        from apps.custom_app import delete_report
        ok = delete_report(app_id, key)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@flask_app.route("/api/reports/<app_id>/<path:key>")
def api_report_content(app_id, key):
    """Fetch a single report's full content for inline display."""
    if app_id == "daily_digest":
        from apps.daily_digest import load_report
        report = load_report(key)
        if not report:
            return jsonify({"error": "not found"}), 404
        return jsonify(report)
    elif app_id == "email_summary":
        from apps.email_summary import get_report
        report = get_report(key)
        if not report:
            return jsonify({"error": "not found"}), 404
        return jsonify(report)
    else:
        from apps.custom_app import get_report, mark_report_read
        report = get_report(app_id, key)
        if not report:
            return jsonify({"error": "not found"}), 404
        mark_report_read(app_id, key)
        return jsonify(report)


# ---------------------------------------------------------------------------
# Routes — Web Monitor
# ---------------------------------------------------------------------------

_monitor_task_lock = threading.Lock()
_monitor_task_status: dict = {}


@flask_app.route("/api/apps/web_monitor/sites")
def api_monitor_sites():
    from apps.web_monitor import list_sites
    return jsonify(list_sites())


@flask_app.route("/api/apps/web_monitor/sites", methods=["POST"])
def api_monitor_add_site():
    body = request.json or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL 不能为空"}), 400
    from apps.web_monitor import add_site
    site = add_site(url, name=body.get("name", ""), mode=body.get("mode", "hash"))
    return jsonify(site)


@flask_app.route("/api/apps/web_monitor/sites/<site_id>", methods=["DELETE"])
def api_monitor_remove_site(site_id):
    from apps.web_monitor import remove_site
    if remove_site(site_id):
        return jsonify({"success": True})
    return jsonify({"error": "站点不存在"}), 404


@flask_app.route("/api/apps/web_monitor/check", methods=["POST"])
def api_monitor_check_all():
    """Trigger a check on all enabled sites (background)."""
    with _monitor_task_lock:
        if _monitor_task_status.get("status") == "running":
            return jsonify({"error": "正在检查中"}), 409
        _monitor_task_status.update({"status": "running", "progress": ""})

    def _run():
        try:
            from apps.web_monitor import check_all_sites
            model_cfg = _get_model_config()

            def _progress(msg):
                with _monitor_task_lock:
                    _monitor_task_status["progress"] = msg

            results = check_all_sites(
                model=model_cfg.get("model"),
                api_key=model_cfg.get("api_key"),
                api_base=model_cfg.get("api_base"),
                progress_cb=_progress,
            )
            changed = [r for r in results if r.get("changed")]
            if changed:
                _push_notification(
                    title="🔍 网页变化通知",
                    content=f"检测到 {len(changed)} 个网页有更新",
                    level="info",
                )
            reg = _load_apps_registry()
            if "web_monitor" in reg:
                reg["web_monitor"]["last_run"] = datetime.now(timezone.utc).isoformat()
                _save_apps_registry(reg)
            with _monitor_task_lock:
                _monitor_task_status.update({"status": "done", "results": results})
        except Exception as exc:
            print(f"[web_monitor] check error: {exc}")
            with _monitor_task_lock:
                _monitor_task_status.update({"status": "error", "error": str(exc)})

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "running"})


@flask_app.route("/api/apps/web_monitor/check/<site_id>", methods=["POST"])
def api_monitor_check_one(site_id):
    from apps.web_monitor import check_site
    model_cfg = _get_model_config()
    result = check_site(
        site_id,
        model=model_cfg.get("model"),
        api_key=model_cfg.get("api_key"),
        api_base=model_cfg.get("api_base"),
    )
    return jsonify(result)


@flask_app.route("/api/apps/web_monitor/status")
def api_monitor_status():
    with _monitor_task_lock:
        return jsonify(dict(_monitor_task_status) if _monitor_task_status else {"status": "idle"})


@flask_app.route("/api/apps/web_monitor/history/<site_id>")
def api_monitor_history(site_id):
    from apps.web_monitor import get_history
    return jsonify(get_history(site_id))


# ---------------------------------------------------------------------------
# Routes — Email Summary
# ---------------------------------------------------------------------------

@flask_app.route("/api/apps/email_summary/run", methods=["POST"])
def api_email_run():
    registry = _load_apps_registry()
    if "email_summary" not in registry:
        return jsonify({"error": "邮件简报应用未安装"}), 400
    from apps.email_summary import run_email_summary
    app_config = registry["email_summary"].get("config", {})
    if not app_config.get("imap_host") or not app_config.get("imap_user"):
        return jsonify({"error": "请先配置 IMAP 邮箱信息"}), 400
    model_cfg = _get_model_config()

    def _run():
        result = run_email_summary(app_config, model_config=model_cfg)
        if result.get("success"):
            reg = _load_apps_registry()
            if "email_summary" in reg:
                reg["email_summary"]["last_run"] = datetime.now(timezone.utc).isoformat()
                _save_apps_registry(reg)
            _push_notification(
                title="📧 邮件简报已生成",
                content=f"汇总了 {result.get('email_count', 0)} 封邮件",
                level="info",
            )

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "running"})


@flask_app.route("/api/apps/email_summary/status")
def api_email_status():
    from apps.email_summary import get_status
    return jsonify(get_status())


@flask_app.route("/api/apps/email_summary/reports")
def api_email_reports():
    from apps.email_summary import list_reports
    return jsonify(list_reports())


@flask_app.route("/api/apps/email_summary/report/<date_str>")
def api_email_report(date_str):
    from apps.email_summary import get_report
    report = get_report(date_str)
    if not report:
        return jsonify({"error": "报告不存在"}), 404
    return jsonify(report)


@flask_app.route("/api/apps/email_summary/test", methods=["POST"])
def api_email_test():
    registry = _load_apps_registry()
    if "email_summary" not in registry:
        return jsonify({"error": "邮件简报应用未安装"}), 400
    from apps.email_summary import test_connection
    app_config = registry["email_summary"].get("config", {})
    return jsonify(test_connection(app_config))


@flask_app.route("/api/apps/email_summary/presets")
def api_email_presets():
    from apps.email_summary import IMAP_PRESETS
    return jsonify(IMAP_PRESETS)


# ---------------------------------------------------------------------------
# Routes — Focus Timer
# ---------------------------------------------------------------------------

@flask_app.route("/api/apps/focus_timer/sessions", methods=["POST"])
def api_focus_save():
    body = request.json or {}
    from apps.focus_timer import save_session
    entry = save_session(body)
    return jsonify(entry)


@flask_app.route("/api/apps/focus_timer/sessions")
def api_focus_sessions():
    days = request.args.get("days", 7, type=int)
    tag = request.args.get("tag", "")
    from apps.focus_timer import list_sessions
    return jsonify(list_sessions(days=days, tag=tag))


@flask_app.route("/api/apps/focus_timer/sessions/<session_id>", methods=["DELETE"])
def api_focus_delete(session_id):
    from apps.focus_timer import delete_session
    if delete_session(session_id):
        return jsonify({"success": True})
    return jsonify({"error": "会话不存在"}), 404


@flask_app.route("/api/apps/focus_timer/stats")
def api_focus_stats():
    days = request.args.get("days", 30, type=int)
    from apps.focus_timer import get_stats
    return jsonify(get_stats(days=days))


@flask_app.route("/api/apps/focus_timer/tags")
def api_focus_tags():
    from apps.focus_timer import get_tags
    return jsonify(get_tags())


# ---------------------------------------------------------------------------
# Routes — Custom Apps
# ---------------------------------------------------------------------------

@flask_app.route("/api/apps/custom", methods=["GET"])
def api_custom_list():
    from apps.custom_app import list_apps
    return jsonify(list_apps())


@flask_app.route("/api/apps/custom", methods=["POST"])
def api_custom_create():
    body = request.json or {}
    name = body.get("name", "").strip()
    prompt_template = body.get("prompt_template", "").strip()
    if not name or not prompt_template:
        return jsonify({"error": "名称和任务描述不能为空"}), 400
    from apps.custom_app import create_app
    app = create_app(
        name=name,
        prompt_template=prompt_template,
        icon=body.get("icon", "🤖"),
        output_format=body.get("output_format", "text"),
        schedule=body.get("schedule"),
        summary=body.get("summary"),
    )
    return jsonify(app)


@flask_app.route("/api/apps/custom/meta", methods=["GET"])
def api_custom_meta():
    from apps.custom_app import OUTPUT_FORMATS, SCHEDULE_MODES
    return jsonify({
        "output_formats": OUTPUT_FORMATS,
        "schedule_modes": SCHEDULE_MODES,
    })


@flask_app.route("/api/apps/custom/unread")
def api_custom_unread():
    from apps.custom_app import all_unread_counts
    return jsonify(all_unread_counts())


@flask_app.route("/api/apps/custom/<app_id>", methods=["GET"])
def api_custom_get(app_id):
    from apps.custom_app import get_app
    app = get_app(app_id)
    if not app:
        return jsonify({"error": "应用不存在"}), 404
    return jsonify(app)


@flask_app.route("/api/apps/custom/<app_id>", methods=["PUT"])
def api_custom_update(app_id):
    body = request.json or {}
    from apps.custom_app import update_app
    app = update_app(app_id, **body)
    if not app:
        return jsonify({"error": "应用不存在"}), 404
    return jsonify(app)


@flask_app.route("/api/apps/custom/<app_id>", methods=["DELETE"])
def api_custom_delete(app_id):
    from apps.custom_app import delete_app
    if delete_app(app_id):
        return jsonify({"success": True})
    return jsonify({"error": "应用不存在"}), 404


@flask_app.route("/api/apps/custom/<app_id>/run", methods=["POST"])
def api_custom_run(app_id):
    """Run a custom app — SSE stream. Supports multiple param groups."""
    from apps.custom_app import get_app, build_message, save_report, set_last_run

    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400

    app = get_app(app_id)
    if not app:
        return jsonify({"error": "应用不存在"}), 404

    body = request.json or {}
    param_groups = body.get("param_groups", None)
    if param_groups is None:
        single = body.get("params", {})
        for p in app.get("parameters", []):
            if p["name"] not in single:
                single[p["name"]] = p.get("default", "")
        param_groups = [single]

    q: queue.Queue[str] = queue.Queue()

    import uuid as _uuid

    async def _process():
        try:
            agent = _get_or_create_agent()

            async def on_progress(content):
                q.put(json.dumps({"type": "progress", "content": content},
                                 ensure_ascii=False))

            need_mcp = bool(agent._mcp_servers)
            has_mcp = any(n.startswith("mcp_") for n in agent.tools._tools)
            if need_mcp and not has_mcp:
                await _connect_mcp_safe(agent, progress_cb=on_progress)

            total = len(param_groups)
            for idx, pv in enumerate(param_groups):
                label = ", ".join(str(v) for v in pv.values()) if pv else ""
                if total > 1:
                    q.put(json.dumps({"type": "progress",
                                      "content": f"[{idx+1}/{total}] {label}"},
                                     ensure_ascii=False))

                message = build_message(app, pv)
                session_key = f"capp_{_uuid.uuid4().hex[:12]}"

                response = await agent.process_direct(
                    message, session_key=session_key, on_progress=on_progress,
                )

                save_report(app_id, content=response or "", params_used=pv)

                if total > 1:
                    q.put(json.dumps({"type": "progress",
                                      "content": f"✅ [{idx+1}/{total}] {label}"},
                                     ensure_ascii=False))

            set_last_run(app_id)
            _inc_run_count(app_id)
            last_resp = ""
            q.put(json.dumps({"type": "done", "content": last_resp},
                             ensure_ascii=False))
        except Exception as exc:
            q.put(json.dumps({"type": "error", "content": str(exc)},
                             ensure_ascii=False))

    _ensure_loop()
    asyncio.run_coroutine_threadsafe(_process(), _async_loop)

    def generate():
        while True:
            try:
                data = q.get(timeout=300)
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f'data: {json.dumps({"type":"error","content":"请求超时"})}\n\n'
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@flask_app.route("/api/apps/custom/<app_id>/reports")
def api_custom_reports(app_id):
    from apps.custom_app import list_reports
    return jsonify(list_reports(app_id))


@flask_app.route("/api/apps/custom/<app_id>/report/<path:key>")
def api_custom_report(app_id, key):
    from apps.custom_app import get_report, mark_report_read
    report = get_report(app_id, key)
    if not report:
        return jsonify({"error": "报告不存在"}), 404
    mark_report_read(app_id, key)
    return jsonify(report)


@flask_app.route("/api/apps/custom/<app_id>/report/<path:key>", methods=["DELETE"])
def api_custom_report_delete(app_id, key):
    from apps.custom_app import delete_report
    if delete_report(app_id, key):
        return jsonify({"success": True})
    return jsonify({"error": "报告不存在"}), 404


@flask_app.route("/api/apps/custom/<app_id>/summary", methods=["POST"])
def api_custom_summary(app_id):
    """Generate a summary from historical reports — direct LLM call, SSE stream."""
    from apps.custom_app import get_app, build_summary_prompt, save_report, mark_triggered

    app = get_app(app_id)
    if not app:
        return jsonify({"error": "应用不存在"}), 404

    prompt = build_summary_prompt(app)
    if not prompt:
        return jsonify({"error": "无历史报告可用于总结"}), 400

    mcfg = _get_model_config()
    if not mcfg.get("model") or not mcfg.get("api_key"):
        return jsonify({"error": "未配置 LLM（请先在设置中填写 API Key）"}), 400

    q: queue.Queue[str] = queue.Queue()

    def _run():
        try:
            q.put(json.dumps({"type": "progress",
                              "content": "正在调用 LLM 生成总结…"},
                             ensure_ascii=False))
            import os, litellm
            os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

            _KNOWN = ("openai/", "azure/", "anthropic/", "cohere/",
                      "huggingface/", "ollama/", "deepseek/", "groq/",
                      "together_ai/", "openrouter/", "gemini/", "mistral/")
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
            if _usage:
                from apps.llm_utils import record_tokens
                record_tokens(
                    prompt_tokens=getattr(_usage, "prompt_tokens", 0),
                    completion_tokens=getattr(_usage, "completion_tokens", 0),
                )
            content = resp.choices[0].message.content or ""

            save_report(app_id, content=content, params_used={},
                        report_type="summary")
            mark_triggered(app_id, "summary")

            q.put(json.dumps({"type": "done", "content": content},
                             ensure_ascii=False))
        except Exception as exc:
            q.put(json.dumps({"type": "error", "content": str(exc)},
                             ensure_ascii=False))

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
                yield f'data: {json.dumps({"type":"error","content":"请求超时"})}\n\n'
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Apps scheduler (background timer)
# ---------------------------------------------------------------------------

_app_scheduler_timer = None


def _start_app_scheduler():
    """Start a background timer that checks scheduled apps every 60 seconds."""
    global _app_scheduler_timer

    def _tick():
        global _app_scheduler_timer
        try:
            _check_scheduled_apps()
        except Exception as exc:
            print(f"[app_scheduler] tick error: {exc}")
        _app_scheduler_timer = threading.Timer(60, _tick)
        _app_scheduler_timer.daemon = True
        _app_scheduler_timer.start()

    _app_scheduler_timer = threading.Timer(60, _tick)
    _app_scheduler_timer.daemon = True
    _app_scheduler_timer.start()
    print("[app_scheduler] started")


def _check_scheduled_apps():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_minute = now.minute
    today = now.strftime("%Y-%m-%d")

    registry = _load_apps_registry()
    for app_id, app in registry.items():
        if not app.get("enabled"):
            continue
        config = app.get("config", {})

        # --- Daily Digest: schedule_time based ---
        if app_id == "daily_digest":
            schedule_time = config.get("schedule_time")
            if not schedule_time or current_time != schedule_time:
                continue
            last_run = app.get("last_run", "")
            if last_run and last_run.startswith(today):
                continue
            with _digest_task_lock:
                if _digest_task_status.get("status") == "running":
                    continue
            print(f"[app_scheduler] triggering daily_digest at {current_time}")
            try:
                from apps.daily_digest import run_daily_digest
                model_cfg = _get_model_config()
                merged = {**config, **model_cfg}
                result = run_daily_digest(merged)
                if result["status"] == "ok":
                    registry[app_id]["last_run"] = datetime.now(timezone.utc).isoformat()
                    _save_apps_registry(registry)
                    stats = result.get("stats", {})
                    _push_notification(
                        title="🎯 每日私享会已更新",
                        content=(
                            f"分析 {stats.get('filtered_count', 0)} 条浏览记录，"
                            f"搜索 {stats.get('search_results', 0)} 条推荐内容。"
                        ),
                        level="info",
                    )
            except Exception as exc:
                print(f"[app_scheduler] daily_digest error: {exc}")

        # --- Web Monitor: interval based ---
        elif app_id == "web_monitor":
            if not config.get("schedule_enabled", True):
                continue
            interval = config.get("check_interval_minutes", 30)
            if current_minute % interval != 0:
                continue
            with _monitor_task_lock:
                if _monitor_task_status.get("status") == "running":
                    continue
            print(f"[app_scheduler] triggering web_monitor check")
            try:
                from apps.web_monitor import check_all_sites
                model_cfg = _get_model_config()
                results = check_all_sites(
                    model=model_cfg.get("model"),
                    api_key=model_cfg.get("api_key"),
                    api_base=model_cfg.get("api_base"),
                )
                changed = [r for r in results if r.get("changed")]
                if changed:
                    _push_notification(
                        title="🔍 网页变化通知",
                        content=f"检测到 {len(changed)} 个网页有更新",
                        level="info",
                    )
                registry[app_id]["last_run"] = datetime.now(timezone.utc).isoformat()
                _save_apps_registry(registry)
            except Exception as exc:
                print(f"[app_scheduler] web_monitor error: {exc}")

        # --- Email Summary: schedule_time based ---
        elif app_id == "email_summary":
            schedule_time = config.get("schedule_time")
            if not schedule_time or current_time != schedule_time:
                continue
            last_run = app.get("last_run", "")
            if last_run and last_run.startswith(today):
                continue
            if not config.get("imap_host") or not config.get("imap_user"):
                continue
            print(f"[app_scheduler] triggering email_summary at {current_time}")
            try:
                from apps.email_summary import run_email_summary
                model_cfg = _get_model_config()
                result = run_email_summary(config, model_config=model_cfg)
                if result.get("success"):
                    registry[app_id]["last_run"] = datetime.now(timezone.utc).isoformat()
                    _save_apps_registry(registry)
                    _push_notification(
                        title="📧 邮件简报已生成",
                        content=f"汇总了 {result.get('email_count', 0)} 封邮件",
                        level="info",
                    )
            except Exception as exc:
                print(f"[app_scheduler] email_summary error: {exc}")


    # --- Custom apps ---
    from apps.custom_app import (
        list_apps as _list_custom, build_message, build_summary_prompt,
        save_report, set_last_run, should_trigger, mark_triggered,
    )
    for capp in _list_custom():
        capp_id = capp["id"]

        # Main task schedule
        sched = capp.get("schedule", {})
        if should_trigger(sched, now):
            print(f"[app_scheduler] triggering custom app '{capp['name']}' at {current_time}")
            try:
                defaults = {p["name"]: p.get("default", "") for p in capp.get("parameters", [])}
                groups = capp.get("param_groups")
                if not groups or not isinstance(groups, list):
                    groups = [capp.get("param_values", defaults)]
                for pv in groups:
                    message = build_message(capp, pv)
                    import uuid as _uuid_sched
                    session_key = f"capp_{_uuid_sched.uuid4().hex[:12]}"
                    result = _run_agent_with_prompt(message, session_key=session_key)
                    save_report(capp_id, content=result["content"], params_used=pv)
                set_last_run(capp_id)
                _inc_run_count(capp_id)
                mark_triggered(capp_id, "schedule")
                _push_notification(
                    title=f"{capp.get('icon', '🤖')} {capp['name']}",
                    content=f"定时执行完成（{len(groups)} 组）",
                    level="info",
                )
            except Exception as exc:
                print(f"[app_scheduler] custom app '{capp['name']}' error: {exc}")

        # Summary schedule — direct LLM call (no agent)
        summary_cfg = capp.get("summary", {})
        summary_sched = summary_cfg.get("schedule", {})
        if summary_cfg.get("enabled") and should_trigger(summary_sched, now):
            print(f"[app_scheduler] triggering summary for '{capp['name']}' at {current_time}")
            try:
                prompt = build_summary_prompt(capp)
                if prompt:
                    mcfg = _get_model_config()
                    if mcfg.get("model") and mcfg.get("api_key"):
                        import os as _os, litellm as _lt
                        _os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
                        _KNOWN = ("openai/", "azure/", "anthropic/", "cohere/",
                                  "huggingface/", "ollama/", "deepseek/", "groq/",
                                  "together_ai/", "openrouter/", "gemini/", "mistral/")
                        _m = mcfg["model"]
                        if not any(_m.startswith(p) for p in _KNOWN) and mcfg.get("api_base"):
                            _m = f"openai/{_m}"
                        resp = _lt.completion(
                            model=_m,
                            messages=[{"role": "user", "content": prompt}],
                            api_key=mcfg["api_key"],
                            api_base=mcfg.get("api_base"),
                            temperature=0.5, max_tokens=4096,
                        )
                        _u = getattr(resp, "usage", None)
                        if _u:
                            from apps.llm_utils import record_tokens as _rec
                            _rec(
                                prompt_tokens=getattr(_u, "prompt_tokens", 0),
                                completion_tokens=getattr(_u, "completion_tokens", 0),
                            )
                        content = resp.choices[0].message.content or ""
                        save_report(capp_id, content=content,
                                    params_used={}, report_type="summary")
                        mark_triggered(capp_id, "summary")
                        _push_notification(
                            title=f"📊 {capp['name']} 总结",
                            content="总结报告已生成",
                            level="info",
                        )
            except Exception as exc:
                print(f"[app_scheduler] summary '{capp['name']}' error: {exc}")


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
        return jsonify({"error": "rating 必须为 like 或 dislike"}), 400

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
                result.append({
                    "ts": obj.get("ts", ""),
                    "prompt": (obj.get("prompt", "") or "")[:80],
                    "comment": obj.get("comment", ""),
                })
            except Exception:
                pass
        result.reverse()
        return result

    return jsonify({
        "positive_count": _count(pos_file),
        "negative_count": _count(neg_file),
        "recent_positive": _recent(pos_file),
        "recent_negative": _recent(neg_file),
    })


# ---------------------------------------------------------------------------
# Routes — gateway
# ---------------------------------------------------------------------------

def _find_nanobot_cmd() -> list[str]:
    """Locate the nanobot executable; fall back to python -c wrapper."""
    exe = shutil.which("nanobot")
    if exe:
        return [exe, "gateway"]
    return [
        sys.executable, "-c",
        "import sys; sys.argv=['nanobot','gateway']; from nanobot.cli.commands import app; app()",
    ]


def _kill_process_tree(pid: int) -> None:
    """Force-kill a process and all its children (Windows-safe)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def _cleanup_gateway() -> None:
    """If the gateway process has exited, reset the global handle."""
    global _gateway_process
    if _gateway_process is not None and _gateway_process.poll() is not None:
        _gateway_process = None


@flask_app.route("/api/gateway/start", methods=["POST"])
def api_gateway_start():
    global _gateway_process
    _cleanup_gateway()
    if _gateway_process is not None:
        return jsonify({"error": "网关已在运行"}), 400
    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        cmd = _find_nanobot_cmd()
        _gateway_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return jsonify({"success": True, "pid": _gateway_process.pid})
    except Exception as e:
        _gateway_process = None
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/gateway/stop", methods=["POST"])
def api_gateway_stop():
    global _gateway_process
    if _gateway_process is None:
        return jsonify({"error": "网关未运行"}), 400
    pid = _gateway_process.pid
    _kill_process_tree(pid)
    try:
        _gateway_process.wait(timeout=5)
    except Exception:
        pass
    _gateway_process = None
    return jsonify({"success": True})


@flask_app.route("/api/gateway/status")
def api_gateway_status():
    _cleanup_gateway()
    running = _gateway_process is not None
    return jsonify({
        "running": running,
        "pid": _gateway_process.pid if running else None,
    })


@flask_app.route("/api/gateway/logs")
def api_gateway_logs():
    if not (_gateway_process and _gateway_process.stdout):
        return jsonify({"logs": ""})
    try:
        lines = []
        while _gateway_process.stdout.readable():
            line = _gateway_process.stdout.readline()
            if not line:
                break
            lines.append(line)
            if len(lines) > 100:
                break
        return jsonify({"logs": "".join(lines)})
    except Exception:
        return jsonify({"logs": ""})


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
            pass
        _gateway_process = None

    # 2. Close MCP connections & async loop
    if _agent is not None and getattr(_agent, '_mcp_stack', None) is not None:
        if _async_loop is not None and _async_loop.is_running():
            async def _close_mcp():
                try:
                    await _agent._mcp_stack.aclose()
                except Exception:
                    pass
            try:
                f = asyncio.run_coroutine_threadsafe(_close_mcp(), _async_loop)
                f.result(timeout=5)
            except Exception:
                pass
    _agent = None

    if _async_loop is not None and _async_loop.is_running():
        _async_loop.call_soon_threadsafe(_async_loop.stop)
    _async_loop = None

    print("[MyxAI Desk] Shutdown complete.", flush=True)


import atexit
atexit.register(_shutdown)


# ---------------------------------------------------------------------------
# Entry‑point
# ---------------------------------------------------------------------------

def main():
    _start_app_scheduler()

    try:
        import webview
    except ImportError:
        print("pywebview 未安装，将在浏览器中打开。")
        print("安装方法：pip install pywebview")
        import webbrowser
        port = 19280
        threading.Thread(
            target=lambda: flask_app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
            daemon=True,
        ).start()
        time.sleep(1)
        webbrowser.open(f"http://127.0.0.1:{port}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        _shutdown()
        return

    port = 19280
    threading.Thread(
        target=lambda: flask_app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    ).start()

    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/check", timeout=1)
            break
        except Exception:
            time.sleep(0.05)

    window = webview.create_window(
        "MyxAI Desk",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
        min_size=(960, 640),
        maximized=True,
    )

    def _grant_media_permissions(win):
        """Auto-allow microphone/camera permissions in WebView2."""
        win.events.loaded.wait(30)
        try:
            from webview.platforms.winforms import BrowserView
            from System import Func, Type

            bv = BrowserView.instances.get(win.uid)
            if not bv or not getattr(bv, 'browser', None):
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
            print(f"[webview] auto-allow permissions failed: {e}")

    webview.start(func=_grant_media_permissions, args=[window])
    _shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
