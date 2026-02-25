"""MCP server call policy rules — server allowlist enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myxai_desk.core.policy.modes import ModePolicy


def evaluate(op: str, args: dict, policy: ModePolicy) -> tuple[str, int, str]:
    """Evaluate an MCP capability call against current mode policy.

    Returns ``(action, risk_score, reason_code)``.
    """
    if not policy.mcp_allowed:
        return "DENY", 70, "MCP_NOT_ALLOWED_IN_MODE"

    server = args.get("server", "")
    if policy.mcp_server_allowlist and server not in policy.mcp_server_allowlist:
        return "DENY", 60, f"MCP_SERVER_NOT_IN_ALLOWLIST:{server}"

    if policy.confirm_level == "strong":
        return "REQUIRE_CONFIRM", 30, "MCP_STRONG_CONFIRM"

    return "ALLOW", 10, "MCP_ALLOWED"
