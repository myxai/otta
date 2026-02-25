"""MyxAI Desk — 桌面可视化客户端.

This file serves as the backward-compatible entry point.  New modules live
under ``myxai_desk/`` and are progressively taking over responsibility.
"""

import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

# Import the new package so its subsystems are initialised on startup.
import myxai_desk  # noqa: F401
from myxai_desk.core.storage import paths as _paths  # noqa: F401

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

_last_usage: dict[str, dict] = {}
_last_usage_lock = threading.Lock()

_last_turn_audit: dict[str, dict] = {}
_last_turn_audit_lock = threading.Lock()


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
            "[Earlier]\n" + "\n".join(summaries[-4:])
        )
        return [{"role": "assistant", "content": summary_text}] + recent
    return recent


def _tool_to_capability(tool_name: str, arguments: dict) -> tuple[str, str]:
    """Map a nanobot tool name to a (capability, operation) pair for policy."""
    tn = tool_name.lower()
    if any(k in tn for k in ("file", "read_file", "write_file", "list_dir",
                              "create_file", "move_file", "copy_file")):
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

    if any(k in tn for k in ("exec", "run", "shell", "command", "bash",
                              "powershell", "terminal", "subprocess")):
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
            post_execution_audit, post_execution_undo,
        )
        post_execution_audit(pa.capability, pa.op, pa.tool_args, result, None)
        post_execution_undo(pa.capability, pa.op, pa.tool_args, result)
        print(f"[policy] Confirmed via chat → executed {pa.tool_name}")
        return f"工具: {pa.tool_name}\n参数: {str(pa.tool_args)[:300]}\n结果: {str(result)[:2000]}"
    except Exception as exc:
        print(f"[policy] Pending execution error: {exc}")
        return f"执行失败: {exc}"


_TOOLS_FS = {"exec", "read_file", "list_dir", "write_file", "edit_file"}
_TOOLS_SEARCH = {"web_search", "web_fetch"}
_TOOLS_SCHEDULE = {"cron"}
_TOOLS_COMM = {"message", "spawn"}

_TRIGGER_SEARCH = _re.compile(
    r"搜索|查找|查询|搜一下|谷歌|百度|google|search|bing|"
    r"新闻|资讯|最新|天气|汇率|股价",
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
    user_msg: str, all_defs: list[dict],
) -> list[dict]:
    """Select only relevant tools based on user intent to minimize tokens."""
    needed = set(_TOOLS_FS)

    if _TRIGGER_SEARCH.search(user_msg):
        needed |= _TOOLS_SEARCH
    if _TRIGGER_SCHEDULE.search(user_msg):
        needed |= _TOOLS_SCHEDULE
    if _TRIGGER_COMM.search(user_msg):
        needed |= _TOOLS_COMM

    include_mcp = bool(_TRIGGER_MCP.search(user_msg))

    return [
        d for d in all_defs
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

        from myxai_desk.core.policy.modes import get_current_mode, SecurityMode
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
                "File deletion: use exec with `del \"path\"` (Win) or `rm \"path\"` (Linux). "
                "NEVER use PowerShell COM or complex scripts for basic file ops."
                + style_hint
            )
        else:
            mode_hint = (
                f"\n[Mode:{mode.value}] "
                "Destructive ops restricted; suggest switching to Operator mode if needed."
                + style_hint
            )

        return base + mode_hint

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

        is_cron = key.startswith("cron:")
        exec_mode = not is_cron and _is_exec_mode(msg.content)

        _keep = 2 if exec_mode else 4
        raw_history = session.get_history(max_messages=self.memory_window)
        clean_history = [
            m for m in raw_history
            if m["role"] != "tool" and "tool_calls" not in m
        ]
        clean_history = _compress_history(clean_history, keep_recent=_keep)
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
        messages = list(initial_messages)
        n_initial = len(messages)
        iteration = 0
        final_content = None
        tools_used = []
        _turn_events: list[dict] = []
        progress = on_progress or _bus_progress
        nudge_count = 0
        from myxai_desk.core.policy.modes import get_current_mode as _gcm, SecurityMode as _SM
        max_nudges = 0 if _gcm() in (_SM.OPERATOR, _SM.DEVELOPER) else 1

        all_tool_defs = self.tools.get_definitions()
        tool_defs = _filter_tool_defs_for_message(msg.content, all_tool_defs)
        print(f"[agent] exec_mode={exec_mode}, tools={len(tool_defs)}/{len(all_tool_defs)}, "
              f"history={n_initial}, model={self.model}")

        _turn_input = 0
        _turn_output = 0
        _turn_search = 0

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
                        if "search" in tc.name.lower():
                            _turn_search += 1
                        print(f"[agent] tool: {tc.name}({str(tc.arguments)[:100]})")

                        # ── Phase 1: Policy gate (pre-execution) ──
                        from myxai_desk.core.policy.engine import decide as _policy_decide
                        _cap, _op = _tool_to_capability(tc.name, tc.arguments)
                        _decision = _policy_decide(
                            capability=_cap, op=_op, args=tc.arguments,
                            context={"workspace": getattr(self, 'workspace', None)},
                        )
                        if _decision.action == "DENY":
                            _suggest = _suggest_mode_for_deny(_decision.reason_code)
                            _upgrade_hint = (
                                f"\n请提示用户将安全模式切换到「{_suggest}」或更高级别即可执行此操作。"
                                if _suggest else ""
                            )
                            result = (
                                f"[BLOCKED] {_decision.explain}{_upgrade_hint}\n"
                                f"(当前模式={_decision.evidence.get('mode','')}, "
                                f"code={_decision.reason_code})"
                            )
                            _turn_events.append({"tool": tc.name, "cap": _cap, "action": "DENY", "code": _decision.reason_code})
                            print(f"[policy] DENIED: {_decision.reason_code}")

                        elif _decision.action == "REQUIRE_CONFIRM":
                            from myxai_desk.core.orchestrator.planner import get_plan_manager
                            _pm = get_plan_manager()
                            _pending_id = _pm.store_pending(
                                tool_name=tc.name,
                                tool_args=tc.arguments,
                                capability=_cap, op=_op,
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
                            _turn_events.append({"tool": tc.name, "cap": _cap, "action": "CONFIRM", "risk": _decision.risk})
                            print(f"[policy] REQUIRE_CONFIRM → pending {_pending_id}")

                        elif _decision.action == "REQUIRE_SANDBOX":
                            from myxai_desk.core.runtime.sandbox import Sandbox as _Sandbox
                            _sbx = _Sandbox(app_id="agent", workspace=getattr(self, 'workspace', None))
                            _path_arg = tc.arguments.get("path", tc.arguments.get("file_path", ""))
                            if _path_arg and not _sbx.is_path_allowed(_path_arg):
                                result = (
                                    f"[SANDBOX] 路径 {_path_arg} 不在沙箱工作区内，操作被拒绝。\n"
                                    f"(risk={_decision.risk}, code={_decision.reason_code})"
                                )
                                _turn_events.append({"tool": tc.name, "cap": _cap, "action": "SANDBOX_DENY"})
                                print(f"[policy] SANDBOX blocked path: {_path_arg}")
                            else:
                                result = await self.tools.execute(tc.name, tc.arguments)
                                from myxai_desk.core.capabilities.governance import (
                                    post_execution_audit, post_execution_undo,
                                )
                                post_execution_audit(_cap, _op, tc.arguments, result, _decision)
                                post_execution_undo(_cap, _op, tc.arguments, result)
                                _turn_events.append({"tool": tc.name, "cap": _cap, "action": "EXEC", "ok": True})
                                print(f"[policy] SANDBOX: passed, executed")

                        elif _decision.action == "REQUIRE_COOLDOWN":
                            result = await self.tools.execute(tc.name, tc.arguments)
                            _cooldown_secs = _decision.ui.get("cooldown_seconds", 5)
                            from myxai_desk.core.capabilities.governance import (
                                post_execution_audit, post_execution_undo,
                            )
                            post_execution_audit(_cap, _op, tc.arguments, result, _decision)
                            post_execution_undo(
                                _cap, _op, tc.arguments, result,
                                cooldown_seconds=_cooldown_secs,
                            )
                            _turn_events.append({"tool": tc.name, "cap": _cap, "action": "EXEC", "ok": True, "cooldown": _cooldown_secs})
                            print(f"[policy] COOLDOWN: executed with {_cooldown_secs}s cooldown")

                        else:
                            # ── Phase 2: nanobot executes (ALLOW) ──
                            result = await self.tools.execute(tc.name, tc.arguments)

                            # ── Phase 3: Post-execution governance ──
                            from myxai_desk.core.capabilities.governance import (
                                post_execution_audit, post_execution_undo,
                            )
                            post_execution_audit(
                                _cap, _op, tc.arguments, result, _decision,
                            )
                            post_execution_undo(
                                _cap, _op, tc.arguments, result,
                            )
                            _turn_events.append({"tool": tc.name, "cap": _cap, "action": "EXEC", "ok": True})

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

        from apps.llm_utils import record_task_usage
        record_task_usage("chat", _turn_input, _turn_output, _turn_search)

        session.add_message("user", msg.content)
        session.add_message("assistant", final_content,
                            tools_used=tools_used if tools_used else None)

        self.sessions.save(session)

        with _last_tools_lock:
            _last_tools_used[key] = list(tools_used)

        with _last_usage_lock:
            _last_usage[key] = {
                "input": _turn_input,
                "output": _turn_output,
                "search": _turn_search,
            }

        # ── Turn-level audit: minimal key events + fingerprint + ref ──
        if _turn_events:
            try:
                import hashlib as _hl
                _events_json = json.dumps(_turn_events, sort_keys=True, ensure_ascii=False, default=str)
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
                print(f"[audit] chat.turn fp={_fingerprint} events={len(_turn_events)} hash={_audit_hash[:12]}…")
            except Exception as _ae:
                print(f"[audit] turn audit failed: {_ae}")

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

        # Wrap exec tool: intercept deletion commands → safe_remove (recoverable)
        _exec_tool = _agent.tools._tools.get("exec")
        if _exec_tool and hasattr(_exec_tool, 'execute'):
            import re as _wrap_re
            _orig_exec_execute = _exec_tool.execute
            _DEL_INTENT = _wrap_re.compile(
                r'\b(?:del|erase|rm|rmdir|rd|remove-item|remove|delete|'
                r'unlink|trash|recycle|\.Delete\b)',
                _wrap_re.IGNORECASE,
            )
            _PATH_QUOTED = _wrap_re.compile(r"""['"]([^'"]{3,})['"]\s*""")
            _PATH_DRIVE = _wrap_re.compile(r'([A-Z]:\\[^\s"\'<>|*?]+)', _wrap_re.IGNORECASE)

            def _extract_paths(cmd: str) -> list[str]:
                paths = _PATH_QUOTED.findall(cmd)
                if not paths:
                    paths = _PATH_DRIVE.findall(cmd)
                return [p for p in paths if '.' in p.split('\\')[-1] or '.' in p.split('/')[-1]
                        or p.endswith(('\\', '/'))]

            async def _safe_exec_wrapper(**kwargs):
                command = kwargs.get("command", "")
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
                app_id=app_id, source=source,
                capability=cap, op=op, args={},
            )
            if d.action in ("ALLOW", "REQUIRE_COOLDOWN", "REQUIRE_SANDBOX"):
                allowed[name] = tool
        except Exception:
            pass

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
            with _last_usage_lock:
                result_holder["usage"] = _last_usage.pop(session_key, {})
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
            cfg = json.load(f)
        return jsonify(cfg)
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
# Security / Profile / Marketplace / Plan / Audit API
# ---------------------------------------------------------------------------

@flask_app.route("/api/security/mode")
def api_security_mode_get():
    """Return current security mode and its policy summary."""
    from myxai_desk.core.policy.modes import get_current_mode, mode_policy_as_dict
    return jsonify(mode_policy_as_dict(get_current_mode()))


@flask_app.route("/api/security/mode", methods=["POST"])
def api_security_mode_set():
    """Switch global security mode (levels 1-3 only; Dev requires system config)."""
    from myxai_desk.core.policy.modes import (
        SecurityMode, set_current_mode, mode_policy_as_dict,
        USER_SELECTABLE_MODES, is_dev_mode_valid,
    )
    data = request.json or {}
    mode_str = data.get("mode", "")
    try:
        mode = SecurityMode(mode_str)
    except ValueError:
        return jsonify({"error": f"Invalid mode: {mode_str}",
                        "valid": [m.value for m in SecurityMode]}), 400

    if mode == SecurityMode.DEVELOPER:
        if not is_dev_mode_valid():
            return jsonify({
                "error": "Developer 模式只能通过系统配置开启，且需要设置失效策略",
                "hint": "请使用 /api/security/dev/enable 端点",
            }), 403

    if mode not in USER_SELECTABLE_MODES and mode != SecurityMode.DEVELOPER:
        return jsonify({"error": f"模式 {mode_str} 不可直接选择"}), 400

    set_current_mode(mode)
    print(f"[security] Global mode switched to {mode.value}")
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="security.mode.switch",
            args={"mode": mode.value}, action_id="",
            result_summary=f"global → {mode.value}",
        )
    except Exception:
        pass
    return jsonify(mode_policy_as_dict(mode))


@flask_app.route("/api/security/modes")
def api_security_modes_list():
    """Return all available modes and their policies."""
    from myxai_desk.core.policy.modes import (
        SecurityMode, mode_policy_as_dict, USER_SELECTABLE_MODES,
        is_dev_mode_valid, get_dev_mode_status,
    )
    result = []
    for m in SecurityMode:
        d = mode_policy_as_dict(m)
        d["user_selectable"] = m in USER_SELECTABLE_MODES
        d["requires_system_config"] = m == SecurityMode.DEVELOPER
        result.append(d)
    dev_status = get_dev_mode_status()
    return jsonify({"modes": result, "dev_mode": dev_status})


# ── Per-App Mode ──────────────────────────────────────────────────

@flask_app.route("/api/security/app/<app_id>/mode", methods=["GET"])
def api_app_mode_get(app_id):
    """Return the per-app mode override (or null if using global)."""
    from myxai_desk.core.policy.modes import (
        get_app_mode, get_current_mode, get_effective_mode,
    )
    app_mode = get_app_mode(app_id)
    return jsonify({
        "app_id": app_id,
        "app_mode": app_mode.value if app_mode else None,
        "global_mode": get_current_mode().value,
        "effective_mode": get_effective_mode(app_id).value,
    })


@flask_app.route("/api/security/app/<app_id>/mode", methods=["POST"])
def api_app_mode_set(app_id):
    """Set a per-app mode override. Requires confirmation if escalating."""
    from myxai_desk.core.policy.modes import (
        SecurityMode, set_app_mode, clear_app_mode,
        get_current_mode, assess_escalation, get_effective_mode,
        USER_SELECTABLE_MODES, is_dev_mode_valid,
    )
    data = request.json or {}
    mode_str = data.get("mode", "")
    confirmed = data.get("confirmed", False)

    if not mode_str or mode_str == "inherit":
        clear_app_mode(app_id)
        return jsonify({
            "app_id": app_id,
            "app_mode": None,
            "effective_mode": get_effective_mode(app_id).value,
        })

    try:
        target = SecurityMode(mode_str)
    except ValueError:
        return jsonify({"error": f"无效的模式: {mode_str}"}), 400

    if target == SecurityMode.DEVELOPER and not is_dev_mode_valid():
        return jsonify({
            "error": "Developer 模式未通过系统配置开启",
            "hint": "请先通过 /api/security/dev/enable 启用 Developer 模式",
        }), 403

    if target not in USER_SELECTABLE_MODES and target != SecurityMode.DEVELOPER:
        return jsonify({"error": f"模式 {mode_str} 不可选择"}), 400

    assessment = assess_escalation(app_id, target)

    if assessment["escalation"] and not confirmed:
        return jsonify({
            "requires_confirm": True,
            "assessment": assessment,
        }), 200

    set_app_mode(app_id, target)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="security.app_mode.set",
            args={"app_id": app_id, "mode": target.value,
                  "escalation": assessment["escalation"]},
            action_id="", result_summary=f"{app_id} → {target.value}",
        )
    except Exception:
        pass
    return jsonify({
        "app_id": app_id,
        "app_mode": target.value,
        "effective_mode": get_effective_mode(app_id).value,
        "assessment": assessment,
    })


@flask_app.route("/api/security/app/_preview/mode", methods=["POST"])
def api_app_mode_preview():
    """Preview escalation assessment without persisting anything."""
    from myxai_desk.core.policy.modes import SecurityMode, assess_escalation
    data = request.json or {}
    mode_str = data.get("mode", "")
    try:
        target = SecurityMode(mode_str)
    except ValueError:
        return jsonify({"error": f"无效的模式: {mode_str}"}), 400
    assessment = assess_escalation("_preview", target)
    return jsonify({"assessment": assessment})


# ── Developer Mode System Config ──────────────────────────────────

@flask_app.route("/api/security/dev/status")
def api_dev_mode_status():
    from myxai_desk.core.policy.modes import get_dev_mode_status, DEV_EXPIRY_POLICIES
    return jsonify({
        **get_dev_mode_status(),
        "available_policies": DEV_EXPIRY_POLICIES,
    })


@flask_app.route("/api/security/dev/enable", methods=["POST"])
def api_dev_mode_enable():
    """Enable Developer mode with a mandatory expiry policy."""
    from myxai_desk.core.policy.modes import enable_dev_mode
    data = request.json or {}
    expiry_policy = data.get("expiry_policy", "")
    if not expiry_policy:
        return jsonify({
            "error": "必须选择失效策略",
            "available_policies": {
                "on_app_close": "关闭应用后失效",
                "duration_1h": "1 小时后失效",
                "duration_24h": "24 小时后失效",
            },
        }), 400
    result = enable_dev_mode(expiry_policy)
    if "error" in result:
        return jsonify(result), 400
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="security.dev_mode.enable",
            args={"expiry_policy": expiry_policy}, action_id="",
            result_summary=f"dev enabled, policy={expiry_policy}",
        )
    except Exception:
        pass
    return jsonify(result)


@flask_app.route("/api/security/dev/disable", methods=["POST"])
def api_dev_mode_disable():
    """Disable Developer mode and revert to Operator."""
    from myxai_desk.core.policy.modes import disable_dev_mode
    result = disable_dev_mode()
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="security.dev_mode.disable", args={}, action_id="",
            result_summary=f"dev disabled, reverted to {result.get('reverted_to', '')}",
        )
    except Exception:
        pass
    return jsonify(result)


# ---------------------------------------------------------------------------
# Profile API
# ---------------------------------------------------------------------------

@flask_app.route("/api/profile/summary")
def api_profile_summary():
    """Return the user's profile summary."""
    from myxai_desk.core.capabilities.profile import Profile
    p = Profile()
    return jsonify(p.get_summary())


@flask_app.route("/api/profile/topics")
def api_profile_topics():
    """Return extracted interest topics."""
    from myxai_desk.core.capabilities.profile import Profile
    days = request.args.get("days", 30, type=int)
    p = Profile()
    return jsonify(p.get_topics(days=days))


@flask_app.route("/api/profile/preferences")
def api_profile_preferences():
    """Return user preferences."""
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_preferences())


@flask_app.route("/api/profile/preferences", methods=["POST"])
def api_profile_preferences_update():
    """Update user preferences."""
    from myxai_desk.core.capabilities.profile import Profile
    p = Profile()
    action_id = p.update_preferences(request.json or {})
    return jsonify({"success": True, "action_id": action_id})


@flask_app.route("/api/profile/collection")
def api_profile_collection():
    """Return data collection settings."""
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_collection_settings())


@flask_app.route("/api/profile/collection", methods=["POST"])
def api_profile_collection_update():
    """Update data collection settings."""
    from myxai_desk.core.capabilities.profile import Profile
    p = Profile()
    settings = request.json or {}
    action_id = p.update_collection_settings(settings)
    return jsonify({"success": True, "action_id": action_id})


@flask_app.route("/api/profile/export")
def api_profile_export():
    """Export all profile data."""
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().export_all())


@flask_app.route("/api/profile/clear", methods=["POST"])
def api_profile_clear():
    """Clear all profile data."""
    from myxai_desk.core.capabilities.profile import Profile
    action_id = Profile().clear_all()
    return jsonify({"success": True, "action_id": action_id})


@flask_app.route("/api/profile/refresh", methods=["POST"])
def api_profile_refresh():
    """Force refresh the profile summary."""
    from myxai_desk.core.capabilities.profile import Profile
    summary = Profile().refresh_summary()
    return jsonify(summary)


# ---------------------------------------------------------------------------
# Persona Engine API
# ---------------------------------------------------------------------------

@flask_app.route("/api/profile/persona")
def api_persona_get():
    """Return the full 6-layer persona profile."""
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_persona())


@flask_app.route("/api/profile/persona/layer/<layer_name>")
def api_persona_layer_get(layer_name):
    """Return a single persona layer."""
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_persona_layer(layer_name))


@flask_app.route("/api/profile/persona/layer/<layer_name>", methods=["POST"])
def api_persona_layer_update(layer_name):
    """Manually edit fields in a persona layer."""
    from myxai_desk.core.capabilities.profile import Profile
    patch = request.get_json(force=True) or {}
    result = Profile().update_persona_layer(layer_name, patch)
    return jsonify(result)


@flask_app.route("/api/profile/persona/versions")
def api_persona_versions():
    """List all stored persona versions."""
    from myxai_desk.core.capabilities.profile import Profile
    return jsonify(Profile().get_persona_versions())


@flask_app.route("/api/profile/persona/rollback", methods=["POST"])
def api_persona_rollback():
    """Rollback persona to a specific version."""
    from myxai_desk.core.capabilities.profile import Profile
    data = request.get_json(force=True) or {}
    version = data.get("version")
    if not isinstance(version, int):
        return jsonify({"error": "version (int) is required"}), 400
    return jsonify(Profile().rollback_persona(version))


@flask_app.route("/api/profile/persona/prompt")
def api_persona_prompt():
    """Generate a task-aware persona prompt for LLM injection."""
    from myxai_desk.core.capabilities.profile import Profile
    from myxai_desk.core.profile.prompt_builder import SUPPORTED_TASK_TYPES
    task_type = request.args.get("task_type", "general")
    prompt = Profile().get_persona_prompt(task_type)
    return jsonify({"task_type": task_type, "prompt": prompt,
                    "supported_types": SUPPORTED_TASK_TYPES})


@flask_app.route("/api/profile/persona/audit")
def api_persona_audit():
    """Return recent persona update audit log entries."""
    from myxai_desk.core.capabilities.profile import Profile
    n = request.args.get("n", 50, type=int)
    return jsonify(Profile().get_persona_audit(n=n))


@flask_app.route("/api/profile/persona/update", methods=["POST"])
def api_persona_update():
    """Trigger a full persona engine update cycle."""
    from myxai_desk.core.capabilities.profile import Profile
    data = request.get_json(force=True) or {}
    force = data.get("force", False)
    result = Profile().run_persona_update(force=force)
    return jsonify(result)


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
            post_execution_audit, post_execution_undo,
        )
        post_execution_audit(pa.capability, pa.op, pa.tool_args, result, None)
        post_execution_undo(pa.capability, pa.op, pa.tool_args, result)
        return jsonify({"success": True, "result": str(result)[:500]})
    except Exception as e:
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
    return Response(data, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=audit_chain.json"})


@flask_app.route("/api/undo/actions")
def api_undo_actions():
    """Return recent undoable actions."""
    from myxai_desk.core.audit.undo import UndoRegistry
    registry = UndoRegistry()
    undoable = request.args.get("undoable", "false").lower() == "true"
    return jsonify(registry.list_actions(undoable_only=undoable))


@flask_app.route("/api/undo/<action_id>", methods=["POST"])
def api_undo_action(action_id):
    """Undo a specific action."""
    from myxai_desk.core.audit.undo import UndoRegistry
    registry = UndoRegistry()
    result = registry.undo(action_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


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

        _display_model = config.agents.defaults.model

        return jsonify({
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

    # ── Inline confirmation: execute pending action via chat ──
    if _CONFIRM_RE.match(message):
        _confirmed_result = _try_execute_pending()
        if _confirmed_result is not None:
            message = (
                f"[用户已确认，操作已执行，结果如下]\n"
                f"{_confirmed_result}\n\n"
                f"请根据以上执行结果，用自然语言向用户汇报。"
            )

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
            with _last_usage_lock:
                _usage_data = _last_usage.pop(session_id, {})
            with _last_turn_audit_lock:
                _audit_data = _last_turn_audit.pop(session_id, None)
            _done_payload = {"type": "done", "content": response or ""}
            if _usage_data:
                _done_payload["usage"] = _usage_data
            if _audit_data:
                _done_payload["audit"] = {
                    "fingerprint": _audit_data["fingerprint"],
                    "events": _audit_data["events"],
                    "hash": _audit_data["audit_hash"][:16],
                }
            q.put(json.dumps(_done_payload, ensure_ascii=False))
        except Exception as exc:
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
        "min_mode": "Observer",
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
        "min_mode": "Observer",
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
        "min_mode": "Assistant",
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
            "security_mode": capp.get("security_mode", ""),
        })
    return jsonify(result)


@flask_app.route("/api/apps/<app_id>/install", methods=["POST"])
def api_app_install(app_id):
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    if app_id not in _APP_CATALOG:
        return jsonify({"error": "应用不存在"}), 404
    registry = _load_apps_registry()
    if app_id in registry:
        return jsonify({"error": "应用已安装"}), 400
    default_configs = {
        "daily_digest": _DEFAULT_DIGEST_CONFIG,
        "web_monitor": _DEFAULT_MONITOR_CONFIG,
        "email_summary": _DEFAULT_EMAIL_CONFIG,
    }
    registry[app_id] = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "config": default_configs.get(app_id, {}),
    }
    _save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.install", args={"app_id": app_id},
            action_id="", result_summary="installed",
        )
    except Exception:
        pass
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/uninstall", methods=["POST"])
def api_app_uninstall(app_id):
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    del registry[app_id]
    _save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.uninstall", args={"app_id": app_id},
            action_id="", result_summary="uninstalled",
        )
    except Exception:
        pass
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/enable", methods=["POST"])
def api_app_enable(app_id):
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    registry[app_id]["enabled"] = True
    _save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.enable", args={"app_id": app_id},
            action_id="", result_summary="enabled",
        )
    except Exception:
        pass
    return jsonify({"success": True})


@flask_app.route("/api/apps/<app_id>/disable", methods=["POST"])
def api_app_disable(app_id):
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    registry[app_id]["enabled"] = False
    _save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.disable", args={"app_id": app_id},
            action_id="", result_summary="disabled",
        )
    except Exception:
        pass
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
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run(app_id, capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    registry = _load_apps_registry()
    if app_id not in registry:
        return jsonify({"error": "应用未安装"}), 404
    new_config = request.json or {}
    registry[app_id]["config"] = new_config
    _save_apps_registry(registry)
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.config.save", args={"app_id": app_id},
            action_id="", result_summary="config_updated",
        )
    except Exception:
        pass
    return jsonify({"success": True})


@flask_app.route("/api/apps/daily_digest/run", methods=["POST"])
def api_digest_run():
    """Start a daily digest run in the background."""
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("daily_digest")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

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
                    reg["daily_digest"]["last_run"] = datetime.now().strftime("%Y-%m-%d")
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

            from myxai_desk.core.runtime.app_governance import finish_app_run
            finish_app_run("daily_digest", success=(result["status"] == "ok"))

            with _digest_task_lock:
                _digest_task_status.update({
                    "status": "done" if result["status"] == "ok" else "error",
                    "result": result,
                })
        except Exception as exc:
            print(f"[daily_digest] run error: {exc}")
            try:
                from myxai_desk.core.runtime.app_governance import finish_app_run
                finish_app_run("daily_digest", success=False, error=str(exc))
            except Exception:
                pass
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
                "read": r.get("read", False),
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
                "read": r.get("read", False),
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


@flask_app.route("/api/reports/unread_count")
def api_reports_unread_count():
    """Lightweight endpoint returning total unread count across all report sources."""
    total = 0
    try:
        from apps.custom_app import all_unread_counts
        total += sum(all_unread_counts().values())
    except Exception:
        pass
    try:
        from apps.daily_digest import list_reports as _dl
        total += sum(1 for r in _dl(limit=60) if not r.get("read"))
    except Exception:
        pass
    try:
        from apps.email_summary import list_reports as _el
        total += sum(1 for r in _el() if not r.get("read"))
    except Exception:
        pass
    return jsonify({"total": total})


@flask_app.route("/api/reports/mark_all_read", methods=["POST"])
def api_mark_all_reports_read():
    # Custom apps
    try:
        from apps.custom_app import list_apps as _list_custom, list_reports as custom_list, mark_report_read
        for app in _list_custom():
            for r in custom_list(app["id"]):
                if not r.get("read"):
                    mark_report_read(app["id"], r.get("key", ""))
    except Exception:
        pass
    # Daily Digest
    try:
        from apps.daily_digest import list_reports as digest_list, mark_report_read as digest_mark
        for r in digest_list(limit=200):
            if not r.get("read"):
                digest_mark(r.get("date", ""))
    except Exception:
        pass
    # Email Summary
    try:
        from apps.email_summary import list_reports as email_list, mark_report_read as email_mark
        for r in email_list():
            if not r.get("read"):
                email_mark(r.get("date", ""))
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
        from apps.daily_digest import load_report, mark_report_read as digest_mark
        report = load_report(key)
        if not report:
            return jsonify({"error": "not found"}), 404
        digest_mark(key)
        return jsonify(report)
    elif app_id == "email_summary":
        from apps.email_summary import get_report, mark_report_read as email_mark
        report = get_report(key)
        if not report:
            return jsonify({"error": "not found"}), 404
        email_mark(key)
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
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("web_monitor", capabilities=["fs.write", "net.http_get"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    body = request.json or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL 不能为空"}), 400
    from apps.web_monitor import add_site
    site = add_site(url, name=body.get("name", ""), mode=body.get("mode", "hash"))
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.web_monitor.add_site", args={"url": url},
            action_id="", result_summary=f"added {site.get('id', '')}",
        )
    except Exception:
        pass
    return jsonify(site)


@flask_app.route("/api/apps/web_monitor/sites/<site_id>", methods=["DELETE"])
def api_monitor_remove_site(site_id):
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("web_monitor", capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    from apps.web_monitor import remove_site
    if remove_site(site_id):
        try:
            from myxai_desk.core.audit.ledger import AuditLedger
            AuditLedger().append_entry(
                capability="app.web_monitor.remove_site", args={"site_id": site_id},
                action_id="", result_summary="removed",
            )
        except Exception:
            pass
        return jsonify({"success": True})
    return jsonify({"error": "站点不存在"}), 404


@flask_app.route("/api/apps/web_monitor/check", methods=["POST"])
def api_monitor_check_all():
    """Trigger a check on all enabled sites (background)."""
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("web_monitor")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

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
                reg["web_monitor"]["last_run"] = datetime.now().strftime("%Y-%m-%d")
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
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("web_monitor")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403
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
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("email_summary")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

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
                reg["email_summary"]["last_run"] = datetime.now().strftime("%Y-%m-%d")
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
# Routes — Custom Apps
# ---------------------------------------------------------------------------

@flask_app.route("/api/apps/custom", methods=["GET"])
def api_custom_list():
    from apps.custom_app import list_apps
    return jsonify(list_apps())


@flask_app.route("/api/apps/custom", methods=["POST"])
def api_custom_create():
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("custom_app_mgmt", source="user",
                            capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

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
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("custom_app_mgmt", source="user",
                            capabilities=["fs.write"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

    body = request.json or {}
    from apps.custom_app import update_app
    app = update_app(app_id, **body)
    if not app:
        return jsonify({"error": "应用不存在"}), 404
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.custom.update", args={"app_id": app_id},
            action_id="", result_summary="updated",
        )
    except Exception:
        pass
    return jsonify(app)


@flask_app.route("/api/apps/custom/<app_id>", methods=["DELETE"])
def api_custom_delete(app_id):
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run("custom_app_mgmt", source="user",
                            capabilities=["fs.write"])
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
    return jsonify({"error": "应用不存在"}), 404


@flask_app.route("/api/apps/custom/<app_id>/run", methods=["POST"])
def api_custom_run(app_id):
    """Run a custom app — SSE stream. Supports multiple param groups."""
    from myxai_desk.core.runtime.app_governance import gate_app_run
    decision = gate_app_run(app_id, source="user")
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403

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

            original_tools = dict(agent.tools._tools)
            safe_tools = _filter_tools_by_policy(
                original_tools, app_id=app_id, source="user",
                app_permissions=app.get("permissions", []),
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
                        q.put(json.dumps({"type": "progress",
                                          "content": f"[{idx+1}/{total}] {label}"},
                                         ensure_ascii=False))

                    message = build_message(app, pv)
                    _CAPP_SAFETY = _build_safety_prompt(app_id, safe_tools)
                    message = _CAPP_SAFETY + message
                    session_key = f"capp_{_uuid.uuid4().hex[:12]}"

                    response = await agent.process_direct(
                        message, session_key=session_key,
                        on_progress=on_progress,
                    )

                    with _last_usage_lock:
                        _run_usage = _last_usage.pop(session_key, {})
                    _app_turn_input += _run_usage.get("input", 0)
                    _app_turn_output += _run_usage.get("output", 0)
                    _app_turn_search += _run_usage.get("search", 0)

                    save_report(app_id, content=response or "",
                                params_used=pv)

                    if total > 1:
                        q.put(json.dumps({"type": "progress",
                                          "content": f"✅ [{idx+1}/{total}] {label}"},
                                         ensure_ascii=False))
            finally:
                agent.tools._tools = original_tools

            _app_cat = f"app_{app.get('name', app_id)}"
            from apps.llm_utils import record_task_usage
            record_task_usage(_app_cat, _app_turn_input, _app_turn_output, _app_turn_search)

            set_last_run(app_id)
            _inc_run_count(app_id)
            try:
                from myxai_desk.core.runtime.app_governance import finish_app_run
                finish_app_run(app_id, success=True)
            except Exception:
                pass
            _done_payload = {"type": "done", "content": ""}
            if _app_turn_input or _app_turn_output:
                _done_payload["usage"] = {
                    "input": _app_turn_input,
                    "output": _app_turn_output,
                    "search": _app_turn_search,
                }
            q.put(json.dumps(_done_payload, ensure_ascii=False))
        except Exception as exc:
            if 'original_tools' in dir():
                agent.tools._tools = original_tools
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
            _sum_pi = 0
            _sum_co = 0
            if _usage:
                _sum_pi = getattr(_usage, "prompt_tokens", 0)
                _sum_co = getattr(_usage, "completion_tokens", 0)
                from apps.llm_utils import record_tokens
                record_tokens(prompt_tokens=_sum_pi, completion_tokens=_sum_co)
            from apps.llm_utils import record_task_usage
            record_task_usage(f"app_{app.get('name', app_id)}", _sum_pi, _sum_co, 0)
            content = resp.choices[0].message.content or ""

            save_report(app_id, content=content, params_used={},
                        report_type="summary")
            mark_triggered(app_id, "summary")

            _done_payload = {"type": "done", "content": content}
            if _sum_pi or _sum_co:
                _done_payload["usage"] = {"input": _sum_pi, "output": _sum_co, "search": 0}
            q.put(json.dumps(_done_payload, ensure_ascii=False))
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
# Apps scheduler (background timer) + catch-up scheduling
# ---------------------------------------------------------------------------

_app_scheduler_timer = None

from myxai_desk.core.scheduler_service import (
    scheduler_service as _scheduler_svc,
    TaskDescriptor as _TaskDescriptor,
    DueSlot as _DueSlot,
    CATCHUP_DEFAULTS as _CATCHUP_DEFAULTS,
)


def _load_official_tasks() -> list["_TaskDescriptor"]:
    """Build TaskDescriptors for official scheduled apps (daily_digest, email_summary)."""
    descriptors: list[_TaskDescriptor] = []
    registry = _load_apps_registry()

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
            descriptors.append(_TaskDescriptor(
                task_id="daily_digest",
                schedule={"enabled": True, "mode": "daily", "time": schedule_time},
                cron_expr=cron_expr,
                created_at=app.get("installed_at", "2024-01-01T00:00:00"),
                last_success_at=app.get("last_run"),
                catchup_policy=catchup_cfg.get("catchup_policy", "LATEST_ONLY"),
                catchup_window_hours=catchup_cfg.get("catchup_window_hours", 24),
                max_catchup_runs=catchup_cfg.get("max_catchup_runs", 1),
                extra={"kind": "daily_digest", "config": config, "registry_app": app},
            ))

        elif app_id == "email_summary":
            schedule_time = config.get("schedule_time")
            if not schedule_time:
                continue
            if not config.get("imap_host") or not config.get("imap_user"):
                continue
            hh, mm = schedule_time.split(":")[:2]
            cron_expr = f"{mm} {hh} * * *"
            catchup_cfg = config.get("catchup", {})
            descriptors.append(_TaskDescriptor(
                task_id="email_summary",
                schedule={"enabled": True, "mode": "daily", "time": schedule_time},
                cron_expr=cron_expr,
                created_at=app.get("installed_at", "2024-01-01T00:00:00"),
                last_success_at=app.get("last_run"),
                catchup_policy=catchup_cfg.get("catchup_policy", "LATEST_ONLY"),
                catchup_window_hours=catchup_cfg.get("catchup_window_hours", 24),
                max_catchup_runs=catchup_cfg.get("max_catchup_runs", 1),
                extra={"kind": "email_summary", "config": config, "registry_app": app},
            ))

        elif app_id == "web_monitor":
            if not config.get("schedule_enabled", True):
                continue
            interval_min = config.get("check_interval_minutes", 30)
            cron_expr = f"*/{interval_min} * * * *"
            descriptors.append(_TaskDescriptor(
                task_id="web_monitor",
                schedule={"enabled": True, "mode": "daily", "time": "00:00"},
                cron_expr=cron_expr,
                created_at=app.get("installed_at", "2024-01-01T00:00:00"),
                last_success_at=app.get("last_run"),
                catchup_policy="NONE",
                catchup_window_hours=1,
                max_catchup_runs=1,
                extra={"kind": "web_monitor", "config": config, "registry_app": app},
            ))

    return descriptors


def _load_custom_tasks() -> list["_TaskDescriptor"]:
    """Build TaskDescriptors for custom (prompt) apps."""
    from apps.custom_app import list_apps as _list_custom, build_task_descriptor
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
    with _digest_task_lock:
        if _digest_task_status.get("status") == "running":
            return

    from myxai_desk.core.runtime.app_governance import gate_app_run
    _gate = gate_app_run("daily_digest")
    if not _gate["allowed"]:
        print(f"[scheduler] daily_digest blocked: {_gate['reason']}")
        return

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(f"[scheduler] triggering daily_digest (scheduled_for={sched_for}, trigger={trigger})")
    from apps.daily_digest import run_daily_digest
    from apps.llm_utils import snapshot_today_tokens, record_task_usage
    model_cfg = _get_model_config()
    merged = {**config, **model_cfg}
    _snap_before = snapshot_today_tokens()
    result = run_daily_digest(merged)
    _snap_after = snapshot_today_tokens()
    _d_in = _snap_after["input"] - _snap_before["input"]
    _d_out = _snap_after["output"] - _snap_before["output"]
    _d_search = result.get("stats", {}).get("search_results", 0)
    record_task_usage("app_每日私享会", _d_in, _d_out,
                      min(_d_search, 1) if _d_search else 0)
    if result["status"] == "ok":
        today = slot.scheduled_for.strftime("%Y-%m-%d")
        registry = _load_apps_registry()
        if "daily_digest" in registry:
            registry["daily_digest"]["last_run"] = today
            _save_apps_registry(registry)
        stats = result.get("stats", {})
        catchup_note = ""
        if trigger in ("startup", "resume"):
            catchup_note = f"（补偿执行，原定 {sched_for}）"
        _push_notification(
            title=f"🎯 每日私享会已更新{catchup_note}",
            content=(
                f"分析 {stats.get('filtered_count', 0)} 条浏览记录，"
                f"搜索 {stats.get('search_results', 0)} 条推荐内容。"
            ),
            level="info",
        )
    else:
        raise RuntimeError(f"daily_digest returned status={result.get('status')}")


def _exec_email_summary(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    config = task.extra["config"]
    from myxai_desk.core.runtime.app_governance import gate_app_run
    _gate = gate_app_run("email_summary")
    if not _gate["allowed"]:
        print(f"[scheduler] email_summary blocked: {_gate['reason']}")
        return

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(f"[scheduler] triggering email_summary (scheduled_for={sched_for}, trigger={trigger})")
    from apps.email_summary import run_email_summary
    from apps.llm_utils import snapshot_today_tokens, record_task_usage
    model_cfg = _get_model_config()
    _snap_before = snapshot_today_tokens()
    result = run_email_summary(config, model_config=model_cfg)
    _snap_after = snapshot_today_tokens()
    _d_in = _snap_after["input"] - _snap_before["input"]
    _d_out = _snap_after["output"] - _snap_before["output"]
    record_task_usage("app_邮件简报", _d_in, _d_out, 0)
    if result.get("success"):
        today = slot.scheduled_for.strftime("%Y-%m-%d")
        registry = _load_apps_registry()
        if "email_summary" in registry:
            registry["email_summary"]["last_run"] = today
            _save_apps_registry(registry)
        catchup_note = ""
        if trigger in ("startup", "resume"):
            catchup_note = f"（补偿执行，原定 {sched_for}）"
        _push_notification(
            title=f"📧 邮件简报已生成{catchup_note}",
            content=f"汇总了 {result.get('email_count', 0)} 封邮件",
            level="info",
        )
    else:
        raise RuntimeError("email_summary failed")


def _exec_web_monitor(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    config = task.extra["config"]
    with _monitor_task_lock:
        if _monitor_task_status.get("status") == "running":
            return

    from myxai_desk.core.runtime.app_governance import gate_app_run
    _gate = gate_app_run("web_monitor")
    if not _gate["allowed"]:
        print(f"[scheduler] web_monitor blocked: {_gate['reason']}")
        return

    print(f"[scheduler] triggering web_monitor check (trigger={trigger})")
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
    today = datetime.now().strftime("%Y-%m-%d")
    registry = _load_apps_registry()
    if "web_monitor" in registry:
        registry["web_monitor"]["last_run"] = today
        _save_apps_registry(registry)


def _exec_custom_app(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    capp = task.extra["app"]
    capp_id = capp["id"]
    from apps.custom_app import (
        build_message, save_report, set_last_run, mark_triggered,
    )
    from myxai_desk.core.runtime.app_governance import gate_app_run, finish_app_run

    _gate = gate_app_run(capp_id, source="user")
    if not _gate["allowed"]:
        print(f"[scheduler] custom app '{capp['name']}' blocked: {_gate['reason']}")
        return

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(f"[scheduler] triggering custom app '{capp['name']}' (scheduled_for={sched_for}, trigger={trigger})")
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
        _inc_run_count(capp_id)
        mark_triggered(capp_id, "schedule")
        finish_app_run(capp_id, success=True)
        catchup_note = ""
        if trigger in ("startup", "resume"):
            catchup_note = f"（补偿执行，原定 {sched_for}）"
        _push_notification(
            title=f"{capp.get('icon', '🤖')} {capp['name']}{catchup_note}",
            content=f"定时执行完成（{len(groups)} 组）",
            level="info",
        )
    except Exception as exc:
        print(f"[scheduler] custom app '{capp['name']}' error: {exc}")
        finish_app_run(capp_id, success=False, error=str(exc))
        raise


def _exec_custom_summary(task: "_TaskDescriptor", slot: "_DueSlot", trigger: str) -> None:
    capp = task.extra["app"]
    capp_id = capp["id"]
    from apps.custom_app import build_summary_prompt, save_report, mark_triggered

    sched_for = slot.scheduled_for.strftime("%Y-%m-%d %H:%M")
    print(f"[scheduler] triggering summary for '{capp['name']}' (scheduled_for={sched_for}, trigger={trigger})")
    prompt = build_summary_prompt(capp)
    if not prompt:
        return
    mcfg = _get_model_config()
    if not mcfg.get("model") or not mcfg.get("api_key"):
        return
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
        title=f"📊 {capp['name']} 总结",
        content="总结报告已生成",
        level="info",
    )


def _init_scheduler_service():
    """Register task loaders and executors with the global SchedulerService."""
    _scheduler_svc.register_task_loader(_load_official_tasks)
    _scheduler_svc.register_task_loader(_load_custom_tasks)
    _scheduler_svc.register_executor("daily_digest", _exec_daily_digest)
    _scheduler_svc.register_executor("email_summary", _exec_email_summary)
    _scheduler_svc.register_executor("web_monitor", _exec_web_monitor)
    _scheduler_svc.register_executor("custom", _exec_custom_app)
    _scheduler_svc.register_executor("custom_summary", _exec_custom_summary)


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
            print(f"[scheduler] tick error: {exc}")
        _app_scheduler_timer = threading.Timer(60, _tick)
        _app_scheduler_timer.daemon = True
        _app_scheduler_timer.start()

    _app_scheduler_timer = threading.Timer(60, _tick)
    _app_scheduler_timer.daemon = True
    _app_scheduler_timer.start()
    print("[scheduler] started (catch-up enabled)")


# ---------------------------------------------------------------------------
# Routes — scheduler / task runs
# ---------------------------------------------------------------------------

@flask_app.route("/api/scheduler/trigger/<task_id>", methods=["POST"])
def api_scheduler_trigger(task_id):
    """Manually trigger a scheduled task."""
    ok, msg = _scheduler_svc.trigger_now(task_id)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 404


@flask_app.route("/api/scheduler/runs/<task_id>", methods=["GET"])
def api_scheduler_runs(task_id):
    """Return recent run history for a task (for UI display)."""
    from myxai_desk.core.scheduler_service import get_recent_runs
    limit = request.args.get("limit", 20, type=int)
    runs = get_recent_runs(task_id, limit=limit)
    return jsonify({"runs": runs})


@flask_app.route("/api/scheduler/status", methods=["GET"])
def api_scheduler_status():
    """Quick overview: list all scheduled tasks with next/last info."""
    from myxai_desk.core.scheduler_service import compute_due_slots
    tasks = _load_official_tasks() + _load_custom_tasks()
    now = datetime.now()
    items = []
    for t in tasks:
        due = compute_due_slots(t, now)
        items.append({
            "task_id": t.task_id,
            "catchup_policy": t.catchup_policy,
            "last_success_at": t.last_success_at,
            "pending_catchup": len(due),
            "pending_slots": [{"scheduled_for": s.scheduled_for.isoformat(),
                               "idempotency_key": s.idempotency_key} for s in due],
        })
    return jsonify({"tasks": items})


# Official app display names / icons
_OFFICIAL_APP_META = {
    "daily_digest":  {"name_zh": "每日私享会", "name_en": "Daily Briefing", "icon": "🎯"},
    "email_summary": {"name_zh": "邮件简报",  "name_en": "Email Briefing", "icon": "📧"},
    "web_monitor":   {"name_zh": "网页监控",  "name_en": "Web Monitor",    "icon": "🔍"},
}


@flask_app.route("/api/scheduler/today", methods=["GET"])
def api_scheduler_today():
    """Return today's task schedule for the sidebar task panel.

    Each item includes: task_id, name, icon, scheduled_time, status, finished_at.
    Statuses: planned | running | success | failed
    """
    from myxai_desk.core.scheduler_service import (
        compute_due_slots, get_today_runs, get_running_tasks,
    )
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # Collect all task descriptors
    tasks = _load_official_tasks() + _load_custom_tasks()

    # Build a lookup: task_id -> (name_zh, name_en, icon, schedule_time)
    task_meta: dict[str, dict] = {}
    for t in tasks:
        meta = _OFFICIAL_APP_META.get(t.task_id)
        if meta:
            name_zh = meta["name_zh"]
            name_en = meta["name_en"]
            icon = meta["icon"]
        else:
            app_data = t.extra.get("app", {})
            base_name = app_data.get("name", t.task_id)
            icon = app_data.get("icon", "🤖")
            kind = t.extra.get("kind", "")
            if kind == "custom_summary":
                name_zh = base_name + " (总结)"
                name_en = base_name + " (Summary)"
                icon = "📊"
            else:
                name_zh = base_name
                name_en = base_name
        sched_time = t.schedule.get("time", "")
        task_meta[t.task_id] = {
            "name_zh": name_zh, "name_en": name_en,
            "icon": icon, "time": sched_time,
            "mode": t.schedule.get("mode", "daily"),
            "catchup_policy": t.catchup_policy,
        }

    # Collect today's runs from DB
    today_runs = get_today_runs()
    running_tasks = get_running_tasks()

    run_by_task: dict[str, list[dict]] = {}
    for r in today_runs:
        run_by_task.setdefault(r["task_id"], []).append(r)

    running_ids = {r["task_id"] for r in running_tasks}

    # Build the result list
    items = []
    seen_tasks = set()

    # 1) Tasks with existing runs today
    for task_id, runs in run_by_task.items():
        seen_tasks.add(task_id)
        meta = task_meta.get(task_id, {"name_zh": task_id, "name_en": task_id, "icon": "🤖", "time": "", "mode": "daily"})
        latest = runs[-1]
        items.append({
            "task_id": task_id,
            "name_zh": meta["name_zh"],
            "name_en": meta["name_en"],
            "icon": meta["icon"],
            "scheduled_time": meta["time"],
            "status": latest["status"],
            "started_at": latest.get("started_at", ""),
            "finished_at": latest.get("finished_at", ""),
            "error": latest.get("error", ""),
            "trigger": latest.get("trigger", ""),
        })

    # 2) Tasks that are due but haven't run yet
    for t in tasks:
        if t.task_id in seen_tasks:
            continue
        if t.task_id in running_ids:
            continue
        due = compute_due_slots(t, now)
        if not due:
            sched_time = t.schedule.get("time", "")
            sched_mode = t.schedule.get("mode", "daily")
            show_planned = False
            if sched_time and sched_time > now.strftime("%H:%M"):
                if sched_mode == "daily":
                    show_planned = True
                elif sched_mode == "weekly":
                    if now.weekday() == t.schedule.get("day_of_week", 0):
                        show_planned = True
                elif sched_mode == "monthly":
                    if now.day == t.schedule.get("day_of_month", 1):
                        show_planned = True
                elif sched_mode == "interval":
                    show_planned = True
            if show_planned:
                meta = task_meta.get(t.task_id, {"name_zh": t.task_id, "name_en": t.task_id, "icon": "🤖", "time": ""})
                items.append({
                    "task_id": t.task_id,
                    "name_zh": meta["name_zh"],
                    "name_en": meta["name_en"],
                    "icon": meta["icon"],
                    "scheduled_time": sched_time,
                    "status": "planned",
                    "started_at": "",
                    "finished_at": "",
                    "error": "",
                    "trigger": "",
                })
        else:
            meta = task_meta.get(t.task_id, {"name_zh": t.task_id, "name_en": t.task_id, "icon": "🤖", "time": ""})
            items.append({
                "task_id": t.task_id,
                "name_zh": meta["name_zh"],
                "name_en": meta["name_en"],
                "icon": meta["icon"],
                "scheduled_time": meta["time"],
                "status": "pending_catchup",
                "started_at": "",
                "finished_at": "",
                "error": "",
                "trigger": "",
            })

    # Sort: running first, then pending_catchup, then planned, then success, then failed
    status_order = {"running": 0, "pending_catchup": 1, "planned": 2, "success": 3, "failed": 4}
    items.sort(key=lambda x: (status_order.get(x["status"], 9), x.get("scheduled_time", "")))

    return jsonify({"tasks": items, "date": today_str})


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
    global _desk_manager

    _start_app_scheduler()

    # Run catch-up check in background so missed tasks are compensated on startup
    threading.Thread(target=_scheduler_svc.on_app_start, daemon=True).start()

    port = 19280

    # --- fallback: no pywebview ------------------------------------------- #
    try:
        import webview  # noqa: F401
    except ImportError:
        print("pywebview 未安装，将在浏览器中打开。")
        print("安装方法：pip install pywebview")
        import webbrowser
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

    # --- start Flask in background ---------------------------------------- #
    threading.Thread(
        target=lambda: flask_app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    ).start()

    import urllib.request
    for _attempt in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/check", timeout=1)
            break
        except Exception:
            time.sleep(0.05)

    # --- DeskManager (tray) ------------------------------------------------ #
    from desk_manager import DeskManager

    _desk_manager = DeskManager(port=port)

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
            pass
        try:
            from apps.daily_digest import list_reports as _dl
            total += sum(1 for r in _dl(limit=60) if not r.get("read"))
        except Exception:
            pass
        try:
            from apps.email_summary import list_reports as _el
            total += sum(1 for r in _el() if not r.get("read"))
        except Exception:
            pass
        return total

    _desk_manager._get_unread_count = _unread_count

    try:
        from apps.llm_utils import get_token_usage
        _desk_manager._get_token_usage = get_token_usage
    except ImportError:
        pass

    _desk_manager._on_resume = _scheduler_svc.on_resume

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

    _desk_manager.run(start_func=_grant_media_permissions)
    _shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
