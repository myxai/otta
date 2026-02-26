"""Safe file-system operations — compatibility shim.

This module delegates to ``myxai_desk.core.capabilities.fs`` and
``myxai_desk.core.policy.rules.fs`` for the canonical implementations.
All apps that import ``from apps.safe_fs import safe_remove`` continue
to work without changes.

All "remove" operations move items to ``~/.nanobot/trash/`` — NO real
deletion, ever.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path

try:
    from myxai_desk.core.timeutil import local_datetime_str
except ImportError:
    from datetime import datetime, timedelta, timezone
    _LOCAL_TZ = timezone(timedelta(hours=8))
    
    def local_datetime_str(dt=None, fmt="%Y%m%d_%H%M%S"):
        return datetime.now(_LOCAL_TZ).strftime(fmt)

try:
    from myxai_desk.core.storage.paths import TRASH_DIR, ensure_dir
except ImportError:
    TRASH_DIR = Path.home() / ".nanobot" / "trash"

    def ensure_dir(p: Path) -> Path:
        p.mkdir(parents=True, exist_ok=True)
        return p


# ── Delegate to myxai_desk where possible ─────────────────────────


def is_safe_path(path: str | Path) -> tuple[bool, str]:
    """Validate that a path is safe for archive/move operations."""
    try:
        from myxai_desk.core.policy.rules.fs import is_safe_path as _is_safe

        return _is_safe(path)
    except ImportError:
        pass
    p = Path(path).resolve()
    if p == p.anchor or str(p) == p.drive + os.sep:
        return False, "root/drive-root directory operations are forbidden"
    return True, ""


def check_same_drive(src: str | Path, dest: str | Path) -> tuple[bool, str]:
    """Ensure source and destination are on the same drive/mount."""
    s = Path(src).resolve()
    d = Path(dest).resolve()
    if sys.platform == "win32":
        if s.drive.upper() != d.drive.upper():
            return False, f"cross-disk move forbidden: {s.drive} → {d.drive}"
    else:
        try:
            if os.stat(s.parent).st_dev != os.stat(d.parent).st_dev:
                return False, "cross-filesystem move forbidden"
        except OSError:
            pass
    return True, ""


def _trash_dest(original: Path) -> Path:
    ensure_dir(TRASH_DIR)
    ts = local_datetime_str()
    unique = uuid.uuid4().hex[:6]
    return TRASH_DIR / f"{ts}_{unique}_{original.name}"


def safe_remove(path: Path | str) -> Path | None:
    """Move a file or directory to the trash folder instead of deleting.

    Also logs to the audit ledger when myxai_desk is available.
    """
    p = Path(path)
    if not p.exists():
        return None
    dest = _trash_dest(p)
    shutil.move(str(p), str(dest))
    try:
        from myxai_desk.core.audit.ledger import AuditLedger

        AuditLedger().append_entry(
            capability="fs.safe_remove",
            args={"path": str(p), "trash": str(dest)},
            action_id="",
            result_summary=f"moved to trash: {dest.name}",
        )
    except Exception:
        pass
    return dest


def safe_remove_empty_dir(directory: Path | str) -> None:
    """Move empty directories to trash, climbing up but stopping at the
    first non-empty ancestor.
    """
    d = Path(directory)
    while d.exists() and d.is_dir() and not any(d.iterdir()):
        safe_remove(d)
        d = d.parent
