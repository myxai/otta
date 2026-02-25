"""Policy Engine — unified ``decide()`` entry point.

Every capability call MUST pass through ``decide()`` before execution.
The engine dispatches to capability-specific rule modules and assembles a
``Decision`` that the caller (orchestrator / runtime) acts upon.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from myxai_desk.core.policy.explain import explain as _explain
from myxai_desk.core.policy.modes import (
    ModePolicy,
    SecurityMode,
    get_current_mode,
    get_current_policy,
)
from myxai_desk.core.policy.rules import fs as _fs_rules
from myxai_desk.core.policy.rules import mcp as _mcp_rules
from myxai_desk.core.policy.rules import net as _net_rules
from myxai_desk.core.policy.rules import proc as _proc_rules
from myxai_desk.core.policy.rules import profile as _profile_rules


@dataclass
class Decision:
    action: Literal["ALLOW", "REQUIRE_CONFIRM", "REQUIRE_SANDBOX", "REQUIRE_COOLDOWN", "DENY"]
    risk: int  # 0-100
    reason_code: str
    explain: str
    evidence: dict[str, Any] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=dict)

    def is_allowed(self) -> bool:
        return self.action == "ALLOW"

    def to_dict(self) -> dict:
        return asdict(self)


# ── Capability → rule-module dispatch ──────────────────────────────

_RULE_DISPATCH: dict[str, Any] = {
    "fs": _fs_rules,
    "proc": _proc_rules,
    "net": _net_rules,
    "search": _net_rules,
    "mcp": _mcp_rules,
    "profile": _profile_rules,
}


def decide(
    app_id: str = "",
    source: str = "official",
    mode: SecurityMode | None = None,
    capability: str = "",
    op: str = "",
    args: dict | None = None,
    context: dict | None = None,
) -> Decision:
    """Central policy decision.

    Parameters
    ----------
    app_id : str
        Identifier of the Prompt App requesting the capability.
    source : str
        ``"official"`` / ``"user"`` / ``"third_party"``.
    mode : SecurityMode or None
        Override; defaults to the globally active mode.
    capability : str
        One of ``"fs"``, ``"proc"``, ``"net"``, ``"search"``, ``"mcp"``,
        ``"profile"``, etc.
    op : str
        Operation within the capability, e.g. ``"write_text"`` for fs.
    args : dict
        Arguments passed to the capability call.
    context : dict
        Additional runtime context (workspace path, session info, …).
    """
    args = args or {}
    context = context or {}
    current_mode = mode or get_current_mode()
    policy = get_current_policy() if mode is None else _policy_for(current_mode)

    rule_mod = _RULE_DISPATCH.get(capability)
    if rule_mod is None:
        return Decision(
            action="ALLOW",
            risk=0,
            reason_code="NO_RULE_MODULE",
            explain="",
        )

    # Special handling: search is routed through net rules with op="search"
    if capability == "search":
        op = "search"

    # Profile rules need app source
    if capability == "profile":
        action, risk, reason = rule_mod.evaluate(
            op,
            args,
            policy,
            app_source=source,
        )
    elif capability == "fs":
        action, risk, reason = rule_mod.evaluate(
            op,
            args,
            policy,
            workspace=context.get("workspace"),
        )
    else:
        action, risk, reason = rule_mod.evaluate(op, args, policy)

    # Source-based escalation: third-party apps get stricter treatment
    if source == "third_party" and action == "ALLOW" and risk > 30:
        action = "REQUIRE_CONFIRM"
        reason = f"THIRD_PARTY_ESCALATION:{reason}"

    explanation = _explain(reason)
    evidence = {
        "mode": current_mode.value,
        "capability": capability,
        "op": op,
        "app_id": app_id,
        "source": source,
        "matched_rule": reason,
    }
    ui = {}
    if action == "REQUIRE_CONFIRM":
        ui["confirm_required"] = True
        ui["confirm_prompt"] = explanation
    if action == "REQUIRE_COOLDOWN":
        ui["cooldown_seconds"] = policy.cooldown_seconds

    # REQUIRE_CONFIRM only in Operator mode; other modes auto-resolve.
    if action == "REQUIRE_CONFIRM" and current_mode != SecurityMode.OPERATOR:
        action = "ALLOW"
        reason = f"AUTO_APPROVED:{reason}"
        ui.pop("confirm_required", None)
        ui.pop("confirm_prompt", None)

    return Decision(
        action=action,
        risk=risk,
        reason_code=reason,
        explain=explanation,
        evidence=evidence,
        ui=ui,
    )


def _policy_for(mode: SecurityMode) -> ModePolicy:
    from myxai_desk.core.policy.modes import DEFAULT_POLICIES

    return DEFAULT_POLICIES[mode]
