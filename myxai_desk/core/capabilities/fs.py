"""File-system capability — governance wrapper + standalone fallback.

Architecture note
-----------------
In the normal Agent loop, file operations are executed by **nanobot's built-in
tools** (``agent.tools.execute``).  The governance layer in
``governance.py`` handles post-execution audit and undo registration.

This module provides a **standalone FS implementation** used only when:
  - A Prompt App runs outside the nanobot Agent loop (``app_runtime.py``)
  - Unit tests need a self-contained FS with audit/undo

It is NOT a replacement for nanobot's file tools.
"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from myxai_desk.core.policy.rules.fs import is_safe_path
from myxai_desk.core.storage.paths import TRASH_DIR, ensure_dir

_LOCAL_TZ = timezone(timedelta(hours=8))
_BACKUP_SUFFIX = ".myxai_bak"


# ── ActionId helper ────────────────────────────────────────────────


def _new_action_id() -> str:
    return f"act_{uuid.uuid4().hex[:12]}"


# ── Trash helpers (from safe_fs.py) ────────────────────────────────


def _trash_dest(original: Path) -> Path:
    ensure_dir(TRASH_DIR)
    ts = datetime.now(_LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
    unique = uuid.uuid4().hex[:6]
    return TRASH_DIR / f"{ts}_{unique}_{original.name}"


# ── FS Capability ──────────────────────────────────────────────────


class FS:
    """Standalone auditable FS capability (fallback for Prompt App runtime).

    In the Agent loop, nanobot's own file tools are used instead.
    See ``governance.py`` for the post-execution governance hooks that apply
    to nanobot tool calls.
    """

    def __init__(self, *, undo_registry: Any = None, audit_ledger: Any = None):
        self._undo = undo_registry
        self._audit = audit_ledger

    # -- read operations (no side-effects) --

    def read_text(self, path: str | Path, *, max_bytes: int = 2_000_000) -> str:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        size = p.stat().st_size
        if size > max_bytes:
            raise ValueError(f"File too large: {size} bytes (max {max_bytes})")
        return p.read_text(encoding="utf-8")

    def list_dir(self, path: str | Path, *, depth: int = 1) -> list[dict]:
        p = Path(path)
        if not p.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        entries = []
        for item in sorted(p.iterdir()):
            entry = {
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            }
            if item.is_dir() and depth > 1:
                entry["children"] = self.list_dir(item, depth=depth - 1)
            entries.append(entry)
        return entries

    # -- write operations (side-effects, require audit + undo) --

    def write_text(
        self, path: str | Path, content: str, *, atomic: bool = True, backup: bool = True
    ) -> str:
        """Write text to *path* atomically; back up the previous version.

        Returns an ``ActionId``.
        """
        p = Path(path).resolve()
        safe, reason = is_safe_path(p)
        if not safe:
            raise PermissionError(f"Unsafe path: {reason}")

        action_id = _new_action_id()
        old_content: str | None = None
        existed = p.exists()

        if existed and backup:
            old_content = p.read_text(encoding="utf-8")

        p.parent.mkdir(parents=True, exist_ok=True)

        if atomic:
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            if os.name == "nt":
                if p.exists():
                    os.replace(str(tmp), str(p))
                else:
                    tmp.rename(p)
            else:
                os.replace(str(tmp), str(p))
        else:
            p.write_text(content, encoding="utf-8")

        self._register_undo(
            action_id,
            "write_text",
            {
                "path": str(p),
                "existed": existed,
                "old_content": old_content,
            },
        )
        self._log_audit("fs.write_text", {"path": str(p)}, action_id)
        return action_id

    def move(self, src: str | Path, dst: str | Path) -> str:
        s = Path(src).resolve()
        d = Path(dst).resolve()
        safe_s, reason_s = is_safe_path(s)
        safe_d, reason_d = is_safe_path(d)
        if not safe_s:
            raise PermissionError(f"Unsafe source: {reason_s}")
        if not safe_d:
            raise PermissionError(f"Unsafe destination: {reason_d}")
        if not s.exists():
            raise FileNotFoundError(f"Source not found: {src}")

        action_id = _new_action_id()
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))

        self._register_undo(
            action_id,
            "move",
            {
                "src": str(d),
                "dst": str(s),
            },
        )
        self._log_audit("fs.move", {"src": str(s), "dst": str(d)}, action_id)
        return action_id

    def copy(self, src: str | Path, dst: str | Path) -> str:
        s = Path(src).resolve()
        d = Path(dst).resolve()
        safe_d, reason_d = is_safe_path(d)
        if not safe_d:
            raise PermissionError(f"Unsafe destination: {reason_d}")
        if not s.exists():
            raise FileNotFoundError(f"Source not found: {src}")

        action_id = _new_action_id()
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(str(s), str(d))
        else:
            shutil.copy2(str(s), str(d))

        self._register_undo(action_id, "copy", {"created": str(d)})
        self._log_audit("fs.copy", {"src": str(s), "dst": str(d)}, action_id)
        return action_id

    def remove(self, path: str | Path) -> str:
        """Move to trash instead of deleting (zero-deletion)."""
        p = Path(path).resolve()
        safe, reason = is_safe_path(p)
        if not safe:
            raise PermissionError(f"Unsafe path: {reason}")
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        action_id = _new_action_id()
        dest = _trash_dest(p)
        shutil.move(str(p), str(dest))

        self._register_undo(
            action_id,
            "remove",
            {
                "trash_path": str(dest),
                "original_path": str(p),
            },
        )
        self._log_audit("fs.remove", {"path": str(p), "trash": str(dest)}, action_id)
        return action_id

    # -- internal helpers --

    def _register_undo(self, action_id: str, op: str, data: dict) -> None:
        if self._undo:
            self._undo.register(action_id, "fs", op, data)

    def _log_audit(self, capability_op: str, args: dict, action_id: str) -> None:
        if self._audit:
            self._audit.append_entry(
                capability=capability_op,
                args=args,
                action_id=action_id,
            )
