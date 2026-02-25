"""Profile data access policy rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myxai_desk.core.policy.modes import ModePolicy


def evaluate(op: str, args: dict, policy: ModePolicy,
             app_source: str = "official") -> tuple[str, int, str]:
    """Evaluate profile capability access.

    Third-party apps never get raw history; only summaries.
    """
    if op == "get_summary":
        return "ALLOW", 0, "PROFILE_SUMMARY_ALLOWED"

    if op in ("get_raw_history", "get_events"):
        if app_source == "third_party":
            return "DENY", 80, "PROFILE_RAW_DENIED_THIRD_PARTY"
        if policy.confirm_level in ("standard", "strong"):
            return "REQUIRE_CONFIRM", 50, "PROFILE_RAW_NEEDS_CONFIRM"
        return "ALLOW", 30, "PROFILE_RAW_ALLOWED"

    if op == "update_preferences":
        if policy.confirm_level == "strong":
            return "REQUIRE_CONFIRM", 40, "PROFILE_UPDATE_CONFIRM"
        return "ALLOW", 20, "PROFILE_UPDATE_ALLOWED"

    return "ALLOW", 0, "PROFILE_DEFAULT"
