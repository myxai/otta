"""全局应用状态管理.

该模块提供统一的应用状态存储和访问接口，用于逐步从 app.py 迁移全局状态。
"""

import asyncio
import subprocess
import threading
from dataclasses import dataclass, field


@dataclass
class AppState:
    """应用全局状态."""

    # 异步循环
    async_loop: asyncio.AbstractEventLoop | None = None
    async_thread: threading.Thread | None = None

    # Agent 相关
    agent: object | None = None
    agent_lock: threading.Lock = field(default_factory=threading.Lock)

    # 会话相关
    session_epoch: int = 0
    session_counter: int = 0

    # Gateway 进程
    gateway_process: subprocess.Popen | None = None

    # 定时任务服务
    cron_service: object | None = None

    # MCP 日志
    mcp_log: list[dict] = field(default_factory=list)
    mcp_log_lock: threading.Lock = field(default_factory=threading.Lock)

    # 通知
    notifications: list[dict] = field(default_factory=list)
    notifications_lock: threading.Lock = field(default_factory=threading.Lock)

    # 工具使用记录
    last_tools_used: dict[str, list[str]] = field(default_factory=dict)
    last_tools_lock: threading.Lock = field(default_factory=threading.Lock)

    # 使用统计
    last_usage: dict[str, dict] = field(default_factory=dict)
    last_usage_lock: threading.Lock = field(default_factory=threading.Lock)

    # 审计记录
    last_turn_audit: dict[str, dict] = field(default_factory=dict)
    last_turn_audit_lock: threading.Lock = field(default_factory=threading.Lock)


def get_state(app) -> AppState:
    """获取或创建应用状态实例.
    
    Args:
        app: Flask 应用实例
        
    Returns:
        AppState 实例
    """
    if "myxai_state" not in app.extensions:
        app.extensions["myxai_state"] = AppState()
    return app.extensions["myxai_state"]
