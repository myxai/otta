"""Security-mode definitions and default policy tables.

Four modes control what capabilities are available and what confirmation /
audit level is required.  The user switches modes via the UI; the active mode
is persisted in ``~/.nanobot/policy/mode.json``.

Architecture:
  - Global mode: the baseline for the entire system (levels 1-3 selectable
    by user; Developer requires system config).
  - Per-app mode: each app may declare its own mode *up to* Developer, but
    any mode **higher** than the global mode requires explicit user
    confirmation with risk acknowledgement.
  - Developer mode: can only be enabled through system config and MUST have
    an expiry policy (on_app_close | duration_24h | duration_1h).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Literal

from myxai_desk.core.storage.paths import SECURITY_MODE_FILE, POLICY_DIR, ensure_dir


# ── Mode enum ──────────────────────────────────────────────────────

class SecurityMode(str, Enum):
    OBSERVER = "Observer"
    ASSISTANT = "Assistant"
    OPERATOR = "Operator"
    DEVELOPER = "Developer"


MODE_ORDER: list[SecurityMode] = [
    SecurityMode.OBSERVER,
    SecurityMode.ASSISTANT,
    SecurityMode.OPERATOR,
    SecurityMode.DEVELOPER,
]

USER_SELECTABLE_MODES: list[SecurityMode] = [
    SecurityMode.OBSERVER,
    SecurityMode.ASSISTANT,
    SecurityMode.OPERATOR,
]


def mode_index(mode: SecurityMode) -> int:
    return MODE_ORDER.index(mode)


def is_escalation(target: SecurityMode, baseline: SecurityMode) -> bool:
    """True if *target* is a higher privilege level than *baseline*."""
    return mode_index(target) > mode_index(baseline)


# ── Per-mode policy table ──────────────────────────────────────────

@dataclass
class ModePolicy:
    fs_read: bool = True
    fs_write_scope: list[str] = field(default_factory=list)
    fs_write_system: bool = False
    proc_allowed: bool = False
    proc_whitelist: list[str] = field(default_factory=list)
    net_search_allowed: bool = True
    net_http_allowed: bool = False
    net_allowlist: list[str] = field(default_factory=list)
    net_exfiltration_allowed: bool = False
    mcp_allowed: bool = False
    mcp_server_allowlist: list[str] = field(default_factory=list)
    confirm_level: Literal["light", "standard", "strong"] = "standard"
    audit_level: Literal["full", "summary", "off"] = "full"
    undo_required: bool = True
    cooldown_seconds: int = 0


# ── Default policies per mode ──────────────────────────────────────

DEFAULT_POLICIES: dict[SecurityMode, ModePolicy] = {
    SecurityMode.OBSERVER: ModePolicy(
        fs_write_scope=["$WORKSPACE"],
        proc_allowed=False,
        net_search_allowed=True,
        net_http_allowed=False,
        mcp_allowed=False,
        confirm_level="light",
        undo_required=True,
    ),
    SecurityMode.ASSISTANT: ModePolicy(
        fs_write_scope=["$WORKSPACE", "$HOME/Documents", "$HOME/Desktop"],
        proc_allowed=True,
        proc_whitelist=["git", "python", "node", "npm", "pip", "code", "ls",
                        "dir", "cat", "type", "echo", "mkdir", "cp", "copy",
                        "mv", "move", "ren", "rename"],
        net_search_allowed=True,
        net_http_allowed=True,
        net_allowlist=["*"],
        mcp_allowed=True,
        confirm_level="standard",
        undo_required=True,
    ),
    SecurityMode.OPERATOR: ModePolicy(
        fs_write_scope=["$WORKSPACE", "$HOME"],
        fs_write_system=False,
        proc_allowed=True,
        proc_whitelist=[],
        net_search_allowed=True,
        net_http_allowed=True,
        net_allowlist=["*"],
        net_exfiltration_allowed=False,
        mcp_allowed=True,
        confirm_level="strong",
        undo_required=True,
        cooldown_seconds=5,
    ),
    SecurityMode.DEVELOPER: ModePolicy(
        fs_write_scope=["*"],
        fs_write_system=False,
        proc_allowed=True,
        proc_whitelist=[],
        net_search_allowed=True,
        net_http_allowed=True,
        net_allowlist=["*"],
        net_exfiltration_allowed=True,
        mcp_allowed=True,
        confirm_level="light",
        audit_level="full",
        undo_required=True,
    ),
}


# ── Runtime state ──────────────────────────────────────────────────

_current_mode: SecurityMode = SecurityMode.ASSISTANT


def get_current_mode() -> SecurityMode:
    return _current_mode


def set_current_mode(mode: SecurityMode) -> None:
    global _current_mode
    _current_mode = mode
    _persist_mode(mode)


def get_current_policy() -> ModePolicy:
    return DEFAULT_POLICIES[_current_mode]


def load_persisted_mode() -> SecurityMode:
    """Load mode from disk, falling back to ASSISTANT."""
    global _current_mode
    try:
        data = json.loads(SECURITY_MODE_FILE.read_text(encoding="utf-8"))
        _current_mode = SecurityMode(data.get("mode", "Assistant"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        _current_mode = SecurityMode.ASSISTANT
    return _current_mode


def _persist_mode(mode: SecurityMode) -> None:
    ensure_dir(SECURITY_MODE_FILE.parent)
    SECURITY_MODE_FILE.write_text(
        json.dumps({"mode": mode.value}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def mode_policy_as_dict(mode: SecurityMode | None = None) -> dict:
    """Serialise the policy for a given mode (default: current)."""
    m = mode or _current_mode
    return {"mode": m.value, "policy": asdict(DEFAULT_POLICIES[m])}


# ══════════════════════════════════════════════════════════════════
# Per-App Mode Override
# ══════════════════════════════════════════════════════════════════

_APP_MODES_FILE = POLICY_DIR / "app_modes.json"


def _load_app_modes() -> dict:
    if _APP_MODES_FILE.exists():
        try:
            return json.loads(_APP_MODES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_app_modes(data: dict) -> None:
    ensure_dir(POLICY_DIR)
    _APP_MODES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def get_app_mode(app_id: str) -> SecurityMode | None:
    """Return the per-app mode override, or None if not set."""
    data = _load_app_modes()
    entry = data.get(app_id)
    if not entry:
        return None
    try:
        return SecurityMode(entry.get("mode"))
    except (ValueError, TypeError):
        return None


def set_app_mode(app_id: str, mode: SecurityMode) -> None:
    """Set a per-app mode override."""
    data = _load_app_modes()
    data[app_id] = {
        "mode": mode.value,
        "set_at": time.time(),
        "confirmed": True,
    }
    _save_app_modes(data)


def clear_app_mode(app_id: str) -> None:
    data = _load_app_modes()
    data.pop(app_id, None)
    _save_app_modes(data)


def get_effective_mode(app_id: str = "") -> SecurityMode:
    """Return the effective mode for an app: per-app override or global.

    Also checks Dev mode expiry — if expired, falls back to global.
    """
    if app_id:
        app_mode = get_app_mode(app_id)
        if app_mode is not None:
            if app_mode == SecurityMode.DEVELOPER:
                if not is_dev_mode_valid():
                    clear_app_mode(app_id)
                    return get_current_mode()
            return app_mode
    global_mode = get_current_mode()
    if global_mode == SecurityMode.DEVELOPER and not is_dev_mode_valid():
        set_current_mode(SecurityMode.OPERATOR)
        return SecurityMode.OPERATOR
    return global_mode


def get_effective_policy(app_id: str = "") -> ModePolicy:
    """Return the policy for the effective mode of an app."""
    return DEFAULT_POLICIES[get_effective_mode(app_id)]


# ── Escalation assessment ──────────────────────────────────────────

def assess_escalation(app_id: str, target_mode: SecurityMode) -> dict:
    """Evaluate the risk of setting *target_mode* for *app_id*.

    Returns a dict with:
      - escalation: bool — whether this is an escalation
      - from_mode / to_mode: str
      - risk_level: "low" / "medium" / "high" / "critical"
      - warnings: list[str] — human-readable warnings
      - requires_confirm: bool
      - capabilities_gained: list[str] — new caps compared to global
    """
    global_mode = get_current_mode()
    esc = is_escalation(target_mode, global_mode)

    if not esc:
        return {
            "escalation": False,
            "from_mode": global_mode.value,
            "to_mode": target_mode.value,
            "risk_level": "low",
            "warnings": [],
            "requires_confirm": False,
            "capabilities_gained": [],
        }

    global_p = DEFAULT_POLICIES[global_mode]
    target_p = DEFAULT_POLICIES[target_mode]

    gained: list[str] = []
    warnings: list[str] = []

    if not global_p.proc_allowed and target_p.proc_allowed:
        gained.append("命令执行")
        warnings.append("应用将获得执行系统命令的能力，存在安全风险")
    if not global_p.net_http_allowed and target_p.net_http_allowed:
        gained.append("HTTP网络请求")
        warnings.append("应用将可以发起HTTP请求访问外部服务")
    if not global_p.mcp_allowed and target_p.mcp_allowed:
        gained.append("MCP工具调用")
        warnings.append("应用将可以调用MCP服务器提供的工具")
    if not global_p.net_exfiltration_allowed and target_p.net_exfiltration_allowed:
        gained.append("数据外传")
        warnings.append("应用将可以向外部发送数据，存在隐私泄露风险")
    if not global_p.fs_write_system and target_p.fs_write_system:
        gained.append("系统文件写入")
        warnings.append("应用将可以修改系统文件，存在高安全风险")

    target_scope = set(target_p.fs_write_scope) - set(global_p.fs_write_scope)
    if target_scope:
        gained.append(f"扩展写入范围: {', '.join(target_scope)}")

    diff = mode_index(target_mode) - mode_index(global_mode)
    if target_mode == SecurityMode.DEVELOPER:
        risk = "critical"
    elif diff >= 2:
        risk = "high"
    elif diff == 1:
        risk = "medium"
    else:
        risk = "low"

    return {
        "escalation": True,
        "from_mode": global_mode.value,
        "to_mode": target_mode.value,
        "risk_level": risk,
        "warnings": warnings,
        "requires_confirm": True,
        "capabilities_gained": gained,
    }


# ══════════════════════════════════════════════════════════════════
# Developer Mode — System Config Only + Expiry Policies
# ══════════════════════════════════════════════════════════════════

_DEV_MODE_FILE = POLICY_DIR / "dev_mode.json"

DEV_EXPIRY_POLICIES = {
    "on_app_close": "关闭应用后失效",
    "duration_1h": "1 小时后失效",
    "duration_24h": "24 小时后失效",
}


@dataclass
class DevModeConfig:
    enabled: bool = False
    expiry_policy: str = "on_app_close"
    activated_at: float = 0.0
    previous_mode: str = ""

    @property
    def is_expired(self) -> bool:
        if not self.enabled:
            return True
        if self.expiry_policy == "on_app_close":
            return False
        if self.expiry_policy == "duration_1h":
            return time.time() > self.activated_at + 3600
        if self.expiry_policy == "duration_24h":
            return time.time() > self.activated_at + 86400
        return False

    @property
    def expires_at(self) -> float | None:
        if not self.enabled:
            return None
        if self.expiry_policy == "duration_1h":
            return self.activated_at + 3600
        if self.expiry_policy == "duration_24h":
            return self.activated_at + 86400
        return None

    @property
    def remaining_seconds(self) -> float | None:
        ea = self.expires_at
        if ea is None:
            return None
        return max(0, ea - time.time())


def _load_dev_config() -> DevModeConfig:
    if _DEV_MODE_FILE.exists():
        try:
            d = json.loads(_DEV_MODE_FILE.read_text(encoding="utf-8"))
            return DevModeConfig(**{k: v for k, v in d.items()
                                    if k in DevModeConfig.__dataclass_fields__})
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return DevModeConfig()


def _save_dev_config(cfg: DevModeConfig) -> None:
    ensure_dir(POLICY_DIR)
    _DEV_MODE_FILE.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8",
    )


def is_dev_mode_valid() -> bool:
    """Check if Developer mode is enabled and not expired."""
    cfg = _load_dev_config()
    if not cfg.enabled:
        return False
    if cfg.is_expired:
        cfg.enabled = False
        _save_dev_config(cfg)
        return False
    return True


def enable_dev_mode(expiry_policy: str = "on_app_close") -> dict:
    """Enable Developer mode (system config only).

    Saves the current global mode so it can be restored on disable.
    Returns status dict for the API response.
    """
    if expiry_policy not in DEV_EXPIRY_POLICIES:
        return {"error": f"无效的失效策略: {expiry_policy}",
                "valid_policies": list(DEV_EXPIRY_POLICIES.keys())}

    current = get_current_mode()
    prev = current.value if current != SecurityMode.DEVELOPER else "Assistant"

    cfg = DevModeConfig(
        enabled=True,
        expiry_policy=expiry_policy,
        activated_at=time.time(),
        previous_mode=prev,
    )
    _save_dev_config(cfg)
    return {
        "success": True,
        "expiry_policy": expiry_policy,
        "expiry_label": DEV_EXPIRY_POLICIES[expiry_policy],
        "activated_at": cfg.activated_at,
        "expires_at": cfg.expires_at,
        "previous_mode": prev,
    }


def disable_dev_mode() -> dict:
    """Disable Developer mode and revert to the mode saved before enabling."""
    old_cfg = _load_dev_config()
    restore_mode_str = old_cfg.previous_mode or "Assistant"

    new_cfg = DevModeConfig(enabled=False)
    _save_dev_config(new_cfg)

    if get_current_mode() == SecurityMode.DEVELOPER:
        try:
            restore = SecurityMode(restore_mode_str)
        except ValueError:
            restore = SecurityMode.ASSISTANT
        if restore == SecurityMode.DEVELOPER:
            restore = SecurityMode.ASSISTANT
        set_current_mode(restore)

    return {"success": True, "reverted_to": get_current_mode().value}


def get_dev_mode_status() -> dict:
    """Return current Developer mode status."""
    cfg = _load_dev_config()
    return {
        "enabled": cfg.enabled and not cfg.is_expired,
        "expiry_policy": cfg.expiry_policy,
        "expiry_label": DEV_EXPIRY_POLICIES.get(cfg.expiry_policy, ""),
        "activated_at": cfg.activated_at,
        "expires_at": cfg.expires_at,
        "remaining_seconds": cfg.remaining_seconds,
        "is_expired": cfg.is_expired,
    }


# Eagerly load persisted mode on import
load_persisted_mode()
