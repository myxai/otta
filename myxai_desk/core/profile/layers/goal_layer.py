"""Goal layer engine — extract user goals from conversations and searches.

Identifies long-term goals, mid-term goals, and current focus areas by
analysing recurring themes in chat goal_keywords and search queries.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from myxai_desk.core.profile.persona_model import GoalLayer


def update(
    events: list[dict],
    current: GoalLayer | None = None,
) -> GoalLayer:
    current = current or GoalLayer()

    goal_counter: Counter = Counter()
    focus_counter: Counter = Counter()
    search_counter: Counter = Counter()

    for e in events:
        et = e.get("event_type", "")
        if et == "chat_message" and e.get("role") == "user":
            for kw in (e.get("goal_keywords") or []):
                goal_counter[kw] += 1
            session = e.get("session", "")
            if session:
                focus_counter[session] += 1
        elif et == "search_performed":
            query = e.get("query", "")
            if len(query) > 3:
                search_counter[query] += 1

    top_goals = [kw for kw, cnt in goal_counter.most_common(5) if cnt >= 2]
    top_focus = [kw for kw, cnt in focus_counter.most_common(5)][:3]

    long_term = current.long_term_goal
    mid_term = current.mid_term_goal

    if top_goals:
        if not long_term:
            long_term = top_goals[0]
        if len(top_goals) > 1 and not mid_term:
            mid_term = top_goals[1]

    current_focus = top_focus or current.current_focus

    signal_count = sum(goal_counter.values()) + sum(search_counter.values())
    return GoalLayer(
        long_term_goal=long_term,
        mid_term_goal=mid_term,
        current_focus=current_focus,
        confidence=min(1.0, signal_count / 15),
        signal_count=signal_count,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
