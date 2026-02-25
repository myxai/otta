"""Versioned persistence for the PersonaProfile.

The current profile lives at ``~/.nanobot/profile/persona_profile.json``.
Every save creates a numbered snapshot under ``versions/`` so the user can
inspect history or roll back.  Only the most recent *MAX_VERSIONS* snapshots
are kept on disk.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from myxai_desk.core.storage.paths import (
    PERSONA_PROFILE_FILE,
    PERSONA_VERSIONS_DIR,
    ensure_dir,
)
from myxai_desk.core.profile.persona_model import PersonaProfile

MAX_VERSIONS = 30


def _next_version_number() -> int:
    ensure_dir(PERSONA_VERSIONS_DIR)
    existing = sorted(PERSONA_VERSIONS_DIR.glob("persona_v*.json"))
    if not existing:
        return 1
    last = existing[-1].stem  # persona_v12
    try:
        return int(last.split("_v")[1]) + 1
    except (IndexError, ValueError):
        return 1


def _prune_old_versions() -> None:
    versions = sorted(PERSONA_VERSIONS_DIR.glob("persona_v*.json"))
    while len(versions) > MAX_VERSIONS:
        versions.pop(0).unlink(missing_ok=True)


# ── Public API ────────────────────────────────────────────────────

def load() -> PersonaProfile:
    """Load the current persona profile from disk (or return a blank one)."""
    if not PERSONA_PROFILE_FILE.exists():
        return PersonaProfile()
    try:
        data = json.loads(PERSONA_PROFILE_FILE.read_text(encoding="utf-8"))
        return PersonaProfile.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return PersonaProfile()


def save(profile: PersonaProfile, *, reason: str = "") -> int:
    """Persist *profile* and create a version snapshot.  Returns the version number."""
    ensure_dir(PERSONA_PROFILE_FILE.parent)

    profile.update_meta.last_updated = datetime.now(timezone.utc).isoformat()
    profile.update_meta.update_count += 1
    profile.confidence_score = profile.overall_confidence()

    payload = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)
    PERSONA_PROFILE_FILE.write_text(payload, encoding="utf-8")

    ensure_dir(PERSONA_VERSIONS_DIR)
    ver = _next_version_number()
    ver_file = PERSONA_VERSIONS_DIR / f"persona_v{ver}.json"
    ver_file.write_text(payload, encoding="utf-8")
    _prune_old_versions()
    return ver


def rollback(version: int) -> PersonaProfile:
    """Restore a previous version and make it the current profile.

    Raises ``FileNotFoundError`` if the version does not exist.
    """
    ver_file = PERSONA_VERSIONS_DIR / f"persona_v{version}.json"
    if not ver_file.exists():
        raise FileNotFoundError(f"Version {version} not found")
    data = json.loads(ver_file.read_text(encoding="utf-8"))
    profile = PersonaProfile.from_dict(data)
    save(profile, reason=f"rollback to v{version}")
    return profile


def list_versions() -> list[dict]:
    """Return metadata for each stored version (newest first)."""
    ensure_dir(PERSONA_VERSIONS_DIR)
    result = []
    for f in sorted(PERSONA_VERSIONS_DIR.glob("persona_v*.json"), reverse=True):
        try:
            ver_num = int(f.stem.split("_v")[1])
        except (IndexError, ValueError):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            meta = data.get("update_meta", {})
            result.append({
                "version": ver_num,
                "file": f.name,
                "last_updated": meta.get("last_updated", ""),
                "confidence_score": data.get("confidence_score", 0),
                "size_bytes": f.stat().st_size,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return result


def delete_all() -> None:
    """Remove the current profile and all versions (with backup)."""
    if PERSONA_PROFILE_FILE.exists():
        backup = PERSONA_PROFILE_FILE.with_suffix(".json.bak")
        shutil.copy2(PERSONA_PROFILE_FILE, backup)
        PERSONA_PROFILE_FILE.unlink()
    if PERSONA_VERSIONS_DIR.exists():
        shutil.rmtree(PERSONA_VERSIONS_DIR, ignore_errors=True)
