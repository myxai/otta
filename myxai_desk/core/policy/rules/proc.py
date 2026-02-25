"""Process / command execution policy rules.

Migrated from the original ``_DANGEROUS_CMD_PATTERNS`` +
``_check_dangerous_tool_call`` in app.py.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myxai_desk.core.policy.modes import ModePolicy

DANGEROUS_CMD_RE = re.compile(
    r"\b("
    r"rm\s|rm$|rmdir\s|rmdir$"
    r"|del\s|del$|erase\s|erase$"
    r"|remove-item\s|remove-item$"
    r"|shutil\.rmtree|os\.remove|os\.unlink|\.unlink\s*\("
    r"|unlink\s|unlink$"
    r"|rd\s|rd$|rd\s+/s"
    r"|format\s+[a-z]:"
    r"|empty.?trash|empty.?recycle|clear.?recycl"
    r"|清空回收站|清空垃圾箱"
    r"|mkfs\.|dd\s+if="
    r"|reg\s+delete|regedit"
    r"|net\s+stop|sc\s+delete|systemctl\s+stop"
    r"|chmod\s+000|icacls.*deny"
    r")\b",
    re.IGNORECASE,
)


def check_dangerous_command(args: dict) -> tuple[bool, str]:
    """Return ``(is_dangerous, reason)``."""
    args_str = str(args)
    if DANGEROUS_CMD_RE.search(args_str):
        return True, "destructive_command_pattern"

    for key in ("command", "cmd", "script", "code", "input"):
        val = args.get(key, "")
        if isinstance(val, str) and DANGEROUS_CMD_RE.search(val):
            return True, f"destructive_command_in_{key}"

    return False, ""


def evaluate(op: str, args: dict, policy: ModePolicy) -> tuple[str, int, str]:
    """Evaluate process capability against current mode policy.

    Returns ``(action, risk_score, reason_code)`` where action is one of
    ``"ALLOW"``, ``"REQUIRE_CONFIRM"``, ``"DENY"``.
    """
    if not policy.proc_allowed:
        return "DENY", 80, "PROC_NOT_ALLOWED_IN_MODE"

    dangerous, reason = check_dangerous_command(args)
    if dangerous:
        # Operator/Developer (proc_allowed, no whitelist): the LLM system
        # prompt already requires an execution-plan confirmation from the
        # user, so we ALLOW here to avoid a second popup confirmation.
        # Lower modes still hard-DENY.
        if not policy.proc_whitelist:
            return "ALLOW", 70, f"PROC_DANGEROUS_ALLOWED:{reason}"
        return "DENY", 100, f"PROC_DANGEROUS:{reason}"

    cmd = args.get("command", args.get("cmd", ""))
    if policy.proc_whitelist and cmd not in policy.proc_whitelist:
        return "REQUIRE_CONFIRM", 60, "PROC_NOT_IN_WHITELIST"

    if policy.confirm_level == "strong":
        return "ALLOW", 30, "PROC_STRONG_ALLOWED"

    return "ALLOW", 10, "PROC_ALLOWED"
