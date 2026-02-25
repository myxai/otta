"""Undo system — reversible action log with cooldown support.

Each capability that supports undo registers a reverse operation after
execution.  The user can undo within the cooldown window, or explicitly
at any time from the "recent actions" list.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock

from myxai_desk.core.storage.paths import AUDIT_DIR, ensure_dir

_UNDO_FILE = AUDIT_DIR / "undo_log.json"


@dataclass
class UndoAction:
    action_id: str
    capability: str
    op: str
    data: dict
    ts: float
    cooldown_until: float = 0.0
    undone: bool = False


class UndoRegistry:
    """Manages reversible actions and their undo operations."""

    def __init__(self):
        self._actions: dict[str, UndoAction] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        if _UNDO_FILE.exists():
            try:
                raw = json.loads(_UNDO_FILE.read_text(encoding="utf-8"))
                for item in raw:
                    a = UndoAction(**item)
                    self._actions[a.action_id] = a
            except (json.JSONDecodeError, OSError, TypeError):
                pass

    def _save(self) -> None:
        ensure_dir(_UNDO_FILE.parent)
        data = [asdict(a) for a in self._actions.values()]
        # Keep only the last 500 actions
        data = data[-500:]
        _UNDO_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def register(
        self, action_id: str, capability: str, op: str, data: dict, *, cooldown_seconds: int = 0
    ) -> None:
        """Register a reversible action."""
        with self._lock:
            now = time.time()
            self._actions[action_id] = UndoAction(
                action_id=action_id,
                capability=capability,
                op=op,
                data=data,
                ts=now,
                cooldown_until=now + cooldown_seconds if cooldown_seconds else 0,
            )
            self._save()

    def undo(self, action_id: str) -> dict:
        """Execute the reverse operation for *action_id*.

        Returns ``{"success": True, ...}`` or ``{"error": ...}``.
        """
        with self._lock:
            action = self._actions.get(action_id)
            if not action:
                return {"error": f"Action not found: {action_id}"}
            if action.undone:
                return {"error": f"Already undone: {action_id}"}

        try:
            result = self._execute_reverse(action)
            with self._lock:
                action.undone = True
                self._save()
            return {"success": True, "action_id": action_id, "detail": result}
        except Exception as e:
            return {"error": str(e)}

    def _execute_reverse(self, action: UndoAction) -> str:
        """Perform the actual reverse operation."""
        cap = action.capability
        op = action.op
        data = action.data

        if cap == "fs" and op == "write_text":
            path = Path(data["path"])
            if data.get("existed") and data.get("old_content") is not None:
                path.write_text(data["old_content"], encoding="utf-8")
                return f"Restored previous content of {path}"
            elif not data.get("existed"):
                if path.exists():
                    from myxai_desk.core.capabilities.fs import _trash_dest

                    dest = _trash_dest(path)
                    shutil.move(str(path), str(dest))
                    return f"Moved newly-created file to trash: {dest}"
            return "No reverse action available"

        if cap == "fs" and op == "move":
            src = Path(data["src"])
            dst = Path(data["dst"])
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                return f"Moved back: {src} -> {dst}"
            return "Source no longer exists; cannot reverse"

        if cap == "fs" and op == "copy":
            created = Path(data["created"])
            if created.exists():
                from myxai_desk.core.capabilities.fs import _trash_dest

                dest = _trash_dest(created)
                shutil.move(str(created), str(dest))
                return f"Removed copy to trash: {dest}"
            return "Copied file no longer exists"

        if cap == "fs" and op == "remove":
            trash_path = Path(data["trash_path"])
            original = Path(data["original_path"])
            if trash_path.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(trash_path), str(original))
                return f"Restored from trash: {original}"
            return "Trash file not found; cannot restore"

        return f"No undo handler for {cap}.{op}"

    def list_actions(self, *, limit: int = 50, undoable_only: bool = False) -> list[dict]:
        """Return recent actions, newest first."""
        with self._lock:
            actions = sorted(
                self._actions.values(),
                key=lambda a: a.ts,
                reverse=True,
            )
            if undoable_only:
                actions = [a for a in actions if not a.undone]
            return [asdict(a) for a in actions[:limit]]

    def is_in_cooldown(self, action_id: str) -> bool:
        action = self._actions.get(action_id)
        if not action:
            return False
        return time.time() < action.cooldown_until


# Global registry instance
_registry = UndoRegistry()


def get_undo_registry() -> UndoRegistry:
    """Get the global undo registry."""
    return _registry
