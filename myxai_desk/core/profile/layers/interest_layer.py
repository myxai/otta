"""Interest layer engine — topic weights with exponential decay.

Core formula:  weight_new = weight_old * decay_factor + signal_strength

The decay factor (default 0.85) is applied per 7-day window, so topics
the user stops visiting naturally fade.  ``trend_shift`` captures the
delta between the current and previous window to surface emerging or
fading interests.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from myxai_desk.core.profile.persona_model import InterestLayer

DECAY_FACTOR = 0.85
SIGNAL_NORM = 10.0
MAX_TOPICS = 30


def update(
    events: list[dict],
    current: InterestLayer | None = None,
) -> InterestLayer:
    """Recompute interest weights from browser + search + chat events."""
    current = current or InterestLayer()
    old_weights: dict[str, float] = dict(current.topic_weight)

    signal_counter: Counter = Counter()

    for e in events:
        et = e.get("event_type", "")
        if et == "browser_visited":
            tag = e.get("category_tag", "")
            if tag:
                signal_counter[tag] += 1
            for kw in (e.get("title_keywords") or []):
                signal_counter[kw] += 1
        elif et == "search_performed":
            query = e.get("query", "")
            for word in query.split():
                if len(word) >= 2:
                    signal_counter[word.lower()] += 1
        elif et == "chat_message":
            for kw in (e.get("goal_keywords") or []):
                signal_counter[kw] += 0.5

    new_weights: dict[str, float] = {}
    all_topics = set(old_weights.keys()) | set(signal_counter.keys())

    for topic in all_topics:
        old_w = old_weights.get(topic, 0.0)
        signal = signal_counter.get(topic, 0) / SIGNAL_NORM
        new_w = old_w * DECAY_FACTOR + signal
        if new_w >= 0.01:
            new_weights[topic] = round(new_w, 4)

    sorted_topics = sorted(new_weights.items(), key=lambda x: x[1], reverse=True)
    new_weights = dict(sorted_topics[:MAX_TOPICS])

    total = sum(new_weights.values()) or 1.0
    new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

    trend: dict[str, float] = {}
    for topic in new_weights:
        old_val = old_weights.get(topic, 0.0)
        delta = new_weights[topic] - old_val
        if abs(delta) >= 0.01:
            trend[topic] = round(delta, 4)

    signal_count = sum(signal_counter.values())
    return InterestLayer(
        topic_weight=new_weights,
        trend_shift=trend,
        window="7_day",
        confidence=min(1.0, signal_count / 20),
        signal_count=int(signal_count),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
