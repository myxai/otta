"""Post-execution governance hooks for nanobot tool calls.

This module does NOT replace nanobot's tool execution.  Instead, it runs
**after** ``agent.tools.execute()`` to record audit entries and register
undo actions.  The relationship is:

    Policy.decide()  →  nanobot tools.execute()  →  governance hooks
    (pre-execution)      (nanobot does the work)     (post-execution)
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

# Lazy singletons — created on first use, then reused.
_audit_ledger = None
_undo_registry = None


def _get_audit():
    global _audit_ledger
    if _audit_ledger is None:
        from myxai_desk.core.audit.ledger import AuditLedger

        _audit_ledger = AuditLedger()
    return _audit_ledger


def _get_undo():
    global _undo_registry
    if _undo_registry is None:
        from myxai_desk.core.audit.undo import UndoRegistry

        _undo_registry = UndoRegistry()
    return _undo_registry


def _new_action_id() -> str:
    return f"act_{uuid.uuid4().hex[:12]}"


def _digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Post-execution audit ──────────────────────────────────────────


def post_execution_audit(
    capability: str,
    op: str,
    args: dict,
    result: Any,
    decision: Any,
) -> None:
    """Record an audit entry after nanobot finishes a tool call."""
    try:
        ledger = _get_audit()
        ledger.append_entry(
            capability=f"{capability}.{op}" if op else capability,
            args=args,
            action_id="",
            result_summary=str(result)[:200] if result else "",
        )
    except Exception as e:
        print(f"[governance] audit error: {e}")


# ── Post-execution undo registration ──────────────────────────────

# Tool argument keys that typically contain file paths
_PATH_KEYS = ("path", "file_path", "destination", "target", "filename", "src", "dst")

# nanobot tool names → (capability, operation) for undo classification
_WRITE_TOOL_PATTERNS = re.compile(
    r"(write_file|create_file|file_write|save_file)",
    re.I,
)
_MOVE_TOOL_PATTERNS = re.compile(
    r"(move_file|rename_file|file_move|file_rename)",
    re.I,
)
_REMOVE_TOOL_PATTERNS = re.compile(
    r"(remove_file|delete_file|file_delete)",
    re.I,
)


def _extract_path(args: dict) -> str:
    """Best-effort extraction of a file path from tool arguments."""
    for key in _PATH_KEYS:
        val = args.get(key)
        if val and isinstance(val, str):
            return val
    return ""


def post_execution_undo(
    capability: str,
    op: str,
    args: dict,
    result: Any,
    cooldown_seconds: int = 0,
) -> None:
    """Register an undo action after nanobot finishes a tool call.

    Only file-system mutations are undoable.  Command execution and search
    calls are logged for audit but cannot be reversed.
    """
    if capability != "fs":
        return

    try:
        undo = _get_undo()
        action_id = _new_action_id()
        path_str = _extract_path(args)

        if op in ("write_text", "write", "create"):
            undo.register(
                action_id,
                "fs",
                "write_text",
                {
                    "path": path_str,
                    "existed": True,
                    "old_content": None,
                    "note": "Written by nanobot tool; original content not captured by governance layer.",
                },
                cooldown_seconds=cooldown_seconds,
            )

        elif op in ("move", "rename"):
            src = args.get("src", args.get("source", args.get("path", "")))
            dst = args.get("dst", args.get("destination", args.get("new_path", "")))
            if src and dst:
                undo.register(
                    action_id,
                    "fs",
                    "move",
                    {
                        "src": dst,
                        "dst": src,
                    },
                    cooldown_seconds=cooldown_seconds,
                )

        elif op in ("remove", "delete"):
            # nanobot's file tools go through safe_fs which moves to trash,
            # so we record the original path for potential restore.
            undo.register(
                action_id,
                "fs",
                "remove",
                {
                    "original_path": path_str,
                    "trash_path": "",
                    "note": "Moved to trash by nanobot; check ~/.nanobot/trash/",
                },
                cooldown_seconds=cooldown_seconds,
            )

    except Exception as e:
        print(f"[governance] undo registration error: {e}")
