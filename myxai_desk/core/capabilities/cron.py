"""Cron / scheduler capability — trigger management for Prompt Apps."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from myxai_desk.core.storage.paths import NANOBOT_HOME, ensure_dir


_CRON_FILE = NANOBOT_HOME / "cron" / "app_triggers.json"


class CronCapability:
    """Manages scheduled triggers for Prompt Apps."""

    def __init__(self):
        self._triggers: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if _CRON_FILE.exists():
            try:
                self._triggers = json.loads(
                    _CRON_FILE.read_text(encoding="utf-8"),
                )
            except (json.JSONDecodeError, OSError):
                self._triggers = {}

    def _save(self) -> None:
        ensure_dir(_CRON_FILE.parent)
        _CRON_FILE.write_text(
            json.dumps(self._triggers, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def register(self, app_id: str, trigger_type: str, spec: dict) -> str:
        """Register a trigger and return its id."""
        tid = f"trg_{uuid.uuid4().hex[:8]}"
        self._triggers[tid] = {
            "app_id": app_id,
            "type": trigger_type,
            "spec": spec,
            "enabled": True,
            "created": datetime.now(timezone.utc).isoformat(),
            "last_fired": None,
        }
        self._save()
        return tid

    def unregister(self, trigger_id: str) -> bool:
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]
            self._save()
            return True
        return False

    def list_triggers(self, app_id: str | None = None) -> list[dict]:
        result = []
        for tid, t in self._triggers.items():
            if app_id and t["app_id"] != app_id:
                continue
            result.append({"id": tid, **t})
        return result

    def mark_fired(self, trigger_id: str) -> None:
        if trigger_id in self._triggers:
            self._triggers[trigger_id]["last_fired"] = (
                datetime.now(timezone.utc).isoformat()
            )
            self._save()
