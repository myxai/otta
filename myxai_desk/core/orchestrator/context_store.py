"""Context storage — thread-safe storage for ExecutionContext instances.

This module provides a centralized store for active ExecutionContext instances,
replacing global dictionaries and eliminating race conditions.

Architecture:
  - Thread-safe storage using locks
  - Automatic cleanup of old contexts
  - Backward compatibility bridge for gradual migration
"""

from __future__ import annotations

import threading
import time
from typing import Any

from myxai_desk.core.orchestrator.context import ExecutionContext


class ContextStore:
    """Thread-safe storage for active ExecutionContext instances.

    This replaces the global dictionaries (_last_tools_used, _last_usage, etc.)
    in app.py with a proper storage mechanism.
    """

    def __init__(self, *, max_age_seconds: int = 3600):
        self._contexts: dict[str, ExecutionContext] = {}
        self._lock = threading.Lock()
        self._max_age = max_age_seconds

    def register(self, key: str, ctx: ExecutionContext) -> None:
        """Register a context with a session key."""
        with self._lock:
            self._contexts[key] = ctx
            self._cleanup_old()

    def get(self, key: str) -> ExecutionContext | None:
        """Get a context by session key."""
        with self._lock:
            return self._contexts.get(key)

    def pop(self, key: str) -> ExecutionContext | None:
        """Remove and return a context by session key."""
        with self._lock:
            return self._contexts.pop(key, None)

    def exists(self, key: str) -> bool:
        """Check if a context exists for the given key."""
        with self._lock:
            return key in self._contexts

    def _cleanup_old(self) -> None:
        """Remove contexts older than max_age (internal, assumes lock held)."""
        now = time.time()
        to_remove = [
            key for key, ctx in self._contexts.items() if now - ctx.started_at > self._max_age
        ]
        for key in to_remove:
            del self._contexts[key]

    def clear(self) -> None:
        """Clear all contexts (mainly for testing)."""
        with self._lock:
            self._contexts.clear()

    def count(self) -> int:
        """Return the number of active contexts."""
        with self._lock:
            return len(self._contexts)


# Global instance (replaces _last_tools_used, _last_usage, _last_turn_audit)
_context_store = ContextStore()


def get_context_store() -> ContextStore:
    """Get the global context store instance."""
    return _context_store


# Backward compatibility helpers for gradual migration
class LegacyBridge:
    """Bridge for backward compatibility with old global dict pattern.

    This allows gradual migration from:
        _last_tools_used[key] = [...]
    to:
        ctx = get_or_create_context(key)
        ctx.add_tool_call(...)
    """

    @staticmethod
    def get_tools_used(key: str) -> list[str]:
        """Get tool names from context (replaces _last_tools_used[key])."""
        ctx = _context_store.get(key)
        return ctx.get_tool_names() if ctx else []

    @staticmethod
    def pop_tools_used(key: str) -> list[str]:
        """Pop tool names from context (replaces _last_tools_used.pop(key))."""
        ctx = _context_store.pop(key)
        return ctx.get_tool_names() if ctx else []

    @staticmethod
    def get_usage(key: str) -> dict[str, Any]:
        """Get usage dict from context (replaces _last_usage[key])."""
        ctx = _context_store.get(key)
        return ctx.usage if ctx else {}

    @staticmethod
    def pop_usage(key: str) -> dict[str, Any]:
        """Pop usage dict from context (replaces _last_usage.pop(key))."""
        ctx = _context_store.pop(key)
        return ctx.usage if ctx else {}

    @staticmethod
    def get_audit(key: str) -> dict[str, Any]:
        """Get audit data from context (replaces _last_turn_audit[key])."""
        ctx = _context_store.get(key)
        if not ctx:
            return {}
        return {
            "request_id": ctx.request_id,
            "events": ctx.audit_events,
            "tool_calls": len(ctx.tool_calls),
        }

    @staticmethod
    def pop_audit(key: str) -> dict[str, Any]:
        """Pop audit data from context (replaces _last_turn_audit.pop(key))."""
        ctx = _context_store.pop(key)
        if not ctx:
            return {}
        return {
            "request_id": ctx.request_id,
            "events": ctx.audit_events,
            "tool_calls": len(ctx.tool_calls),
        }


def get_or_create_context(key: str, *, session_id: str = "", app_id: str = "") -> ExecutionContext:
    """Get existing context or create a new one for the given key.

    This is the recommended way to obtain a context in app.py.
    """
    ctx = _context_store.get(key)
    if ctx is None:
        from myxai_desk.core.orchestrator.context import ExecutionContext, _new_request_id

        ctx = ExecutionContext(
            request_id=_new_request_id(),
            started_at=time.time(),
            session_id=session_id,
            app_id=app_id,
        )
        _context_store.register(key, ctx)
    return ctx
