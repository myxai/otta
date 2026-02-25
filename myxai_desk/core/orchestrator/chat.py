"""Chat orchestration — governance-aware wrapper around nanobot's agent loop.

This module does NOT replace nanobot's LLM orchestration.  Instead, it
provides higher-level hooks that app.py can call to add governance
concerns around the chat flow:

  1. Pre-processing: enrich the user message with profile context
  2. Tool-call interception: delegate to Policy Engine (already in app.py)
  3. Post-processing: record to audit + profile event store
  4. History compression awareness

The actual LLM <-> tool-call loop remains inside nanobot's AgentLoop.
"""

from __future__ import annotations

from typing import Any


def enrich_with_profile(message: str, *, max_tokens: int = 500) -> str:
    """No-op — persona is never injected into regular conversations.

    Persona data is only used explicitly in daily digest explore prompts,
    controlled by the user's privacy settings.
    """
    return message


def record_chat_event(role: str, content: str, session_id: str = "") -> None:
    """Record a chat message to the profile event store."""
    try:
        from myxai_desk.core.profile.events import EventStore, ChatMessage
        import hashlib
        import time
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        event = ChatMessage(
            role=role,
            text_digest=digest,
            ts=str(time.time()),
            session=session_id,
        )
        store = EventStore()
        store.append(event)
    except Exception:
        pass


def build_system_context(mode: str = "", workspace: str = "") -> str:
    """Build additional system context reflecting the current governance state."""
    parts = []
    if mode:
        parts.append(f"当前安全模式: {mode}")

    try:
        from myxai_desk.core.policy.modes import get_current_mode, get_current_policy
        m = get_current_mode()
        p = get_current_policy()
        parts.append(f"安全模式: {m.value}")
        if not p.proc_allowed:
            parts.append("注意: 当前模式禁止执行命令")
        if not p.net_http_allowed:
            parts.append("注意: 当前模式禁止 HTTP 请求")
    except Exception:
        pass

    if workspace:
        parts.append(f"工作区: {workspace}")

    return "\n".join(parts) if parts else ""
