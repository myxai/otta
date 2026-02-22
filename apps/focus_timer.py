"""Focus Timer App — Pomodoro sessions, tags, history and statistics.

Timer logic runs in the frontend (JS). This module handles persistence
and statistics queries.
"""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_APP_DIR = Path.home() / ".nanobot" / "apps" / "focus_timer"
_SESSIONS_FILE = _APP_DIR / "sessions.json"


# ── Persistence ─────────────────────────────────────────────────────

def _ensure_dirs():
    _APP_DIR.mkdir(parents=True, exist_ok=True)


def _load_sessions() -> list[dict]:
    if _SESSIONS_FILE.exists():
        try:
            return json.loads(_SESSIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_sessions(sessions: list[dict]):
    _ensure_dirs()
    _SESSIONS_FILE.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8",
    )


# ── CRUD ────────────────────────────────────────────────────────────

def save_session(data: dict) -> dict:
    """Save a completed focus session. Returns the saved entry."""
    sessions = _load_sessions()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "tag": data.get("tag", ""),
        "duration_minutes": data.get("duration_minutes", 25),
        "started_at": data.get("started_at", ""),
        "completed_at": data.get("completed_at", datetime.now(timezone.utc).isoformat()),
        "completed": True,
    }
    sessions.insert(0, entry)
    _save_sessions(sessions)
    return entry


def list_sessions(days: int = 7, tag: str = "") -> list[dict]:
    """List sessions within the given day range, optionally filtered by tag."""
    sessions = _load_sessions()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = []
    for s in sessions:
        if s.get("completed_at", "") < cutoff:
            continue
        if tag and s.get("tag", "") != tag:
            continue
        result.append(s)
    return result


def delete_session(session_id: str) -> bool:
    sessions = _load_sessions()
    before = len(sessions)
    sessions = [s for s in sessions if s["id"] != session_id]
    if len(sessions) == before:
        return False
    _save_sessions(sessions)
    return True


def get_tags() -> list[str]:
    """Return all unique tags that have been used."""
    sessions = _load_sessions()
    tags = set()
    for s in sessions:
        t = s.get("tag", "")
        if t:
            tags.add(t)
    return sorted(tags)


# ── Statistics ──────────────────────────────────────────────────────

def get_stats(days: int = 30) -> dict:
    """Compute focus statistics for the given day range."""
    sessions = list_sessions(days=days)

    total_minutes = sum(s.get("duration_minutes", 0) for s in sessions)
    count = len(sessions)

    # Per-tag breakdown
    by_tag: dict[str, int] = defaultdict(int)
    for s in sessions:
        by_tag[s.get("tag", "") or "未分类"] += s.get("duration_minutes", 0)

    # Daily trend (last N days)
    daily: dict[str, int] = defaultdict(int)
    daily_count: dict[str, int] = defaultdict(int)
    for s in sessions:
        ca = s.get("completed_at", "")
        if len(ca) >= 10:
            day = ca[:10]
            daily[day] += s.get("duration_minutes", 0)
            daily_count[day] += 1

    today = datetime.now().date()
    trend = []
    for i in range(min(days, 30)):
        d = (today - timedelta(days=i)).isoformat()
        trend.append({
            "date": d,
            "minutes": daily.get(d, 0),
            "count": daily_count.get(d, 0),
        })
    trend.reverse()

    # Today's stats
    today_str = today.isoformat()
    today_minutes = daily.get(today_str, 0)
    today_count = daily_count.get(today_str, 0)

    return {
        "days": days,
        "total_minutes": total_minutes,
        "total_sessions": count,
        "daily_average": round(total_minutes / max(days, 1), 1),
        "today_minutes": today_minutes,
        "today_sessions": today_count,
        "by_tag": dict(by_tag),
        "trend": trend,
    }
