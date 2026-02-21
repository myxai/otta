"""nanobot Desktop — Windows 桌面可视化客户端."""

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
_session_counter = 0
_gateway_process: subprocess.Popen | None = None
_cron_service = None

_mcp_log: list[dict] = []
_mcp_log_lock = threading.Lock()

_notifications: list[dict] = []
_notifications_lock = threading.Lock()


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
            "4. Keep responses concise and natural."
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
        exec_mode = _is_exec_mode(msg.content)
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
        agent_ref = _agent

        async def _on_cron_job(job):
            """Cron callback: process job through agent and push notification."""
            print(f"[cron] on_job callback: '{job.name}' ({job.id}), msg={job.payload.message[:60]}")
            try:
                response = await agent_ref.process_direct(
                    job.payload.message,
                    session_key=f"cron:{job.id}",
                    channel=job.payload.channel or "cli",
                    chat_id=job.payload.to or "cron",
                )
                print(f"[cron] on_job response: {(response or '')[:80]}")
                _push_notification(
                    title=job.name,
                    content=response or job.payload.message,
                    level="info",
                )
                return response
            except Exception as e:
                print(f"[cron] on_job error: {e}")
                _push_notification(
                    title=job.name,
                    content=f"执行失败: {e}",
                    level="error",
                )
                raise

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
    session_id = (request.json or {}).get("session_id", f"desktop:{_session_counter}")
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
    return jsonify({"success": True, "session_id": f"desktop:{_session_counter}"})


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
    global _gateway_process, _agent, _async_loop, _cron_service

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

    print("[nanobot Desktop] Shutdown complete.", flush=True)


import atexit
atexit.register(_shutdown)


# ---------------------------------------------------------------------------
# Entry‑point
# ---------------------------------------------------------------------------

def main():
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
        "nanobot Desktop",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
        min_size=(960, 640),
    )
    webview.start()
    _shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
