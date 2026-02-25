"""SSE (Server-Sent Events) channel for real-time governance notifications.

Provides a ``/api/events`` SSE endpoint that streams:
  - ``policy_decision`` — when the Policy Engine blocks/confirms an action
  - ``audit_entry``     — new audit log entries
  - ``pending_action``  — actions waiting for user confirmation
  - ``cooldown_tick``   — countdown updates for cooldown actions
  - ``notification``    — general push notifications

The frontend connects to this endpoint and updates the UI in real-time
instead of polling ``/api/plan/pending`` etc.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Generator

from flask import Blueprint, Response

events_bp = Blueprint("events", __name__, url_prefix="/api")

# Thread-safe event bus — subscribers receive copies of events
_subscribers: list[queue.Queue] = []
_lock = threading.Lock()


@dataclass
class SSEEvent:
    event: str
    data: dict
    id: str = ""


def publish(event_type: str, data: dict) -> None:
    """Publish an event to all connected SSE subscribers."""
    msg = SSEEvent(event=event_type, data=data, id=str(time.time()))
    with _lock:
        dead: list[queue.Queue] = []
        for q in _subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def _event_stream(q: queue.Queue) -> Generator[str, None, None]:
    """Yield SSE-formatted strings from a subscriber queue."""
    yield "event: connected\ndata: {}\n\n"
    while True:
        try:
            msg: SSEEvent = q.get(timeout=30)
            payload = json.dumps(msg.data, ensure_ascii=False, default=str)
            yield f"event: {msg.event}\nid: {msg.id}\ndata: {payload}\n\n"
        except queue.Empty:
            yield ": heartbeat\n\n"


@events_bp.route("/events", methods=["GET"])
def sse_events():
    """SSE endpoint — long-lived connection for real-time events."""
    q: queue.Queue = queue.Queue(maxsize=200)
    with _lock:
        _subscribers.append(q)

    def on_close():
        with _lock:
            if q in _subscribers:
                _subscribers.remove(q)

    resp = Response(
        _event_stream(q),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
    resp.call_on_close(on_close)
    return resp


# ── Convenience publishers ────────────────────────────────────────

def publish_policy_decision(decision_dict: dict) -> None:
    publish("policy_decision", decision_dict)


def publish_audit_entry(entry: dict) -> None:
    publish("audit_entry", entry)


def publish_pending_action(action: dict) -> None:
    publish("pending_action", action)


def publish_notification(title: str, body: str = "",
                         level: str = "info") -> None:
    publish("notification", {"title": title, "body": body, "level": level})
