"""Plan generation, risk analysis, and user-confirmation flow.

When a tool call receives ``REQUIRE_CONFIRM`` from the Policy Engine, the
action is stored as a *pending action* rather than being immediately blocked.
The frontend renders a confirmation dialog; once the user approves (or
rejects), the action is executed (or discarded).

Flow:
    Policy → REQUIRE_CONFIRM → store_pending() → frontend dialog
    User clicks Confirm → confirm_pending() → nanobot tools.execute()
    User clicks Reject  → reject_pending()  → discard
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Any, Literal

from myxai_desk.core.storage.paths import AUDIT_DIR, ensure_dir

_PENDING_FILE = AUDIT_DIR / "pending_actions.json"


@dataclass
class PendingAction:
    action_id: str
    tool_name: str
    tool_args: dict
    capability: str
    op: str
    risk: int
    explain: str
    evidence: dict = field(default_factory=dict)
    ui: dict = field(default_factory=dict)
    created_at: float = 0.0
    status: Literal["pending", "confirmed", "rejected", "expired"] = "pending"
    result: Any = None
    ttl_seconds: int = 300

    @property
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_seconds


@dataclass
class ExecutionPlan:
    """A structured execution plan for multi-step operations."""

    plan_id: str
    steps: list[dict] = field(default_factory=list)
    total_risk: int = 0
    affected_scope: str = ""
    reversible: bool = True
    requires_confirm: bool = False

    def add_step(
        self, description: str, capability: str, op: str, risk: int, reversible: bool = True
    ) -> None:
        self.steps.append(
            {
                "index": len(self.steps) + 1,
                "description": description,
                "capability": capability,
                "op": op,
                "risk": risk,
                "reversible": reversible,
            }
        )
        self.total_risk = max(self.total_risk, risk)
        if not reversible:
            self.reversible = False
        if risk > 40:
            self.requires_confirm = True


class PlanConfirmationManager:
    """Manages pending actions that require user confirmation."""

    def __init__(self):
        self._pending: dict[str, PendingAction] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        if _PENDING_FILE.exists():
            try:
                raw = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
                for item in raw:
                    pa = PendingAction(**item)
                    if not pa.is_expired and pa.status == "pending":
                        self._pending[pa.action_id] = pa
            except (json.JSONDecodeError, OSError, TypeError):
                pass

    def _save(self) -> None:
        ensure_dir(_PENDING_FILE.parent)
        active = [a for a in self._pending.values() if not a.is_expired]
        data = [asdict(a) for a in active]
        _PENDING_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def store_pending(
        self,
        tool_name: str,
        tool_args: dict,
        capability: str,
        op: str,
        risk: int,
        explain: str,
        evidence: dict | None = None,
        ui: dict | None = None,
    ) -> str:
        """Store a pending action that requires confirmation.

        Returns the ``action_id`` for the frontend to reference.
        """
        action_id = f"pend_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._pending[action_id] = PendingAction(
                action_id=action_id,
                tool_name=tool_name,
                tool_args=tool_args,
                capability=capability,
                op=op,
                risk=risk,
                explain=explain,
                evidence=evidence or {},
                ui=ui or {},
                created_at=time.time(),
            )
            self._save()
        return action_id

    def get_pending(self, action_id: str) -> PendingAction | None:
        with self._lock:
            pa = self._pending.get(action_id)
            if pa and pa.is_expired:
                pa.status = "expired"
                self._save()
                return None
            return pa

    def confirm_pending(self, action_id: str) -> PendingAction | None:
        """Mark a pending action as confirmed. Returns the action for execution."""
        with self._lock:
            pa = self._pending.get(action_id)
            if not pa or pa.status != "pending" or pa.is_expired:
                return None
            pa.status = "confirmed"
            self._save()
            return pa

    def reject_pending(self, action_id: str) -> bool:
        with self._lock:
            pa = self._pending.get(action_id)
            if not pa or pa.status != "pending":
                return False
            pa.status = "rejected"
            self._save()
            return True

    def list_pending(self) -> list[dict]:
        """Return all non-expired pending actions."""
        with self._lock:
            result = []
            for pa in self._pending.values():
                if pa.is_expired and pa.status == "pending":
                    pa.status = "expired"
                if pa.status == "pending":
                    result.append(asdict(pa))
            self._save()
            return result

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        with self._lock:
            before = len(self._pending)
            self._pending = {
                k: v for k, v in self._pending.items() if not v.is_expired or v.status != "pending"
            }
            self._save()
            return before - len(self._pending)


# Singleton
_manager: PlanConfirmationManager | None = None


def get_plan_manager() -> PlanConfirmationManager:
    global _manager
    if _manager is None:
        _manager = PlanConfirmationManager()
    return _manager


def analyze_risk(capability: str, op: str, args: dict) -> dict:
    """Quick risk analysis summary for a single tool call."""
    risk_factors = []
    risk_score = 0

    if capability == "fs":
        if op in ("write_text", "write", "create"):
            risk_score += 20
            risk_factors.append("file_write")
        if op in ("remove", "delete"):
            risk_score += 40
            risk_factors.append("file_delete")
        if op in ("move", "rename"):
            risk_score += 30
            risk_factors.append("file_move")

    elif capability == "proc":
        risk_score += 50
        risk_factors.append("command_execution")
        cmd = args.get("command", "")
        if any(p in cmd for p in ("rm ", "del ", "format ", "mkfs")):
            risk_score += 30
            risk_factors.append("destructive_command")

    elif capability == "net":
        risk_score += 20
        risk_factors.append("network_access")
        if op in ("http_post", "upload"):
            risk_score += 20
            risk_factors.append("data_exfiltration_risk")

    elif capability == "mcp":
        risk_score += 30
        risk_factors.append("mcp_tool_call")

    return {
        "risk_score": min(100, risk_score),
        "risk_factors": risk_factors,
        "reversible": capability == "fs" and op != "remove",
    }
