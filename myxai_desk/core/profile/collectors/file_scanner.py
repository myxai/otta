"""File scanner collector — privacy-first metadata from file changes.

Records project_prefix (sanitised), file_extension, operation_type, and
diff_size_bucket.  Never reads file content.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from myxai_desk.core.profile.events import EventStore, FileTouched

_SKIP_PREFIXES = ('.', '~', '__pycache__', 'node_modules', '.git', '.venv', 'venv')
_SKIP_EXTENSIONS = {'.tmp', '.swp', '.lock', '.bak', '.pyc', '.pyo', '.log'}


def _sanitise_project_prefix(path: str, watch_root: str) -> str:
    """Reduce the full path to a project-level prefix for privacy."""
    try:
        rel = os.path.relpath(path, watch_root)
        parts = Path(rel).parts
        return parts[0] if parts else "root"
    except (ValueError, TypeError):
        return "unknown"


def _diff_size_bucket(file_size: int) -> str:
    if file_size < 1024:
        return "tiny"
    if file_size < 10240:
        return "small"
    if file_size < 102400:
        return "medium"
    return "large"


def scan_file_changes(
    watch_paths: list[str],
    days: int = 7,
    store: EventStore | None = None,
) -> int:
    """Scan specified folders for files created/modified in the last *days* days.

    Returns the number of file events recorded.
    """
    if not watch_paths:
        return 0

    store = store or EventStore()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = 0

    for watch_path in watch_paths:
        if not os.path.isdir(watch_path):
            continue

        try:
            for root, dirs, files in os.walk(watch_path):
                dirs[:] = [d for d in dirs if not any(
                    d.startswith(p) for p in _SKIP_PREFIXES
                )]

                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        if any(fname.startswith(p) for p in ('.', '~')):
                            continue

                        ext = Path(fpath).suffix.lower()
                        if ext in _SKIP_EXTENSIONS:
                            continue

                        mtime = datetime.fromtimestamp(
                            os.path.getmtime(fpath), tz=timezone.utc
                        )
                        if mtime < cutoff:
                            continue

                        ctime = datetime.fromtimestamp(
                            os.path.getctime(fpath), tz=timezone.utc
                        )
                        op = "create" if ctime >= cutoff else "modify"

                        try:
                            fsize = os.path.getsize(fpath)
                        except OSError:
                            fsize = 0

                        event = FileTouched(
                            project_prefix=_sanitise_project_prefix(fpath, watch_path),
                            file_extension=ext or "none",
                            operation_type=op,
                            diff_size_bucket=_diff_size_bucket(fsize),
                            ts=mtime.isoformat(),
                        )
                        store.record(event)
                        count += 1

                    except (OSError, PermissionError):
                        continue
        except Exception:
            continue

    return count
