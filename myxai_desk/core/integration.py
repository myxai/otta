"""Integration helpers for gradual migration to new architecture.

This module provides utilities to bridge the gap between the old app.py
architecture and the new ExecutionContext/ToolExecutor architecture.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from myxai_desk.core.orchestrator.context import ExecutionContext


def create_context_for_session(session_id: str, app_id: str = "desktop") -> ExecutionContext:
    """Create an ExecutionContext for a session.

    This should be called at the start of each /api/chat request.
    """
    from myxai_desk.core.orchestrator.context import ExecutionContext
    from myxai_desk.core.orchestrator.context_store import get_context_store

    ctx = ExecutionContext(
        request_id=f"req_{session_id}_{int(time.time())}",
        started_at=time.time(),
        session_id=session_id,
        app_id=app_id,
    )

    # Register in store for later retrieval
    store = get_context_store()
    store.register(session_id, ctx)

    return ctx


def get_context_for_session(session_id: str) -> ExecutionContext | None:
    """Get the ExecutionContext for a session."""
    from myxai_desk.core.orchestrator.context_store import get_context_store

    store = get_context_store()
    return store.get(session_id)


def finalize_context_for_session(session_id: str) -> dict[str, Any] | None:
    """Finalize and remove the ExecutionContext for a session.

    This should be called at the end of each /api/chat request.
    Returns the finalized context data.
    """
    from myxai_desk.core.orchestrator.context_store import get_context_store

    store = get_context_store()
    ctx = store.pop(session_id)

    if ctx:
        return ctx.finalize()
    return None


def migrate_legacy_dict_to_context(
    session_id: str,
    tools_used: list[str] | None = None,
    usage: dict | None = None,
    audit_data: dict | None = None,
) -> None:
    """Migrate data from legacy global dicts to ExecutionContext.

    This is a transition helper to gradually move away from:
    - _last_tools_used
    - _last_usage
    - _last_turn_audit

    Usage in app.py:
        # After agent.process_direct()
        migrate_legacy_dict_to_context(
            session_id,
            tools_used=_last_tools_used.pop(session_id, []),
            usage=_last_usage.pop(session_id, {}),
            audit_data=_last_turn_audit.pop(session_id, None),
        )
    """
    ctx = get_context_for_session(session_id)
    if not ctx:
        return

    # Migrate tools_used
    if tools_used:
        for tool_name in tools_used:
            ctx.add_tool_call(
                tool=tool_name,
                args={},  # Not available in legacy format
                result=None,
            )

    # Migrate usage
    if usage:
        ctx.add_usage("unknown", usage)

    # Migrate audit_data
    if audit_data:
        ctx.add_audit_event(
            {
                "event": "legacy_audit",
                "data": audit_data,
            }
        )


def audit_capability_execution(
    capability: str,
    operation: str,
    args: dict,
    result: Any,
    *,
    request_id: str | None = None,
) -> None:
    """Record capability execution to audit ledger.

    This should be called by each capability function (fs, proc, net, etc.)
    after successful execution.

    Usage in capabilities:
        from myxai_desk.core.integration import audit_capability_execution

        def file_write(path, content):
            result = _do_write(path, content)
            audit_capability_execution(
                "fs", "write",
                {"path": str(path)},
                result
            )
            return result
    """
    from myxai_desk.core.audit.ledger import AuditEntry, AuditLedger
    from myxai_desk.core.policy.modes import get_current_mode
    from datetime import datetime, timezone
    import hashlib
    import json

    ledger = AuditLedger()

    # Compute digests
    args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
    args_digest = hashlib.sha256(args_str.encode()).hexdigest()[:16]

    result_str = str(result)[:1000]  # Limit size
    result_digest = hashlib.sha256(result_str.encode()).hexdigest()[:16]

    entry = AuditEntry(
        ts=datetime.now(timezone.utc).isoformat(),
        app_id="system",
        source=f"{capability}.{operation}",
        mode=get_current_mode().value,
        capability=capability,
        op=operation,
        args_digest=args_digest,
        result_digest=result_digest,
        undo={"action_id": request_id} if request_id else {},
    )

    ledger.append(entry)


# Decorator for automatic capability auditing
def audit_capability(capability: str, operation: str):
    """Decorator to automatically audit capability function calls.

    Usage:
        @audit_capability("fs", "write")
        def file_write(path, content):
            # ... implementation ...
            return result
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Extract args for auditing (skip 'self' if method)
            audit_args = kwargs.copy()
            if args:
                # Try to match positional args to parameters
                import inspect

                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        param_name = param_names[i]
                        if param_name != "self":
                            audit_args[param_name] = str(arg)[:100]

            audit_capability_execution(capability, operation, audit_args, result)
            return result

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
