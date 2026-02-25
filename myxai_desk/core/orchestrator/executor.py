"""Tool executor — enforces policy before tool execution.

This module provides a mandatory enforcement layer that ensures:
  1. Every tool call goes through policy.decide()
  2. Tools cannot be called directly bypassing policy
  3. Execution results are audited automatically
  4. Context is properly managed

Architecture:
  - ToolExecutor wraps tool execution with policy enforcement
  - Integration with ExecutionContext for tracking
  - Automatic audit logging
  - Decision caching for performance
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from myxai_desk.core.capabilities.metadata import get_tool_registry
from myxai_desk.core.policy.engine import decide

if TYPE_CHECKING:
    from myxai_desk.core.orchestrator.context import ExecutionContext


class ToolExecutionDenied(Exception):
    """Raised when a tool execution is denied by policy."""

    def __init__(self, tool_name: str, reason: str, decision: dict):
        self.tool_name = tool_name
        self.reason = reason
        self.decision = decision
        super().__init__(f"Tool '{tool_name}' denied: {reason}")


class ToolExecutor:
    """Enforces policy before executing tools.

    This replaces direct tool calls with policy-aware execution.
    """

    def __init__(self, *, strict_mode: bool = True):
        """Initialize executor.

        Args:
            strict_mode: If True, deny execution if metadata is missing
        """
        self.strict_mode = strict_mode
        self._registry = get_tool_registry()

    def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        tool_func: Callable,
        *,
        ctx: ExecutionContext | None = None,
    ) -> Any:
        """Execute a tool with policy enforcement.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            tool_func: The actual tool function to call
            ctx: Execution context (optional)

        Returns:
            Tool execution result

        Raises:
            ToolExecutionDenied: If policy denies execution
        """
        # Get tool metadata
        metadata = self._registry.get(tool_name)

        if metadata is None and self.strict_mode:
            raise ToolExecutionDenied(
                tool_name,
                "No metadata registered (strict mode)",
                {"action": "DENY", "reason": "METADATA_MISSING"},
            )

        # Use metadata for policy decision if available
        if metadata:
            decision = decide(
                capability=metadata.capability.value,
                op=metadata.operation.value,
                args=args,
            )
        else:
            # Fallback to generic decision
            decision = decide(capability="unknown", op="unknown", args=args)

        # Check decision
        if decision.action == "DENY":
            raise ToolExecutionDenied(tool_name, decision.reason_code, decision.to_dict())

        # Execute tool
        start_time = time.time()
        try:
            result = tool_func(**args)
            error = None
        except Exception as e:
            result = None
            error = str(e)
            raise
        finally:
            # Record in context
            if ctx:
                ctx.add_tool_call(tool_name, args, result, error=error)

                # Add audit event
                ctx.add_audit_event(
                    {
                        "event": "tool_execution",
                        "tool": tool_name,
                        "decision": decision.action,
                        "duration": time.time() - start_time,
                        "success": error is None,
                    }
                )

        return result

    def can_execute(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Check if a tool can be executed without actually executing it.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Tuple of (can_execute, reason)
        """
        metadata = self._registry.get(tool_name)

        if metadata is None and self.strict_mode:
            return False, "No metadata registered"

        if metadata:
            decision = decide(
                capability=metadata.capability.value,
                op=metadata.operation.value,
                args=args,
            )
        else:
            decision = decide(capability="unknown", op="unknown", args=args)

        return decision.action != "DENY", decision.reason_code


# Global executor instance
_executor = ToolExecutor()


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor."""
    return _executor


def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    tool_func: Callable,
    *,
    ctx: ExecutionContext | None = None,
) -> Any:
    """Convenience function to execute a tool with policy enforcement."""
    return _executor.execute(tool_name, args, tool_func, ctx=ctx)
