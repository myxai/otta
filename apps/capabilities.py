"""CapabilityManager + CapabilityGuard — environment probing and capability-based tool routing.

CapabilityManager probes and caches system capabilities:
  - Static: OS, shell, workspace (once at startup)
  - Tools: registered tool names (once at startup)
  - Network: outbound connectivity (refreshed with TTL)

CapabilityGuard uses the capability map for hard interception:
  - Network tools blocked when network is down
  - exec network commands blocked when network is down
  - Browser MCP tools blocked when not enabled
"""

import platform
import re
import shutil
import time
from typing import Any

import httpx

_PROBE_URLS = [
    "http://www.baidu.com",
    "http://connectivitycheck.platform.hicloud.com/generate_204",
    "https://www.msftconnecttest.com/connecttest.txt",
]
_PROBE_TIMEOUT = 3.0
_NETWORK_TTL = 120  # seconds between probes

_NETWORK_TOOLS = frozenset({"smart_fetch", "web_fetch", "web_search"})

_NET_FETCH_CMD = re.compile(
    r"\b(?:curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b",
    re.IGNORECASE,
)

_BROWSER_MCP_KW = frozenset({
    "browser", "playwright", "puppeteer", "selenium",
    "navigate", "screenshot", "chrome", "webview",
})


class CapabilityManager:
    """Probe, cache, and expose system capabilities (MVP: 8 fields)."""

    def __init__(self, workspace: str | None = None):
        self._workspace = workspace
        self._os = ""
        self._shells: list[str] = []
        self._tools_available: set[str] = set()

        self._network_outbound = True  # optimistic default
        self._dns_ok = True
        self._http_get_ok = True
        self._latency_ms = 0
        self._network_ts: float = 0

        self._policy: dict[str, Any] = {
            "allow_exec_network": False,
            "allow_browser_mcp": False,
            "max_attempts": {
                "fetch_url": 2,
                "search": 1,
                "exec": 2,
            },
        }

    # ── probes ──────────────────────────────────────────────────────

    def probe_static(self):
        """OS + available shells.  Call once at startup."""
        self._os = platform.system().lower()
        self._shells = [
            s for s in ("powershell", "pwsh", "cmd", "bash", "zsh", "sh")
            if shutil.which(s)
        ]

    def probe_tools(self, tool_names: set[str] | list[str]):
        """Record registered tool names (call after all tools are registered)."""
        self._tools_available = set(tool_names)

    def probe_network_sync(self) -> bool:
        """Synchronous HTTP probe — try multiple URLs, first success wins."""
        for url in _PROBE_URLS:
            try:
                t0 = time.monotonic()
                r = httpx.get(url, timeout=_PROBE_TIMEOUT, follow_redirects=True)
                ms = int((time.monotonic() - t0) * 1000)
                if r.status_code < 500:
                    self._network_outbound = True
                    self._http_get_ok = True
                    self._dns_ok = True
                    self._latency_ms = ms
                    self._network_ts = time.monotonic()
                    return True
            except Exception:
                continue
        self._network_outbound = False
        self._http_get_ok = False
        self._latency_ms = int(_PROBE_TIMEOUT * 1000)
        self._network_ts = time.monotonic()
        return False

    async def probe_network_async(self) -> bool:
        """Async HTTP probe — try multiple URLs, first success wins."""
        async with httpx.AsyncClient(
            timeout=_PROBE_TIMEOUT, follow_redirects=True
        ) as c:
            for url in _PROBE_URLS:
                try:
                    t0 = time.monotonic()
                    r = await c.get(url)
                    ms = int((time.monotonic() - t0) * 1000)
                    if r.status_code < 500:
                        self._network_outbound = True
                        self._http_get_ok = True
                        self._dns_ok = True
                        self._latency_ms = ms
                        self._network_ts = time.monotonic()
                        return True
                except Exception:
                    continue
        self._network_outbound = False
        self._http_get_ok = False
        self._latency_ms = int(_PROBE_TIMEOUT * 1000)
        self._network_ts = time.monotonic()
        return False

    def mark_network_ok(self):
        """Implicit confirmation: a network tool succeeded, so network is up."""
        self._network_outbound = True
        self._http_get_ok = True
        self._dns_ok = True
        self._network_ts = time.monotonic()

    # ── accessors ───────────────────────────────────────────────────

    def needs_network_refresh(self) -> bool:
        return self._network_ts == 0 or (time.monotonic() - self._network_ts) > _NETWORK_TTL

    @property
    def network_outbound(self) -> bool:
        return self._network_outbound

    @property
    def os_name(self) -> str:
        return self._os

    @property
    def tools_available(self) -> set[str]:
        return self._tools_available

    @property
    def policy(self) -> dict:
        return self._policy

    def get(self) -> dict:
        """Full capability map (for logging / API exposure)."""
        return {
            "env": {
                "os": self._os,
                "shell": self._shells,
                "workspace": self._workspace,
            },
            "tools": {
                n: {"available": True} for n in sorted(self._tools_available)
            },
            "network": {
                "outbound": self._network_outbound,
                "dns": self._dns_ok,
                "http_get": self._http_get_ok,
                "latency_ms": self._latency_ms,
            },
            "policy": self._policy,
        }

    def get_prompt_summary(self) -> str:
        """Short one-liner for system prompt injection (low token cost)."""
        net = "可用" if self._network_outbound else "不可用"
        tools = ", ".join(sorted(self._tools_available)) if self._tools_available else "none"
        parts = [
            f"OS={self._os}",
            f"网络={net}",
            f"可用工具=[{tools}]",
        ]
        if not self._policy.get("allow_exec_network", True):
            parts.append("禁止exec抓网页")
        if not self._policy.get("allow_browser_mcp", True):
            parts.append("浏览器MCP未启用")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# CapabilityGuard — pre-execution interception based on capability map
# ---------------------------------------------------------------------------


class CapabilityGuard:
    """Block tool calls that would certainly fail given current capabilities.

    Runs BEFORE FetchGuard (turn-level) and Policy gate (security-level).
    Triggers async network refresh when probe data is stale.
    """

    def __init__(self, cap_manager: CapabilityManager):
        self._caps = cap_manager

    async def check(self, tool_name: str, tool_args: dict) -> str | None:
        """Returns error string if tool call should be blocked, None if OK."""

        # Lazy network refresh when stale and tool needs network
        if tool_name in _NETWORK_TOOLS and self._caps.needs_network_refresh():
            await self._caps.probe_network_async()

        # 1. Network tools when connectivity is down
        if tool_name in _NETWORK_TOOLS and not self._caps.network_outbound:
            return (
                f"[CAPABILITY] 当前网络不可用，{tool_name} 无法执行。"
                "请检查网络连接后重试，或告知用户当前无法联网。"
            )

        # 2. exec with network-fetch commands when network is down
        if tool_name == "exec" and not self._caps.network_outbound:
            cmd = tool_args.get("command", "")
            if _NET_FETCH_CMD.search(cmd):
                return (
                    "[CAPABILITY] 当前网络不可用，exec 网络命令将失败。"
                    "请检查网络连接后重试。"
                )

        # 3. Browser MCP when not enabled
        if (
            tool_name.startswith("mcp_")
            and _is_browser_mcp_tool(tool_name)
            and not self._caps.policy.get("allow_browser_mcp", True)
        ):
            return (
                f"[CAPABILITY] 浏览器 MCP 工具 ({tool_name}) 未启用。"
                "如需使用，请在设置中启用浏览器 MCP。"
            )

        return None


def _is_browser_mcp_tool(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _BROWSER_MCP_KW)
