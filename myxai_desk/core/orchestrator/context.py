"""Execution context — unified request-scoped state management.

This module provides ``ExecutionContext`` to replace global dictionaries and
eliminate race conditions in concurrent request handling.  Every chat request
gets its own context that carries:
  - request_id (unique identifier)
  - tool calls history
  - usage statistics
  - audit events
  - session metadata

Architecture:
  - Created at the start of each request (in app.py or orchestrator)
  - Passed through the execution pipeline
  - Automatically written to audit ledger on finalization
  - Thread-safe by design (no shared mutable state)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from myxai_desk.core.policy.modes import SecurityMode, get_current_mode


def _new_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


@dataclass
class ToolCall:
    """Single tool call record."""

    tool: str
    args: dict[str, Any]
    result: Any
    ts: float
    error: str | None = None


@dataclass
class ExecutionContext:
    """Unified execution context for a single request.

    Replaces global dictionaries (_last_tools_used, _last_usage, etc.) with
    request-scoped state that eliminates race conditions.
    """

    request_id: str
    started_at: float
    session_id: str = ""
    app_id: str = ""
    mode: SecurityMode = field(default_factory=get_current_mode)
    workspace: str = ""

    # Execution data (replaces global dicts)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    audit_events: list[dict] = field(default_factory=list)

    # User message and response
    user_message: str = ""
    assistant_response: str = ""

    def add_tool_call(
        self, tool: str, args: dict[str, Any], result: Any, *, error: str | None = None
    ) -> None:
        """Record a tool call."""
        self.tool_calls.append(
            ToolCall(
                tool=tool,
                args=args,
                result=result,
                ts=time.time(),
                error=error,
            )
        )

    def add_usage(self, model: str, usage: dict[str, Any]) -> None:
        """Accumulate token usage."""
        if "models" not in self.usage:
            self.usage["models"] = {}
        if model not in self.usage["models"]:
            self.usage["models"][model] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            if key in usage:
                self.usage["models"][model][key] += usage.get(key, 0)

    def add_audit_event(self, event: dict[str, Any]) -> None:
        """Record an audit event."""
        event["request_id"] = self.request_id
        event["ts"] = event.get("ts", time.time())
        self.audit_events.append(event)

    def get_tool_names(self) -> list[str]:
        """Get list of tool names used in this request."""
        return [tc.tool for tc in self.tool_calls]

    def finalize(self) -> dict[str, Any]:
        """Finalize the execution and return summary statistics."""
        duration = time.time() - self.started_at
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "duration": duration,
            "tool_calls_count": len(self.tool_calls),
            "tool_names": self.get_tool_names(),
            "usage": self.usage,
            "mode": self.mode.value,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "started_at": self.started_at,
            "session_id": self.session_id,
            "app_id": self.app_id,
            "mode": self.mode.value,
            "workspace": self.workspace,
            "tool_calls": [asdict(tc) for tc in self.tool_calls],
            "usage": self.usage,
            "audit_events": self.audit_events,
            "user_message": self.user_message,
            "assistant_response": self.assistant_response,
        }


class ContextManager:
    """Context manager for ExecutionContext lifecycle.

    Usage:
        with ContextManager() as ctx:
            # Execute request with ctx
            result = handle_chat(message, ctx)
            # Context automatically finalized on exit
    """

    def __init__(self, *, session_id: str = "", app_id: str = "", workspace: str = "") -> None:
        self.session_id = session_id
        self.app_id = app_id
        self.workspace = workspace
        self.ctx: ExecutionContext | None = None

    def __enter__(self) -> ExecutionContext:
        self.ctx = ExecutionContext(
            request_id=_new_request_id(),
            started_at=time.time(),
            session_id=self.session_id,
            app_id=self.app_id,
            workspace=self.workspace,
        )
        return self.ctx

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.ctx is None:
            return

        # Log error if exception occurred
        if exc_type is not None:
            self.ctx.add_audit_event(
                {
                    "event": "execution_error",
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val),
                }
            )

        # Write to audit ledger
        try:
            from myxai_desk.core.audit.ledger import AuditLedger

            ledger = AuditLedger()
            ledger.append_entry(
                capability="chat",
                args={
                    "message": self.ctx.user_message,
                    "session_id": self.ctx.session_id,
                },
                action_id=self.ctx.request_id,
                app_id=self.ctx.app_id,
                result_summary=f"{len(self.ctx.tool_calls)} tools, {self.ctx.usage.get('total_tokens', 0)} tokens",
            )
        except Exception:
            pass  # Don't fail the request if audit fails
