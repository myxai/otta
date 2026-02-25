"""Chat history collector — extracts structural signals from conversations.

Beyond recording raw chat events, this collector analyses message patterns
to extract persona-relevant signals:
  - output preference (structured / concise / code-first)
  - depth preference
  - recurring goal keywords
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from myxai_desk.core.storage.paths import SESSIONS_FILE
from myxai_desk.core.profile.events import ChatMessage, EventStore

# ── Signal detection helpers ─────────────────────────────────────

_STRUCTURE_MARKERS = re.compile(
    r"(表格|列表|分点|分步|步骤|结构化|markdown|json|yaml"
    r"|table|list|step.by.step|structured|bullet)",
    re.I,
)
_CODE_MARKERS = re.compile(
    r"(代码|示例代码|code|snippet|实现|function|class\s|def\s|import\s)",
    re.I,
)
_CONCISE_MARKERS = re.compile(
    r"(简洁|简短|一句话|直接|brief|concise|short|tl;?dr|直接说)",
    re.I,
)
_DEPTH_MARKERS = re.compile(
    r"(详细|深入|原理|底层|完整|展开|elaborate|detail|in.depth|explain)",
    re.I,
)
_GOAL_PATTERNS = re.compile(
    r"(目标|计划|打算|想要|需要|希望|goal|plan|want|need|aim|build|构建|实现|完成)",
    re.I,
)


def _detect_output_preference(text: str) -> str:
    if _CODE_MARKERS.search(text):
        return "code_first"
    if _STRUCTURE_MARKERS.search(text):
        return "structured"
    if _CONCISE_MARKERS.search(text):
        return "concise"
    return ""


def _detect_depth_preference(text: str) -> str:
    if _DEPTH_MARKERS.search(text):
        return "deep"
    if _CONCISE_MARKERS.search(text):
        return "shallow"
    return ""


def _extract_goal_keywords(text: str) -> list[str]:
    if not _GOAL_PATTERNS.search(text):
        return []
    words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text)
    stop = {"目标", "计划", "打算", "想要", "需要", "希望", "一个", "这个",
            "goal", "plan", "want", "need", "the", "and", "for"}
    return [w for w in words if w.lower() not in stop][:6]


# ── Public API ────────────────────────────────────────────────────

def read_chat_history(hours: int = 72) -> list[dict]:
    """Read recent nanobot chat conversations."""
    if not SESSIONS_FILE.exists():
        return []
    try:
        data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    sessions = []
    for sid, sess in data.items():
        updated = sess.get("updated_at", "")
        if not updated:
            continue
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except Exception:
            continue
        if ts < cutoff:
            continue
        msgs = sess.get("messages", [])
        if not msgs:
            continue
        sessions.append({
            "session_title": sess.get("title", sid),
            "updated_at": updated,
            "messages": msgs,
        })
    return sessions


def collect_chat_events(hours: int = 72) -> list[dict]:
    """Read chat history and return as event dicts (no persistence).
    
    Returns list of chat_message event dicts for in-memory analysis only.
    """
    sessions = read_chat_history(hours=hours)
    events: list[dict] = []
    for sess in sessions:
        for msg in sess["messages"]:
            content = msg.get("content", "")
            role = msg.get("role", "")
            if not content or role == "system":
                continue
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            ts = msg.get("ts", sess.get("updated_at", ""))

            out_pref = ""
            depth_pref = ""
            goal_kws: list[str] = []
            if role == "user":
                out_pref = _detect_output_preference(content)
                depth_pref = _detect_depth_preference(content)
                goal_kws = _extract_goal_keywords(content)

            events.append({
                "event_type": "chat_message",
                "role": role,
                "text_digest": digest,
                "ts": ts,
                "session": sess["session_title"],
                "output_preference": out_pref,
                "depth_preference": depth_pref,
                "goal_keywords": goal_kws or None,
            })
    return events


def collect_to_events(hours: int = 72,
                      store: EventStore | None = None) -> int:
    """Read chat history and record as profile events with structural signals."""
    store = store or EventStore()
    sessions = read_chat_history(hours=hours)
    count = 0
    for sess in sessions:
        for msg in sess["messages"]:
            content = msg.get("content", "")
            role = msg.get("role", "")
            if not content or role == "system":
                continue
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            ts = msg.get("ts", sess.get("updated_at", ""))

            out_pref = ""
            depth_pref = ""
            goal_kws: list[str] = []
            if role == "user":
                out_pref = _detect_output_preference(content)
                depth_pref = _detect_depth_preference(content)
                goal_kws = _extract_goal_keywords(content)

            event = ChatMessage(
                role=role,
                text_digest=digest,
                ts=ts,
                session=sess["session_title"],
                output_preference=out_pref,
                depth_preference=depth_pref,
                goal_keywords=goal_kws or None,
            )
            store.record(event)
            count += 1
    return count


def aggregate_chat_signals(store: EventStore, n: int = 300) -> dict:
    """Aggregate structural signals from recent chat events.

    Returns a dict summarising dominant preferences and recurring goals.
    """
    events = store.recent(n=n, event_type="chat_message")
    user_events = [e for e in events if e.get("role") == "user"]

    out_counter: Counter = Counter()
    depth_counter: Counter = Counter()
    goal_counter: Counter = Counter()

    for e in user_events:
        op = e.get("output_preference", "")
        if op:
            out_counter[op] += 1
        dp = e.get("depth_preference", "")
        if dp:
            depth_counter[dp] += 1
        for kw in (e.get("goal_keywords") or []):
            goal_counter[kw] += 1

    return {
        "output_preference": out_counter.most_common(1)[0][0] if out_counter else "structured",
        "depth_preference": depth_counter.most_common(1)[0][0] if depth_counter else "",
        "recurring_goals": [kw for kw, _ in goal_counter.most_common(10) if _ >= 2],
        "total_user_messages": len(user_events),
    }
