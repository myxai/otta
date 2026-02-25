"""File scanner collector — metadata from newly created files only.

Collects:
- File name (not path, for privacy)
- File extension  
- Creation time

Filters out: temp files, build artifacts, dependencies, large binaries.
Never reads file content.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Directories to skip entirely
_SKIP_DIRS = {
    '.git', '.svn', '.hg',
    '__pycache__', '.pytest_cache', '.mypy_cache', '.tox',
    'node_modules', 'venv', '.venv', 'env', '.env',
    'dist', 'build', '.next', '.nuxt', 'target',
    '.idea', '.vscode', '.vs',
    'coverage', 'htmlcov',
}

# File extensions to skip (temp, cache, build artifacts)
_SKIP_EXTENSIONS = {
    # Temp files
    '.tmp', '.temp', '.swp', '.swo', '.bak', '.backup', '~',
    # Lock files
    '.lock', '.lck', '.pid',
    # Compiled/binary
    '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.exe', '.bin',
    '.o', '.obj', '.class', '.jar',
    # Logs
    '.log', '.logs',
    # Database files
    '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal',
    # Cache
    '.cache', '.caches',
    # Archives (usually large)
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
    # Large media
    '.mp4', '.avi', '.mkv', '.mov', '.wmv',
    '.mp3', '.wav', '.flac', '.ogg',
    '.psd', '.ai', '.sketch',
    # OS files
    '.DS_Store', 'Thumbs.db', 'desktop.ini',
}

# File name patterns to skip
_SKIP_NAME_PATTERNS = {
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'Cargo.lock',
    'Pipfile.lock',
    'poetry.lock',
    '.gitignore',
    '.gitkeep',
    '.env',
    '.env.local',
}

# Max file size to consider (10MB) — larger files are likely media/binaries
_MAX_FILE_SIZE = 10 * 1024 * 1024


def _should_skip_file(fname: str, fpath: str, fsize: int) -> bool:
    """Check if file should be filtered out."""
    # Skip hidden files
    if fname.startswith('.') or fname.startswith('~'):
        return True
    
    # Skip specific names
    if fname in _SKIP_NAME_PATTERNS:
        return True
    
    # Skip by extension
    ext = Path(fpath).suffix.lower()
    if ext in _SKIP_EXTENSIONS:
        return True
    
    # Skip large files
    if fsize > _MAX_FILE_SIZE:
        return True
    
    return False


def collect_file_events(
    watch_paths: list[str],
    days: int = 7,
) -> list[dict]:
    """Scan for newly created files in the last N days (no persistence).
    
    Returns list of file event dicts with: filename, extension, created_at.
    Only newly created files, not modified files.
    """
    if not watch_paths:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events: list[dict] = []

    for watch_path in watch_paths:
        if not os.path.isdir(watch_path):
            continue

        try:
            for root, dirs, files in os.walk(watch_path):
                # Skip unwanted directories
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]

                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        # Get file stats
                        stat = os.stat(fpath)
                        fsize = stat.st_size
                        ctime = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                        
                        # Only newly created files
                        if ctime < cutoff:
                            continue
                        
                        # Apply filters
                        if _should_skip_file(fname, fpath, fsize):
                            continue
                        
                        ext = Path(fpath).suffix.lower() or "none"
                        
                        events.append({
                            "event_type": "file_created",
                            "filename": fname,
                            "extension": ext,
                            "created_at": ctime.isoformat(),
                            "ts": ctime.isoformat(),
                        })
                    
                    except (OSError, PermissionError):
                        continue
        except Exception:
            continue

    return events


# Keep old function for backward compatibility (stub)
def scan_file_changes(
    watch_paths: list[str],
    days: int = 7,
    store = None,
) -> int:
    """Deprecated — kept for backward compatibility."""
    return 0
