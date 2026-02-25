"""Notification capability — push notifications to the frontend."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


class Notify:
    """Send notifications to the user via the frontend event stream."""

    def __init__(self, *, notification_sink: list | None = None):
        self._sink = notification_sink if notification_sink is not None else []

    def push(self, title: str, body: str = "", *, level: str = "info", app_id: str = "") -> str:
        nid = f"n_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": nid,
            "title": title,
            "body": body,
            "level": level,
            "app_id": app_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        self._sink.append(entry)
        return nid

    def get_unread(self) -> list[dict]:
        return [n for n in self._sink if not n.get("read")]

    def mark_read(self, nid: str) -> None:
        for n in self._sink:
            if n["id"] == nid:
                n["read"] = True
                break
