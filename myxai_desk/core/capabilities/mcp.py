"""MCP server call capability — thin wrapper with policy + audit hooks."""

from __future__ import annotations

import uuid
from typing import Any


def _new_action_id() -> str:
    return f"act_{uuid.uuid4().hex[:12]}"


class MCPCapability:
    """Wraps MCP tool execution with audit logging."""

    def __init__(self, *, agent: Any = None, audit_ledger: Any = None):
        self._agent = agent
        self._audit = audit_ledger

    async def call_tool(self, server: str, tool_name: str,
                        arguments: dict | None = None) -> Any:
        """Invoke an MCP tool via the nanobot agent's MCP stack."""
        action_id = _new_action_id()

        if self._agent is None:
            return {"error": "No agent available for MCP calls"}

        try:
            result = await self._agent.tools.execute(tool_name, arguments or {})
        except Exception as e:
            result = {"error": str(e)}

        if self._audit:
            self._audit.append_entry(
                capability="mcp.call_tool",
                args={"server": server, "tool": tool_name},
                action_id=action_id,
                result_summary=str(result)[:200],
            )

        return result

    def list_servers(self) -> list[str]:
        """Return names of connected MCP servers."""
        if self._agent and hasattr(self._agent, '_mcp_stack'):
            try:
                return list(self._agent._mcp_stack._servers.keys())
            except Exception:
                pass
        return []
