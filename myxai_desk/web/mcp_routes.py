"""MCP (Model Context Protocol) 路由 — MCP 服务器连接测试和管理.

迁移自 app.py 的 /api/mcp/* 路由。
"""

import asyncio
import logging
import contextlib
import shutil

from flask import Blueprint, current_app, jsonify

log = logging.getLogger("myxai.web.mcp_routes")
bp = Blueprint("mcp", __name__, url_prefix="/api/mcp")


@bp.post("/test")
def test():
    """测试 MCP 服务器连接，不影响运行中的 agent."""
    try:
        from nanobot.config.loader import load_config
    except ImportError:
        return jsonify({"error": "nanobot 未安装"}), 400

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
                    import app as _app
                    cmd, args = _app._win_fix_cmd(cfg.command, list(cfg.args))
                    stack = AsyncExitStack()
                    await stack.__aenter__()
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
                with contextlib.suppress(Exception):
                    await stack.aclose()
            except asyncio.TimeoutError:
                entry["message"] = "Connection timed out (90s)"
            except Exception as e:
                log.warning("MCP test failed for server %s: %s", name, e, exc_info=True)
                entry["message"] = f"{type(e).__name__}: {e}"
            results.append(entry)

    import app as _app
    _app._ensure_loop()
    
    future = asyncio.run_coroutine_threadsafe(_test(), _app._async_loop)
    try:
        future.result(timeout=180)
    except Exception as e:
        log.exception("MCP test timed out")
        return jsonify({"error": f"Test timed out: {e}"}), 500

    return jsonify({"results": results})


@bp.post("/reconnect")
def reconnect():
    """强制重新连接运行中 agent 的 MCP 服务器."""
    try:
        import nanobot  # noqa: F401
    except ImportError:
        return jsonify({"error": "nanobot 未安装"}), 400
    
    import app as _app
    
    if _app._agent is None:
        return jsonify({"error": "Agent not yet created — send a message first"}), 400

    agent = _app._agent
    if agent._mcp_stack is not None:

        async def _close_old():
            with contextlib.suppress(Exception):
                await agent._mcp_stack.aclose()

        _app._ensure_loop()
        f = asyncio.run_coroutine_threadsafe(_close_old(), _app._async_loop)
        with contextlib.suppress(Exception):
            f.result(timeout=10)
        agent._mcp_stack = None

    agent._mcp_connected = False
    for key in list(agent.tools._tools.keys()):
        if key.startswith("mcp_"):
            del agent.tools._tools[key]

    with _app._mcp_log_lock:
        _app._mcp_log.clear()

    async def _reconn():
        await _app._connect_mcp_safe(agent)

    future = asyncio.run_coroutine_threadsafe(_reconn(), _app._async_loop)
    try:
        future.result(timeout=180)
    except Exception as e:
        log.exception("MCP reconnect failed")
        return jsonify({"error": str(e)}), 500

    mcp_tools = [n for n in agent.tools._tools if n.startswith("mcp_")]
    with _app._mcp_log_lock:
        log_copy = list(_app._mcp_log)
    return jsonify(
        {
            "success": True,
            "mcp_tool_count": len(mcp_tools),
            "mcp_tools": mcp_tools,
            "mcp_log": log_copy,
        }
    )


@bp.get("/log")
def log():
    """返回 MCP 诊断日志."""
    import app as _app
    with _app._mcp_log_lock:
        return jsonify(list(_app._mcp_log))
