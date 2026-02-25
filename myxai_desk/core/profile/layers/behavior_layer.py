"""Behavior layer engine — model activity patterns from timestamps.

Builds a picture of when the user is active, their deep-work windows,
and which projects get the most attention.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from myxai_desk.core.profile.persona_model import BehaviorLayer


def _parse_hour(ts_str: str) -> int | None:
    """Extract the hour from an ISO timestamp or timestamp_bucket."""
    try:
        if "_" in ts_str and len(ts_str) <= 16:
            return int(ts_str.rsplit("_", 1)[1])
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.hour
    except Exception:
        return None


def _hour_range_label(hours: list[int]) -> str:
    if not hours:
        return ""
    start = min(hours)
    end = max(hours)
    return f"{start:02d}:00-{end + 1:02d}:00"


def update(
    events: list[dict],
    current: BehaviorLayer | None = None,
) -> BehaviorLayer:
    current = current or BehaviorLayer()

    hour_counter: Counter = Counter()
    project_counter: Counter = Counter()
    session_lengths: list[int] = []

    for e in events:
        et = e.get("event_type", "")
        ts = e.get("ts", "") or e.get("timestamp_bucket", "")
        hour = _parse_hour(ts)
        if hour is not None:
            hour_counter[hour] += 1

        if et == "file_touched":
            proj = e.get("project_prefix", "")
            if proj:
                project_counter[proj] += 1
        elif et == "browser_visited":
            bucket = e.get("timestamp_bucket", "")
            if bucket:
                hour_counter[_parse_hour(bucket) or 0] += 1

    top_hours = [h for h, _ in hour_counter.most_common(6)]
    top_hours.sort()
    active_hours = _hour_range_label(top_hours) if top_hours else current.active_hours

    consecutive = []
    if top_hours:
        run = [top_hours[0]]
        for h in top_hours[1:]:
            if h == run[-1] + 1:
                run.append(h)
            else:
                if len(run) >= 3:
                    consecutive.append(run[:])
                run = [h]
        if len(run) >= 3:
            consecutive.append(run[:])

    if consecutive:
        longest = max(consecutive, key=len)
        deep_work = f"连续{len(longest)}小时以上工作 ({_hour_range_label(longest)})"
    else:
        deep_work = current.deep_work_pattern

    total_proj = sum(project_counter.values()) or 1
    focus_map = {
        proj: round(cnt / total_proj, 2)
        for proj, cnt in project_counter.most_common(5)
    }
    if not focus_map:
        focus_map = current.project_focus_map

    unique_sessions = set()
    for e in events:
        if e.get("event_type") == "chat_message":
            s = e.get("session", "")
            if s:
                unique_sessions.add(s)
    switching = "低" if len(unique_sessions) <= 3 else ("中" if len(unique_sessions) <= 8 else "高")

    signal_count = sum(hour_counter.values())
    return BehaviorLayer(
        active_hours=active_hours,
        deep_work_pattern=deep_work,
        project_focus_map=focus_map,
        context_switching=switching,
        confidence=min(1.0, signal_count / 30),
        signal_count=signal_count,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
