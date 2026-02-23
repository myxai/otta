"""Safe file-system operations — NO real deletion, ever.

All "remove" operations move items to a timestamped trash directory under
``~/.nanobot/trash/``.  This ensures complete recoverability and enforces the
project-wide rule that no file or directory may be permanently deleted.

Path safety rules enforced here:
  - No cross-disk moves
  - No system directory access
  - No root / drive-root directory operations
"""

import os
import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_LOCAL_TZ = timezone(timedelta(hours=8))
_TRASH_DIR = Path.home() / ".nanobot" / "trash"

# ── Path safety ───────────────────────────────────────────────────────

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
    """Validate that a path is safe for archive/move operations.

    Returns (True, "") if safe, or (False, reason) if blocked.
    """
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


def check_same_drive(src: str | Path, dest: str | Path) -> tuple[bool, str]:
    """Ensure source and destination are on the same drive/mount.

    Returns (True, "") if same drive, or (False, reason) if cross-disk.
    """
    s = Path(src).resolve()
    d = Path(dest).resolve()
    if sys.platform == "win32":
        if s.drive.upper() != d.drive.upper():
            return False, (f"cross-disk move forbidden: "
                           f"{s.drive} → {d.drive}")
    else:
        try:
            if os.stat(s.parent).st_dev != os.stat(d.parent).st_dev:
                return False, "cross-filesystem move forbidden"
        except OSError:
            pass
    return True, ""


def _trash_dest(original: Path) -> Path:
    """Build a unique path inside the trash directory."""
    _TRASH_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(_LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
    unique = uuid.uuid4().hex[:6]
    return _TRASH_DIR / f"{ts}_{unique}_{original.name}"


def safe_remove(path: Path | str) -> Path | None:
    """Move a file **or directory** to the trash folder instead of deleting.

    Returns the new path in the trash, or ``None`` if the source didn't exist.
    """
    p = Path(path)
    if not p.exists():
        return None
    dest = _trash_dest(p)
    shutil.move(str(p), str(dest))
    return dest


def safe_remove_empty_dir(directory: Path | str) -> None:
    """Move empty directories to trash, climbing up but stopping at the first
    non-empty ancestor.  Non-empty directories are never touched.
    """
    d = Path(directory)
    while d.exists() and d.is_dir() and not any(d.iterdir()):
        safe_remove(d)
        d = d.parent
