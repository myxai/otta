"""Gateway 路由 — 进程管理和日志查看.

迁移自 app.py 的 /api/gateway/* 路由。
"""

import contextlib
import logging
import os
import shutil
import subprocess
import sys
from flask import Blueprint, jsonify, current_app

from myxai_desk.web.state import get_state
from myxai_desk.web.migration_guards import mark

log = logging.getLogger("myxai.web.gateway_routes")
bp = Blueprint("gateway", __name__, url_prefix="/api/gateway")


def _find_nanobot_cmd() -> list[str]:
    """Locate the nanobot executable; fall back to python -c wrapper."""
    exe = shutil.which("nanobot")
    if exe:
        return [exe, "gateway"]
    return [
        sys.executable,
        "-c",
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

        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(pid), signal.SIGTERM)


def _cleanup_gateway(state) -> None:
    """If the gateway process has exited, reset the global handle."""
    if state.gateway_process is not None and state.gateway_process.poll() is not None:
        state.gateway_process = None


@bp.post("/start")
def start():
    """启动 nanobot gateway 进程."""
    mark("[NEW] gateway/start")
    state = get_state(current_app)
    
    # 使用全局锁保护进程状态（第一版宁可锁大一点）
    with state.agent_lock:
        _cleanup_gateway(state)
        if state.gateway_process is not None:
            return jsonify({"error": "网关已在运行"}), 400
        try:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            cmd = _find_nanobot_cmd()
            state.gateway_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return jsonify({"success": True, "pid": state.gateway_process.pid})
        except Exception as e:
            log.exception("Failed to start gateway process")
            state.gateway_process = None
            return jsonify({"error": str(e)}), 500


@bp.post("/stop")
def stop():
    """停止 nanobot gateway 进程."""
    mark("[NEW] gateway/stop")
    state = get_state(current_app)
    
    with state.agent_lock:
        if state.gateway_process is None:
            return jsonify({"error": "网关未运行"}), 400
        pid = state.gateway_process.pid
        _kill_process_tree(pid)
        with contextlib.suppress(Exception):
            state.gateway_process.wait(timeout=5)
        state.gateway_process = None
        return jsonify({"success": True})


@bp.get("/status")
def status():
    """查询 gateway 进程状态."""
    mark("[NEW] gateway/status")
    state = get_state(current_app)
    
    with state.agent_lock:
        _cleanup_gateway(state)
        running = state.gateway_process is not None
        return jsonify(
            {
                "running": running,
                "pid": state.gateway_process.pid if running else None,
            }
        )


@bp.get("/logs")
def logs():
    """获取 gateway 进程日志（最多 100 行）."""
    mark("[NEW] gateway/logs")
    state = get_state(current_app)
    
    with state.agent_lock:
        if not (state.gateway_process and state.gateway_process.stdout):
            return jsonify({"logs": ""})
        try:
            lines = []
            while state.gateway_process.stdout.readable():
                line = state.gateway_process.stdout.readline()
                if not line:
                    break
                lines.append(line)
                if len(lines) > 100:
                    break
            return jsonify({"logs": "".join(lines)})
        except Exception:
            log.warning("Failed to read gateway logs", exc_info=True)
            return jsonify({"logs": ""})
