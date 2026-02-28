"""Replay validator — pre-execution safety and constraint checks.

Runs before any golden/template plan is replayed to ensure the plan
is still safe and applicable in the current context.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from myxai_desk.core.golden.models import ValidationResult

log = logging.getLogger("myxai")

# Tools considered high-risk by default
_DEFAULT_HIGH_RISK = {"exec"}

# Security mode ordering (higher index = more permissive)
_MODE_ORDER = ["observer", "assistant", "operator", "developer"]


def validate(
    plan_steps: list[dict],
    slot_values: dict[str, str],
    constraints: dict[str, Any] | None = None,
) -> ValidationResult:
    """Run all validation checks on a plan before replay.

    Checks (in order):
    1. Plan is non-empty
    2. Security mode meets minimum requirement
    3. Path slots reference valid locations
    4. Workspace restriction (if enabled)
    5. No high-risk tools unless security mode allows
    """
    constraints = constraints or {}

    if not plan_steps:
        return ValidationResult(ok=False, reason="empty plan")

    # Check 1: security mode minimum
    result = _check_security_mode(constraints)
    if not result.ok:
        return result

    # Check 2: path existence / validity
    result = _check_paths(slot_values, plan_steps)
    if not result.ok:
        return result

    # Check 3: workspace restriction
    result = _check_workspace_restriction(slot_values)
    if not result.ok:
        return result

    # Check 4: high-risk tool usage
    result = _check_high_risk_tools(plan_steps, constraints)
    if not result.ok:
        return result

    return ValidationResult(ok=True)


# ── Individual checks ────────────────────────────────────────────


def _check_security_mode(constraints: dict[str, Any]) -> ValidationResult:
    """Verify current security mode meets the minimum required by constraints."""
    min_mode = constraints.get("security_mode_min", "")
    if not min_mode:
        return ValidationResult(ok=True)

    try:
        from myxai_desk.core.policy.modes import get_current_mode
        current = get_current_mode().value.lower()
    except Exception:
        current = "assistant"

    min_idx = _mode_index(min_mode.lower())
    cur_idx = _mode_index(current)

    if cur_idx < min_idx:
        return ValidationResult(
            ok=False,
            reason=f"requires security mode >= {min_mode}, current is {current}",
        )
    return ValidationResult(ok=True)


def _check_paths(
    slot_values: dict[str, str],
    plan_steps: list[dict],
) -> ValidationResult:
    """Verify that path-type slot values point to valid locations.

    For read operations: target must exist.
    For write operations: parent directory must exist.
    """
    read_tools = {"read_file", "list_dir", "fs.count"}
    write_tools = {"write_file", "edit_file"}

    tool_names = {s.get("tool_name", s.get("tool", "")) for s in plan_steps}

    for name, value in slot_values.items():
        if not _looks_like_path(value):
            continue

        is_read = bool(tool_names & read_tools)
        is_write = bool(tool_names & write_tools)

        p = Path(value)
        if is_read and not p.exists():
            return ValidationResult(
                ok=False,
                reason=f"path does not exist: {value}",
            )
        if is_write and not p.parent.exists():
            return ValidationResult(
                ok=False,
                reason=f"parent directory does not exist: {p.parent}",
            )

    return ValidationResult(ok=True)


def _check_workspace_restriction(slot_values: dict[str, str]) -> ValidationResult:
    """If workspace restriction is enabled, verify paths are within workspace."""
    try:
        from myxai_desk.core.config_service import get_config
        cfg = get_config()
        if not cfg.get("restrict_workspace"):
            return ValidationResult(ok=True)
        workspace = cfg.get("workspace_dir", "")
        if not workspace:
            return ValidationResult(ok=True)
    except Exception:
        return ValidationResult(ok=True)

    ws = os.path.abspath(workspace).lower()
    for name, value in slot_values.items():
        if not _looks_like_path(value):
            continue
        abs_val = os.path.abspath(value).lower()
        if not abs_val.startswith(ws):
            return ValidationResult(
                ok=False,
                reason=f"path {value} is outside workspace {workspace}",
            )

    return ValidationResult(ok=True)


def _check_high_risk_tools(
    plan_steps: list[dict],
    constraints: dict[str, Any],
) -> ValidationResult:
    """Refuse high-risk tools unless security mode is Operator+."""
    try:
        from myxai_desk.core.intent_engine.config import get as ie_get
        high_risk = set(ie_get("high_risk_tools") or [])
    except Exception:
        high_risk = _DEFAULT_HIGH_RISK

    risky_in_plan = set()
    for step in plan_steps:
        tool = step.get("tool_name", step.get("tool", ""))
        if tool in high_risk:
            risky_in_plan.add(tool)

    if not risky_in_plan:
        return ValidationResult(ok=True)

    try:
        from myxai_desk.core.policy.modes import get_current_mode
        cur_idx = _mode_index(get_current_mode().value.lower())
    except Exception:
        cur_idx = 1  # default: assistant

    operator_idx = _mode_index("operator")
    if cur_idx < operator_idx:
        return ValidationResult(
            ok=False,
            reason=f"high-risk tools {risky_in_plan} require Operator mode or above",
        )

    return ValidationResult(ok=True)


# ── Helpers ──────────────────────────────────────────────────────


def _mode_index(mode: str) -> int:
    try:
        return _MODE_ORDER.index(mode)
    except ValueError:
        return 1  # default: assistant


def _looks_like_path(value: str) -> bool:
    """Heuristic check: does this value look like a file path?"""
    if not value:
        return False
    if value.startswith(("http://", "https://")):
        return False
    if len(value) < 2:
        return False
    # Windows drive letter or Unix absolute/home path
    if value[1] == ":" or value.startswith(("/", "~/")):
        return True
    return os.sep in value or "/" in value
