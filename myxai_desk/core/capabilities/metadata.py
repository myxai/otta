"""Tool capability metadata — structured metadata for tool classification.

This module replaces string-based tool name guessing with structured metadata
that declares:
  - capability (fs/proc/net/profile/search/mcp/notify)
  - operation (read/write/delete/exec/http_get/...)
  - risk level (low/medium/high/critical)

Architecture:
  - Tools declare metadata via decorators or registration
  - Policy engine uses metadata instead of name guessing
  - Metadata is immutable and validated at registration
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    """Tool capability categories."""

    FS = "fs"  # File system operations
    PROC = "proc"  # Process/command execution
    NET = "net"  # Network operations
    PROFILE = "profile"  # User profile access
    SEARCH = "search"  # Web search
    MCP = "mcp"  # MCP tool invocation
    NOTIFY = "notify"  # System notifications
    CHAT = "chat"  # Chat/conversation


class Operation(str, Enum):
    """Tool operation types."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MOVE = "move"
    EXEC = "exec"
    HTTP_GET = "http_get"
    HTTP_POST = "http_post"
    QUERY = "query"
    UPDATE = "update"
    SEND = "send"


class RiskLevel(str, Enum):
    """Risk level assessment."""

    LOW = "low"  # Read-only, no side effects
    MEDIUM = "medium"  # Write operations, reversible
    HIGH = "high"  # Destructive operations, hard to reverse
    CRITICAL = "critical"  # System-level, irreversible


@dataclass(frozen=True)
class ToolMetadata:
    """Immutable metadata for a tool.

    This replaces the old pattern of guessing capability from tool name.
    """

    name: str
    capability: Capability
    operation: Operation
    risk: RiskLevel
    description: str = ""
    requires_confirm: bool = False
    supports_undo: bool = False
    audit_required: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "capability": self.capability.value,
            "operation": self.operation.value,
            "risk": self.risk.value,
            "description": self.description,
            "requires_confirm": self.requires_confirm,
            "supports_undo": self.supports_undo,
            "audit_required": self.audit_required,
        }


class ToolRegistry:
    """Central registry for tool metadata.

    This replaces the _tool_to_capability string matching in app.py.
    """

    def __init__(self):
        self._tools: dict[str, ToolMetadata] = {}
        self._register_builtin_tools()

    def register(self, metadata: ToolMetadata) -> None:
        """Register a tool with its metadata."""
        self._tools[metadata.name] = metadata

    def get(self, tool_name: str) -> ToolMetadata | None:
        """Get metadata for a tool by name."""
        return self._tools.get(tool_name)

    def get_by_capability(self, capability: Capability) -> list[ToolMetadata]:
        """Get all tools with a specific capability."""
        return [m for m in self._tools.values() if m.capability == capability]

    def get_high_risk(self) -> list[ToolMetadata]:
        """Get all high-risk and critical tools."""
        return [m for m in self._tools.values() if m.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)]

    def _register_builtin_tools(self) -> None:
        """Register built-in tool metadata."""
        # File system tools
        self.register(
            ToolMetadata(
                name="file_read",
                capability=Capability.FS,
                operation=Operation.READ,
                risk=RiskLevel.LOW,
                description="Read file contents",
            )
        )
        self.register(
            ToolMetadata(
                name="file_write",
                capability=Capability.FS,
                operation=Operation.WRITE,
                risk=RiskLevel.MEDIUM,
                description="Write to file",
                supports_undo=True,
            )
        )
        self.register(
            ToolMetadata(
                name="file_delete",
                capability=Capability.FS,
                operation=Operation.DELETE,
                risk=RiskLevel.HIGH,
                description="Delete file",
                requires_confirm=True,
                supports_undo=True,
            )
        )

        # Process tools
        self.register(
            ToolMetadata(
                name="execute_command",
                capability=Capability.PROC,
                operation=Operation.EXEC,
                risk=RiskLevel.HIGH,
                description="Execute shell command",
                requires_confirm=True,
            )
        )

        # Network tools
        self.register(
            ToolMetadata(
                name="http_get",
                capability=Capability.NET,
                operation=Operation.HTTP_GET,
                risk=RiskLevel.MEDIUM,
                description="Make HTTP GET request",
            )
        )
        self.register(
            ToolMetadata(
                name="http_post",
                capability=Capability.NET,
                operation=Operation.HTTP_POST,
                risk=RiskLevel.MEDIUM,
                description="Make HTTP POST request",
            )
        )

        # Search tools
        self.register(
            ToolMetadata(
                name="web_search",
                capability=Capability.SEARCH,
                operation=Operation.QUERY,
                risk=RiskLevel.LOW,
                description="Search the web",
            )
        )

        # Profile tools
        self.register(
            ToolMetadata(
                name="profile_read",
                capability=Capability.PROFILE,
                operation=Operation.READ,
                risk=RiskLevel.LOW,
                description="Read user profile",
            )
        )

        # MCP tools (generic)
        self.register(
            ToolMetadata(
                name="mcp_call",
                capability=Capability.MCP,
                operation=Operation.EXEC,
                risk=RiskLevel.MEDIUM,
                description="Call MCP tool",
            )
        )


# Global registry instance
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


def register_tool(
    name: str,
    capability: Capability,
    operation: Operation,
    risk: RiskLevel,
    **kwargs,
) -> None:
    """Convenience function to register a tool."""
    metadata = ToolMetadata(
        name=name, capability=capability, operation=operation, risk=risk, **kwargs
    )
    _registry.register(metadata)


def tool_metadata(
    capability: Capability,
    operation: Operation,
    risk: RiskLevel,
    **kwargs,
) -> Callable:
    """Decorator to attach metadata to a tool function.

    Usage:
        @tool_metadata(Capability.FS, Operation.WRITE, RiskLevel.MEDIUM)
        def my_tool(args):
            ...
    """

    def decorator(func: Callable) -> Callable:
        metadata = ToolMetadata(
            name=func.__name__,
            capability=capability,
            operation=operation,
            risk=risk,
            description=func.__doc__ or "",
            **kwargs,
        )
        _registry.register(metadata)
        func._tool_metadata = metadata  # Attach to function
        return func

    return decorator
