"""Profile event schema — structured behavioural events.

Events are the raw input to the profile system.  They are collected from
browsers, chat, app runs, etc. and fed into feature extraction to build
the user's interest graph, project context, and preferences.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from myxai_desk.core.storage.paths import PROFILE_EVENTS_FILE, ensure_dir

if TYPE_CHECKING:
    from pathlib import Path

# ── Privacy-first browser event ──────────────────────────────────


@dataclass
class BrowserVisited:
    domain: str
    title_keywords: list[str]
    timestamp_bucket: str
    dwell_time_bucket: str
    category_tag: str
    ts: str
    visit_count: int = 1
    title: str = ""
    url: str = ""
    event_type: str = "browser_visited"


# ── Chat event with structural signals ───────────────────────────


@dataclass
class ChatMessage:
    role: str
    text_digest: str
    ts: str
    session: str = ""
    output_preference: str = ""
    depth_preference: str = ""
    goal_keywords: list[str] | None = None
    event_type: str = "chat_message"


@dataclass
class AppRun:
    app_id: str
    ts: str
    inputs_digest: str = ""
    outputs_digest: str = ""
    event_type: str = "app_run"


@dataclass
class SearchPerformed:
    engine: str
    query: str
    ts: str
    event_type: str = "search_performed"


# ── Privacy-first file event ─────────────────────────────────────


@dataclass
class FileTouched:
    project_prefix: str
    file_extension: str
    operation_type: str
    diff_size_bucket: str
    ts: str
    event_type: str = "file_touched"


# ── Event store ────────────────────────────────────────────────────


class EventStore:
    """Append-only JSONL store for profile events."""

    def __init__(self, path: Path | None = None):
        self._path = path or PROFILE_EVENTS_FILE

    def record(self, event) -> None:
        """Append a single event."""
        ensure_dir(self._path.parent)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    append = record  # alias used by chat orchestrator

    def recent(self, n: int = 200, event_type: str | None = None) -> list[dict]:
        """Return the last *n* events, optionally filtered by type."""
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").strip().splitlines()
        events = []
        for line in reversed(lines):
            if len(events) >= n:
                break
            try:
                e = json.loads(line)
                if event_type and e.get("event_type") != event_type:
                    continue
                events.append(e)
            except json.JSONDecodeError:
                continue
        events.reverse()
        return events

    def all_events(self, event_type: str | None = None) -> list[dict]:
        """Return all events (expensive — prefer ``recent`` for UI)."""
        if not self._path.exists():
            return []
        events = []
        for line in self._path.read_text(encoding="utf-8").strip().splitlines():
            try:
                e = json.loads(line)
                if event_type and e.get("event_type") != event_type:
                    continue
                events.append(e)
            except json.JSONDecodeError:
                continue
        return events

    def count(self) -> int:
        if not self._path.exists():
            return 0
        return sum(1 for _ in open(self._path, encoding="utf-8"))

    def clear(self) -> None:
        """Clear all events (with backup)."""
        if self._path.exists():
            backup = self._path.with_suffix(".jsonl.bak")
            self._path.replace(backup)
