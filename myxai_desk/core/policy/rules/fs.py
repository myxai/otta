"""File-system policy rules.

Migrated from ``apps/safe_fs.py`` path-safety checks and extended with
mode-aware write-scope enforcement.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myxai_desk.core.policy.modes import ModePolicy

# ── System directory protection (from safe_fs.py) ─────────────────

_SYSTEM_DIRS_WIN = {
    "windows", "program files", "program files (x86)", "programdata",
    "system volume information", "$recycle.bin", "recovery",
    "boot", "perflogs",
}
_SYSTEM_DIRS_UNIX = {
    "/usr", "/etc", "/bin", "/sbin", "/lib", "/lib64",
    "/boot", "/proc", "/sys", "/dev", "/var", "/root",
    "/snap", "/opt",
}


def is_safe_path(path: str | Path) -> tuple[bool, str]:
    """Check if *path* is safe for write/move operations."""
    p = Path(path).resolve()

    if p == p.anchor or str(p) == p.drive + os.sep:
        return False, "root/drive-root directory operations are forbidden"

    if len(p.parts) <= 2 and sys.platform == "win32":
        return False, "top-level drive directory operations are forbidden"

    name_lower = p.name.lower()
    if sys.platform == "win32":
        if name_lower in _SYSTEM_DIRS_WIN:
            return False, f"system directory '{p.name}' is protected"
        for part in p.parts:
            if part.lower() in _SYSTEM_DIRS_WIN:
                return False, f"path contains system directory '{part}'"
    else:
        p_str = str(p)
        for sd in _SYSTEM_DIRS_UNIX:
            if p_str == sd or p_str.startswith(sd + "/"):
                return False, f"system directory '{sd}' is protected"

    return True, ""


def _resolve_scope(scope_patterns: list[str], workspace: str | None = None) -> list[Path]:
    """Expand ``$WORKSPACE`` / ``$HOME`` / ``*`` in scope patterns."""
    resolved: list[Path] = []
    for pattern in scope_patterns:
        if pattern == "*":
            return []  # empty list == everything allowed
        expanded = pattern.replace("$HOME", str(Path.home()))
        if workspace:
            expanded = expanded.replace("$WORKSPACE", workspace)
        else:
            expanded = expanded.replace("$WORKSPACE", str(Path.cwd()))
        resolved.append(Path(expanded).resolve())
    return resolved


def _path_in_scope(target: Path, scope: list[Path]) -> bool:
    """Return True if *target* is under one of the *scope* directories."""
    if not scope:
        return True  # empty scope == wildcard
    target = target.resolve()
    return any(
        target == s or s in target.parents or target == s
        for s in scope
    )


def evaluate(op: str, args: dict, policy: ModePolicy,
             workspace: str | None = None) -> tuple[str, int, str]:
    """Evaluate a filesystem operation against current mode policy.

    Returns ``(action, risk_score, reason_code)``.
    """
    path_str = args.get("path", args.get("src", args.get("destination", "")))
    if not path_str:
        return "ALLOW", 0, "FS_NO_PATH"

    target = Path(path_str).resolve()

    safe, reason = is_safe_path(target)
    if not safe:
        return "DENY", 100, f"FS_UNSAFE_PATH:{reason}"

    if op in ("read_text", "list_dir", "read"):
        return "ALLOW", 0, "FS_READ_ALLOWED"

    # Write operations
    if not policy.fs_write_system:
        safe_sys, sys_reason = is_safe_path(target)
        if not safe_sys:
            return "DENY", 90, f"FS_SYSTEM_WRITE_BLOCKED:{sys_reason}"

    scope = _resolve_scope(policy.fs_write_scope, workspace)
    if scope and not _path_in_scope(target, scope):
        return "DENY", 70, "FS_OUT_OF_WRITE_SCOPE"

    if op == "remove":
        if policy.confirm_level == "standard":
            return "REQUIRE_CONFIRM", 50, "FS_REMOVE_NEEDS_CONFIRM"
        # strong (Operator) and light (Observer/Developer): allow directly.
        # Operator gets plan confirmation from the LLM prompt instead of a
        # double confirm; actual deletion uses move-to-trash (safe_fs).
        return "ALLOW", 30, "FS_REMOVE_TO_TRASH"

    if op in ("write_text", "move", "copy"):
        if policy.confirm_level == "strong":
            return "REQUIRE_CONFIRM", 40, "FS_WRITE_STRONG_CONFIRM"
        return "ALLOW", 20, "FS_WRITE_ALLOWED"

    return "ALLOW", 10, "FS_DEFAULT_ALLOW"
