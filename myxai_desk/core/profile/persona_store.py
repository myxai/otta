"""Simplified persona storage — two JSON files, no versioning overhead.

~/.nanobot/profile/persona_stable.json
~/.nanobot/profile/persona_recent.json
"""

from __future__ import annotations

import json
import shutil

from myxai_desk.core.profile.persona_model import RecentSnapshot, StablePersona
from myxai_desk.core.storage.paths import (
    PERSONA_RECENT_FILE,
    PERSONA_STABLE_FILE,
    ensure_dir,
)


def load_stable() -> StablePersona:
    if not PERSONA_STABLE_FILE.exists():
        return StablePersona()
    try:
        data = json.loads(PERSONA_STABLE_FILE.read_text(encoding="utf-8"))
        return StablePersona.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return StablePersona()


def load_recent() -> RecentSnapshot:
    if not PERSONA_RECENT_FILE.exists():
        return RecentSnapshot()
    try:
        data = json.loads(PERSONA_RECENT_FILE.read_text(encoding="utf-8"))
        return RecentSnapshot.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return RecentSnapshot()


def save_stable(persona: StablePersona) -> None:
    ensure_dir(PERSONA_STABLE_FILE.parent)
    payload = json.dumps(persona.to_dict(), ensure_ascii=False, indent=2)
    PERSONA_STABLE_FILE.write_text(payload, encoding="utf-8")


def save_recent(snapshot: RecentSnapshot) -> None:
    ensure_dir(PERSONA_RECENT_FILE.parent)
    payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2)
    PERSONA_RECENT_FILE.write_text(payload, encoding="utf-8")


def delete_all() -> None:
    for f in (PERSONA_STABLE_FILE, PERSONA_RECENT_FILE):
        if f.exists():
            backup = f.with_suffix(".json.bak")
            shutil.copy2(f, backup)
            f.unlink()
